# Podcast Buddy — College Project Demonstration & Viva Guide

## 1. Project Introduction
**Podcast Buddy** is an end-to-end AI-powered news discovery and automated podcast production platform. It transforms real-time news headlines and web articles into engaging, conversational multi-speaker podcast episodes with natural audio synthesis in multiple Indian regional languages, including **Odia**, **Hindi**, **Hinglish**, and **English**.

---

## 2. Problem Statement
- **Information Overload:** Readers are overwhelmed with endless text articles and fragmented news across the web.
- **Accessibility Barriers:** Commuters, visually impaired users, and busy professionals prefer hands-free audio formats over reading text.
- **Language & Cultural Gaps:** Most automated text-to-speech tools only support generic English. Indian regional languages—especially Odia and conversational Hindi—lack accessible, natural, dual-speaker conversational audio synthesis.
- **Manual Production Bottleneck:** Traditional podcast production requires human hosts, scriptwriting, voice recording, sound editing, and audio post-processing, taking hours for a single episode.

---

## 3. Project Objectives
1. **Automated Discovery:** Aggregate live, credible news articles using SerpAPI without manual curation.
2. **AI Intelligence & Synthesis:** Summarize key points, detect sentiment, identify perspectives, and synthesize natural conversational scripts using Google Gemini.
3. **Dual-Speaker Conversational Audio:** Convert scripts into dynamic two-person dialogue (Host & Co-Host) rather than flat monotone narration.
4. **Regional Language Inclusivity:** Support genuine Odia speech synthesis via **Sarvam AI Bulbul v3** alongside Hindi, English, and Hinglish via **Microsoft Edge Neural TTS**.
5. **Interactive Audio Studio:** Provide an intuitive web interface with synchronized playback, seeking, volume controls, real-time waveform visualization, and episode library management.

---

## 4. Technology Stack

| Layer | Technologies Used | Purpose |
|---|---|---|
| **Backend Framework** | Python 3.14 / Flask | RESTful API service, routing, session handling, business logic |
| **Database** | SQLite3 (`podcast_buddy.db`) | Relational storage for episodes, news sources, scripts, and audio metadata |
| **News Retrieval** | SerpAPI (Google News engine) | Live news querying, article snippets, source attribution |
| **LLM & Intelligence** | Google Gemini API (`google-genai`) | Source analysis, perspective detection, and dual-speaker script drafting |
| **Odia TTS Engine** | Sarvam AI (`bulbul:v3`) | Native Odia (`od-IN`) neural speech synthesis (`shubh` host & `kavya` cohost) |
| **Hindi & English TTS** | Microsoft Edge Neural TTS (`edge-tts`) | Free neural voices (`hi-IN-MadhurNeural`, `hi-IN-SwaraNeural`, `en-US-GuyNeural`, `en-US-JennyNeural`) |
| **Audio Processing** | PyDub + FFmpeg | Audio stitching, segment normalization, pause insertion, MP3 encoding |
| **Frontend UI** | HTML5, Vanilla JavaScript (ES6+), Vanilla CSS | Responsive UI, Audio Studio, HTML5 audio player, dynamic CSS waveform |
| **Testing & Automation** | Python `unittest`, Chrome DevTools Protocol (CDP) | 150 automated unit/integration tests and real-browser headless validation |

---

## 5. System Architecture & Component Diagram

```
+-------------------------------------------------------------+
|                       Web Browser UI                        |
|  - News Search & Discovery   - Saved Episodes Library       |
|  - Audio Studio & Waveform   - Dual-Speaker Dialogue Script |
+------------------------------+------------------------------+
                               | REST APIs / JSON / Audio Stream
                               v
+-------------------------------------------------------------+
|                     Flask Backend Server                    |
|  - /api/news/search          - /api/episodes                |
|  - /api/episodes/<id>/script - /api/episodes/<id>/generate-audio |
|  - /api/episodes/<id>/audio  - Error Handling & Validation  |
+---------+--------------------+-------------------+----------+
          |                    |                   |
          v                    v                   v
   +--------------+     +---------------+   +---------------+
   |   SerpAPI    |     | Google Gemini |   |  TTS Engines  |
   | (Live News)  |     | (LLM Scripts) |   | Sarvam/EdgeTTS|
   +--------------+     +---------------+   +-------+-------+
                                                    |
                                                    v
                                            +---------------+
                                            | PyDub / FFmpeg|
                                            | (Stitch/Norm) |
                                            +-------+-------+
                                                    |
                                                    v
                                            +---------------+
                                            |generated_audio|
                                            | (.mp3 storage)|
                                            +---------------+
```

