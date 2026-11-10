# Podcast Buddy — Live Demonstration Guide & Script

This document provides a step-by-step walkthrough for your live final-year B.Tech project presentation and viva evaluation. Follow these exact steps and speak the provided script in simple, confident English.

---

## 🎯 Pre-Demo Setup Checklist (Do This Before Starting)
1. **Start the Flask Server:** Open a terminal in the project directory and run:
   ```powershell
   .venv\Scripts\python.exe backend/app.py
   ```
2. **Open the Web Browser:** Navigate to `http://127.0.0.1:5000/app`.
3. **Verify Volume:** Make sure your laptop audio or speakers are turned on and set to a comfortable volume (around 70%).
4. **Browser Autoplay Note:** Browsers block audio from playing automatically without a user click. Always click the "Listen" or "Audio Studio" button directly to start audio.

---

## 🎬 Step-by-Step Live Demonstration Walkthrough

### Step 1: Project Introduction
- **On-Screen Action:** Keep the browser open on the top Hero section (`#hero`) of Podcast Buddy.
- **What to Say (Spoken Script):**
  > "Respected examiners, good morning. Today, I am proud to present my final-year project: **Podcast Buddy – AI-Powered Podcast and News Discovery Assistant**.
  >
  > In today's digital world, we face severe information overload. We have hundreds of text news articles published every minute, but commuters, visually impaired individuals, and busy professionals do not have the time to read them. Furthermore, existing text-to-speech tools only offer flat, robotic reading in English, completely neglecting Indian regional languages like Odia and Hindi.
  >
  > Podcast Buddy solves this by automatically transforming live verified news into engaging, dual-speaker conversational podcasts featuring a Host and a Co-Host. Today, I will demonstrate our complete end-to-end pipeline."

---

### Step 2: Show the Dashboard & Architecture Overview
- **On-Screen Action:** Scroll down slightly to show the **Core Demonstration Workflow** cards (5 steps) and highlight the key metrics badges.
- **What to Say (Spoken Script):**
  > "Here is our main dashboard. It follows a clean 5-stage automated pipeline:
  > 1. Discover live news via SerpAPI.
  > 2. Select and bundle verified stories.
  > 3. Synthesize source-grounded intelligence using Google Gemini.
  > 4. Draft a two-speaker dialogue script between Host and Co-Host.
  > 5. Generate neural conversational audio in Odia, Hindi, Hinglish, and English.
  >
  > Let us walk through each stage live."

---

### Step 3: Demonstrate News Discovery
- **On-Screen Action:** Scroll to **Step 1: Discover News** (`#news-discovery`). Click on the featured category chip **"🚀 Technology & AI"** or type `"Artificial Intelligence"` in the search input and click **"Discover News"**.
- **What to Say (Spoken Script):**
  > "In the News Discovery panel, our system queries the Google News index via SerpAPI. As you can see, we immediately get live, verified news stories with genuine publisher names, publication timestamps, and direct URLs to the original publisher.
  >
  > Unlike fake news aggregators, our system prevents hallucination right from the ingestion stage by enforcing publisher traceability. A user can select between 1 and 5 stories to curate a customized episode topic."

---

### Step 4: Explain Grounded AI Insights
- **On-Screen Action:** Scroll down to the **Saved Episodes Library** (`#episodes-library`). Find **Episode #9** or **Episode #8** and click the **"✨ Insights"** button. The Grounded AI Intelligence card (`#ai-intelligence-viewer`) will open.
- **What to Say (Spoken Script):**
  > "Now, let us examine our Grounded AI Intelligence Engine. When we curate news stories, Google Gemini analyzes the source text with strict negative prompting constraints.
  >
  > Notice what Gemini produces:
  > - An **Executive Overview** summarizing the core events.
  > - Verifiable **Key Takeaways** and **Important Facts**.
  > - Extracted **Named Entities** categorizing people, organizations, and technologies.
  > - And most importantly, our **Multi-Source Corroboration**: the system highlights facts confirmed by multiple publishers, points out unique claims, and neutrally flags conflicting reports.
  >
  > This ensures our podcasts are factually grounded and free from AI hallucinations."

---

### Step 5: Show the Generated Multi-Speaker Podcast Script
- **On-Screen Action:** Click the close button on the AI viewer, then click **"🎙️ Audio Studio"** on **Episode #10**. Scroll to the **Script Dialogue** section (`#script-dialogue-container`). Click the **"📋 Copy Script"** button and observe the visual `"✓ Copied!"` feedback.
- **What to Say (Spoken Script):**
  > "Next, our system translates the factual intelligence into a dynamic, multi-turn podcast script.
  >
  > As you can see on the screen, this is not a boring single-person monologue. We have structured conversational turns between a **Host** and a **Co-Host**. The Host introduces the theme and asks engaging questions, while the Co-Host provides deep analysis and takeaways.
  >
  > We also have a convenient **Copy Script** button with immediate clipboard feedback, allowing creators to export scripts for human review."

---

### Step 6: Demonstrate Multilingual Audio (The Showcase Demonstration)
- **On-Screen Action:** In the **Audio Studio**, look at the language selector. Note that **Episode #10** has pre-generated neural audio across all 4 languages.
  1. Click the **Odia (ଓଡ଼ିଆ)** language pill. Click the green **"▶ Listen"** or the main circular **Play** button. Let it play for 6 to 8 seconds so examiners hear the native Odia voices.
  2. Switch to **Hindi (हिंदी)**. Let it play for 5 seconds so examiners hear *Madhur* and *Swara*.
  3. Switch to **English**. Let it play for 5 seconds so examiners hear the dual British and Indian accents.
