import os
import shutil
import logging
from typing import List, Dict, Any, Optional


def _ensure_ffmpeg_available():
    """Ensure FFmpeg executable is discovered and registered in PATH for pydub/system."""
    if shutil.which("ffmpeg"):
        return
    if os.name == "nt":
        # Check User and System PATH from Windows Registry (e.g. if installed during runtime)
        try:
            import winreg
            for hive, subkey in [
                (winreg.HKEY_CURRENT_USER, r"Environment"),
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
            ]:
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        val, _ = winreg.QueryValueEx(key, "Path")
                        for p in val.split(";"):
                            p = p.strip()
                            if p and os.path.isfile(os.path.join(p, "ffmpeg.exe")):
                                if p not in os.environ.get("PATH", ""):
                                    os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
                                return
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback check in local WinGet packages folder
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            winget_pkgs = os.path.join(local_appdata, "Microsoft", "WinGet", "Packages")
            if os.path.isdir(winget_pkgs):
                for root, dirs, files in os.walk(winget_pkgs):
                    if "ffmpeg.exe" in files:
                        if root not in os.environ.get("PATH", ""):
                            os.environ["PATH"] = root + os.pathsep + os.environ.get("PATH", "")
                        return


_ensure_ffmpeg_available()

from pydub import AudioSegment
import miniaudio

_ffmpeg_bin = shutil.which("ffmpeg")
if _ffmpeg_bin:
    AudioSegment.converter = _ffmpeg_bin


from backend.config import AUDIO_OUTPUT_DIR

logger = logging.getLogger("podcast_buddy.audio_processor")
if not logger.handlers:
    _log_handler = logging.StreamHandler()
    _log_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [AudioProcessor] %(message)s"))
    logger.addHandler(_log_handler)
    logger.setLevel(logging.INFO)


class AudioProcessingError(Exception):
    """Base exception for audio processing failures."""
    pass


class AudioPathSecurityError(AudioProcessingError):
    """Raised when an audio path violates directory security constraints."""
    pass


class AudioEmptyInputError(AudioProcessingError):
    """Raised when attempting to merge an empty list of audio files."""
    pass


class AudioDecodeError(AudioProcessingError):
    """Raised when an audio clip cannot be decoded or loaded."""
    pass


def validate_safe_audio_path(target_path: str, base_dir: Optional[str] = None) -> str:
    """
    Ensure target_path resolves strictly within base_dir (default: AUDIO_OUTPUT_DIR).
    Guards against path traversal and arbitrary filesystem writes.
    Returns the resolved absolute path.
    """
    base = os.path.abspath(base_dir or AUDIO_OUTPUT_DIR)
    resolved = os.path.abspath(target_path)

    # Use os.path.commonpath to strictly enforce confinement
    try:
        common = os.path.commonpath([base, resolved])
    except ValueError as e:
        raise AudioPathSecurityError(f"Access denied: path '{target_path}' is outside base directory.") from e

    if common != base:
        raise AudioPathSecurityError(f"Access denied: path '{target_path}' attempts path traversal outside '{base}'.")

    return resolved


