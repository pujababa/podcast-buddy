import os
import re
import json
import time
import uuid
import shutil
import logging
import tempfile
import asyncio
import base64
import concurrent.futures
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import requests
import edge_tts
from gtts import gTTS

from backend.config import AUDIO_OUTPUT_DIR, SARVAM_API_KEY, SARVAM_TTS_URL, SARVAM_MODEL
from backend.services.audio_processor import AudioProcessor, audio_processor, AudioProcessingError

logger = logging.getLogger("podcast_buddy.tts_service")
if not logger.handlers:
    _log_handler = logging.StreamHandler()
    _log_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [TTSService] %(message)s"))
    logger.addHandler(_log_handler)
    logger.setLevel(logging.INFO)


# =============================================================================
# Exceptions
# =============================================================================
class TTSError(Exception):
    """Base exception for TTS and audio generation failures."""
    pass


class TTSLanguageError(TTSError):
    """Raised when an invalid or unsupported language is requested."""
    pass


class TTSScriptEmptyError(TTSError):
    """Raised when the podcast script has no dialogue lines to synthesize."""
    pass


class TTSSynthesisError(TTSError):
    """Raised when speech synthesis fails for one or more dialogue lines."""
    pass


def _redact_key(text: Any, key: Optional[str] = None) -> str:
    """Safely redact API keys and sensitive tokens from error messages and logs."""
    msg = str(text) if text is not None else ""
    if key and len(key.strip()) >= 4:
        msg = msg.replace(key.strip(), "[REDACTED_API_KEY]")
    for env_var in ("SARVAM_API_KEY", "TTS_API_KEY", "GEMINI_API_KEY", "SERPAPI_API_KEY"):
        val = os.getenv(env_var, "").strip()
        if val and len(val) >= 4 and val in msg:
            msg = msg.replace(val, f"[REDACTED_{env_var}]")
    return msg


# Supported Languages Definition
SUPPORTED_LANGUAGES = {
    "english": "English",
    "hindi": "Hindi",
    "odia": "Odia",
    "hinglish": "Hinglish"
}

LANGUAGE_ALIASES = {
    "en": "english",
    "eng": "english",
    "english": "english",
    "hi": "hindi",
    "hin": "hindi",
    "hindi": "hindi",
    "or": "odia",
    "ori": "odia",
    "odia": "odia",
    "oriya": "odia",
    "hinglish": "hinglish"
}


def normalize_language(language_input: Any) -> str:
    """
    Validate and normalize language string to one of: english, hindi, odia, hinglish.
    Raises TTSLanguageError on invalid or missing language.
    """
    if not language_input or not isinstance(language_input, str):
        raise TTSLanguageError(
            f"Language must be a non-empty string. Supported languages: {', '.join(SUPPORTED_LANGUAGES.values())}."
        )

    clean = language_input.strip().lower()
    if clean not in LANGUAGE_ALIASES:
        valid_options = ", ".join(SUPPORTED_LANGUAGES.values())
        raise TTSLanguageError(
            f"Unsupported language '{language_input}'. Supported languages are: {valid_options}."
        )
    return LANGUAGE_ALIASES[clean]


def transliterate_odia_to_devanagari(odia_text: str) -> str:
    """
    Phonetically map Odia Unicode codepoints (U+0B00 to U+0B7F) to Devanagari (U+0900 to U+097F).
    """
    chars = []
    for c in odia_text:
        cp = ord(c)
        if 0x0B00 <= cp <= 0x0B7F:
            chars.append(chr(cp - 0x0200))
        else:
            chars.append(c)
    return "".join(chars)


def _run_async_safely(coro):
    """
    Safely execute an asynchronous coroutine synchronously in any environment
    (active event loop or worker thread).
    """
    try:
        return asyncio.run(coro)
    except RuntimeError:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()


