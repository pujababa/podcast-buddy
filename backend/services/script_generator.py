import json
import logging
from typing import Dict, Any, List, Optional

from backend.services.llm_service import (
    gemini_service,
    GeminiService,
    GeminiError,
    GeminiResponseError,
    GeminiConfigurationError,
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiServiceError
)

logger = logging.getLogger("script_generator")
if not logger.handlers:
    _log_handler = logging.StreamHandler()
    _log_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [ScriptGenerator] %(message)s"))
    logger.addHandler(_log_handler)
    logger.setLevel(logging.INFO)


class ScriptGenerationError(GeminiError):
    """Raised when podcast script generation encounters an error."""
    pass


class ScriptValidationError(GeminiResponseError):
    """Raised when generated podcast script fails schema or speaker validation."""
    pass


ALLOWED_SPEAKERS = {"host", "cohost"}

PODCAST_SCRIPT_SYSTEM_INSTRUCTION = """You are a professional podcast producer and scriptwriter for "Podcast Buddy".
Your job is to generate an engaging, natural, and conversational news podcast script featuring two hosts: "host" (Host) and "cohost" (CoHost).

CRITICAL GROUNDING & ACCURACY RULES:
1. STRICT GROUNDING: Base the entire discussion strictly and exclusively on the provided Episode Information and AI Intelligence (overview, key points, facts, entities, source insights, limitations, and confidence).
2. DO NOT FABRICATE: Do NOT invent facts, statistics, dates, quotes, claims, or personal anecdotes. If a detail is not in the supplied intelligence, do not include it.
3. PRESERVE UNCERTAINTY: If the intelligence notes uncertainty, conflicting reporting between sources, or limitations, have the hosts explicitly acknowledge that uncertainty in their dialogue.
4. SOURCE ATTRIBUTION: When discussing information, use natural conversational attribution (e.g. "According to the supplied reporting...", "One source highlights that...", "The report from [Publisher] notes..."). If sources disagree, present both sides neutrally without declaring one correct.
5. CONVERSATIONAL TONE:
   - Dynamic, natural back-and-forth between Host and CoHost.
   - Avoid reading bullet points verbatim or robotic recitations.
   - Keep dialogue turns balanced (avoid long uninterrupted monologues).
   - Use conversational transitions, curiosity, and clarifying questions between speakers.
   - Do not use clickbait or fake external calls-to-action (like subscribing to YouTube channels).
6. SPEAKERS: Dialogue lines MUST only specify speaker as "host" or "cohost".
7. OUTPUT FORMAT: Return ONLY a valid JSON object matching the requested schema. No code fences, no introductory or trailing text."""


import re

DEVANAGARI_REGEX = re.compile(r'[\u0900-\u097F]')
ODIA_REGEX = re.compile(r'[\u0B00-\u0B7F]')