class AudioProcessor:
    """
    Service responsible for loading, decoding, pacing, and merging
    multi-speaker podcast dialogue audio clips into a single continuous podcast audio file.
    NEVER uses raw binary byte concatenation.
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = os.path.abspath(output_dir or AUDIO_OUTPUT_DIR)
        os.makedirs(self.output_dir, exist_ok=True)

    def load_audio_file(self, file_path: str) -> AudioSegment:
        """
        Safely decode and load an audio file into a pydub AudioSegment.
        Uses miniaudio for robust multi-format decoding (MP3, WAV, FLAC, etc.)
        with fallback to pydub native loader.
        """
        if not os.path.isfile(file_path):
            raise AudioDecodeError(f"Audio file not found: {file_path}")

        try:
            # miniaudio handles MP3, WAV, etc. cleanly in pure memory without external ffmpeg requirement
            decoded = miniaudio.decode_file(file_path)
            segment = AudioSegment(
                data=decoded.samples.tobytes(),
                sample_width=2,
                frame_rate=decoded.sample_rate,
                channels=decoded.nchannels
            )
            return segment
        except Exception as e_miniaudio:
            # Fallback to direct pydub loader (e.g. for pure WAV)
            try:
                if file_path.lower().endswith(".wav"):
                    return AudioSegment.from_wav(file_path)
                return AudioSegment.from_file(file_path)
            except Exception as e_pydub:
                logger.error("Failed to decode audio file %s: miniaudio err=%s, pydub err=%s", file_path, e_miniaudio, e_pydub)
                raise AudioDecodeError(f"Failed to decode audio file '{file_path}': {e_miniaudio}") from e_miniaudio

    def generate_silence(self, duration_ms: int = 300, frame_rate: int = 24000, channels: int = 1) -> AudioSegment:
        """Generate silent audio segment for natural conversational pauses."""
        if duration_ms <= 0:
            return AudioSegment.empty()
        return AudioSegment.silent(duration=duration_ms, frame_rate=frame_rate)

    def merge_audio_segments(
        self,
        audio_files: List[str],
        output_filename_or_path: str,
        pause_ms: int = 300
    ) -> Dict[str, Any]:
        """
        Properly merges an ordered sequence of speaker audio files with conversational pauses.
        Enforces security checks on the output destination.
        
        Args:
            audio_files: List of audio file paths to concatenate.
            output_filename_or_path: Target filename (or path) inside output_dir.
            pause_ms: Milliseconds of natural pause between speaker dialogue turns.
            
        Returns:
            Dict containing output_path, duration_ms, file_size, and format.
        """
        if not audio_files:
            raise AudioEmptyInputError("Cannot merge an empty list of audio files.")

        # Determine target absolute path safely
        if not os.path.isabs(output_filename_or_path):
            target_path = os.path.join(self.output_dir, output_filename_or_path)
        else:
            target_path = output_filename_or_path

        safe_output_path = validate_safe_audio_path(target_path, self.output_dir)

        # Ensure parent directory exists
        parent_dir = os.path.dirname(safe_output_path)
        os.makedirs(parent_dir, exist_ok=True)

        logger.info("Merging %d audio segments into: %s (pause=%dms)", len(audio_files), safe_output_path, pause_ms)

        combined = AudioSegment.empty()
        base_frame_rate: Optional[int] = None
        base_channels: Optional[int] = None

        for idx, f_path in enumerate(audio_files):
            seg = self.load_audio_file(f_path)
            if len(seg) == 0:
                continue

            if base_frame_rate is None:
                base_frame_rate = seg.frame_rate
                base_channels = seg.channels
            else:
                # Normalize sample rate and channels to match first segment
                if seg.frame_rate != base_frame_rate or seg.channels != base_channels:
                    seg = seg.set_frame_rate(base_frame_rate).set_channels(base_channels)

            if idx > 0 and pause_ms > 0 and len(combined) > 0:
                silence = AudioSegment.silent(duration=pause_ms, frame_rate=base_frame_rate)
                if base_channels and base_channels > 1:
                    silence = silence.set_channels(base_channels)
                combined += silence

            combined += seg

        if len(combined) == 0:
            raise AudioProcessingError("All provided audio segments were empty.")

        # Export merged audio
        # Default format based on file extension (.wav or .mp3)
        ext = os.path.splitext(safe_output_path)[1].lower().lstrip(".")
        export_format = ext if ext in ("wav", "mp3") else "wav"

        try:
            combined.export(safe_output_path, format=export_format)
        except Exception as e:
            # If MP3 export failed (e.g. ffmpeg missing), fall back safely to WAV
            if export_format == "mp3":
                wav_path = os.path.splitext(safe_output_path)[0] + ".wav"
                logger.warning("MP3 export failed (%s). Falling back safely to WAV: %s", e, wav_path)
                combined.export(wav_path, format="wav")
                safe_output_path = wav_path
                export_format = "wav"
            else:
                logger.error("Failed to export combined audio to %s: %s", safe_output_path, e)
                raise AudioProcessingError(f"Failed to export audio file '{safe_output_path}': {e}") from e

        file_size = os.path.getsize(safe_output_path)
        duration_ms = len(combined)

        logger.info(
            "Successfully merged audio: duration=%.2fs, size=%d bytes, path=%s",
            duration_ms / 1000.0,
            file_size,
            safe_output_path
        )

        return {
            "output_path": safe_output_path,
            "filename": os.path.basename(safe_output_path),
            "duration_ms": duration_ms,
            "file_size": file_size,
            "format": export_format
        }


# Singleton instance
audio_processor = AudioProcessor()