- **What to Say (Spoken Script):**
  > "Now, I would like to demonstrate the crowning achievement of our project: **Regional Multilingual Neural Audio Synthesis**.
  >
  > Most existing platforms completely ignore Indian regional languages. In Podcast Buddy, we integrated **Sarvam AI Bulbul v3** to produce authentic, native **Odia** speech.
  >
  > Let us listen to Episode 10 in Odia. *(Play Odia audio for 6 seconds)*. Notice the clear Odia pronunciation and how the male host *Shubh* and female co-host *Kavya* alternate with natural 250-millisecond pauses.
  >
  > Now, let us switch seamlessly to Hindi. *(Play Hindi audio for 5 seconds)*. Here, we use Microsoft Edge Neural TTS with *Madhur* and *Swara*.
  >
  > We also support **Hinglish** and **English**, giving users complete linguistic freedom."

---

### Step 7: Demonstrate Audio Studio Controls & Playback Speeds
- **On-Screen Action:** While the audio is playing:
  1. Press the **Spacebar** on your keyboard to pause. Press **Spacebar** again to resume.
  2. Click the **Forward 15s** button or press the **Right Arrow** key.
  3. Adjust the **Volume Slider** or press the **M key** to mute and unmute.
  4. Point to the **Playback Speed Selector** (`#player-speed-selector`). Click **`1.25x`**, then **`1.5x`**, and observe the speed increase.
  5. Switch the language track to English while at `1.25x` and show that the speed remains preserved.
  6. Point to the animated **Waveform visualizer** pulsing in real time.
  7. Click the **"⬇️ Download MP3"** button to show that the episode can be saved locally.
- **What to Say (Spoken Script):**
  > "Our Audio Studio is fully interactive and engineered for optimal user experience:
  > - We have full **Keyboard Accessibility**: pressing the Spacebar pauses and resumes instantly, and arrow keys seek backward and forward by 15 seconds.
  > - Our **Dynamic Acoustic Waveform** visualizer pulses in real time based on active playback.
  > - We have dedicated **Playback Speed Controls**: users can select 0.75x, 1.0x, 1.25x, or 1.5x. Crucially, if I switch language tracks, our state hook strictly preserves the selected speed.
  > - Users can also download the standalone MP3 file with a single click."

---

### Step 8: Show Saved Episodes, Live Search & Filters
- **On-Screen Action:** Scroll down to the **Saved Podcast Episodes** section (`#episodes-library`).
  1. Click into the search bar (`#episodes-search-input`) and type `"Quantum"`. Show that the list instantly filters down to the 3 matching Quantum episodes, and the summary text updates.
  2. In the **Language** filter dropdown, select **Odia**. Show that it isolates only episodes containing Odia audio tracks.
  3. Type random gibberish like `"XYZ999"` to demonstrate the friendly **No-Results Message** and click the **"Clear All Filters"** button to restore all 11 saved episodes.
- **What to Say (Spoken Script):**
  > "Finally, let us look at our persistent storage and library management.
  >
  > All episodes, scripts, and audio tracks are saved locally in our SQLite database. To help users navigate large episode libraries, we engineered an instant **Search and Filter Engine**:
  > - If I search for `'Quantum'`, the cards filter instantaneously.
  > - I can filter by language, such as showing only episodes with Odia audio.
  > - If a search has no matches, the system displays a friendly empty state with an instant reset button.
  > - And when an episode is deleted, our backend safely cleans up only its associated audio files from disk while preserving all other episode assets."

---

### Step 9: Conclude the Demonstration
- **On-Screen Action:** Scroll back to the system architecture section or leave the Audio Studio visible. Look up confidently at the examiners.
- **What to Say (Spoken Script):**
  > "To conclude: Podcast Buddy transforms static, fragmented news into an engaging, multi-speaker conversational podcast in under a minute. By combining SerpAPI for credible news, Google Gemini for grounded intelligence, Sarvam AI and Microsoft Edge TTS for regional linguistic diversity, and an accessible web studio, we have built a complete, production-ready AI product.
  >
  > All test suites—including real-browser Chrome DevTools Protocol automation and backend unit tests—have achieved 100% pass rates with zero console errors.
  >
  > Thank you for your time. I am now ready for your questions."

---

## 💡 Examiner Demonstration Pro Tips
1. **Always Use Episode #10 for Audio:** Episode #10 already has pre-synthesized audio in all 4 languages stored safely in your local `generated_audio/` folder. This guarantees 100% reliability, instant playback, zero network lag, and zero external API quota consumption during your viva!
2. **If Examiner asks you to generate live audio:** Explain:
   > *"Sir/Ma'am, our live generation pipeline is fully functional and demonstrated in our test suite. In live environments, generating a full dual-speaker audio track takes approximately 20 to 30 seconds to call the neural TTS APIs, concatenate the audio, and normalize loudness. To respect your time during this presentation, I have pre-generated Episode #10 so you can immediately inspect the audio quality."*
3. **If Keyboard Hotkeys don't fire:** Ensure your mouse focus is on the page body and not inside a text input box. The system intentionally disables hotkeys inside inputs to prevent accidental triggers while typing search queries.

