import os
import sys
import json
import time
import urllib.request
import urllib.error
from pydub import AudioSegment

BASE_URL = "http://127.0.0.1:5000"
WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AUDIO_DIR = os.path.join(WORKSPACE, "generated_audio")

def post_json(url, payload=None, retries=5):
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
            if err.code in (502, 503) and attempt < retries - 1:
                print(f"      [Retry] Transient HTTP {err.code}, waiting 4s (attempt {attempt+1}/{retries})...")
                time.sleep(4)
                continue
            return err.code, parsed_body

def get_json(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, json.loads(resp.read().decode())

def get_bytes(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, resp.headers, resp.read()

def main():
    print("================================================================================")
    print("      PODCAST BUDDY — LIVE HTTP MANUAL DEMO READINESS VALIDATION                ")
    print("================================================================================")

    # 1. Health check
    print("\n[1] Checking Backend Health...")
    status, health = get_json(f"{BASE_URL}/health")
    assert status == 200 and health.get("status") == "healthy", f"Health failed: {health}"
    print(f"    PASSED: /health is healthy (status={status})")

    # 2. News search
    print("\n[2] Searching Live News via SerpAPI...")
    status, search_res = get_json(f"{BASE_URL}/api/news/search?q=james+webb+space+telescope")
    assert status == 200 and search_res.get("success") is True, f"Search failed: {search_res}"
    articles = search_res.get("results", [])
    assert len(articles) > 0, "No articles returned."
    print(f"    PASSED: Retrieved {len(articles)} real articles.")
    for i, a in enumerate(articles[:2]):
        print(f"      Source {i+1}: '{a.get('title')[:45]}...' by {a.get('publisher')} ({a.get('url')[:35]}...)")
        assert a.get("url", "").startswith("http"), f"Invalid source URL: {a.get('url')}"
        assert a.get("publisher"), "Missing publisher"

    # 3. Create Episode
    print("\n[3] Creating New Demo Episode from Live Articles...")
    selected = articles[:2]
    status, ep_res = post_json(f"{BASE_URL}/api/episodes", {
        "title": "Cosmic Deep Field: JWST Live Demo",
        "description": "Faculty demo episode created live from James Webb Space Telescope news.",
        "articles": selected
    })
    assert status == 201 and ep_res.get("success") is True, f"Episode creation failed: {ep_res}"
    ep = ep_res.get("episode", {})
    ep_id = ep.get("id")
    print(f"    PASSED: Created Episode #{ep_id}: '{ep.get('title')}' with {len(ep.get('sources', []))} sources.")

    # 4. Generate Gemini Intelligence
    print(f"\n[4] Generating Gemini Intelligence for Episode #{ep_id}...")
    status, intel_res = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-intelligence")
    assert status == 200 and intel_res.get("success") is True, f"Intelligence failed: {intel_res}"
    intel = intel_res.get("intelligence", {})
    print(f"    PASSED: Overview: '{intel.get('overview')[:70]}...'")
    print(f"            Key points: {len(intel.get('key_points', []))}, Confidence: {intel.get('confidence')}")

    # 5. Generate Podcast Script
    print(f"\n[5] Generating Host/Co-Host Podcast Script for Episode #{ep_id}...")
    status, script_res = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-script", {"length": "standard"})
    assert status == 200 and script_res.get("success") is True, f"Script failed: {script_res}"
    script = script_res.get("podcast_script", {})
    intro_lines = script.get("intro", {}).get("lines", [])
    segments = script.get("segments", [])
    total_lines = len(intro_lines) + sum(len(s.get("lines", [])) for s in segments)
    print(f"    PASSED: Script generated with {total_lines} dialogue lines across {len(segments)} segments.")
    if intro_lines:
        print(f"            Host opener: \"{intro_lines[0].get('text')[:65]}...\"")

    # 6. Generate and Verify Audio for English, Hindi, and Hinglish
    audio_records = {}
    for lang in ["english", "hindi", "hinglish"]:
        print(f"\n[6-{lang.capitalize()}] Generating {lang.upper()} Audio for Episode #{ep_id}...")
        status, audio_res = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-audio", {"language": lang})
        assert status == 200 and audio_res.get("success") is True, f"Audio failed for {lang}: {audio_res}"
        audio_path = audio_res.get("audio_path")
        audio_dur = audio_res.get("duration_ms")
        audio_size = audio_res.get("file_size")

        full_disk_path = os.path.join(AUDIO_DIR, audio_path)
        assert os.path.isfile(full_disk_path), f"File missing on disk: {full_disk_path}"
        disk_bytes = os.path.getsize(full_disk_path)
        assert disk_bytes == audio_size, f"Size mismatch: API={audio_size}, disk={disk_bytes}"

        # Decode verification with pydub to verify it is real playable audio
        seg = AudioSegment.from_file(full_disk_path)
        actual_dur_ms = len(seg)
        assert actual_dur_ms > 10000, f"Audio too short: {actual_dur_ms}ms"

        # Stream verification via GET /api/episodes/<id>/audio
        s_code, headers, stream_data = get_bytes(f"{BASE_URL}/api/episodes/{ep_id}/audio")
        assert s_code == 200, f"Streaming returned status {s_code}"
        assert headers.get("Content-Type") == "audio/mpeg", f"Unexpected mime: {headers.get('Content-Type')}"
        assert len(stream_data) == disk_bytes, f"Streamed bytes mismatch disk"

        audio_records[lang] = {
            "path": audio_path,
            "size": disk_bytes,
            "duration_ms": actual_dur_ms,
            "channels": seg.channels,
            "frame_rate": seg.frame_rate
        }
        print(f"    PASSED: {lang.upper()} Audio Generated & Stream Verified:")
        print(f"            File: {audio_path}")
        print(f"            Size: {disk_bytes} bytes | Duration: {actual_dur_ms/1000:.2f}s | Sample Rate: {seg.frame_rate}Hz")

    # Verify that English, Hindi, and Hinglish produced distinct non-cached files
    assert audio_records["english"]["path"] != audio_records["hindi"]["path"], "Hindi re-used English file"
    assert audio_records["hindi"]["path"] != audio_records["hinglish"]["path"], "Hinglish re-used Hindi file"
    print("\n    CONFIRMED: English, Hindi, and Hinglish files are distinctly generated, unique files (not cached).")

    # 7. Odia Limitation Verification
    print(f"\n[7] Testing ODIA Audio Generation for Episode #{ep_id}...")
    status, odia_res = post_json(f"{BASE_URL}/api/episodes/{ep_id}/generate-audio", {"language": "odia"})
    print(f"    Odia HTTP Status: {status}")
    print(f"    Odia Response Body: {odia_res}")
    assert status == 502, f"Expected 502 for Odia, got {status}"
    assert odia_res.get("code") == "TTS_ERROR", f"Expected TTS_ERROR code"
    assert "not supported by Google Translate TTS" in odia_res.get("error", "")
    print("    PASSED: Odia transparently refused with clear provider limitation (no fake audio generated).")

    # 8. Frontend Assets Verification
    print("\n[8] Verifying Frontend Web App Pages and Static Assets...")
    app_status, _, app_html = get_bytes(f"{BASE_URL}/app")
    assert app_status == 200, "/app returned non-200"
    html_text = app_html.decode("utf-8")
    assert '<select id="audio-language-select"' in html_text
    assert 'Odia (Provider Unavailable)' in html_text
    assert '<audio id="html-podcast-audio"' in html_text
    print("    PASSED: /app served valid HTML with audio player and Odia disclaimer option.")

    print("\n================================================================================")
    print("            ALL 8 DEMO READINESS CHECKS PASSED WITH REAL SERVICES!              ")
    print("================================================================================")

if __name__ == "__main__":
    main()
