"""
Podcast Buddy - Audit & Major Project Readiness Test Suite
Verifies:
1. Audio state preservation on failure/retry (no overwriting existing audio_path)
2. Audio streaming with language parameter (?lang=) and file-presence verification
3. Language integrity and provider capability handling (Odia rejection vs English/Hindi/Hinglish)
4. Episode listing audio_ready enrichment
5. Diagnostics / health endpoint contracts
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import app
import backend.models.database as db_module
import backend.routes.episodes as episodes_module
from backend.models.database import (
    init_db,
    create_episode,
    get_episode,
    update_episode_audio
)
from backend.services.tts_service import (
    normalize_language,
    TTSLanguageError,
    TTSSynthesisError,
    tts_service
)


class TestAuditAndHardeningFixes(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "test_audit.db")

        # Patch module-level database and audio paths
        self.db_patcher = patch.object(db_module, "DATABASE_PATH", self.db_path)
        self.db_patcher.start()

        self.audio_dir = os.path.join(self.temp_dir.name, "audio_out")
        os.makedirs(self.audio_dir, exist_ok=True)
        self.audio_patcher = patch.object(episodes_module, "AUDIO_OUTPUT_DIR", self.audio_dir)
        self.audio_patcher.start()

        init_db(self.db_path)

        app.testing = True
        self.client = app.test_client()

        # Seed sample episode
        self.sample_episode = create_episode(
            title="AI Revolution in Healthcare",
            description="Recent clinical breakthroughs in diagnostic algorithms",
            articles=[{
                "id": "med-1",
                "title": "AI in Diagnostics",
                "publisher": "Health Tech Today",
                "snippet": "New models show 98% accuracy in clinical trials.",
                "url": "https://example.com/ai-health"
            }],
            db_path=self.db_path
        )
        self.ep_id = self.sample_episode["id"]

    def tearDown(self):
        self.audio_patcher.stop()
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_audio_state_preserved_when_failure_occurs(self):
        """
        Verify that if an episode already has an audio_path, an audio generation
        failure or retry does NOT wipe out the existing audio_path in the database.
        """
        existing_audio_file = "episode_1_english_123456.mp3"
        update_episode_audio(
            episode_id=self.ep_id,
            audio_status="completed",
            audio_language="english",
            audio_path=existing_audio_file,
            generated_at=datetime.now(timezone.utc).isoformat(),
            db_path=self.db_path
        )

        ep_before = get_episode(self.ep_id, db_path=self.db_path)
        self.assertEqual(ep_before["audio_status"], "completed")
        self.assertEqual(ep_before["audio_path"], existing_audio_file)

        # Simulate subsequent failure
        update_episode_audio(
            episode_id=self.ep_id,
            audio_status="failed",
            audio_error="Speech synthesis provider error",
            db_path=self.db_path
        )

        ep_after = get_episode(self.ep_id, db_path=self.db_path)
        self.assertEqual(ep_after["audio_status"], "failed")
        self.assertEqual(ep_after["audio_error"], "Speech synthesis provider error")
        # Critical verification: previous audio_path was NOT wiped to None!
        self.assertEqual(ep_after["audio_path"], existing_audio_file)
        self.assertEqual(ep_after["audio_language"], "english")

    def test_audio_streaming_language_query_parameter(self):
        """
        Verify GET /api/episodes/<id>/audio?lang=hindi finds and streams language-specific file.
        """
        hindi_filename = f"episode_{self.ep_id}_hindi_testtrack.mp3"
        hindi_filepath = os.path.join(self.audio_dir, hindi_filename)
        with open(hindi_filepath, "wb") as f:
            f.write(b"ID3\x03\x00\x00\x00\x00\x00#mock-mp3-hindi-stream-data#")

        update_episode_audio(
            episode_id=self.ep_id,
            audio_status="completed",
            audio_language="english",
            audio_path=f"episode_{self.ep_id}_english_primary.mp3",
            db_path=self.db_path
        )

        res = self.client.get(f"/api/episodes/{self.ep_id}/audio?lang=hindi")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "audio/mpeg")
        self.assertIn(b"mock-mp3-hindi-stream-data", res.data)
        res.close()

    def test_audio_ready_flag_in_episode_listing(self):
        """
        Verify handle_list_episodes includes audio_ready=True only when
        audio file actually exists on disk with non-zero size.
        """
        update_episode_audio(
            episode_id=self.ep_id,
            audio_status="completed",
            audio_language="english",
            audio_path="ghost_audio_file.mp3",
            db_path=self.db_path
        )

        res = self.client.get("/api/episodes")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        ep = next(e for e in data["episodes"] if e["id"] == self.ep_id)
        self.assertFalse(ep["audio_ready"], "Audio ready must be False if file missing from disk")

        # Now write the file to disk
        real_path = os.path.join(self.audio_dir, "ghost_audio_file.mp3")
        with open(real_path, "wb") as f:
            f.write(b"MOCK_AUDIO_DATA_FOR_READY_CHECK")

        res2 = self.client.get("/api/episodes")
        data2 = res2.get_json()
        ep2 = next(e for e in data2["episodes"] if e["id"] == self.ep_id)
        self.assertTrue(ep2["audio_ready"], "Audio ready must be True when file exists on disk")

    def test_language_integrity_odia_provider_limitation(self):
        """
        Verify that requesting Odia speech synthesis raises TTSSynthesisError
        with accurate explanation of provider limitations, while English/Hindi are valid.
        """
        self.assertEqual(normalize_language("english"), "english")
        self.assertEqual(normalize_language("hindi"), "hindi")
        self.assertEqual(normalize_language("hinglish"), "hinglish")
        self.assertEqual(normalize_language("odia"), "odia")

        dummy_out = os.path.join(self.temp_dir.name, "test_odia.mp3")
        with patch("backend.services.tts_service.SARVAM_API_KEY", ""):
            with patch.dict(os.environ, {"SARVAM_API_KEY": "", "TTS_API_KEY": ""}):
                with self.assertRaises(TTSSynthesisError) as ctx:
                    tts_service.synthesize_line("test", speaker="host", language="odia", output_path=dummy_out)

        err_msg = str(ctx.exception)
        self.assertIn("Odia", err_msg)
        self.assertIn("Google Translate TTS", err_msg)

    def test_health_and_root_endpoints(self):
        """
        Verify /health and / endpoints return expected status codes and JSON structure.
        """
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        data_health = res_health.get_json()
        self.assertEqual(data_health["status"], "healthy")

        res_root = self.client.get("/")
        self.assertIn(res_root.status_code, (301, 302))
        self.assertEqual(res_root.headers.get("Location"), "/app")

    def test_requested_odia_audio_returns_404_not_serving_other_language(self):
        """
        Verify that requesting Odia audio via ?lang=odia returns 404 rather than
        falling back to serving a Hinglish or English file.
        """
        # Create an English audio file on disk
        en_filename = f"episode_{self.ep_id}_english_testtrack.mp3"
        en_filepath = os.path.join(self.audio_dir, en_filename)
        with open(en_filepath, "wb") as f:
            f.write(b"ID3\x03#mock-english-audio#")

        update_episode_audio(
            episode_id=self.ep_id,
            audio_status="completed",
            audio_language="english",
            audio_path=en_filename,
            db_path=self.db_path
        )

        res = self.client.get(f"/api/episodes/{self.ep_id}/audio?lang=odia")
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["code"], "LANGUAGE_TRACK_NOT_FOUND")

    def test_episode_computed_fields_enrichment(self):
        """
        Verify handle_list_episodes and handle_get_episode return computed fields:
        available_audio_languages, script_ready, ai_ready based on actual data.
        """
        # Initially no audio on disk and no script
        res = self.client.get(f"/api/episodes/{self.ep_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ep = data["episode"]
        self.assertFalse(ep["audio_ready"])
        self.assertEqual(ep["available_audio_languages"], [])
        self.assertFalse(ep["script_ready"])

        # Write Hindi audio to disk
        hi_filename = f"episode_{self.ep_id}_hindi_track.mp3"
        with open(os.path.join(self.audio_dir, hi_filename), "wb") as f:
            f.write(b"ID3\x03#mock-hindi-audio#")

        res2 = self.client.get(f"/api/episodes/{self.ep_id}")
        ep2 = res2.get_json()["episode"]
        self.assertTrue(ep2["audio_ready"])
        self.assertIn("hindi", ep2["available_audio_languages"])

    def test_frontend_ui_diagnostics_and_nav_structure(self):
        """
        Verify frontend/index.html has removed raw health text from navbar,
        has collapsed developer diagnostics by default, and includes the subtle status dot.
        """
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Raw label removed from normal nav/hero
        self.assertNotIn("Backend: Online (Healthy)", html)

        # Subtle indicator dot present
        self.assertIn('id="backend-status-indicator"', html)

        # Developer diagnostics exists and is collapsed by default (no open attribute)
        self.assertIn('id="developer-diagnostics"', html)
        self.assertIn('<details class="diagnostics-details">', html)
        self.assertNotIn('<details class="diagnostics-details" open>', html)

        # Unified Audio Studio viewer exists
        self.assertIn('id="podcast-studio-viewer"', html)
        self.assertIn('id="studio-active-track-pill"', html)

    def test_database_and_existing_episodes_preserved(self):
        """
        Verify the real SQLite database has at least 10 episodes preserved.
        """
        live_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "podcast_buddy.db"))
        self.assertTrue(os.path.exists(live_db), "Live database must exist")
        import sqlite3
        conn = sqlite3.connect(live_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM episodes;")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertGreaterEqual(count, 10, "Existing 10 episodes must be preserved")


if __name__ == "__main__":
    unittest.main()
