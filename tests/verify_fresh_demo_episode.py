import os
import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime
from pydub import AudioSegment

BASE_URL = "http://127.0.0.1:5000"
WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AUDIO_DIR = os.path.join(WORKSPACE, "generated_audio")

def post_json(url, payload=None, retries=4):
    data = json.dumps(payload).encode() if payload is not None else b""
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as err:
            body = err.read().decode()
            try:
                parsed_body = json.loads(body)
            except Exception:
                parsed_body = {"raw": body}
            if "odia" in str(parsed_body).lower():
                return err.code, parsed_body
            if err.code in (502, 503) and attempt < retries - 1:
                print(f"      [Retry] Transient HTTP {err.code}, waiting 3s (attempt {attempt+1}/{retries})...")
                time.sleep(3)
                continue
            return err.code, parsed_body

def get_json(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, json.loads(resp.read().decode())

def get_bytes(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, resp.headers, resp.read()

def main():
    report = {}

    print("================================================================================")
    print("      PODCAST BUDDY — FRESH END-TO-END DEMO EPISODE VERIFICATION               ")
    print("================================================================================")

    # Stage 1: Health Check
    t0 = time.time()
    try:
        status, health = get_json(f"{BASE_URL}/health")
        assert status == 200 and health.get("status") == "healthy"
        report["Stage 1: Health Endpoint"] = {
            "status": "PASS",
            "evidence": f"HTTP 200, status='healthy' in {time.time()-t0:.2f}s"
        }
        print(f"[STAGE 1] PASS: Health endpoint is healthy (status={status})")
    except Exception as e:
        report["Stage 1: Health Endpoint"] = {"status": "FAIL", "evidence": str(e)}
        print(f"[STAGE 1] FAIL: {e}")

    # Stage 2: SerpAPI Live News Search
    t0 = time.time()
    search_articles = []
    try:
        status, search_res = get_json(f"{BASE_URL}/api/news/search?q=quantum+computing")
        assert status == 200 and search_res.get("success") is True
        search_articles = search_res.get("results", [])
        assert len(search_articles) >= 2, "Expected at least 2 articles"
        
        # Verify source links
        for a in search_articles[:2]:
            assert a.get("url", "").startswith("http"), f"Invalid source URL: {a.get('url')}"
            assert a.get("title") and a.get("publisher"), "Missing title or publisher"
            
        report["Stage 2: Live News Search (SerpAPI)"] = {
            "status": "PASS",
            "evidence": f"Retrieved {len(search_articles)} real stories. Top: '{search_articles[0]['title'][:40]}...' from {search_articles[0]['publisher']} ({search_articles[0]['url'][:35]}...) in {time.time()-t0:.2f}s"
        }
        print(f"[STAGE 2] PASS: Live news retrieved ({len(search_articles)} articles, verified http source links)")
    except Exception as e:
        report["Stage 2: Live News Search (SerpAPI)"] = {"status": "FAIL", "evidence": str(e)}
        print(f"[STAGE 2] FAIL: {e}")

    # Stage 3: Create Fresh Episode
    t0 = time.time()
    ep_id = None
    try:
        selected = search_articles[:2]
        status, ep_res = post_json(f"{BASE_URL}/api/episodes", {
            "title": f"Quantum Frontiers: Live Demo Episode #{datetime.now().strftime('%H%M%S')}",
            "description": "End-to-end verified demo episode created live from real quantum computing news.",
            "articles": selected
        })
        assert status == 201 and ep_res.get("success") is True
        ep_id = ep_res["episode"]["id"]
        report["Stage 3: Episode Creation"] = {
            "status": "PASS",
            "evidence": f"Created Episode #{ep_id}: '{ep_res['episode']['title']}' with {len(ep_res['episode']['sources'])} sources in {time.time()-t0:.2f}s"
        }
        print(f"[STAGE 3] PASS: Created Episode #{ep_id}")
    except Exception as e:
        report["Stage 3: Episode Creation"] = {"status": "FAIL", "evidence": str(e)}
        print(f"[STAGE 3] FAIL: {e}")

    # Stage 4: Gemini Summary Intelligence
    t0 = time.time()
    try:
        assert ep_id is not None
        status, intel_res = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-intelligence")
        assert status == 200 and intel_res.get("success") is True
        intel = intel_res["intelligence"]
        report["Stage 4: Gemini AI Summary Intelligence"] = {
            "status": "PASS",
            "evidence": f"Overview: '{intel['overview'][:50]}...' | Key points: {len(intel.get('key_points', []))} | Confidence: {intel.get('confidence')} in {time.time()-t0:.2f}s"
        }
        print(f"[STAGE 4] PASS: AI summary generated via Gemini in {time.time()-t0:.2f}s")
    except Exception as e:
        report["Stage 4: Gemini AI Summary Intelligence"] = {"status": "FAIL", "evidence": str(e)}
        print(f"[STAGE 4] FAIL: {e}")

    # Stage 5: Host/Co-Host Script Generation
    t0 = time.time()
    try:
        assert ep_id is not None
        status, script_res = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-script", {"length": "standard"})
        assert status == 200 and script_res.get("success") is True
        script = script_res["podcast_script"]
        intro_lines = script.get("intro", {}).get("lines", [])
        segments = script.get("segments", [])
        total_dialogue_turns = len(intro_lines) + sum(len(s.get("lines", [])) for s in segments)
        report["Stage 5: Host/Co-Host Script Generation"] = {
            "status": "PASS",
            "evidence": f"Generated {total_dialogue_turns} dialogue lines across {len(segments)} segments in {time.time()-t0:.2f}s"
        }
        print(f"[STAGE 5] PASS: Script generated with {total_dialogue_turns} dialogue turns in {time.time()-t0:.2f}s")
    except Exception as e:
        report["Stage 5: Host/Co-Host Script Generation"] = {"status": "FAIL", "evidence": str(e)}
        print(f"[STAGE 5] FAIL: {e}")

    # Stage 6: Fresh English Audio Generation & Streaming Verification
    t0 = time.time()
    english_file = None
    try:
        assert ep_id is not None
        status, audio_en = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-audio", {"language": "english"})
        assert status == 200 and audio_en.get("success") is True, f"HTTP {status}: {audio_en}"
        english_file = audio_en["audio_path"]
        en_path = os.path.join(AUDIO_DIR, english_file)
        assert os.path.isfile(en_path) and os.path.getsize(en_path) > 0
        seg = AudioSegment.from_file(en_path)
        assert len(seg) > 5000
        
        # Verify streaming endpoint
        s_code, headers, stream_data = get_bytes(f"{BASE_URL}/api/episodes/{ep_id}/audio")
        assert s_code == 200 and headers.get("Content-Type") == "audio/mpeg"
        assert len(stream_data) == os.path.getsize(en_path)

        report["Stage 6: Audio Generation (English)"] = {
            "status": "PASS",
            "evidence": f"File='{english_file}', size={os.path.getsize(en_path)} bytes, duration={len(seg)/1000:.2f}s, sample_rate={seg.frame_rate}Hz, stream verified 200 in {time.time()-t0:.2f}s"
        }
        print(f"[STAGE 6] PASS: English audio verified ({os.path.getsize(en_path)} bytes, {len(seg)/1000:.2f}s)")
    except Exception as e:
        report["Stage 6: Audio Generation (English)"] = {"status": "FAIL", "evidence": str(e)}
        print(f"[STAGE 6] FAIL: {e}")

    # Stage 7: Fresh Hindi Audio Generation & Streaming Verification
    t0 = time.time()
    hindi_file = None
    try:
        assert ep_id is not None
        status, audio_hi = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-audio", {"language": "hindi"})
        assert status == 200 and audio_hi.get("success") is True, f"HTTP {status}: {audio_hi}"
        hindi_file = audio_hi["audio_path"]
        assert hindi_file != english_file, "Hindi audio re-used English file (cached)!"
        hi_path = os.path.join(AUDIO_DIR, hindi_file)
        assert os.path.isfile(hi_path) and os.path.getsize(hi_path) > 0
        seg = AudioSegment.from_file(hi_path)
        assert len(seg) > 5000

        # Verify streaming endpoint
        s_code, headers, stream_data = get_bytes(f"{BASE_URL}/api/episodes/{ep_id}/audio")
        assert s_code == 200 and headers.get("Content-Type") == "audio/mpeg"
        assert len(stream_data) == os.path.getsize(hi_path)

        report["Stage 7: Audio Generation (Hindi)"] = {
            "status": "PASS",
            "evidence": f"File='{hindi_file}', size={os.path.getsize(hi_path)} bytes, duration={len(seg)/1000:.2f}s, unique from English in {time.time()-t0:.2f}s"
        }
        print(f"[STAGE 7] PASS: Hindi audio verified ({os.path.getsize(hi_path)} bytes, {len(seg)/1000:.2f}s, unique file)")
    except Exception as e:
        report["Stage 7: Audio Generation (Hindi)"] = {"status": "FAIL", "evidence": str(e)}
        print(f"[STAGE 7] FAIL: {e}")

    # Stage 8: Fresh Hinglish Audio Generation & Streaming Verification
    t0 = time.time()
    hinglish_file = None
    try:
        assert ep_id is not None
        status, audio_hing = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-audio", {"language": "hinglish"})
        assert status == 200 and audio_hing.get("success") is True, f"HTTP {status}: {audio_hing}"
        hinglish_file = audio_hing["audio_path"]
        assert hinglish_file != hindi_file and hinglish_file != english_file, "Hinglish audio re-used old file (cached)!"
        hing_path = os.path.join(AUDIO_DIR, hinglish_file)
        assert os.path.isfile(hing_path) and os.path.getsize(hing_path) > 0
        seg = AudioSegment.from_file(hing_path)
        assert len(seg) > 5000

        # Verify streaming endpoint
        s_code, headers, stream_data = get_bytes(f"{BASE_URL}/api/episodes/{ep_id}/audio")
        assert s_code == 200 and headers.get("Content-Type") == "audio/mpeg"
        assert len(stream_data) == os.path.getsize(hing_path)

        report["Stage 8: Audio Generation (Hinglish)"] = {
            "status": "PASS",
            "evidence": f"File='{hinglish_file}', size={os.path.getsize(hing_path)} bytes, duration={len(seg)/1000:.2f}s, unique from En/Hi in {time.time()-t0:.2f}s"
        }
        print(f"[STAGE 8] PASS: Hinglish audio verified ({os.path.getsize(hing_path)} bytes, {len(seg)/1000:.2f}s, unique file)")
    except Exception as e:
        report["Stage 8: Audio Generation (Hinglish)"] = {"status": "FAIL", "evidence": str(e)}
        print(f"[STAGE 8] FAIL: {e}")

    # Stage 9: Odia Provider Limitation Check
    t0 = time.time()
    try:
        assert ep_id is not None
        status, odia_res = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-audio", {"language": "odia"})
        assert status == 502, f"Expected 502, got {status}"
        assert odia_res.get("code") == "TTS_ERROR"
        assert "not supported by Google Translate TTS" in odia_res.get("error", "")
        report["Stage 9: Odia Limitation Notice"] = {
            "status": "PASS",
            "evidence": f"HTTP 502 returned with explicit provider limitation message in {time.time()-t0:.2f}s. No fake audio produced."
        }
        print(f"[STAGE 9] PASS: Odia rejected with honest provider limitation error (HTTP 502)")
    except Exception as e:
        report["Stage 9: Odia Limitation Notice"] = {"status": "FAIL", "evidence": str(e)}
        print(f"[STAGE 9] FAIL: {e}")

    # Stage 10: In-Browser Playback Verification Status
    report["Stage 10: Browser Audio Playback Execution"] = {
        "status": "NOT VERIFIED (AUTOMATED)",
        "evidence": "Playwright headless browser binary cannot download in sandboxed runner. Manual in-browser playback instructions provided."
    }

    # Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY REPORT:")
    print("=" * 80)
    for stg, val in report.items():
        print(f"[{val['status']:<14}] {stg}")
        print(f"               Evidence: {val['evidence']}")
    print("=" * 80)

if __name__ == "__main__":
    main()