def build_script_generation_prompt(
    episode: Dict[str, Any],
    intelligence: Dict[str, Any],
    length: str = "standard",
    language: str = "english"
) -> str:
    """Construct the prompt containing episode, intelligence data, and language instructions for Gemini."""
    ep_title = episode.get("title") or "Untitled Episode"
    ep_desc = episode.get("description") or "No description provided."

    norm_lang = str(language or "english").strip().lower()

    # Craft language-specific instructions
    if norm_lang == "hindi":
        lang_instruction = """CRITICAL LANGUAGE & SCRIPT REQUIREMENT (STRICT DEVANAGARI):
- The entire podcast dialogue for BOTH "host" and "cohost" MUST be written in genuine HINDI using DEVANAGARI SCRIPT (देवनागरी लिपि).
- Example: {"speaker": "host", "text": "नमस्ते और पॉडकास्ट बडी में आपका स्वागत है। आज हम बात करेंगे..."}
- DO NOT use English, Latin, or Romanized transliteration for Hindi dialogue text.
- Every spoken sentence must use proper Hindi grammar and Devanagari Unicode characters."""
    elif norm_lang == "odia":
        lang_instruction = """CRITICAL LANGUAGE & SCRIPT REQUIREMENT (STRICT ODIA SCRIPT):
- The entire podcast dialogue for BOTH "host" and "cohost" MUST be written in genuine ODIA using ODIA SCRIPT (ଓଡ଼ିଆ ଲିପି).
- Example: {"speaker": "host", "text": "ନମସ୍କାର ଏବଂ ପଡ଼କାଷ୍ଟ ବଡିକୁ ଆପଣଙ୍କୁ ସ୍ୱାଗତ। ଆଜି ଆମେ ଆଲୋଚନା କରିବା..."}
- DO NOT use English or Roman transliteration for Odia dialogue text.
- Every spoken sentence must use proper Odia grammar and Odia Unicode characters."""
    elif norm_lang == "hinglish":
        lang_instruction = """LANGUAGE REQUIREMENT:
- The podcast dialogue should be in vibrant, natural conversational Hinglish (a blend of Hindi and English written in Latin/Roman script with authentic Indian podcast transitions and idioms)."""
    else:
        lang_instruction = """LANGUAGE REQUIREMENT:
- The podcast dialogue must be written in clear, engaging, professional conversational English."""

    # Format intelligence components
    overview = intelligence.get("overview") or "N/A"
    key_points = intelligence.get("key_points") or []
    important_facts = intelligence.get("important_facts") or []
    topics = intelligence.get("topics") or []
    entities = intelligence.get("entities") or []
    source_insights = intelligence.get("source_insights") or []
    confidence = intelligence.get("confidence") or "medium"
    limitations = intelligence.get("limitations") or []

    prompt = f"""Generate a two-speaker podcast script for Podcast Buddy based on the following verified intelligence:

{lang_instruction}

EPISODE INFORMATION:
- Title: {ep_title}
- Description: {ep_desc}
- Target Format: {length} conversational news breakdown (approx. 5-8 minutes spoken dialogue)
- Target Language: {norm_lang.upper()}

AI INTELLIGENCE SUMMARY:
- Overview: {overview}

KEY POINTS:
{chr(10).join(f"- {p}" for p in key_points) if key_points else "- None provided"}

IMPORTANT FACTS:
{chr(10).join(f"- {f}" for f in important_facts) if important_facts else "- None provided"}

TOPICS:
{", ".join(topics) if topics else "General News"}

IDENTIFIED ENTITIES:
{json.dumps(entities, indent=2) if entities else "None"}

SOURCE-SPECIFIC INSIGHTS:
{json.dumps(source_insights, indent=2) if source_insights else "None"}

CONFIDENCE LEVEL: {confidence}

LIMITATIONS & GROUNDING CONSTRAINTS:
{chr(10).join(f"- {l}" for l in limitations) if limitations else "- Strictly grounded in provided source information"}

REQUIRED SCRIPT JSON SCHEMA:
{{
  "intro": {{
    "title": "Episode intro hook title",
    "lines": [
      {{ "speaker": "host", "text": "..." }},
      {{ "speaker": "cohost", "text": "..." }}
    ]
  }},
  "segments": [
    {{
      "title": "Segment or Story Title",
      "lines": [
        {{ "speaker": "host", "text": "..." }},
        {{ "speaker": "cohost", "text": "..." }}
      ]
    }}
  ],
  "key_takeaways": [
    {{ "speaker": "host", "text": "..." }},
    {{ "speaker": "cohost", "text": "..." }}
  ],
  "outro": {{
    "lines": [
      {{ "speaker": "host", "text": "..." }},
      {{ "speaker": "cohost", "text": "..." }}
    ]
  }}
}}

Remember: Return ONLY the valid JSON object conforming strictly to the schema above."""
    return prompt


def validate_dialogue_line(line: Any, location: str) -> Dict[str, str]:
    """Validate an individual dialogue line."""
    if not isinstance(line, dict):
        raise ScriptValidationError(f"Expected dialogue line object at {location}, got {type(line).__name__}.")

    speaker = str(line.get("speaker") or "").strip().lower()
    if speaker not in ALLOWED_SPEAKERS:
        raise ScriptValidationError(
            f"Invalid speaker '{line.get('speaker')}' at {location}. Allowed speakers are: {', '.join(sorted(ALLOWED_SPEAKERS))}."
        )

    text = line.get("text")
    if text is None or not isinstance(text, str) or not text.strip():
        raise ScriptValidationError(f"Empty or missing dialogue text for speaker '{speaker}' at {location}.")

    return {
        "speaker": speaker,
        "text": text.strip()
    }