---

## 6. End-to-End Workflow

1. **Search News:** User submits a search query (e.g. "Odisha Technology"). SerpAPI returns live news stories with sources, snippets, and timestamps.
2. **Select & Ingest:** User chooses 1 to 5 stories and creates an episode.
3. **AI Intelligence Analysis:** Google Gemini analyzes source facts, extracts key takeaways, and identifies diverse perspectives.
4. **Dialogue Script Generation:** Gemini drafts a natural conversational script with sections (Intro, Segments, Key Takeaways, Outro) and alternating Host & Co-Host dialogue.
5. **Multi-Speaker Audio Synthesis:**
   - For **Odia**: Sarvam AI Bulbul v3 synthesizes *Shubh* (Host) and *Kavya* (CoHost).
   - For **Hindi**: Edge Neural TTS synthesizes *MadhurNeural* (Host) and *SwaraNeural* (CoHost).
   - For **English**: Edge Neural TTS synthesizes *GuyNeural* (Host) and *JennyNeural* (CoHost).
6. **Audio Assembly & Normalization:** PyDub stitches turn-by-turn clips with 250ms conversational pauses and normalizes volume to -16 dBFS.
7. **Streaming & Interactive Playback:** Flask streams the MP3 to the browser HTML5 audio element with synchronized waveform visualizer, seeking, volume control, and library status updates.

---

## 7. Odia and Hindi Dual-Speaker Synthesis Highlights

- **Genuine Regional Dual-Speaker Voices:**
  - **Odia (`od-IN`):** Uses Sarvam AI Bulbul v3 with **Shubh** (Host, expressive male) and **Kavya** (Co-Host, expressive female).
  - **Hindi (`hi-IN`):** Uses Microsoft Edge Neural TTS with **MadhurNeural** (Host, male) and **SwaraNeural** (Co-Host, female).
  - **English (`en-US`):** Uses **GuyNeural** (Host) and **JennyNeural** (Co-Host).
- **Conversational Pacing:** A 250ms natural acoustic silence is inserted between dialogue turns via PyDub to simulate real-life studio banter rather than robotic overlap.
- **Volume & Loudness Normalization:** Output audio tracks are normalized to ~-16 dBFS to prevent sudden volume spikes or muffled audio.

---

## 8. Live Demonstration Checklist (Step-by-Step for Presentation)

1. **Open the Web Application:**
   - Open browser to: `http://127.0.0.1:5000/app`
   - Point out the clean dark-mode UI with sections: **Search & Discover News**, **Saved Episodes Library**, and **Podcast Audio Studio**.

2. **Demonstrate Saved Episodes & Multi-Lingual Tracks:**
   - Scroll to **Saved Episodes** and show **Episode #10** (Odisha / AI news).
   - Click the **Studio** button on the card.
   - Explain how the Audio Studio dynamically links the script, metadata, and audio tracks.

3. **Demonstrate Odia Audio Playback (Primary Wow Factor):**
   - In Audio Studio, click the **Odia (ଓଡ଼ିଆ)** quick selector pill (or use the language dropdown).
   - Show the dynamic track pill: `Track: ODIA (Ready)`.
   - Click **▶ Play** (or tap **[Spacebar]**):
     - *Point out:* The male Host (*Shubh*) introduces the episode in authentic Odia, followed by the female CoHost (*Kavya*).
     - *Point out:* The dynamic **Equalizer Waveform Visualizer** activates with real-time acoustic rhythm while playing.
   - Click **⏸ Pause** (or press **[Spacebar]**) — show that audio halts and waveform settles into subtle idle state.
   - Press **[←] / [→]** (or click Rewind/Forward) — show that audio seeks 15 seconds backward/forward.
   - Adjust the **Volume slider** or press **[M]** to demonstrate instant volume gain and mute toggle.

