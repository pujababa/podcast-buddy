
"""
Unit tests for Phase 1 enhancements:
1. Audio Download MP3 endpoint (?download=1)
2. Audio Duration computation and formatting (MM:SS / HH:MM:SS)
3. Audio File Cleanup on Episode Deletion (isolated to targeted episode only)
4. Missing audio file handling during deletion
"""
import os
import sys
import unittest
import tempfile
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app import app
from backend.routes.episodes import (
    format_audio_duration,
    enrich_episode_computed_fields,
    AUDIO_OUTPUT_DIR
)
from backend.models.database import (
    init_db,
    create_episode,
    get_episode,
    delete_episode
)


class TestPhase1Enhancements(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_audio_duration_formatting(self):
        """Verify format_audio_duration handles various second ranges correctly."""
        self.assertEqual(format_audio_duration(45), "00:45")
        self.assertEqual(format_audio_duration(167.59), "02:48")
        self.assertEqual(format_audio_duration(3600), "01:00:00")
        self.assertEqual(format_audio_duration(3665), "01:01:05")
        self.assertIsNone(format_audio_duration(0))
        self.assertIsNone(format_audio_duration(None))
        self.assertIsNone(format_audio_duration(-10))

    def test_enrich_episode_includes_duration(self):
        """Verify enrich_episode_computed_fields attaches duration metadata."""
        ep = get_episode(10)
        if ep:
            enriched = enrich_episode_computed_fields(ep)
            self.assertIn("audio_duration_seconds", enriched)
            self.assertIn("audio_duration_formatted", enriched)
            self.assertIsNotNone(enriched["audio_duration_seconds"])
            self.assertEqual(enriched["audio_duration_formatted"], "02:48")

    def test_audio_download_endpoint(self):
        """Verify ?download=1 returns Content-Disposition attachment header."""
        resp = self.client.get("/api/episodes/10/audio?lang=odia&download=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "audio/mpeg")
        cd = resp.headers.get("Content-Disposition", "")
        self.assertIn("attachment", cd)
        self.assertIn("podcast_buddy_ep10_odia", cd)
        self.assertIn(".mp3", cd)

    def test_audio_file_cleanup_on_delete_isolated(self):
        """Verify deleting an episode only deletes its own audio files and never others."""
        target_ep_id = 99998
        other_ep_id = 999980  # Similar prefix that must NOT be deleted

        # Create dummy audio files in AUDIO_OUTPUT_DIR
        target_file1 = os.path.join(AUDIO_OUTPUT_DIR, f"episode_{target_ep_id}_odia_test.mp3")
        target_file2 = os.path.join(AUDIO_OUTPUT_DIR, f"episode_{target_ep_id}_hindi_test.mp3")
        other_file = os.path.join(AUDIO_OUTPUT_DIR, f"episode_{other_ep_id}_english_test.mp3")

        with open(target_file1, "wb") as f:
            f.write(b"dummy_target_1")
        with open(target_file2, "wb") as f:
            f.write(b"dummy_target_2")
        with open(other_file, "wb") as f:
            f.write(b"dummy_other")

        try:
            # Create a test episode in the database
            created_ep = create_episode(
                title="Temporary Test Episode for Cleanup",
                description="Testing audio cleanup",
                articles=[]
            )
            created_id = created_ep["id"]

            # Create an audio file matching created_id
            created_audio = os.path.join(AUDIO_OUTPUT_DIR, f"episode_{created_id}_odia_cleanup.mp3")
            with open(created_audio, "wb") as f:
                f.write(b"dummy_created_audio")

            # Call delete endpoint
            del_resp = self.client.delete(f"/api/episodes/{created_id}")
            self.assertEqual(del_resp.status_code, 200)
            data = del_resp.get_json()
            self.assertTrue(data.get("success"))
            self.assertGreaterEqual(data.get("audio_files_removed", 0), 1)

            # Assert created_audio was removed
            self.assertFalse(os.path.exists(created_audio))

            # Assert unrelated files were completely untouched
            self.assertTrue(os.path.exists(target_file1))
            self.assertTrue(os.path.exists(target_file2))
            self.assertTrue(os.path.exists(other_file))

        finally:
            # Clean up dummy test files
            for p in (target_file1, target_file2, other_file):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    def test_audio_cleanup_handles_missing_files_gracefully(self):
        """Verify deleting an episode whose audio files are already missing succeeds gracefully."""
        created_ep = create_episode(
            title="Episode with No Audio On Disk",
            description="Testing graceful missing audio",
            articles=[]
        )
        created_id = created_ep["id"]

        del_resp = self.client.delete(f"/api/episodes/{created_id}")
        self.assertEqual(del_resp.status_code, 200)
        data = del_resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("audio_files_removed"), 0)


if __name__ == "__main__":
    unittest.main()