def validate_script_language(script_data: Dict[str, Any], language: Optional[str] = None) -> None:
    """
    Verify that the generated script dialogue adheres to the required script.
    - Hindi output must actually be written in Devanagari script (U+0900 to U+097F).
    - Odia output must actually be written in Odia script (U+0B00 to U+0B7F).
    Raises ScriptValidationError if the output fails script/language validation.
    """
    if not language:
        return

    norm_lang = str(language).strip().lower()
    if norm_lang not in ("hindi", "odia"):
        return

    # Extract all dialogue text
    all_texts = []
    for line in script_data.get("intro", {}).get("lines", []):
        all_texts.append(line.get("text", ""))
    for seg in script_data.get("segments", []):
        for line in seg.get("lines", []):
            all_texts.append(line.get("text", ""))
    for line in script_data.get("key_takeaways", []):
        all_texts.append(line.get("text", ""))
    for line in script_data.get("outro", {}).get("lines", []):
        all_texts.append(line.get("text", ""))

    combined_text = " ".join(all_texts)
    if not combined_text.strip():
        raise ScriptValidationError("Script contains no dialogue text to validate language.")

    if norm_lang == "hindi":
        dev_matches = DEVANAGARI_REGEX.findall(combined_text)
        if len(dev_matches) < 15:
            raise ScriptValidationError(
                "Hindi dialogue generation failed script verification: dialogue must be written in Devanagari script (U+0900 to U+097F). "
                f"Found only {len(dev_matches)} Devanagari characters in generated dialogue."
            )

    elif norm_lang == "odia":
        odia_matches = ODIA_REGEX.findall(combined_text)
        if len(odia_matches) < 15:
            raise ScriptValidationError(
                "Odia dialogue generation failed script verification: dialogue must be written in Odia script (U+0B00 to U+0B7F). "
                f"Found only {len(odia_matches)} Odia characters in generated dialogue."
            )