4. **Demonstrate Synchronized State & Multi-Language Tracks in Saved Episodes:**
   - Look at the Episode #10 card under **Saved Episodes** while playing in Studio.
   - Point out the **Available Tracks** chips: `🇬🇧 ENGLISH`, `🇮🇳 HINDI`, `🇮🇳 HINGLISH`, `🇮🇳 ODIA`.
   - Show that the card button has automatically synchronized to `⏸ Pause` with a glowing active border and `Selected in Studio` badge.
   - Click any language track chip (e.g. `🇮🇳 HINDI`) directly on the card to demonstrate instant track switching and synchronized playback.

5. **Demonstrate Language Switching (Hindi, English, Hinglish, Odia):**
   - Click the **Hindi (हिंदी)** quick selector pill: show instantaneous track loading and dual-speaker synthesis (*Madhur* and *Swara*).
   - Click the **English** pill: show standard studio dual-speaker synthesis (*Guy* and *Jenny*).
   - Click the **Hinglish** pill: show bilingual conversational synthesis.
   - Click the **Odia** pill: return to regional Odia synthesis (*Shubh* and *Kavya*).

6. **Demonstrate Verified News Attribution & Gemini Grounded Intelligence:**
   - Scroll up to **Discover News** and show verified publisher source attribution links with external icons.
   - Click **✨ AI Insights** on any episode to reveal factual grounding, key takeaways, entities, and source claim breakdown generated strictly by Google Gemini without hallucinations.

---

## 9. Key Technical Challenges Solved
1. **Odia TTS Provider Availability:** Standard browser speech synthesis and Edge TTS do not support Odia. Researched and cleanly integrated Sarvam AI Bulbul v3 with authenticated REST calls and base64 audio decoding.
2. **Audio Merging & Dual-Speaker Stitching:** Synthesizing separate audio chunks per dialogue turn required seamless stitching with consistent sample rates, channels, and realistic inter-speaker pauses.
3. **State Synchronization:** Kept the standalone Audio Studio player and the Saved Episodes list cards fully in sync without full page refreshes.
4. **Graceful Error Handling:** Handled missing API keys, rate limits, and network errors gracefully with clear user banners instead of silent failures or false successes.

---

## 10. Limitations & Future Scope

### Limitations
- Audio generation requires active Internet connectivity for Gemini and Sarvam AI APIs.
- First-time audio generation takes 15–30 seconds depending on API response latency.
- Current storage uses local filesystem and SQLite; enterprise scale would require cloud blob storage (AWS S3) and PostgreSQL.

### Future Scope
- **Automated RSS Feeds:** Publish generated episodes directly to Spotify, Apple Podcasts, and Google Podcasts via RSS 2.0 feeds.
- **Voice Cloning:** Allow users to upload a 30-second voice sample to clone their own voice as the Host.
- **More Regional Languages:** Add Bengali, Tamil, Telugu, and Marathi dual-speaker models.
- **Background Music & Sound Effects:** Add introductory jingles, transition whooshes, and ambient studio background music.

---

## 11. 15 Likely Viva Questions & Answers

### Q1: What is the core architecture of the Podcast Buddy project?
**Answer:** Podcast Buddy follows a client-server architecture. The backend is built in Python using Flask, which provides RESTful APIs for news retrieval, script generation, and audio synthesis. The database is SQLite for persisting episodes and metadata. The frontend is built in Vanilla HTML, CSS, and JavaScript with HTML5 Audio and custom waveform visualization.

### Q2: Why did you choose Flask instead of Django or FastAPI?
**Answer:** Flask is lightweight, flexible, and has minimal overhead. It allows direct control over routing, static asset serving, streaming binary audio responses, and integrating background AI pipelines without unnecessary boilerplate.

### Q3: How does the application search and fetch live news?
**Answer:** The frontend sends a search query to the Flask route `/api/news/search`. The backend uses SerpAPI to query Google News, parses the JSON response, validates fields (title, snippet, link, source, date), and returns a clean list of articles to the frontend.

### Q4: How is Google Gemini used in this project?
**Answer:** Gemini is used in two stages:
1. **Intelligence Analysis:** It analyzes selected news articles to extract unbiased key takeaways, topics, and perspective notes.
2. **Dialogue Scripting:** It drafts a natural two-speaker conversational script with a structured JSON format containing Introduction, Segments, Key Takeaways, and Outro with assigned speakers (Host and CoHost).

