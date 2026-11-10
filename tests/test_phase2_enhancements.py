"""
Phase 2 Enhancements Automated Verification Script via Chrome DevTools Protocol (CDP).
Tests:
  - Feature 2.1: Audio Playback Speed (0.75x, 1.0x, 1.25x, 1.5x, speed preservation across track changes, waveform sync)
  - Feature 2.2: Search and Filter Saved Episodes (title search, language filter, status filter, clear filters, friendly empty state)
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


async def run_phase2_tests():
    print("=" * 65)
    print("PODCAST BUDDY — PHASE 2 ENHANCEMENTS VERIFICATION (CDP)")
    print("=" * 65)

    temp_profile = tempfile.mkdtemp(prefix="edge_cdp_phase2_")
    cmd = [
        EDGE_PATH,
        "--remote-debugging-port=9224",
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
        with urllib.request.urlopen("http://127.0.0.1:9224/json") as r:
            targets = json.loads(r.read().decode())
        
        app_target = None
        for t in targets:
            if "http://127.0.0.1:5000/app" in t.get("url", ""):
                app_target = t
                break
        
        assert app_target is not None, "Failed to find Podcast Buddy tab in Edge!"
        ws_url = app_target["webSocketDebuggerUrl"]
        cdp = CDPSession(ws_url)
        await cdp.connect()

        # Wait for page to initialize and episodes to load
        for _ in range(30):
            ready = await cdp.eval("document.readyState === 'complete' && document.querySelectorAll('.episode-item-card').length > 0")
            if ready:
                break
            time.sleep(0.3)

        initial_count = await cdp.eval("document.querySelectorAll('.episode-item-card').length")
        print(f"\n[Step 1] Initial Page Load: {initial_count} saved episodes in DOM.")
        assert initial_count > 0, "No episode cards rendered on initial load!"

        # -----------------------------------------------------------------
        # FEATURE 2.1: AUDIO PLAYBACK SPEED CONTROLS
        # -----------------------------------------------------------------
        print("\n[Step 2] Testing Playback Speed Controls existence and defaults...")
        speed_info = await cdp.eval("""
            (() => {
                const selector = document.getElementById("player-speed-selector");
                const mainBtn = document.getElementById("main-speed-btn");
                const buttons = Array.from(document.querySelectorAll(".speed-btn")).map(b => ({
                    speed: b.dataset.speed,
                    text: b.textContent.trim(),
                    active: b.classList.contains("active")
                }));
                const audio = document.getElementById("html-podcast-audio");
                return {
                    selectorExists: Boolean(selector),
                    mainBtnExists: Boolean(mainBtn),
                    mainBtnText: mainBtn ? mainBtn.textContent.trim() : null,
                    buttons: buttons,
                    audioPlaybackRate: audio ? audio.playbackRate : null
                };
            })()
        """)
        print("  Speed controls info:", speed_info)
        assert speed_info["selectorExists"], "Playback speed selector group missing!"
        assert speed_info["mainBtnExists"], "Main speed badge button missing!"
        assert speed_info["mainBtnText"] == "1x" or speed_info["mainBtnText"] == "1.0x", f"Expected default 1.0x, got: {speed_info['mainBtnText']}"
        expected_speeds = ["0.75", "1.0", "1.25", "1.5"]
        actual_speeds = [b["speed"] for b in speed_info["buttons"]]
        assert actual_speeds == expected_speeds, f"Speed options mismatch! Expected {expected_speeds}, got {actual_speeds}"

        # 1.0x button should be active by default
        default_active = [b["speed"] for b in speed_info["buttons"] if b["active"]]
        assert default_active == ["1.0"], f"Expected 1.0 to be default active, got: {default_active}"

        print("\n[Step 3] Testing Speed Option Selection (1.25x & 1.5x)...")
        # Click 1.25x speed option
        res_125 = await cdp.eval("""
            (() => {
                const btn125 = document.querySelector('.speed-btn[data-speed="1.25"]');
                if (btn125) btn125.click();
                const audio = document.getElementById("html-podcast-audio");
                const mainBtn = document.getElementById("main-speed-btn");
                return {
                    audioRate: audio ? audio.playbackRate : null,
                    mainBtnText: mainBtn ? mainBtn.textContent.trim() : null,
                    btn125Active: btn125 ? btn125.classList.contains("active") : false
                };
            })()
        """)
        print("  After selecting 1.25x:", res_125)
        assert res_125["audioRate"] == 1.25, f"Expected audio.playbackRate == 1.25, got {res_125['audioRate']}"
        assert res_125["mainBtnText"] == "1.25x", f"Expected main speed text '1.25x', got {res_125['mainBtnText']}"
        assert res_125["btn125Active"], "1.25x speed button should have 'active' class!"

        # Click 1.5x speed option
        res_150 = await cdp.eval("""
            (() => {
                const btn15 = document.querySelector('.speed-btn[data-speed="1.5"]');
                if (btn15) btn15.click();
                const audio = document.getElementById("html-podcast-audio");
                const mainBtn = document.getElementById("main-speed-btn");
                return {
                    audioRate: audio ? audio.playbackRate : null,
                    mainBtnText: mainBtn ? mainBtn.textContent.trim() : null,
                    btn15Active: btn15 ? btn15.classList.contains("active") : false
                };
            })()
        """)
        print("  After selecting 1.5x:", res_150)
        assert res_150["audioRate"] == 1.5, f"Expected audio.playbackRate == 1.5, got {res_150['audioRate']}"
        assert res_150["mainBtnText"] == "1.5x", f"Expected main speed text '1.5x', got {res_150['mainBtnText']}"
        assert res_150["btn15Active"], "1.5x speed button should have 'active' class!"

        print("\n[Step 4] Testing cycling with #main-speed-btn...")
        # Clicking main-speed-btn when at 1.5x should cycle to 0.75x
        res_cycle = await cdp.eval("""
            (() => {
                const mainBtn = document.getElementById("main-speed-btn");
                if (mainBtn) mainBtn.click();
                const audio = document.getElementById("html-podcast-audio");
                const btn075 = document.querySelector('.speed-btn[data-speed="0.75"]');
                return {
                    audioRate: audio ? audio.playbackRate : null,
                    mainBtnText: mainBtn ? mainBtn.textContent.trim() : null,
                    btn075Active: btn075 ? btn075.classList.contains("active") : false
                };
            })()
        """)
        print("  After cycling main-speed-btn:", res_cycle)
        assert res_cycle["audioRate"] == 0.75, f"Expected audio.playbackRate == 0.75, got {res_cycle['audioRate']}"
        assert res_cycle["mainBtnText"] == "0.75x", f"Expected main speed text '0.75x', got {res_cycle['mainBtnText']}"
        assert res_cycle["btn075Active"], "0.75x speed button should have 'active' class!"

        print("\n[Step 5] Testing Playback & Waveform animation at modified speed...")
        # Start playback
        play_res = await cdp.eval("""
            (async () => {
                const playBtn = document.getElementById("main-play-btn");
                if (playBtn) playBtn.click();
                await new Promise(r => setTimeout(r, 600));
                const audio = document.getElementById("html-podcast-audio");
                const waveform = document.querySelector(".waveform-bars");
                return {
                    paused: audio ? audio.paused : true,
                    rate: audio ? audio.playbackRate : null,
                    waveformActive: waveform ? waveform.classList.contains("is-playing") : false
                };
            })()
        """, await_promise=True)
        print("  Playback state:", play_res)
        assert play_res["paused"] is False, "Audio should be playing!"
        assert play_res["rate"] == 0.75, f"Expected rate 0.75, got {play_res['rate']}"
        assert play_res["waveformActive"], "Waveform should have .is-playing class!"

        print("\n[Step 6] Testing Speed Preservation across Track/Language switch...")
        # Set speed to 1.25x while playing
        await cdp.eval("document.querySelector('.speed-btn[data-speed=\"1.25\"]').click()")
        rate_before = await cdp.eval("document.getElementById('html-podcast-audio').playbackRate")
        assert rate_before == 1.25, f"Expected 1.25, got {rate_before}"

        # Switch language to hindi
        switch_res = await cdp.eval("""
            (async () => {
                const select = document.getElementById("audio-language-select");
                if (select) {
                    select.value = "hindi";
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                }
                await new Promise(r => setTimeout(r, 800));
                const audio = document.getElementById("html-podcast-audio");
                return {
                    src: audio ? audio.src : null,
                    rate: audio ? audio.playbackRate : null
                };
            })()
        """, await_promise=True)
        print("  After switching to Hindi track:", switch_res)
        assert "lang=hindi" in switch_res["src"], "Language track should have changed to hindi!"
        assert switch_res["rate"] == 1.25, f"Expected playbackRate 1.25 to be preserved, got {switch_res['rate']}!"

        # Pause playback before starting search/filter tests
        await cdp.eval("document.getElementById('html-podcast-audio').pause()")

        # -----------------------------------------------------------------
        # FEATURE 2.2: SEARCH AND FILTER SAVED EPISODES
        # -----------------------------------------------------------------
        print("\n[Step 7] Testing Search & Filter Toolbar element existence...")
        toolbar_info = await cdp.eval("""
            (() => {
                const toolbar = document.getElementById("episodes-filter-toolbar");
                const searchInput = document.getElementById("episodes-search-input");
                const langSelect = document.getElementById("episodes-filter-language");
                const statusSelect = document.getElementById("episodes-filter-status");
                const clearBtn = document.getElementById("btn-clear-filters");
                return {
                    toolbarExists: Boolean(toolbar),
                    searchInputExists: Boolean(searchInput),
                    langSelectExists: Boolean(langSelect),
                    statusSelectExists: Boolean(statusSelect),
                    clearBtnExists: Boolean(clearBtn)
                };
            })()
        """)
        print("  Toolbar info:", toolbar_info)
        assert all(toolbar_info.values()), f"Toolbar components missing! {toolbar_info}"

        print("\n[Step 8] Testing Title Search Filtering...")
        # Type 'Quantum' into search
        search_res = await cdp.eval("""
            (() => {
                const input = document.getElementById("episodes-search-input");
                input.value = "Quantum";
                input.dispatchEvent(new Event("input", { bubbles: true }));
                const cards = Array.from(document.querySelectorAll(".episode-item-card")).map(c => ({
                    id: c.dataset.id,
                    title: c.querySelector(".episode-item-title") ? c.querySelector(".episode-item-title").textContent.trim() : ""
                }));
                const summary = document.getElementById("episodes-filter-summary");
                const summaryText = document.getElementById("episodes-filter-count-text");
                return {
                    cardCount: cards.length,
                    cards: cards,
                    summaryVisible: summary ? summary.style.display !== "none" : false,
                    summaryText: summaryText ? summaryText.textContent.trim() : ""
                };
            })()
        """)
        print(f"  Search 'Quantum': {search_res['cardCount']} cards found.")
        print(f"  Summary text: '{search_res['summaryText']}'")
        assert 0 < search_res["cardCount"] < initial_count, f"Expected filtered subset, got {search_res['cardCount']} of {initial_count}"
        for card in search_res["cards"]:
            assert "quantum" in card["title"].lower(), f"Card '{card['title']}' does not match 'Quantum'!"
        assert search_res["summaryVisible"], "Filter summary should be visible during search!"

        print("\n[Step 9] Testing Language Filter dropdown...")
        # Clear search and select 'odia'
        lang_res = await cdp.eval("""
            (() => {
                const input = document.getElementById("episodes-search-input");
                input.value = "";
                input.dispatchEvent(new Event("input", { bubbles: true }));

                const langSelect = document.getElementById("episodes-filter-language");
                langSelect.value = "odia";
                langSelect.dispatchEvent(new Event("change", { bubbles: true }));

                const cards = Array.from(document.querySelectorAll(".episode-item-card")).map(c => c.dataset.id);
                return {
                    cardCount: cards.length,
                    cardIds: cards
                };
            })()
        """)
        print(f"  Language 'odia': {lang_res['cardCount']} cards found ({lang_res['cardIds']}).")
        assert lang_res["cardCount"] > 0, "Expected at least 1 Odia episode!"
        assert "10" in lang_res["cardIds"], "Episode #10 must be in Odia filtered results!"

        print("\n[Step 10] Testing Non-Matching Query & Friendly Empty State...")
        # Search for non-existent keyword
        empty_res = await cdp.eval("""
            (() => {
                const langSelect = document.getElementById("episodes-filter-language");
                langSelect.value = "all";
                langSelect.dispatchEvent(new Event("change", { bubbles: true }));

                const input = document.getElementById("episodes-search-input");
                input.value = "NonExistentEpisodeQueryXYZ999";
                input.dispatchEvent(new Event("input", { bubbles: true }));

                const emptyState = document.getElementById("episodes-no-results");
                const emptyMsg = emptyState ? emptyState.querySelector(".empty-msg").textContent.trim() : null;
                const clearBtn = document.getElementById("btn-empty-clear-filters");
                const cardCount = document.querySelectorAll(".episode-item-card").length;
                return {
                    cardCount: cardCount,
                    emptyStateExists: Boolean(emptyState),
                    emptyMsg: emptyMsg,
                    clearBtnExists: Boolean(clearBtn)
                };
            })()
        """)
        print("  Non-matching search result:", empty_res)
        assert empty_res["cardCount"] == 0, "No episode cards should be visible!"
        assert empty_res["emptyStateExists"], "Friendly empty state element must appear!"
        assert "No episodes found" in empty_res["emptyMsg"], f"Unexpected empty message: {empty_res['emptyMsg']}"
        assert empty_res["clearBtnExists"], "'Clear All Filters' button inside empty state must exist!"

        print("\n[Step 11] Testing 'Clear All Filters' button inside empty state...")
        restored_res = await cdp.eval("""
            (() => {
                const clearBtn = document.getElementById("btn-empty-clear-filters");
                if (clearBtn) clearBtn.click();
                const cardCount = document.querySelectorAll(".episode-item-card").length;
                const searchVal = document.getElementById("episodes-search-input").value;
                const langVal = document.getElementById("episodes-filter-language").value;
                return {
                    cardCount: cardCount,
                    searchVal: searchVal,
                    langVal: langVal
                };
            })()
        """)
        print(f"  After clearing: {restored_res['cardCount']} cards restored (search='{restored_res['searchVal']}').")
        assert restored_res["cardCount"] == initial_count, f"Expected {initial_count} cards restored, got {restored_res['cardCount']}"
        assert restored_res["searchVal"] == "", "Search input should be cleared!"
        assert restored_res["langVal"] == "all", "Language filter should be reset to 'all'!"

        print("\n[Step 12] Testing Toolbar 'Clear Filters' button...")
        # Apply a filter and click the toolbar Clear button
        toolbar_clear_res = await cdp.eval("""
            (() => {
                const langSelect = document.getElementById("episodes-filter-language");
                langSelect.value = "hindi";
                langSelect.dispatchEvent(new Event("change", { bubbles: true }));

                const clearBtn = document.getElementById("btn-clear-filters");
                if (clearBtn) clearBtn.click();

                const cardCount = document.querySelectorAll(".episode-item-card").length;
                const langVal = document.getElementById("episodes-filter-language").value;
                return {
                    cardCount: cardCount,
                    langVal: langVal
                };
            })()
        """)
        print(f"  After toolbar Clear: {toolbar_clear_res['cardCount']} cards restored (lang='{toolbar_clear_res['langVal']}').")
        assert toolbar_clear_res["cardCount"] == initial_count, f"Expected {initial_count} cards, got {toolbar_clear_res['cardCount']}"
        assert toolbar_clear_res["langVal"] == "all", "Language filter should be 'all'!"

        print("\n[Step 13] Checking Console Errors & Page Runtime Errors...")
        print(f"  Page runtime errors: {cdp.page_errors}")
        print(f"  Console errors: {cdp.console_messages}")
        assert len(cdp.page_errors) == 0, f"Page runtime errors found: {cdp.page_errors}"
        assert len(cdp.console_messages) == 0, f"Console error logs found: {cdp.console_messages}"

        print("\n" + "=" * 65)
        print("ALL PHASE 2 ENHANCEMENT TESTS PASSED SUCCESSFULLY!")
        print("=" * 65)

        await cdp.close()

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run_phase2_tests())
