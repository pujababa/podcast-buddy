import os
import sys
import json
import time
import traceback
from datetime import datetime

# Add project root to sys.path
WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from dotenv import load_dotenv
load_dotenv(os.path.join(WORKSPACE, ".env"))

from backend.config import SERPAPI_API_KEY, GEMINI_API_KEY, AUDIO_OUTPUT_DIR
from backend.app import app
from backend.models.database import get_episode, list_episodes

# Redact any sensitive tokens from logs and tracebacks
SECRET_TOKENS = [t for t in [SERPAPI_API_KEY, GEMINI_API_KEY] if t and len(t) > 4]

def sanitize(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    for s in SECRET_TOKENS:
        text = text.replace(s, "[REDACTED_API_KEY]")
    return text

def log_progress(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {sanitize(msg)}", flush=True)

class WorkflowVerifier:
    def __init__(self):
        self.client = app.test_client()
        self.results = {}
        self.created_episode_id = None
        self.search_articles = []
        self.last_audio_file = None

    def record_stage(self, name: str, status: str, details: str, duration: float, error_tb: str = None):
        self.results[name] = {
            "status": status,
            "details": sanitize(details),
            "duration": round(duration, 2),
            "traceback": sanitize(error_tb) if error_tb else None
        }

    def run_stage_search(self):
        stage_name = "Stage 0: SerpAPI Live News Search"
        log_progress(f"--- STARTING {stage_name} ---")
        t0 = time.time()
        try:
            resp = self.client.get("/api/news/search?q=space+exploration")
            dur = time.time() - t0
            data = resp.get_json() if resp.is_json else {}

            if resp.status_code != 200 or not data.get("success"):
                err_msg = f"Search returned status {resp.status_code}: {data.get('error')}"
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            results = data.get("results", [])
            if not results:
                err_msg = "Search returned 0 results."
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            self.search_articles = results
            info = f"Status: {resp.status_code}, Success: True, Total Results: {len(results)}. Sample: '{results[0].get('title', '')[:40]}...'"
            log_progress(f"[PASSED] {stage_name}: {info}")
            self.record_stage(stage_name, "PASSED", info, dur)
            return True
        except Exception as e:
            dur = time.time() - t0
            tb = traceback.format_exc()
            log_progress(f"[EXCEPTION] {stage_name}: {e}")
            print(sanitize(tb), flush=True)
            self.record_stage(stage_name, "FAILED", f"Exception: {e}", dur, tb)
            return False

    def run_stage_create_episode(self):
        stage_name = "Stage 1: Create Episode with Real Search Results"
        log_progress(f"--- STARTING {stage_name} ---")
        t0 = time.time()

        if not self.search_articles:
            dur = time.time() - t0
            log_progress(f"[SKIPPED] {stage_name}: No search results available from previous stage.")
            self.record_stage(stage_name, "SKIPPED", "No search results available", dur)
            return False

        try:
            selected_sources = self.search_articles[:2]
            payload = {
                "title": f"Cosmic Discoveries: Live E2E Verification {datetime.now().strftime('%m%d_%H%M')}",
                "description": "End-to-end verified episode generated from live SerpAPI news search.",
                "articles": selected_sources
            }
            resp = self.client.post("/api/episodes", json=payload)
            dur = time.time() - t0
            data = resp.get_json() if resp.is_json else {}

            if resp.status_code != 201 or not data.get("success"):
                err_msg = f"Create episode returned status {resp.status_code}: {data.get('error')}"
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            episode = data.get("episode", {})
            self.created_episode_id = episode.get("id")
            info = f"Created Episode #{self.created_episode_id}: '{episode.get('title')}' with {len(episode.get('sources', []))} sources."
            log_progress(f"[PASSED] {stage_name}: {info}")
            self.record_stage(stage_name, "PASSED", info, dur)
            return True
        except Exception as e:
            dur = time.time() - t0
            tb = traceback.format_exc()
            log_progress(f"[EXCEPTION] {stage_name}: {e}")
            print(sanitize(tb), flush=True)
            self.record_stage(stage_name, "FAILED", f"Exception: {e}", dur, tb)
            return False

    def run_stage_generate_intelligence(self):
        stage_name = "Stage 2: Generate Summary/Intelligence via Gemini"
        log_progress(f"--- STARTING {stage_name} ---")
        t0 = time.time()

        if not self.created_episode_id:
            dur = time.time() - t0
            log_progress(f"[SKIPPED] {stage_name}: No episode created in previous stage.")
            self.record_stage(stage_name, "SKIPPED", "Episode not created", dur)
            return False

        try:
            resp = self.client.post(f"/api/episodes/{self.created_episode_id}/generate-intelligence")
            dur = time.time() - t0
            data = resp.get_json() if resp.is_json else {}

            if resp.status_code != 200 or not data.get("success"):
                err_msg = f"Generate intelligence returned status {resp.status_code}: {data.get('error')}"
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            intel = data.get("intelligence", {})
            overview = intel.get("overview", "")
            key_points_count = len(intel.get("key_points", []))
            confidence = intel.get("confidence", "unknown")

            # Check database persistence
            db_ep = get_episode(self.created_episode_id)
            if not db_ep or db_ep.get("ai_status") != "completed":
                err_msg = f"Database ai_status mismatch: expected 'completed', got '{db_ep.get('ai_status') if db_ep else None}'"
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            info = f"Overview: '{overview[:60]}...' | Key Points: {key_points_count} | Confidence: {confidence} | DB ai_status: completed"
            log_progress(f"[PASSED] {stage_name}: {info}")
            self.record_stage(stage_name, "PASSED", info, dur)
            return True
        except Exception as e:
            dur = time.time() - t0
            tb = traceback.format_exc()
            log_progress(f"[EXCEPTION] {stage_name}: {e}")
            print(sanitize(tb), flush=True)
            self.record_stage(stage_name, "FAILED", f"Exception: {e}", dur, tb)
            return False

    def run_stage_generate_script(self):
        stage_name = "Stage 3: Generate Host/Co-Host Podcast Script via Gemini"
        log_progress(f"--- STARTING {stage_name} ---")
        t0 = time.time()

        if not self.created_episode_id:
            dur = time.time() - t0
            log_progress(f"[SKIPPED] {stage_name}: No episode created.")
            self.record_stage(stage_name, "SKIPPED", "Episode not created", dur)
            return False

        try:
            resp = self.client.post(
                f"/api/episodes/{self.created_episode_id}/generate-script",
                json={"length": "standard"}
            )
            dur = time.time() - t0
            data = resp.get_json() if resp.is_json else {}

            if resp.status_code != 200 or not data.get("success"):
                err_msg = f"Generate script returned status {resp.status_code}: {data.get('error')}"
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            script = data.get("podcast_script", {})
            intro_lines = script.get("intro", {}).get("lines", [])
            segments = script.get("segments", [])
            total_lines = len(intro_lines) + sum(len(s.get("lines", [])) for s in segments)

            # Check database persistence
            db_ep = get_episode(self.created_episode_id)
            if not db_ep or db_ep.get("script_status") != "completed":
                err_msg = f"Database script_status mismatch: expected 'completed', got '{db_ep.get('script_status') if db_ep else None}'"
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            info = f"Total script dialogue turns: {total_lines} across {len(segments)} segments. DB script_status: completed"
            log_progress(f"[PASSED] {stage_name}: {info}")
            self.record_stage(stage_name, "PASSED", info, dur)
            return True
        except Exception as e:
            dur = time.time() - t0
            tb = traceback.format_exc()
            log_progress(f"[EXCEPTION] {stage_name}: {e}")
            print(sanitize(tb), flush=True)
            self.record_stage(stage_name, "FAILED", f"Exception: {e}", dur, tb)
            return False

    def run_stage_audio_single(self, language: str):
        stage_name = f"Stage 4 ({language.capitalize()}): Audio Generation & Verification"
        log_progress(f"--- STARTING {stage_name} ---")
        t0 = time.time()

        if not self.created_episode_id:
            dur = time.time() - t0
            log_progress(f"[SKIPPED] {stage_name}: No episode created.")
            self.record_stage(stage_name, "SKIPPED", "Episode not created", dur)
            return False

        try:
            resp = self.client.post(
                f"/api/episodes/{self.created_episode_id}/generate-audio",
                json={"language": language}
            )
            dur = time.time() - t0
            data = resp.get_json() if resp.is_json else {}

            if resp.status_code == 200 and data.get("success"):
                audio_path = data.get("audio_path")
                full_path = os.path.join(AUDIO_OUTPUT_DIR, audio_path) if not os.path.isabs(audio_path) else audio_path
                file_exists = os.path.isfile(full_path)
                file_size = os.path.getsize(full_path) if file_exists else 0
                duration_ms = data.get("duration_ms", 0)

                if not file_exists or file_size == 0:
                    err_msg = f"Audio API reported success, but file '{full_path}' does not exist or is empty (size={file_size})."
                    log_progress(f"[FAILED] {stage_name}: {err_msg}")
                    self.record_stage(stage_name, "FAILED", err_msg, dur)
                    return False

                self.last_audio_file = audio_path
                info = f"Generated file: '{os.path.basename(audio_path)}', size: {file_size} bytes, duration: {duration_ms}ms"
                log_progress(f"[PASSED] {stage_name}: {info}")
                self.record_stage(stage_name, "PASSED", info, dur)
                return True

            # If it failed, check if it's the known Odia provider limitation
            err_msg = data.get("error", f"HTTP {resp.status_code}")
            log_progress(f"[FAILED] {stage_name}: Status {resp.status_code}, error: {err_msg}")
            self.record_stage(stage_name, "FAILED", f"Status {resp.status_code}: {err_msg}", dur)
            return False

        except Exception as e:
            dur = time.time() - t0
            tb = traceback.format_exc()
            log_progress(f"[EXCEPTION] {stage_name}: {e}")
            print(sanitize(tb), flush=True)
            self.record_stage(stage_name, "FAILED", f"Exception: {e}", dur, tb)
            return False

    def run_stage_verify_audio_endpoint(self):
        stage_name = "Stage 5: Verify Episode Audio Endpoint Points to New File"
        log_progress(f"--- STARTING {stage_name} ---")
        t0 = time.time()

        if not self.created_episode_id:
            dur = time.time() - t0
            log_progress(f"[SKIPPED] {stage_name}: No episode created.")
            self.record_stage(stage_name, "SKIPPED", "Episode not created", dur)
            return False

        try:
            # Query the episode from database
            ep = get_episode(self.created_episode_id)
            if not ep:
                err_msg = f"Episode #{self.created_episode_id} not found in database."
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            db_audio_path = ep.get("audio_path")
            db_audio_status = ep.get("audio_status")

            if db_audio_status != "completed" or not db_audio_path:
                err_msg = f"Episode audio not in completed state in DB: status='{db_audio_status}', path='{db_audio_path}'"
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            # Verify that the DB audio path matches the last audio file generated
            if self.last_audio_file and os.path.basename(db_audio_path) != os.path.basename(self.last_audio_file):
                err_msg = f"DB audio_path '{db_audio_path}' does not match last generated file '{self.last_audio_file}'"
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            # Request audio stream via GET /api/episodes/<id>/audio
            resp = self.client.get(f"/api/episodes/{self.created_episode_id}/audio")
            dur = time.time() - t0

            if resp.status_code != 200:
                err_msg = f"Audio endpoint GET returned status {resp.status_code}"
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            content_len = len(resp.data)
            content_type = resp.headers.get("Content-Type", "")

            full_path = os.path.join(AUDIO_OUTPUT_DIR, db_audio_path) if not os.path.isabs(db_audio_path) else db_audio_path
            disk_size = os.path.getsize(full_path) if os.path.isfile(full_path) else 0

            if content_len == 0 or content_len != disk_size:
                err_msg = f"Streamed byte count ({content_len}) does not match file on disk ({disk_size})."
                log_progress(f"[FAILED] {stage_name}: {err_msg}")
                self.record_stage(stage_name, "FAILED", err_msg, dur)
                return False

            info = f"Stream URL '/api/episodes/{self.created_episode_id}/audio' verified: Content-Type='{content_type}', bytes={content_len}, synced with disk='{os.path.basename(db_audio_path)}'"
            log_progress(f"[PASSED] {stage_name}: {info}")
            self.record_stage(stage_name, "PASSED", info, dur)
            return True

        except Exception as e:
            dur = time.time() - t0
            tb = traceback.format_exc()
            log_progress(f"[EXCEPTION] {stage_name}: {e}")
            print(sanitize(tb), flush=True)
            self.record_stage(stage_name, "FAILED", f"Exception: {e}", dur, tb)
            return False

    def run_all(self):
        log_progress("================================================================================")
        log_progress("STARTING PODCAST BUDDY END-TO-END WORKFLOW VERIFICATION")
        log_progress("================================================================================")

        # Stage 0: Search
        self.run_stage_search()

        # Stage 1: Create Episode
        self.run_stage_create_episode()

        # Stage 2: Gemini Intelligence
        self.run_stage_generate_intelligence()

        # Stage 3: Gemini Script
        self.run_stage_generate_script()

        # Stage 4: Audio for all languages
        for lang in ["english", "hindi", "odia", "hinglish"]:
            self.run_stage_audio_single(lang)

        # Stage 5: Audio URL verification
        self.run_stage_verify_audio_endpoint()

        # Print Final Report
        self.print_final_report()

    def print_final_report(self):
        print("\n" + "=" * 80, flush=True)
        print("                     COMPLETE FINAL VERIFICATION REPORT                        ", flush=True)
        print("=" * 80, flush=True)
        
        passed_count = sum(1 for s in self.results.values() if s["status"] == "PASSED")
        failed_count = sum(1 for s in self.results.values() if s["status"] == "FAILED")
        skipped_count = sum(1 for s in self.results.values() if s["status"] == "SKIPPED")
        total_count = len(self.results)

        for name, data in self.results.items():
            status_box = f"[{data['status']}]"
            print(f"\n{status_box:<11} {name} ({data['duration']}s)", flush=True)
            print(f"            Details: {data['details']}", flush=True)
            if data["traceback"]:
                print(f"            Traceback:\n{data['traceback']}", flush=True)

        print("\n" + "-" * 80, flush=True)
        print(f"SUMMARY: Total Stages: {total_count} | Passed: {passed_count} | Failed: {failed_count} | Skipped: {skipped_count}", flush=True)
        print("=" * 80 + "\n", flush=True)

if __name__ == "__main__":
    verifier = WorkflowVerifier()
    verifier.run_all()