### Q5: How did you implement dual-speaker audio synthesis?
**Answer:** The podcast script separates lines between `Host` and `CoHost`. During audio generation, the backend iterates through each dialogue line, sends Host text to a male neural voice and CoHost text to a female neural voice, saves intermediate audio clips, and stitches them together with short natural pauses using PyDub.

### Q6: Why did you use Sarvam AI Bulbul v3 for Odia audio instead of Edge TTS?
**Answer:** Microsoft Edge TTS and standard web speech APIs currently do not have native high-quality neural voices for Odia (`od-IN`). Sarvam AI is specifically trained for Indic regional languages and provides natural, expressive Odia voices (`shubh` male and `kavya` female).

### Q7: What is the request/response format for the Sarvam Bulbul API?
**Answer:** It is an HTTP POST request to `https://api.sarvam.ai/text-to-speech` with the header `api-subscription-key`. The JSON payload contains `"inputs": [text]`, `"target_language_code": "od-IN"`, `"speaker": "shubh"` or `"kavya"`, and `"model": "bulbul:v3"`. The response returns base64-encoded WAV audio, which our service decodes into binary audio.

### Q8: How is Hindi and English TTS implemented?
**Answer:** Hindi and English use Microsoft Edge Neural TTS via Python's asynchronous `edge-tts` library. For Hindi, we use `hi-IN-MadhurNeural` (Host) and `hi-IN-SwaraNeural` (Co-Host). For English, we use `en-US-GuyNeural` and `en-US-JennyNeural`. This provides natural audio without API costs.

### Q9: How are individual audio clips merged into a final podcast episode?
**Answer:** We use the `pydub` library backed by `FFmpeg`. Each synthesized clip is loaded as an `AudioSegment`. We insert a 250ms silence segment between turns, concatenate all segments in order, normalize the final track volume, and export it as an MP3 file in the `generated_audio/` folder.

### Q10: How does audio streaming work between Flask and the browser?
**Answer:** When the user clicks play, the HTML5 audio element requests `GET /api/episodes/<id>/audio?lang=<language>`. Flask locates the generated MP3 file on disk and uses Flask's `send_file` helper with `mimetype="audio/mpeg"` to stream the audio directly to the browser.

### Q11: How is the database structured?
**Answer:** We use SQLite (`podcast_buddy.db`) with an `episodes` table containing columns for `id`, `title`, `description`, `category`, `podcast_script` (stored as JSON), `audio_path`, `audio_language`, `available_audio_languages` (stored as JSON array), `status`, and timestamps (`created_at`, `updated_at`).

### Q12: How do you handle errors during audio generation?
**Answer:** If an external API fails (e.g., quota exceeded or invalid key), the exception is caught in the backend service, logged, and returned as a structured JSON error response `{"success": false, "error": "..."}` with appropriate HTTP status codes. The frontend receives this and renders a prominent red error banner with actionable details instead of showing a false success.

### Q13: How did you test and verify the application?
**Answer:** We developed a test suite of **150 automated tests** in Python (`unittest`) covering models, routes, script generation, audio merging, and TTS providers. Additionally, we used a Chrome DevTools Protocol (CDP) automated browser script to test real browser UI interactions, play/pause state transitions, and waveform animations in Microsoft Edge.

### Q14: How are sensitive API keys secured in this project?
**Answer:** All API keys (`SARVAM_API_KEY`, `GEMINI_API_KEY`, `SERPAPI_API_KEY`) are stored exclusively in a server-side `.env` file that is excluded from version control via `.gitignore`. The frontend never receives or handles raw API credentials; all requests are proxied securely through local Flask endpoints.

### Q15: How does the waveform animation work on the frontend?
**Answer:** The waveform consists of CSS bars in the UI. When the HTML5 `<audio>` element fires the `'play'` or `'playing'` event, JavaScript adds the CSS class `.is-playing` to the waveform container, which activates keyframe animations simulating sound frequencies. When the `'pause'`, `'ended'`, or `'waiting'` event fires, the class is removed and the bars freeze.
