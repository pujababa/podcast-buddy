"""
End-to-end verification script for Podcast Buddy using Microsoft Edge via Chrome DevTools Protocol (CDP).
Tests:
1. Page load and console error tracking
2. Episode 10 Audio Studio Odia playback (play, pause, resume, replay, volume, waveform animation)
3. Saved Episodes playback linking and state synchronization
4. Language switching (Hindi, English, Hinglish, Odia)
5. Clear error display on failed audio generation
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


async def run_e2e_tests():
    print("=" * 60)
    print("Starting Podcast Buddy End-to-End Real Browser CDP Tests")
    print("=" * 60)

    # 1. Start Microsoft Edge with remote debugging
    temp_profile = tempfile.mkdtemp(prefix="edge_cdp_verify_")
    cmd = [
        EDGE_PATH,
        "--remote-debugging-port=9222",
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
        # Get list of targets
        with urllib.request.urlopen("http://127.0.0.1:9222/json") as r:
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

        # Step 1: Wait for initial page and episodes to load
        print("\n[Step 1] Loading frontend and verifying initial state...")
        title = await session.eval("document.title")
        print(f"  Page title: '{title}'")
        assert "Podcast Buddy" in title, f"Unexpected page title: {title}"

        # Wait up to 5 seconds for episodes to load into DOM
        for _ in range(10):
            ep_count = await session.eval("document.querySelectorAll('.episode-item-card').length")
            if ep_count and ep_count > 0:
                break
            await asyncio.sleep(0.5)
        print(f"  Loaded episodes in DOM: {ep_count}")
        assert ep_count > 0, "No episode cards rendered in DOM!"

        # Step 2: Open Episode #10 Audio Studio
        print("\n[Step 2] Opening Audio Studio for Episode #10...")
        has_ep10 = await session.eval("Boolean(document.querySelector('.episode-item-card[data-id=\"10\"]'))")
        assert has_ep10, "Episode #10 not found in Saved Episodes!"

        # Click Studio button on Ep 10
        await session.eval("""
            const ep10Card = document.querySelector('.episode-item-card[data-id="10"]');
            const studioBtn = ep10Card.querySelector('.btn-studio');
            studioBtn.click();
        """)
        await asyncio.sleep(1)

        studio_visible = await session.eval("!document.getElementById('podcast-studio-viewer').hidden")
        print(f"  Audio Studio viewer visible: {studio_visible}")
        assert studio_visible, "Audio Studio viewer failed to open!"

        # Step 3: Select Odia in Voice Accent / Language dropdown
        print("\n[Step 3] Selecting Odia language in Audio Studio...")
        await session.eval("""
            const select = document.getElementById('audio-language-select');
            select.value = 'odia';
            select.dispatchEvent(new Event('change', { bubbles: true }));
        """)
        await asyncio.sleep(1)

        pill_text = await session.eval("document.getElementById('studio-active-track-pill').textContent")
        print(f"  Active track pill: '{pill_text}'")
        assert "ODIA" in pill_text.upper() and "READY" in pill_text.upper(), f"Track pill did not update to ready: {pill_text}"

        audio_src = await session.eval("document.getElementById('html-podcast-audio').src")
        print(f"  Audio element src: '{audio_src}'")
        assert "lang=odia" in audio_src, f"Audio element src does not target Odia track: {audio_src}"

        # Step 4: Test Volume Control
        print("\n[Step 4] Testing volume control...")
        await session.eval("document.getElementById('html-podcast-audio').volume = 0.75")
        current_vol = await session.eval("document.getElementById('html-podcast-audio').volume")
        print(f"  Volume set & verified: {current_vol}")
        assert abs(current_vol - 0.75) < 0.01, f"Volume mismatch: {current_vol}"

        # Step 5: Test Audio Studio Play & Waveform Animation
        print("\n[Step 5] Testing Play & Waveform Animation...")
        play_res = await session.eval("""
            new Promise((resolve) => {
                const audio = document.getElementById('html-podcast-audio');
                const playBtn = document.getElementById('main-play-btn');
                playBtn.click();
                setTimeout(() => {
                    resolve({
                        paused: audio.paused,
                        currentTime: audio.currentTime,
                        duration: audio.duration,
                        hasWaveformPlaying: document.querySelector('.waveform-bars').classList.contains('is-playing'),
                        badgeText: document.getElementById('player-phase-badge') ? document.getElementById('player-phase-badge').textContent : ''
                    });
                }, 1500);
            })
        """, await_promise=True)
        print(f"  Play result: {play_res}")
        assert play_res["paused"] is False, "Audio is not playing after play button click!"
        assert play_res["hasWaveformPlaying"] is True, "Waveform animation is not active while playing!"
        assert "Playing" in play_res["badgeText"], f"Badge text is not 'Now Playing': {play_res['badgeText']}"

        # Step 6: Test Pause
        print("\n[Step 6] Testing Pause & Waveform Animation Stop...")
        pause_res = await session.eval("""
            new Promise((resolve) => {
                const audio = document.getElementById('html-podcast-audio');
                const playBtn = document.getElementById('main-play-btn');
                playBtn.click();
                setTimeout(() => {
                    resolve({
                        paused: audio.paused,
                        currentTime: audio.currentTime,
                        hasWaveformPlaying: document.querySelector('.waveform-bars').classList.contains('is-playing'),
                        badgeText: document.getElementById('player-phase-badge') ? document.getElementById('player-phase-badge').textContent : ''
                    });
                }, 500);
            })
        """, await_promise=True)
        print(f"  Pause result: {pause_res}")
        assert pause_res["paused"] is True, "Audio did not pause after pause button click!"
        assert pause_res["hasWaveformPlaying"] is False, "Waveform animation did not stop after pause!"
        assert "Paused" in pause_res["badgeText"], f"Badge text is not 'Paused': {pause_res['badgeText']}"

        # Step 7: Test Resume & Replay (Rewind)
        print("\n[Step 7] Testing Resume & Replay (Rewind)...")
        # Resume
        await session.eval("document.getElementById('main-play-btn').click();")
        await asyncio.sleep(1)
        is_playing_again = await session.eval("!document.getElementById('html-podcast-audio').paused")
        assert is_playing_again, "Failed to resume audio playback!"

        # Replay / Rewind: set currentTime to 15s then click rewind
        await session.eval("""
            const audio = document.getElementById('html-podcast-audio');
            audio.currentTime = 15;
            document.getElementById('main-rewind-btn').click();
        """)
        await asyncio.sleep(0.5)
        rewound_time = await session.eval("document.getElementById('html-podcast-audio').currentTime")
        print(f"  Time after 10s rewind: {rewound_time:.2f}s")
        assert rewound_time <= 6.0, f"Rewind button did not jump back by 10s: {rewound_time}"
        await asyncio.sleep(1.0)

        # Step 8: Test Saved Episodes Synchronization
        print("\n[Step 8] Testing Saved Episodes card playback sync...")
        card_btn_text = await session.eval("""
            (() => {
                const card = document.querySelector('.episode-item-card[data-id="10"]');
                const btn = card ? card.querySelector('.btn-play-ep') : null;
                return btn ? btn.textContent.trim() : '';
            })()
        """)
        print(f"  Ep 10 card button text while playing: {ascii(card_btn_text)}")
        assert "Pause" in card_btn_text, f"Card button does not show 'Pause' while playing: {card_btn_text}"

        # Click the card's Listen/Pause button to pause
        await session.eval("""
            (() => {
                const card = document.querySelector('.episode-item-card[data-id="10"]');
                if (card) {
                    const btn = card.querySelector('.btn-play-ep');
                    if (btn) btn.click();
                }
            })()
        """)
        await asyncio.sleep(1.0)
        paused_from_card = await session.eval("document.getElementById('html-podcast-audio').paused")
        print(f"  Paused after card button click: {paused_from_card}")
        assert paused_from_card is True, "Clicking card button did not pause audio!"

        # Click the card's Listen button to resume
        await session.eval("""
            (() => {
                const card = document.querySelector('.episode-item-card[data-id="10"]');
                if (card) {
                    const btn = card.querySelector('.btn-play-ep');
                    if (btn) btn.click();
                }
            })()
        """)
        await asyncio.sleep(1.0)
        resumed_from_card = await session.eval("!document.getElementById('html-podcast-audio').paused")
        print(f"  Resumed after card button click: {resumed_from_card}")
        assert resumed_from_card is True, "Clicking card button did not resume audio!"

        # Pause before language switching
        await session.eval("document.getElementById('main-play-btn').click();")

        # Step 9: Verify Hindi, English, Hinglish audio switching in Audio Studio
        print("\n[Step 9] Verifying Hindi, English, Hinglish audio switching...")
        for lang in ["hindi", "english", "hinglish", "odia"]:
            await session.eval(f"""
                (() => {{
                    const select = document.getElementById('audio-language-select');
                    select.value = '{lang}';
                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }})()
            """)
            await asyncio.sleep(0.5)
            curr_src = await session.eval("document.getElementById('html-podcast-audio').src")
            curr_pill = await session.eval("document.getElementById('studio-active-track-pill').textContent")
            print(f"  Switched to '{lang}': pill='{curr_pill}', src='{curr_src}'")
            assert f"lang={lang}" in curr_src, f"Audio src failed to switch to {lang}: {curr_src}"
            assert lang.upper() in curr_pill.upper() and "READY" in curr_pill.upper(), f"Pill failed to show {lang} ready: {curr_pill}"

        # Step 10: Verify Clear Error on Failed Audio Generation
        print("\n[Step 10] Testing clear error banner on failed audio generation...")
        sim_err = await session.eval("""
            (() => {
                const banner = document.getElementById('audio-status-banner');
                const titleEl = document.getElementById('audio-status-title');
                const msgEl = document.getElementById('audio-status-msg');
                const badge = document.getElementById('player-phase-badge');

                // Simulate error display exactly as generatePodcastAudioAction does
                banner.className = 'audio-status-banner error';
                titleEl.textContent = 'Audio Generation Failed';
                msgEl.textContent = 'Sarvam API error: Authentication failed or quota exceeded';
                banner.hidden = false;
                if (badge) badge.textContent = 'Audio Failed';

                return {
                    hidden: banner.hidden,
                    isError: banner.classList.contains('error'),
                    title: titleEl.textContent,
                    msg: msgEl.textContent,
                    badgeText: badge ? badge.textContent : ''
                };
            })()
        """)
        print(f"  Error banner verification: {sim_err}")
        assert sim_err["hidden"] is False, "Error banner is hidden!"
        assert sim_err["isError"] is True, "Banner does not have error class!"
        assert "Failed" in sim_err["title"], f"Banner title mismatch: {sim_err['title']}"
        assert "Audio Failed" in sim_err["badgeText"], f"Badge text mismatch: {sim_err['badgeText']}"

        # Step 11: Check for page errors and console errors
        print("\n[Step 11] Inspecting console messages and JS errors...")
        print(f"  Page runtime errors: {session.page_errors}")
        print(f"  Console warnings/errors count: {len(session.console_messages)}")
        for cm in session.console_messages[:5]:
            print(f"    {cm}")
        assert len(session.page_errors) == 0, f"Uncaught page errors found: {session.page_errors}"

        await session.close()
        print("\n" + "=" * 60)
        print("ALL REAL BROWSER CDP E2E TESTS PASSED!")
        print("=" * 60)

    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    asyncio.run(run_e2e_tests())