# Voice configurations for Host vs CoHost per language
# Hindi: Verified Microsoft Edge Neural TTS voices (hi-IN-MadhurNeural, hi-IN-SwaraNeural)
# Odia: Sarvam AI Indic Neural TTS provider (model: bulbul:v3 / target_language_code: od-IN)
VOICE_CONFIGS = {
    "english": {
        "host": {"voice": "en-GB-RyanNeural", "lang": "en", "tld": "co.uk", "provider": "gtts"},
        "cohost": {"voice": "en-IN-NeerjaNeural", "lang": "en", "tld": "co.in", "provider": "gtts"}
    },
    "hindi": {
        "host": {
            "voice": "hi-IN-MadhurNeural",
            "gender": "male",
            "lang": "hi",
            "tld": "co.in",
            "provider": "edge-tts"
        },
        "cohost": {
            "voice": "hi-IN-SwaraNeural",
            "gender": "female",
            "lang": "hi",
            "tld": "com",
            "provider": "edge-tts"
        }
    },
    "hinglish": {
        "host": {"voice": "hi-IN-MadhurNeural", "lang": "hi", "tld": "co.in", "provider": "gtts"},
        "cohost": {"voice": "en-IN-NeerjaNeural", "lang": "en", "tld": "co.in", "provider": "gtts"}
    },
    "odia": {
        "host": {
            "voice": "od-IN-Host",
            "speaker": "shubh",
            "lang": "or",
            "tld": "co.in",
            "provider": "sarvam",
            "target_language_code": "od-IN"
        },
        "cohost": {
            "voice": "od-IN-CoHost",
            "speaker": "kavya",
            "lang": "or",
            "tld": "com",
            "provider": "sarvam",
            "target_language_code": "od-IN"
        }
    }
}


