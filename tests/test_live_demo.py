import json
import urllib.request
import urllib.error
import time

def run_live_demo_check():
    base = "http://127.0.0.1:5000"

    # 1. Search Live News
    print("[1/6] Searching live news...")
    with urllib.request.urlopen(f"{base}/api/news/search?q=technology") as resp:
        data = json.loads(resp.read().decode())
    assert data["success"] is True
    articles = data["results"]
    print(f"      Retrieved {len(articles)} real articles. Top: '{articles[0]['title'][:40]}...'")

    # 2. Create Episode
    print("[2/6] Creating new episode...")
    payload = {
        "title": "Technology Digest: Live Demo Readiness",
        "description": "Verified demo episode created from live search.",
        "articles": articles[:2]
    }
    req = urllib.request.Request(
        f"{base}/api/episodes",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        created = json.loads(resp.read().decode())
    assert created["success"] is True
    ep_id = created["episode"]["id"]
    print(f"      Created Episode #{ep_id}: '{created['episode']['title']}'")

    # 3. Generate Intelligence via Gemini
    print("[3/6] Generating AI intelligence via Gemini...")
    req = urllib.request.Request(
        f"{base}/api/episodes/{ep_id}/generate-intelligence",
        data=b"",
        headers={"Content-Type": "application/json"}
    )
    intel = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req) as resp:
                intel = json.loads(resp.read().decode())
                break
        except urllib.error.HTTPError as e:
            if e.code in (502, 503) and attempt < 2:
                print(f"      Transient HTTP {e.code}, retrying in 3s (attempt {attempt+1}/3)...")
                time.sleep(3)
                continue
            raise
    assert intel and intel["success"] is True
    print(f"      AI Overview: '{intel['intelligence']['overview'][:60]}...'")

    # 4. Generate Script via Gemini
    print("[4/6] Generating Host/Co-Host podcast script...")
    req = urllib.request.Request(
        f"{base}/api/episodes/{ep_id}/generate-script",
        data=json.dumps({"length": "quick"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        script = json.loads(resp.read().decode())
    assert script["success"] is True
    intro = script["podcast_script"].get("intro", {}).get("lines", [])
    print(f"      Script generated with {len(intro)} intro lines.")

    # 5. Generate Audio (English)
    print("[5/6] Generating audio in English...")
    req = urllib.request.Request(
        f"{base}/api/episodes/{ep_id}/generate-audio",
        data=json.dumps({"language": "english"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        audio = json.loads(resp.read().decode())
    assert audio["success"] is True
    print(f"      Audio: {audio['audio_path']}, size={audio['file_size']} bytes, duration={audio['duration_ms']}ms")

    # 6. Stream and Verify Audio Endpoint
    print("[6/6] Verifying browser streaming endpoint...")
    with urllib.request.urlopen(f"{base}/api/episodes/{ep_id}/audio") as resp:
        stream_bytes = len(resp.read())
        content_type = resp.headers.get("Content-Type")
    assert resp.status == 200
    assert content_type == "audio/mpeg"
    assert stream_bytes == audio["file_size"]
    print(f"      Streamed {stream_bytes} bytes (Content-Type: {content_type}), byte-exact match with generated file.")

    print("\n=======================================================")
    print("DEMO READINESS: FULL LIVE HTTP WORKFLOW FULLY VERIFIED!")
    print("=======================================================")

if __name__ == "__main__":
    run_live_demo_check()
