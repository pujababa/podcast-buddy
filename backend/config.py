import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Database path resolution: if relative path, resolve relative to BASE_DIR
raw_db_path = os.getenv("DATABASE_PATH", "podcast_buddy.db")
if not os.path.isabs(raw_db_path):
    DATABASE_PATH = os.path.abspath(os.path.join(BASE_DIR, raw_db_path))
else:
    DATABASE_PATH = raw_db_path

# Server settings
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 5000))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

# External API settings (Server-Side Only)
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
SERPAPI_CONNECT_TIMEOUT = float(os.getenv("SERPAPI_CONNECT_TIMEOUT", 5.0))
SERPAPI_READ_TIMEOUT = float(os.getenv("SERPAPI_READ_TIMEOUT", 10.0))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL

# Audio output directory settings
raw_audio_dir = os.getenv("AUDIO_OUTPUT_DIR", "generated_audio")
if not os.path.isabs(raw_audio_dir):
    AUDIO_OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, raw_audio_dir))
else:
    AUDIO_OUTPUT_DIR = raw_audio_dir

if not os.path.exists(AUDIO_OUTPUT_DIR):
    os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

# Text-to-Speech Settings (Server-Side Only)
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", os.getenv("TTS_API_KEY", "")).strip()
SARVAM_TTS_URL = os.getenv("SARVAM_TTS_URL", "https://api.sarvam.ai/text-to-speech").strip()
DEFAULT_SARVAM_MODEL = "bulbul:v3"
SARVAM_MODEL = os.getenv("SARVAM_MODEL", DEFAULT_SARVAM_MODEL).strip() or DEFAULT_SARVAM_MODEL

