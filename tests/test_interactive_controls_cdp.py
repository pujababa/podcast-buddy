"""
Interactive controls, keyboard accessibility, and UI verification script
using Microsoft Edge via Chrome DevTools Protocol (CDP).
"""
import asyncio
import json
import os
import subprocess
import tempfile
import time
import urllib.request
import websockets

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
APP_URL = "http://127.0.0.1:5000/app"


class CDPSession:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self._msg_id = 0
        self.console_messages = []
        self.page_errors = []

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=10 * 1024 * 1024)
        asyncio.create_task(self._listen())
        await self.send("Runtime.enable")
        await self.send("Log.enable")

    async def _listen(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                method = msg.get("method", "")
                if method == "Log.entryAdded":
                    entry = msg.get("params", {}).get("entry", {})
                    level = entry.get("level")
                    text = entry.get("text", "")
                    if level in ("error", "warning"):
                        self.console_messages.append(f"[{level.upper()}] {text}")
                elif method == "Runtime.exceptionThrown":
                    exc_details = msg.get("params", {}).get("exceptionDetails", {})
                    self.page_errors.append(str(exc_details.get("text") or exc_details.get("exception", {}).get("description")))
        except Exception:
            pass

    async def send(self, method, params=None):
        self._msg_id += 1
        req_id = self._msg_id
        payload = {"id": req_id, "method": method}
        if params:
            payload["params"] = params
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await self.ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == req_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})

    async def eval(self, expression, await_promise=False):
        res = await self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise
            }
        )
        return res.get("result", {}).get("value")

    async def close(self):
        if self.ws:
            await self.ws.close()