class TTSService:
    """
    Service responsible for converting podcast scripts into multi-speaker audio.
    Supports English, Hindi, Odia, and Hinglish with distinct voice configs for Host and CoHost.
    Uses Microsoft Edge Neural TTS for Hindi, Sarvam AI for Odia, and gTTS for English/Hinglish.
    """

    def __init__(
        self,
        processor: Optional[AudioProcessor] = None,
        output_dir: Optional[str] = None
    ):
        self.processor = processor or audio_processor
        self.output_dir = os.path.abspath(output_dir or AUDIO_OUTPUT_DIR)
        os.makedirs(self.output_dir, exist_ok=True)

    def extract_dialogue_lines(self, script: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract ordered list of dialogue turns from validated Phase 6 script.
        Includes intro, segments, key_takeaways, and outro.
        """
        lines = []

        # 1. Intro
        intro = script.get("intro")
        if isinstance(intro, dict):
            for l in intro.get("lines") or []:
                if isinstance(l, dict) and l.get("text"):
                    lines.append({
                        "speaker": str(l.get("speaker") or "host").strip().lower(),
                        "text": str(l.get("text") or "").strip(),
                        "section": "intro"
                    })

        # 2. Segments
        segments = script.get("segments") or []
        for s_idx, seg in enumerate(segments):
            if isinstance(seg, dict):
                for l in seg.get("lines") or []:
                    if isinstance(l, dict) and l.get("text"):
                        lines.append({
                            "speaker": str(l.get("speaker") or "host").strip().lower(),
                            "text": str(l.get("text") or "").strip(),
                            "section": f"segment_{s_idx}"
                        })

        # 3. Key Takeaways
        key_takeaways = script.get("key_takeaways") or []
        for l in key_takeaways:
            if isinstance(l, dict) and l.get("text"):
                lines.append({
                    "speaker": str(l.get("speaker") or "host").strip().lower(),
                    "text": str(l.get("text") or "").strip(),
                    "section": "takeaways"
                })

        # 4. Outro
        outro = script.get("outro")
        if isinstance(outro, dict):
            for l in outro.get("lines") or []:
                if isinstance(l, dict) and l.get("text"):
                    lines.append({
                        "speaker": str(l.get("speaker") or "host").strip().lower(),
                        "text": str(l.get("text") or "").strip(),
                        "section": "outro"
                    })

        if not lines:
            raise TTSScriptEmptyError("The provided podcast script contains no dialogue lines.")

        return lines

    def _synthesize_edge_tts(self, text: str, voice: str, output_path: str) -> str:
        """
        Synthesize speech using Microsoft Edge Neural TTS with high audio fidelity.
        """
        async def _edge_generate():
            communicate = edge_tts.Communicate(text=text, voice=voice)
            await communicate.save(output_path)

        _run_async_safely(_edge_generate())

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise TTSSynthesisError(f"Edge TTS generated empty audio file for voice '{voice}'.")
        return output_path

    def _synthesize_sarvam_tts(
        self,
        text: str,
        speaker: str,
        output_path: str,
        api_key: Optional[str] = None
    ) -> str:
        """
        Synthesize genuine Odia speech using Sarvam AI Bulbul neural TTS.
        Requires SARVAM_API_KEY in server environment or .env file.
        Supports Bulbul v3 / v4-flash with od-IN language code.
        """
        # Dynamic key resolution: explicit -> os.environ -> module config -> re-read .env on disk
        key = (api_key or os.getenv("SARVAM_API_KEY") or os.getenv("TTS_API_KEY") or SARVAM_API_KEY or "").strip()
        if not key and "SARVAM_API_KEY" not in os.environ and "TTS_API_KEY" not in os.environ:
            try:
                from dotenv import dotenv_values
                vals = dotenv_values(".env")
                disk_key = (vals.get("SARVAM_API_KEY") or vals.get("TTS_API_KEY") or "").strip()
                if disk_key:
                    os.environ["SARVAM_API_KEY"] = disk_key
                    key = disk_key
            except Exception:
                pass

        if not key:
            raise TTSSynthesisError(
                "Odia ('or') speech synthesis is not supported by Google Translate TTS (gTTS) or Microsoft Edge TTS. "
                "Provider limitation: Google Translate TTS lacks an Odia voice model. "
                "Genuine Odia synthesis is integrated via Sarvam AI ('od-IN'), which requires a SARVAM_API_KEY in your .env file. "
                "Please configure SARVAM_API_KEY in .env (sign up at https://dashboard.sarvam.ai)."
            )

        model = os.getenv("SARVAM_MODEL", SARVAM_MODEL or "bulbul:v3").strip() or "bulbul:v3"
        valid_speakers = ("shubh", "kavya", "ritu", "priya", "neha", "pooja", "simran", "aditya", "rahul", "rohan", "amit", "dev", "ashutosh")
        chosen_speaker = speaker if speaker in valid_speakers else ("shubh" if speaker == "host" else "kavya")

        headers = {
            "api-subscription-key": key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "target_language_code": "od-IN",
            "model": model,
            "speaker": chosen_speaker,
            "pace": 1.0,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
            "output_audio_codec": "mp3",
            "audio_codec": "mp3"
        }

        try:
            resp = requests.post(SARVAM_TTS_URL, headers=headers, json=payload, timeout=25.0)
            if resp.status_code in (401, 403):
                raise TTSSynthesisError(
                    "Sarvam AI authentication failed. Please verify that your SARVAM_API_KEY is valid and active at https://dashboard.sarvam.ai."
                )
            if resp.status_code == 429:
                raise TTSSynthesisError(
                    "Sarvam AI rate limit or quota exceeded. Please check your credit balance at https://dashboard.sarvam.ai."
                )
            if resp.status_code != 200:
                clean_msg = _redact_key(resp.text[:200], key)
                raise TTSSynthesisError(f"Sarvam AI TTS API error (HTTP {resp.status_code}): {clean_msg}")

            data = resp.json()
            audios = data.get("audios") or []
            if not audios:
                raise TTSSynthesisError("Sarvam AI returned an empty audio list.")

            audio_bytes = base64.b64decode(audios[0])
            with open(output_path, "wb") as f:
                f.write(audio_bytes)

            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise TTSSynthesisError("Sarvam AI generated empty audio output.")
            return output_path

        except requests.RequestException as e:
            clean_err = _redact_key(str(e), key)
            raise TTSSynthesisError(f"Failed to communicate with Sarvam AI TTS endpoint: {clean_err}") from e

    def _synthesize_gtts(
        self,
        text: str,
        lang: str,
        tld: str,
        output_path: str
    ) -> str:
        """
        Synthesize speech using Google Translate TTS (gTTS) with automatic TLD retries.
        """
        candidate_tlds = [tld]
        if "co.in" not in candidate_tlds:
            candidate_tlds.append("co.in")
        if "com" not in candidate_tlds:
            candidate_tlds.append("com")

        last_err = None
        for current_tld in candidate_tlds:
            for attempt in range(2):
                try:
                    tts = gTTS(text=text, lang=lang, tld=current_tld, slow=False)
                    tts.save(output_path)
                    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                        raise TTSSynthesisError(f"TTS generated empty audio file for text: '{text[:30]}...'")
                    return output_path
                except Exception as e:
                    last_err = e
                    time.sleep(1.0)

        raise TTSSynthesisError(f"gTTS speech synthesis failed: {last_err}") from last_err

    def synthesize_line(
        self,
        text: str,
        speaker: str,
        language: str,
        output_path: str
    ) -> str:
        """
        Synthesize a single dialogue line for a given speaker and language.
        Configures voices differently for Host and CoHost.
        - Hindi: Uses verified Microsoft Edge Neural TTS voices:
          * Host: hi-IN-MadhurNeural
          * CoHost: hi-IN-SwaraNeural
        - Odia: Uses genuine Sarvam AI Indic TTS ('od-IN') via SARVAM_API_KEY
        - English & Hinglish: Uses multi-accent gTTS
        """
        clean_text = text.strip()
        if not clean_text:
            raise TTSSynthesisError("Cannot synthesize empty dialogue text.")

        normalized_lang = normalize_language(language)
        spk = "cohost" if speaker.strip().lower() == "cohost" else "host"
        config = VOICE_CONFIGS.get(normalized_lang, VOICE_CONFIGS["english"]).get(spk)

        # 1. Hindi Synthesis via Microsoft Edge Neural TTS
        if normalized_lang == "hindi":
            voice = config.get("voice", "hi-IN-MadhurNeural" if spk == "host" else "hi-IN-SwaraNeural")
            try:
                self._synthesize_edge_tts(clean_text, voice=voice, output_path=output_path)
                return output_path
            except Exception as e:
                logger.warning("Edge TTS Hindi synthesis failed for voice=%s, falling back to gTTS: %s", voice, e)
                try:
                    return self._synthesize_gtts(clean_text, lang="hi", tld=config.get("tld", "co.in"), output_path=output_path)
                except Exception as gtts_err:
                    raise TTSSynthesisError(f"Failed to synthesize Hindi audio for speaker '{spk}': {e} | Fallback error: {gtts_err}") from e

        # 2. Odia Synthesis via Sarvam AI
        elif normalized_lang == "odia":
            sarvam_speaker = config.get("speaker", "shubh" if spk == "host" else "kavya")
            return self._synthesize_sarvam_tts(clean_text, speaker=sarvam_speaker, output_path=output_path)

        # 3. English and Hinglish Synthesis via gTTS
        else:
            tts_lang = config.get("lang", "en")
            tts_tld = config.get("tld", "com")
            return self._synthesize_gtts(clean_text, lang=tts_lang, tld=tts_tld, output_path=output_path)

    def generate_podcast_audio(
        self,
        episode_id: int,
        script: Dict[str, Any],
        language: str = "english",
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Converts the entire podcast script into multi-speaker merged audio.
        Supports repeated audio generation safely.
        
        Args:
            episode_id: Database episode ID.
            script: Phase 6 podcast script dictionary.
            language: Target language (english, hindi, odia, hinglish).
            output_dir: Optional override directory.
            
        Returns:
            Dict with metadata: audio_path, filename, language, duration_ms, file_size.
        """
        target_dir = os.path.abspath(output_dir or self.output_dir)
        os.makedirs(target_dir, exist_ok=True)

        norm_lang = normalize_language(language)
        lines = self.extract_dialogue_lines(script)

        logger.info(
            "Generating audio for episode %d in '%s' (%d dialogue lines)",
            episode_id, norm_lang, len(lines)
        )

        # Temporary workspace for individual dialogue lines
        temp_dir = tempfile.mkdtemp(prefix=f"podcast_buddy_ep{episode_id}_")
        clip_paths = []

        try:
            for idx, line in enumerate(lines):
                clip_filename = f"line_{idx:03d}_{line['speaker']}.mp3"
                clip_path = os.path.join(temp_dir, clip_filename)

                self.synthesize_line(
                    text=line["text"],
                    speaker=line["speaker"],
                    language=norm_lang,
                    output_path=clip_path
                )
                clip_paths.append(clip_path)

            # Generate distinct timestamped final filename for safety and repeat generation
            now_iso = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            final_filename = f"episode_{episode_id}_{norm_lang}_{now_iso}.mp3"
            final_path = os.path.join(target_dir, final_filename)

            # Merge audio using AudioProcessor scoped to target_dir
            processor = self.processor if self.processor.output_dir == target_dir else AudioProcessor(output_dir=target_dir)
            merge_result = processor.merge_audio_segments(
                audio_files=clip_paths,
                output_filename_or_path=final_path,
                pause_ms=300
            )

            relative_path = os.path.relpath(merge_result["output_path"], target_dir)

            return {
                "episode_id": episode_id,
                "language": norm_lang,
                "audio_path": relative_path,
                "full_path": merge_result["output_path"],
                "filename": merge_result["filename"],
                "duration_ms": merge_result["duration_ms"],
                "file_size": merge_result["file_size"],
                "format": merge_result["format"],
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

        finally:
            # Clean up all individual temporary clip files
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning("Failed to clean up temp dir %s: %s", temp_dir, e)


# Singleton instance
tts_service = TTSService()
