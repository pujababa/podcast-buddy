# Podcast Buddy – AI-Powered Podcast & News Discovery Assistant

Podcast Buddy is an intelligent, full-stack news discovery and automated podcast production platform designed for end-to-end multi-language podcast generation. It transforms live trending news stories into curated summaries, multi-speaker conversational scripts, and mastered audio episodes with multi-language synthesis.

---

## 📌 Architecture & Features Overview

Podcast Buddy implements a complete 7-stage pipeline:
1. **Live News Discovery**: Server-side SerpAPI integration with topic filtering, real source URLs, publisher attribution, and duplicate-click prevention.
2. **Story Selection & Persistence**: SQLite-backed episode tracking preserving article selections, summaries, multi-language scripts, and audio file metadata.
3. **AI Summarization**: Google Gemini LLM summarization pipeline with structured insights and key takeaways.
4. **Conversational Script Generation**: Dual-host (Host & Co-Host) natural dialogue script rendering in English, Hindi, and Hinglish.
5. **Multi-Language Audio Synthesis**: Text-to-Speech (TTS) voice generation with separate audio tracks for English, Hindi, and Hinglish.
6. **Audio Player & Streaming**: Native HTML5 audio player supporting track switching, playback controls, and persistent saved audio recall.
7. **Interactive Episode Q&A**: In-context LLM chat allowing listeners to ask questions directly about any generated episode.

---

## 📂 Project Structure

```text
podcast-buddy/
├── backend/
│   ├── app.py                     # Flask application entry point and configuration
│   ├── database.py                # SQLite database connection and schema management
│   ├── routes/
│   │   ├── __init__.py            # Blueprint registrations
│   │   ├── news.py                # Live SerpAPI search endpoints
│   │   └── episodes.py            # Episode management, AI generation, and audio streaming
│   └── services/
│       ├── serpapi_service.py     # Live news query and error handling
│       ├── llm_service.py         # Google Gemini summarization and chat engine
│       ├── script_generator.py    # Multi-language conversational script generator
│       ├── tts_service.py         # gTTS and edge-tts synthesis pipeline
│       └── audio_processor.py     # Dialogue segment stitching and audio export
├── frontend/
│   └── index.html                 # Semantic dashboard and responsive UI
├── static/
│   ├── css/
│   │   └── style.css              # Dark-mode styling, glassmorphism design system
│   └── js/
│       └── app.js                 # Frontend application state, audio player, API client
├── tests/
│   ├── test_app.py                # Health check and root route tests
│   ├── test_episodes.py           # Episode workflow, database, and route tests
│   ├── test_news_routes.py        # SerpAPI endpoints and error handling tests
│   ├── test_script_generator.py   # Script formatting and language tests
│   ├── test_audio_generation.py   # Audio rendering and synthesis tests
│   └── test_audit_fixes.py        # Targeted regression suite for audit fixes
├── generated_audio/               # Rendered MP3 episode tracks
├── podcast_buddy.db               # SQLite database file
├── .env.example                   # Environment configuration template
├── requirements.txt               # Project dependencies
└── README.md                      # Project documentation and guide
```

---

## 🚀 Getting Started

### 1. Prerequisites
* **Python 3.10+** (Recommended: Python 3.11 or later)
* **FFmpeg** (Installed and accessible in system `PATH` for `pydub` audio processing)

---

### 2. Virtual Environment Setup

Open PowerShell or terminal in the `podcast-buddy` root directory:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

*Note: If execution policies restrict running scripts in PowerShell, run:*
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Configure Environment Variables

Create your local `.env` file from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Populate the required environment keys in `.env`:
* `SERPAPI_API_KEY`: Required for live Google News search via SerpAPI.
* `GEMINI_API_KEY`: Required for AI summaries, script generation, and Q&A chat via Google Gemini.
* `FLASK_ENV`: Set to `development` for local testing.