async def verify_interactive_demo_flow():
    print("=" * 65)
    print("PODCAST BUDDY — PRE-PRESENTATION INTERACTIVE & DEMO VERIFICATION")
    print("=" * 65)

    temp_profile = tempfile.mkdtemp(prefix="edge_cdp_prepress_")
    cmd = [
        EDGE_PATH,
        "--remote-debugging-port=9223",
        "--headless=new",
        f"--user-data-dir={temp_profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--autoplay-policy=no-user-gesture-required",
        APP_URL
    ]
    proc = subprocess.Popen(cmd)
    time.sleep(2.5)

    try:
        with urllib.request.urlopen("http://127.0.0.1:9223/json") as r:
            targets = json.loads(r.read().decode())
        
        app_target = None
        for t in targets:
            if "http://127.0.0.1:5000/app" in t.get("url", ""):
                app_target = t
                break
        
        assert app_target is not None, "Failed to find Podcast Buddy tab in Edge!"
        ws_url = app_target["webSocketDebuggerUrl"]

        session = CDPSession(ws_url)
        await session.connect()

        # Step 1: Open app & verify layout
        print("\n[Step 1] Verifying frontend load and sections...")
        title = await session.eval("document.title")
        print(f"  Title: '{title}'")
        assert "Podcast Buddy" in title

        has_hero = await session.eval("Boolean(document.querySelector('.hero-section'))")
        has_studio = await session.eval("Boolean(document.querySelector('.podcast-section'))")
        has_episodes = await session.eval("Boolean(document.querySelector('.library-section'))")
        has_about = await session.eval("Boolean(document.querySelector('.about-section'))")
        assert has_hero and has_studio and has_episodes and has_about, "Core sections missing!"
        print("  All core sections verified (Hero, Studio, Saved Episodes, Architecture).")

        # Step 2: Select Episode 10 Odia
        print("\n[Step 2] Selecting Episode #10 and verifying Odia audio track...")
        for _ in range(10):
            ep_count = await session.eval("document.querySelectorAll('.episode-item-card').length")
            if ep_count and ep_count > 0:
                break
            await asyncio.sleep(0.5)

        # Click Studio on Ep 10
        await session.eval("""
            const ep10 = document.querySelector('.episode-item-card[data-id="10"]');
            if (ep10) ep10.querySelector('.btn-studio').click();
        """)
        await asyncio.sleep(1)

        # Switch to Odia via pill
        await session.eval("""
            const odiaPill = document.querySelector('.lang-pill-btn[data-lang="odia"]');
            if (odiaPill) odiaPill.click();
        """)
        await asyncio.sleep(1)

        odia_src = await session.eval("document.getElementById('html-podcast-audio').src")
        odia_pill_text = await session.eval("document.getElementById('studio-active-track-pill').textContent")
        print(f"  Odia Audio src: '{odia_src}'")
        print(f"  Track Pill: '{odia_pill_text}'")
        assert "lang=odia" in odia_src
        assert "ODIA" in odia_pill_text.upper() and "READY" in odia_pill_text.upper()

        # Step 3: Test Play / Pause via Click & Spacebar
        print("\n[Step 3] Testing Play / Pause, Waveform Animation & Spacebar shortcut...")
        # 3a: Click play
        await session.eval("document.getElementById('main-play-btn').click()")
        play_state = None
        for _ in range(20):
            play_state = await session.eval("""({
                paused: document.getElementById('html-podcast-audio').paused,
                currentTime: document.getElementById('html-podcast-audio').currentTime,
                waveformPlaying: document.querySelector('.waveform-bars').classList.contains('is-playing'),
                badge: document.getElementById('player-phase-badge').textContent
            })""")
            if play_state and play_state["paused"] is False and play_state["currentTime"] > 0:
                break
            await asyncio.sleep(0.2)

        print(f"  After Click Play: {play_state}")
        assert play_state["paused"] is False, "Audio should be playing!"
        assert play_state["waveformPlaying"] is True, "Waveform should have is-playing class!"

        # 3b: Spacebar pause
        await session.eval("""
            window.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', code: 'Space', bubbles: true }));
        """)
        pause_state = None
        for _ in range(15):
            pause_state = await session.eval("""({
                paused: document.getElementById('html-podcast-audio').paused,
                waveformPlaying: document.querySelector('.waveform-bars').classList.contains('is-playing'),
                badge: document.getElementById('player-phase-badge').textContent
            })""")
            if pause_state and pause_state["paused"] is True:
                break
            await asyncio.sleep(0.2)

        print(f"  After Spacebar Pause: {pause_state}")
        assert pause_state["paused"] is True, "Audio should be paused via Spacebar!"
        assert pause_state["waveformPlaying"] is False, "Waveform should not have is-playing class when paused!"

        # 3c: Spacebar resume
        await session.eval("""
            window.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', code: 'Space', bubbles: true }));
        """)
        resume_state = False
        for _ in range(15):
            resume_state = await session.eval("!document.getElementById('html-podcast-audio').paused")
            if resume_state is True:
                break
            await asyncio.sleep(0.2)

        print(f"  After Spacebar Resume: playing={resume_state}")
        assert resume_state is True, "Audio should resume playing via Spacebar!"

        # Step 4: Test Seeking with Arrow Keys
        print("\n[Step 4] Testing Left/Right Arrow Seeking...")
        cur_t = await session.eval("document.getElementById('html-podcast-audio').currentTime")
        # Seek +15s with ArrowRight
        await session.eval("""
            window.dispatchEvent(new KeyboardEvent('keydown', { code: 'ArrowRight', bubbles: true }));
        """)
        await asyncio.sleep(0.5)
        new_t = await session.eval("document.getElementById('html-podcast-audio').currentTime")
        print(f"  Seek +15s: before={cur_t:.2f}s, after={new_t:.2f}s")
        assert new_t > cur_t + 10, "ArrowRight should advance audio position by ~15s!"

        # Seek -15s with ArrowLeft
        await session.eval("""
            window.dispatchEvent(new KeyboardEvent('keydown', { code: 'ArrowLeft', bubbles: true }));
        """)
        await asyncio.sleep(0.5)
        rewound_t = await session.eval("document.getElementById('html-podcast-audio').currentTime")
        print(f"  Seek -15s: after rewind={rewound_t:.2f}s")
        assert rewound_t < new_t - 5, "ArrowLeft should rewind audio position by ~15s!"

        # Step 5: Test Volume Slider and Mute key 'M'
        print("\n[Step 5] Testing Volume Slider and Mute Toggle (M key)...")
        # Slider input
        await session.eval("""
            const slider = document.getElementById('main-volume-slider');
            slider.value = 0.6;
            slider.dispatchEvent(new Event('input', { bubbles: true }));
        """)
        vol_60 = await session.eval("document.getElementById('html-podcast-audio').volume")
        print(f"  Slider set to 0.6: audio.volume={vol_60:.2f}")
        assert abs(vol_60 - 0.6) < 0.01

        # Press 'M' to mute
        await session.eval("""
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'm', code: 'KeyM', bubbles: true }));
        """)
        await asyncio.sleep(0.4)
        vol_muted = await session.eval("document.getElementById('html-podcast-audio').volume")
        icon_muted = await session.eval("document.getElementById('volume-icon-muted').style.display !== 'none'")
        print(f"  Press 'M': audio.volume={vol_muted}, icon_muted_visible={icon_muted}")
        assert vol_muted == 0.0 and icon_muted is True, "Audio should be muted and muted icon visible!"

        # Press 'M' to unmute
        await session.eval("""
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'm', code: 'KeyM', bubbles: true }));
        """)
        await asyncio.sleep(0.4)
        vol_unmuted = await session.eval("document.getElementById('html-podcast-audio').volume")
        print(f"  Press 'M' again: audio.volume={vol_unmuted:.2f}")
        assert abs(vol_unmuted - 0.6) < 0.01, "Audio volume should restore previous value!"

        # Step 6: Verify keyboard shortcuts are blocked when typing in inputs/textareas
        print("\n[Step 6] Verifying keyboard shortcuts do NOT trigger while typing in inputs...")
        # Focus on search input
        await session.eval("""
            const searchIn = document.getElementById('search-input');
            searchIn.focus();
        """)
        is_playing_before = await session.eval("!document.getElementById('html-podcast-audio').paused")
        # Dispatch spacebar on focused input
        await session.eval("""
            const searchIn = document.getElementById('search-input');
            searchIn.dispatchEvent(new KeyboardEvent('keydown', { code: 'Space', bubbles: true }));
        """)
        await asyncio.sleep(0.5)
        is_playing_after_space = await session.eval("!document.getElementById('html-podcast-audio').paused")
        print(f"  Typing Space in search input: playing before={is_playing_before}, playing after={is_playing_after_space}")
        assert is_playing_before == is_playing_after_space, "Spacebar inside input must NOT toggle playback!"

        # Dispatch 'm' on focused input
        await session.eval("""
            const searchIn = document.getElementById('search-input');
            searchIn.dispatchEvent(new KeyboardEvent('keydown', { key: 'm', code: 'KeyM', bubbles: true }));
        """)
        await asyncio.sleep(0.4)
        vol_after_m_typing = await session.eval("document.getElementById('html-podcast-audio').volume")
        print(f"  Typing 'm' in search input: volume={vol_after_m_typing:.2f}")
        assert vol_after_m_typing > 0, "Pressing 'm' inside input must NOT mute audio!"

        # Step 7: Language Controls: Hindi and English
        print("\n[Step 7] Testing Hindi & English Language switching in Audio Studio...")
        # Hindi
        await session.eval("document.querySelector('.lang-pill-btn[data-lang=\"hindi\"]').click()")
        await asyncio.sleep(0.8)
        hi_src = await session.eval("document.getElementById('html-podcast-audio').src")
        hi_pill = await session.eval("document.getElementById('studio-active-track-pill').textContent")
        print(f"  Hindi track: src='{hi_src}', pill='{hi_pill}'")
        assert "lang=hindi" in hi_src and "HINDI" in hi_pill.upper()

        # English
        await session.eval("document.querySelector('.lang-pill-btn[data-lang=\"english\"]').click()")
        await asyncio.sleep(0.8)
        en_src = await session.eval("document.getElementById('html-podcast-audio').src")
        en_pill = await session.eval("document.getElementById('studio-active-track-pill').textContent")
        print(f"  English track: src='{en_src}', pill='{en_pill}'")
        assert "lang=english" in en_src and "ENGLISH" in en_pill.upper()

        # Step 7b: Phase 1 Enhancements Verification (Download MP3, Copy Script, Duration Pills)
        print("\n[Step 7b] Verifying Phase 1 Enhancements (Download MP3, Copy Script, Track Durations)...")
        has_dl_btn = await session.eval("Boolean(document.getElementById('btn-download-audio'))")
        dl_disabled = await session.eval("Boolean(document.getElementById('btn-download-audio').disabled)")
        print(f"  Download MP3 button: exists={has_dl_btn}, disabled={dl_disabled}")
        assert has_dl_btn is True and dl_disabled is False, "Download MP3 button must exist and be enabled for ready track!"

        has_copy_btn = await session.eval("Boolean(document.getElementById('btn-copy-script'))")
        copy_disabled = await session.eval("Boolean(document.getElementById('btn-copy-script').disabled)")
        print(f"  Copy Script button: exists={has_copy_btn}, disabled={copy_disabled}")
        assert has_copy_btn is True and copy_disabled is False, "Copy Script button must exist and be enabled when script is ready!"

        # Trigger Copy Script click
        await session.eval("document.getElementById('btn-copy-script').click()")
        copy_btn_feedback = ""
        for _ in range(15):
            copy_btn_feedback = await session.eval("document.getElementById('btn-copy-script-text').textContent")
            if "Copied" in copy_btn_feedback:
                break
            await asyncio.sleep(0.1)
        print(f"  Copy Script feedback text: '{copy_btn_feedback}'")
        assert "Copied" in copy_btn_feedback, "Copy Script button must display 'Copied!' feedback!"

        # Verify Duration Pills in Saved Episodes
        duration_pills = await session.eval("""
            Array.from(document.querySelectorAll('.episode-duration-pill')).map(p => p.textContent.trim())
        """)
        print(f"  Saved Episodes Duration Pills: count={len(duration_pills)}, samples={duration_pills[:3]}")
        assert len(duration_pills) > 0, "Episode cards with ready audio must display duration pills!"
        assert any(":" in dp for dp in duration_pills), "Duration pill must be formatted with MM:SS!"

        # Step 8: Insights & Architecture section verification
        print("\n[Step 8] Verifying Insights & Architecture content...")
        card_debug = await session.eval("""
            Array.from(document.querySelectorAll('.episode-item-card')).map(c => ({
                id: c.getAttribute('data-id'),
                buttons: Array.from(c.querySelectorAll('button')).map(b => b.className)
            }))
        """)
        print(f"  Cards in DOM at Step 8: {card_debug}")

        # Find an episode with ready AI Insights button (.btn-view-ai)
        clicked_data = await session.eval("""
            (() => {
                const btn = document.querySelector('.btn-view-ai');
                if (!btn) return null;
                const card = btn.closest('.episode-item-card');
                const epId = card ? card.getAttribute('data-id') : btn.getAttribute('data-id');
                btn.click();
                return {
                    epId: epId,
                    title: card ? card.querySelector('.episode-card-title, .episode-item-title').textContent.trim() : ''
                };
            })()
        """)
        assert clicked_data is not None, "Failed to find any episode card with .btn-view-ai!"
        print(f"  Clicked AI Insights button for Episode #{clicked_data['epId']}: '{clicked_data['title'][:40]}...'")

        # Wait up to 3s for viewer to become visible and populated with real data
        ai_viewer_visible = False
        ai_overview = ""
        for _ in range(15):
            ai_viewer_visible = await session.eval("!document.getElementById('ai-intelligence-viewer').hidden")
            ai_overview = await session.eval("document.getElementById('ai-overview-text').textContent.trim()")
            if ai_viewer_visible and len(ai_overview) > 10 and ai_overview != "...":
                break
            await asyncio.sleep(0.2)

        ai_title = await session.eval("document.getElementById('ai-viewer-title').textContent")
        print(f"  AI Insights Viewer open: {ai_viewer_visible}")
        print(f"  AI Title: '{ai_title}'")
        print(f"  AI Overview sample ({len(ai_overview)} chars): '{ai_overview[:80]}...'")
        assert ai_viewer_visible is True, "AI Insights Viewer must be visible after clicking Insights button!"
        assert len(ai_overview) > 20, f"AI overview must contain real content, got: '{ai_overview}'"
        assert ai_overview != "...", "Placeholder '...' is not valid overview content!"

        # Architecture section
        arch_chips = await session.eval("""
            Array.from(document.querySelectorAll('.about-tech-stack .tech-chip')).map(c => c.textContent)
        """)
        print(f"  Architecture Tech Chips: {arch_chips}")
        assert any("Sarvam" in c for c in arch_chips)
        assert any("Edge" in c for c in arch_chips)
        assert any("Gemini" in c for c in arch_chips)
        assert any("Flask" in c for c in arch_chips)

        # Step 9: Inspect Console Errors
        print("\n[Step 9] Inspecting Console Logs and Errors...")
        print(f"  Page Runtime Errors: {session.page_errors}")
        print(f"  Console Messages: {session.console_messages}")
        assert len(session.page_errors) == 0, f"Found page runtime errors: {session.page_errors}"

        print("\n" + "=" * 65)
        print("ALL INTERACTIVE CONTROLS AND DEMO FLOW CHECKS PASSED!")
        print("=" * 65)

    finally:
        await session.close()
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    asyncio.run(verify_interactive_demo_flow())