def validate_and_normalize_script(data: Dict[str, Any], language: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate the complete podcast script structure.
    Checks:
    - Top-level sections: intro, segments, key_takeaways, outro
    - Valid non-empty lines in each section
    - Speaker validation ('host' or 'cohost')
    - Non-empty dialogue text
    - Language and script verification (Devanagari for Hindi, Odia script for Odia)
    """
    if not isinstance(data, dict):
        raise ScriptValidationError("Podcast script output must be a top-level JSON object.")

    # 1. Intro validation
    if "intro" not in data or not isinstance(data["intro"], dict):
        raise ScriptValidationError("Missing or invalid required section 'intro' in podcast script.")
    intro_dict = data["intro"]
    intro_title = str(intro_dict.get("title") or "Introduction").strip()
    raw_intro_lines = intro_dict.get("lines")
    if not isinstance(raw_intro_lines, list) or len(raw_intro_lines) == 0:
        raise ScriptValidationError("Section 'intro' must contain a non-empty list of dialogue 'lines'.")

    intro_lines = [validate_dialogue_line(l, f"intro.lines[{idx}]") for idx, l in enumerate(raw_intro_lines)]

    # 2. Segments validation
    if "segments" not in data or not isinstance(data["segments"], list):
        raise ScriptValidationError("Missing or invalid required section 'segments' (must be a list).")
    if len(data["segments"]) == 0:
        raise ScriptValidationError("Section 'segments' must contain at least one story segment.")

    segments = []
    for s_idx, seg in enumerate(data["segments"]):
        if not isinstance(seg, dict):
            raise ScriptValidationError(f"Segment at index {s_idx} must be an object.")
        seg_title = str(seg.get("title") or f"Story Segment {s_idx + 1}").strip()
        raw_seg_lines = seg.get("lines")
        if not isinstance(raw_seg_lines, list) or len(raw_seg_lines) == 0:
            raise ScriptValidationError(f"Segment '{seg_title}' at index {s_idx} must contain a non-empty 'lines' list.")

        seg_lines = [validate_dialogue_line(l, f"segments[{s_idx}].lines[{l_idx}]") for l_idx, l in enumerate(raw_seg_lines)]
        segments.append({
            "title": seg_title,
            "lines": seg_lines
        })

    # 3. Key Takeaways validation
    if "key_takeaways" not in data or not isinstance(data["key_takeaways"], list):
        raise ScriptValidationError("Missing or invalid required section 'key_takeaways' (must be a list).")
    if len(data["key_takeaways"]) == 0:
        raise ScriptValidationError("Section 'key_takeaways' must contain at least one dialogue line.")

    key_takeaways = [validate_dialogue_line(l, f"key_takeaways[{idx}]") for idx, l in enumerate(data["key_takeaways"])]

    # 4. Outro validation
    if "outro" not in data or not isinstance(data["outro"], dict):
        raise ScriptValidationError("Missing or invalid required section 'outro' in podcast script.")
    outro_dict = data["outro"]
    raw_outro_lines = outro_dict.get("lines")
    if not isinstance(raw_outro_lines, list) or len(raw_outro_lines) == 0:
        raise ScriptValidationError("Section 'outro' must contain a non-empty list of dialogue 'lines'.")

    outro_lines = [validate_dialogue_line(l, f"outro.lines[{idx}]") for idx, l in enumerate(raw_outro_lines)]

    result = {
        "intro": {
            "title": intro_title,
            "lines": intro_lines
        },
        "segments": segments,
        "key_takeaways": key_takeaways,
        "outro": {
            "lines": outro_lines
        }
    }

    if language:
        result["language"] = str(language).strip().lower()

    # 5. Language and script verification
    validate_script_language(result, language=language)

    return result


class PodcastScriptGenerator:
    """
    Service responsible for constructing grounded podcast script prompts,
    dispatching to the Gemini service, and validating conversational script structure.
    """

    def __init__(self, service: Optional[GeminiService] = None):
        self.gemini = service or gemini_service

    def generate_podcast_script(
        self,
        episode: Dict[str, Any],
        intelligence: Dict[str, Any],
        length: str = "standard",
        language: str = "english"
    ) -> Dict[str, Any]:
        """
        Generate a structured, source-grounded podcast script for an episode.

        :param episode: Episode dictionary containing title, description, and metadata.
        :param intelligence: Validated Phase 5 AI intelligence dictionary.
        :param length: Target episode length style (default: 'standard').
        :param language: Target language style ('english', 'hindi', 'odia', 'hinglish').
        :return: Validated structured podcast script dictionary.
        """
        if not intelligence or not isinstance(intelligence, dict):
            raise ScriptGenerationError("Valid AI intelligence must be provided to generate a podcast script.")

        if not episode or not isinstance(episode, dict):
            raise ScriptGenerationError("Valid episode information must be provided.")

        logger.info(
            "Generating podcast script for episode '%s' (length=%s, language=%s)",
            episode.get("title", "Untitled"),
            length,
            language
        )

        prompt = build_script_generation_prompt(episode, intelligence, length=length, language=language)

        # Call Gemini service to obtain structured JSON
        raw_json = self.gemini.generate_structured_json(
            prompt=prompt,
            system_instruction=PODCAST_SCRIPT_SYSTEM_INSTRUCTION,
            temperature=0.3
        )

        # Validate complete script schema and language script
        script = validate_and_normalize_script(raw_json, language=language)
        logger.info(
            "Successfully validated podcast script (%s) with %d segments and %d takeaways.",
            language,
            len(script["segments"]),
            len(script["key_takeaways"])
        )
        return script


# Default singleton instance and convenience function
script_generator = PodcastScriptGenerator()


def generate_podcast_script(
    episode: Dict[str, Any],
    intelligence: Dict[str, Any],
    length: str = "standard",
    language: str = "english"
) -> Dict[str, Any]:
    """Module-level convenience function for generating a podcast script."""
    return script_generator.generate_podcast_script(episode, intelligence, length=length, language=language)