> **Security Note:** Never commit API keys or `.env` files to version control. All API calls are executed strictly server-side.

---

### 5. Launch the Application

```powershell
python backend/app.py
```

Open your browser and navigate to:
**`http://127.0.0.1:5000/app`** (or `http://127.0.0.1:5000`)

---

## 📡 Key API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status check |
| `GET` | `/app` | Main dashboard user interface |
| `GET` | `/api/news/search?q=<query>&category=<cat>` | Live SerpAPI news search |
| `GET` | `/api/news/categories` | Preconfigured topic categories |
| `POST` | `/api/episodes` | Create new episode from selected news articles |
| `GET` | `/api/episodes` | List all saved episodes |
| `GET` | `/api/episodes/<id>` | Retrieve episode metadata, script, and audio info |
| `POST` | `/api/episodes/<id>/summary` | Generate AI executive summary |
| `POST` | `/api/episodes/<id>/script` | Generate dual-host conversational script |
| `POST` | `/api/episodes/<id>/generate-audio` | Synthesize multi-speaker audio (`english`, `hindi`, `hinglish`) |
| `GET` | `/api/episodes/<id>/audio?lang=<lang>` | Stream generated MP3 audio track |
| `POST` | `/api/episodes/<id>/chat` | Interactive Q&A chat about the episode |

---

## 🧪 Automated Testing

Podcast Buddy includes an extensive automated test suite covering routes, services, database integrity, error recovery, and audio processing:

```powershell
# Run all unit and integration tests
python -m unittest discover tests

# Run targeted audit regression tests
python -m unittest tests/test_audit_fixes.py
```

---

## ⚠️ Known Limitations & Provider Constraints

1. **Odia Audio Synthesis Limitation**:
   - Google Translate TTS (`gTTS`) does not currently provide a native Odia (`or`) speech model.
   - Odia is explicitly marked as disabled in the Audio Studio language selector with an informative notice.
   - Any manual synthesis request for Odia safely returns `HTTP 502 Bad Gateway` (`TTS_ERROR`) explaining provider unavailability rather than generating fake or incorrect audio.

2. **SerpAPI Search Quota & Connectivity**:
   - Live news discovery relies on external SerpAPI connectivity and account plan limits.
   - If an empty query, rate limit, or network issue occurs, the UI presents an inline error state with a dedicated **Retry Search** button to recover cleanly.

3. **Audio Hardware Playback**:
   - Automated server-side tests verify audio file creation, MP3 headers, sample rates, byte lengths, and streaming endpoints.
   - Physical headphone/speaker playback must be validated manually in the browser.

---

## 🎬 Manual Demonstration Steps

Follow this simple flow during project demonstrations:

1. **Start Server**: Run `python backend/app.py` and navigate to `http://127.0.0.1:5000/app`.
2. **Discover News**:
   - Click a topic category (e.g., **Technology** or **AI & ML**) or type a search query (e.g., `space exploration`).
   - Click **Search News** to view real article cards, publishers, dates, and live source links.
3. **Select Stories**: Select 1 to 3 article cards using the checkboxes.
4. **Create Episode**: Click **Create Episode from Selected** to open the Episode Studio.
5. **AI Summarization**: Click **Generate Summary** to produce an executive brief with key takeaways.
6. **Script Generation**: Click **Generate Script** to create dual-host conversational dialogue.
7. **Audio Synthesis & Playback**:
   - Choose language (**English**, **Hindi**, or **Hinglish**). Note that Odia is honestly disabled.
   - Click **Generate Audio**. Once generated, use the player to play, pause, seek, and verify the audio output.
   - Switch language selector to hear language-specific tracks.
8. **Episode Q&A**: Ask a question in the Episode Q&A box (e.g., *"What were the key breakthroughs mentioned?"*) and receive real-time AI answers based on the selected stories.
9. **Saved Library**: Navigate to **Saved Episodes** to verify all episodes and their generated audio remain permanently saved and playable across sessions.
