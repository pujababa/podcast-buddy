import os
import sys
import json
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import app
import backend.models.database as db_module
import backend.config as config_module
from backend.models.database import (
    init_db,
    get_db_connection,
    create_episode,
    get_episode,
    list_episodes,
    update_episode_podcast_script,
    update_episode_audio
)
from backend.services.audio_processor import (
    AudioProcessor,
    AudioProcessingError,
    AudioPathSecurityError,
    AudioEmptyInputError,
    AudioDecodeError,
    validate_safe_audio_path
)
from backend.services.tts_service import (
    TTSService,
    tts_service,
    TTSError,
    TTSLanguageError,
    TTSScriptEmptyError,
    TTSSynthesisError,
    normalize_language,
    transliterate_odia_to_devanagari,
    VOICE_CONFIGS,
    SUPPORTED_LANGUAGES
)
from pydub import AudioSegment


# Deterministic mock podcast script fixture matching Phase 6 schema
DETERMINISTIC_MOCK_SCRIPT = {
    "intro": {
        "title": "Welcome to Podcast Buddy",
        "lines": [
            {"speaker": "host", "text": "Welcome to Podcast Buddy! Today we are looking at the latest news."},
            {"speaker": "cohost", "text": "Excited to be here. What is our first major story?"}
        ]
    },
    "segments": [
        {
            "title": "Major Breakthrough in AI Technology",
            "lines": [
                {"speaker": "host", "text": "According to verified reports, new efficiency gains have emerged."},
                {"speaker": "cohost", "text": "That matches what independent sources were reporting earlier this week."}
            ]
        }
    ],
    "key_takeaways": [
        {"speaker": "host", "text": "The main takeaway is that technology is moving at rapid pace."},
        {"speaker": "cohost", "text": "And staying informed with verified sources is essential."}
    ],
    "outro": {
        "lines": [
            {"speaker": "host", "text": "That wraps up today's breakdown on Podcast Buddy."},
            {"speaker": "cohost", "text": "Thanks for tuning in. See you next time!"}
        ]
    }
}


def create_deterministic_dummy_wav(path: str, duration_ms: int = 150) -> str:
    """Create a real, deterministic WAV audio file fixture for testing without external calls."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    seg = AudioSegment.silent(duration=duration_ms, frame_rate=24000)
    seg.export(path, format="wav")
    return path


class TestPhase7AudioGeneration(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for isolated test DB and generated audio
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.test_db_path = os.path.join(self.temp_dir.name, "test_podcast_buddy.db")
        self.test_audio_dir = os.path.join(self.temp_dir.name, "test_generated_audio")
        os.makedirs(self.test_audio_dir, exist_ok=True)

        # Patch module-level database and audio output directory
        self.db_patcher = patch.object(db_module, "DATABASE_PATH", self.test_db_path)
        self.audio_dir_patcher = patch.object(config_module, "AUDIO_OUTPUT_DIR", self.test_audio_dir)
        self.route_audio_patcher = patch("backend.routes.episodes.AUDIO_OUTPUT_DIR", self.test_audio_dir)
        self.tts_dir_patcher = patch.object(tts_service, "output_dir", self.test_audio_dir)

        self.db_patcher.start()
        self.audio_dir_patcher.start()
        self.route_audio_patcher.start()
        self.tts_dir_patcher.start()

        # Initialize isolated schema
        init_db(self.test_db_path)

        # Flask test client
        self.app = app
        self.app.testing = True
        self.client = self.app.test_client()

        # Seed sample episode
        sample_articles = [
            {
                "id": "art-1",
                "title": "AI Technology Advances",
                "publisher": "Tech Daily",
                "snippet": "Researchers announced major advancements.",
                "url": "https://example.com/ai-advances",
                "date": "2026-10-06"
            }
        ]
        self.episode = create_episode(
            title="Episode 1: AI Revolution",
            description="Discussion of latest AI advances.",
            articles=sample_articles,
            db_path=self.test_db_path
        )
        self.episode_id = self.episode["id"]

        # Attach Phase 6 script to episode
        update_episode_podcast_script(
            episode_id=self.episode_id,
            script_status="completed",
            podcast_script=DETERMINISTIC_MOCK_SCRIPT,
            generated_at="2026-10-06T12:00:00Z",
            db_path=self.test_db_path
        )

    def tearDown(self):
        self.tts_dir_patcher.stop()
        self.route_audio_patcher.stop()
        self.audio_dir_patcher.stop()
        self.db_patcher.stop()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Helper to create deterministic mock TTS result
    # -------------------------------------------------------------------------
    def _create_mock_audio_result(self, lang: str = "english"):
        filename = f"episode_{self.episode_id}_{lang}_test.mp3"
        full_path = os.path.join(self.test_audio_dir, filename)
        create_deterministic_dummy_wav(full_path, duration_ms=400)
        return {
            "episode_id": self.episode_id,
            "language": lang,
            "audio_path": filename,
            "full_path": full_path,
            "filename": filename,
            "duration_ms": 400,
            "file_size": os.path.getsize(full_path),
            "format": "mp3",
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    # -------------------------------------------------------------------------
    # 1. English Audio Generation Test
    # -------------------------------------------------------------------------
    def test_english_audio_generation(self):
        """Verify successful English audio generation with deterministic mocked TTS service."""
        mock_result = self._create_mock_audio_result(lang="english")

        with patch.object(tts_service, "generate_podcast_audio", return_value=mock_result) as mock_gen:
            response = self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "english"}),
                content_type="application/json"
            )

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["audio_status"], "completed")
            self.assertEqual(data["audio_language"], "english")
            self.assertEqual(data["audio_url"], f"/api/episodes/{self.episode_id}/audio")
            self.assertIn(".mp3", data["audio_path"])
            self.assertEqual(data["format"], "mp3")

            mock_gen.assert_called_once_with(
                episode_id=self.episode_id,
                script=DETERMINISTIC_MOCK_SCRIPT,
                language="english"
            )

    # -------------------------------------------------------------------------
    # 2. Hindi Audio Generation Test
    # -------------------------------------------------------------------------
    def test_hindi_audio_generation(self):
        """Verify successful Hindi audio generation."""
        mock_result = self._create_mock_audio_result(lang="hindi")

        with patch.object(tts_service, "generate_podcast_audio", return_value=mock_result) as mock_gen:
            response = self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "hindi"}),
                content_type="application/json"
            )

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["audio_language"], "hindi")
            self.assertEqual(data["audio_status"], "completed")

            mock_gen.assert_called_once_with(
                episode_id=self.episode_id,
                script=DETERMINISTIC_MOCK_SCRIPT,
                language="hindi"
            )

    # -------------------------------------------------------------------------
    # 3. Odia Audio Generation Test
    # -------------------------------------------------------------------------
    def test_odia_audio_generation(self):
        """Verify successful Odia audio generation."""
        mock_result = self._create_mock_audio_result(lang="odia")

        with patch.object(tts_service, "generate_podcast_audio", return_value=mock_result) as mock_gen:
            response = self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "odia"}),
                content_type="application/json"
            )

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["audio_language"], "odia")
            self.assertEqual(data["audio_status"], "completed")

            mock_gen.assert_called_once_with(
                episode_id=self.episode_id,
                script=DETERMINISTIC_MOCK_SCRIPT,
                language="odia"
            )

    # -------------------------------------------------------------------------
    # 4. Hinglish Audio Generation Test
    # -------------------------------------------------------------------------
    def test_hinglish_audio_generation(self):
        """Verify successful Hinglish audio generation."""
        mock_result = self._create_mock_audio_result(lang="hinglish")

        with patch.object(tts_service, "generate_podcast_audio", return_value=mock_result) as mock_gen:
            response = self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "hinglish"}),
                content_type="application/json"
            )

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["audio_language"], "hinglish")
            self.assertEqual(data["audio_status"], "completed")

            mock_gen.assert_called_once_with(
                episode_id=self.episode_id,
                script=DETERMINISTIC_MOCK_SCRIPT,
                language="hinglish"
            )

    # -------------------------------------------------------------------------
    # 5. Invalid Language Test
    # -------------------------------------------------------------------------
    def test_invalid_language_returns_400(self):
        """Verify that an unsupported language returns HTTP 400 with descriptive error."""
        response = self.client.post(
            f"/api/episodes/{self.episode_id}/generate-audio",
            data=json.dumps({"language": "klingon"}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["code"], "INVALID_LANGUAGE")
        self.assertIn("klingon", data["error"])

    # -------------------------------------------------------------------------
    # 6. Missing Episode Test
    # -------------------------------------------------------------------------
    def test_missing_episode_returns_404(self):
        """Verify that attempting to generate audio for non-existent episode returns 404."""
        response = self.client.post(
            "/api/episodes/99999/generate-audio",
            data=json.dumps({"language": "english"}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["code"], "NOT_FOUND")

    # -------------------------------------------------------------------------
    # 7. Missing Podcast Script Test
    # -------------------------------------------------------------------------
    def test_missing_podcast_script_returns_400(self):
        """Verify that attempting audio generation before script generation returns 400."""
        # Create fresh episode without script
        fresh_ep = create_episode(
            title="Scriptless Episode",
            description="No script generated yet",
            articles=[],
            db_path=self.test_db_path
        )

        response = self.client.post(
            f"/api/episodes/{fresh_ep['id']}/generate-audio",
            data=json.dumps({"language": "english"}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["code"], "SCRIPT_REQUIRED")

    # -------------------------------------------------------------------------
    # 8. TTS Failure Test
    # -------------------------------------------------------------------------
    def test_tts_failure_handling(self):
        """Verify that TTS service failure returns 502 and persists failed status in database."""
        with patch.object(
            tts_service,
            "generate_podcast_audio",
            side_effect=TTSSynthesisError("TTS synthesis engine network timeout")
        ):
            response = self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "english"}),
                content_type="application/json"
            )

            self.assertEqual(response.status_code, 502)
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertEqual(data["code"], "TTS_ERROR")

            # Verify database persistence of failed status
            ep = get_episode(self.episode_id, db_path=self.test_db_path)
            self.assertEqual(ep["audio_status"], "failed")
            self.assertIn("network timeout", ep["audio_error"])

    # -------------------------------------------------------------------------
    # 9. Audio-Processing Failure Test
    # -------------------------------------------------------------------------
    def test_audio_processing_failure_handling(self):
        """Verify that audio processor failure returns 500 and updates DB status."""
        with patch.object(
            tts_service,
            "generate_podcast_audio",
            side_effect=AudioProcessingError("Corrupted audio frame encountered during merge")
        ):
            response = self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "english"}),
                content_type="application/json"
            )

            self.assertEqual(response.status_code, 500)
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertEqual(data["code"], "AUDIO_PROCESSING_ERROR")

            # Verify database persistence of failed status
            ep = get_episode(self.episode_id, db_path=self.test_db_path)
            self.assertEqual(ep["audio_status"], "failed")
            self.assertIn("Corrupted audio frame", ep["audio_error"])

    # -------------------------------------------------------------------------
    # 10. Database Persistence Test
    # -------------------------------------------------------------------------
    def test_database_persistence_of_audio_fields(self):
        """Verify that audio_status, audio_language, audio_path, timestamp, and errors persist in database."""
        mock_result = self._create_mock_audio_result(lang="hindi")

        with patch.object(tts_service, "generate_podcast_audio", return_value=mock_result):
            self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "hindi"}),
                content_type="application/json"
            )

        # Inspect database record
        ep = get_episode(self.episode_id, db_path=self.test_db_path)
        self.assertEqual(ep["audio_status"], "completed")
        self.assertEqual(ep["audio_language"], "hindi")
        self.assertEqual(ep["audio_path"], mock_result["audio_path"])
        self.assertIsNotNone(ep["audio_generated_at"])
        self.assertIsNone(ep["audio_error"])

        # Also inspect via list_episodes
        ep_list = list_episodes(db_path=self.test_db_path)
        found = next((e for e in ep_list if e["id"] == self.episode_id), None)
        self.assertIsNotNone(found)
        self.assertEqual(found["audio_status"], "completed")
        self.assertEqual(found["audio_language"], "hindi")

    # -------------------------------------------------------------------------
    # 11. Repeated Audio Generation Test
    # -------------------------------------------------------------------------
    def test_repeated_audio_generation_does_not_corrupt_data(self):
        """Verify repeated audio generation overwrites cleanly without data corruption."""
        mock_en = self._create_mock_audio_result(lang="english")
        mock_hi = self._create_mock_audio_result(lang="hindi")

        # First run: English
        with patch.object(tts_service, "generate_podcast_audio", return_value=mock_en):
            res1 = self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "english"}),
                content_type="application/json"
            )
            self.assertEqual(res1.status_code, 200)

        ep_after_en = get_episode(self.episode_id, db_path=self.test_db_path)
        self.assertEqual(ep_after_en["audio_language"], "english")

        # Second run: Hindi
        with patch.object(tts_service, "generate_podcast_audio", return_value=mock_hi):
            res2 = self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "hindi"}),
                content_type="application/json"
            )
            self.assertEqual(res2.status_code, 200)

        ep_after_hi = get_episode(self.episode_id, db_path=self.test_db_path)
        self.assertEqual(ep_after_hi["audio_language"], "hindi")
        self.assertEqual(ep_after_hi["audio_path"], mock_hi["audio_path"])
        # Original script and intelligence must remain intact
        self.assertIsNotNone(ep_after_hi["podcast_script"])
        self.assertEqual(ep_after_hi["script_status"], "completed")

    # -------------------------------------------------------------------------
    # 12. Audio Retrieval Endpoint (GET /api/episodes/<id>/audio) Tests
    # -------------------------------------------------------------------------
    def test_get_audio_file_success(self):
        """Verify GET /api/episodes/<id>/audio returns 200 and audio file stream."""
        mock_result = self._create_mock_audio_result(lang="english")

        with patch.object(tts_service, "generate_podcast_audio", return_value=mock_result):
            self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "english"}),
                content_type="application/json"
            )

        res = self.client.get(f"/api/episodes/{self.episode_id}/audio")
        self.assertEqual(res.status_code, 200)
        self.assertIn("audio/", res.content_type)
        self.assertGreater(len(res.data), 0)

    def test_get_audio_file_unready_returns_404(self):
        """Verify GET /api/episodes/<id>/audio returns 404 when audio has not been generated."""
        res = self.client.get(f"/api/episodes/{self.episode_id}/audio")
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertEqual(data["code"], "AUDIO_NOT_FOUND")

    # -------------------------------------------------------------------------
    # 13. Security & Safe Path Confinement Tests
    # -------------------------------------------------------------------------
    def test_validate_safe_audio_path_rejects_directory_traversal(self):
        """Verify that validate_safe_audio_path prevents path traversal attacks."""
        base_dir = self.test_audio_dir
        evil_path = os.path.join(base_dir, "../../secret_file.wav")

        with self.assertRaises(AudioPathSecurityError):
            validate_safe_audio_path(evil_path, base_dir)

    # -------------------------------------------------------------------------
    # 14. Unit Tests for TTSService and AudioProcessor Operations
    # -------------------------------------------------------------------------
    def test_normalize_language_variants(self):
        """Verify language code aliases map accurately to supported languages."""
        self.assertEqual(normalize_language("en"), "english")
        self.assertEqual(normalize_language("ENGLISH"), "english")
        self.assertEqual(normalize_language("hi"), "hindi")
        self.assertEqual(normalize_language("or"), "odia")
        self.assertEqual(normalize_language("oriya"), "odia")
        self.assertEqual(normalize_language("hinglish"), "hinglish")

        with self.assertRaises(TTSLanguageError):
            normalize_language("french")

    def test_transliterate_odia_to_devanagari(self):
        """Verify Odia codepoints map accurately to Devanagari codepoints."""
        # Odia 'ନ' (U+0B28) -> Devanagari 'न' (U+0928)
        odia = "\u0B28\u0B2E\u0B38\u0B4D\u0B15\u0B3E\u0B30"
        deva = transliterate_odia_to_devanagari(odia)
        expected = "\u0928\u092E\u0938\u094D\u0915\u093E\u0930"
        self.assertEqual(deva, expected)

    def test_audio_processor_merges_wav_segments_properly(self):
        """Verify AudioProcessor concatenates distinct clips with silence without byte concat."""
        proc = AudioProcessor(output_dir=self.test_audio_dir)

        clip1 = create_deterministic_dummy_wav(os.path.join(self.test_audio_dir, "clip1.wav"), 100)
        clip2 = create_deterministic_dummy_wav(os.path.join(self.test_audio_dir, "clip2.wav"), 100)
        output_file = "merged_test.wav"

        result = proc.merge_audio_segments(
            audio_files=[clip1, clip2],
            output_filename_or_path=output_file,
            pause_ms=50
        )

        self.assertIn("merged_test.wav", result["output_path"])
        # Expected duration: 100ms + 50ms pause + 100ms = 250ms
        self.assertGreaterEqual(result["duration_ms"], 240)
        self.assertTrue(os.path.isfile(result["output_path"]))
        self.assertGreater(result["file_size"], 0)

    def test_audio_processor_merges_mp3_segments_properly(self):
        """Verify AudioProcessor produces an actual .mp3 file with pydub and FFmpeg."""
        proc = AudioProcessor(output_dir=self.test_audio_dir)

        clip1 = create_deterministic_dummy_wav(os.path.join(self.test_audio_dir, "clip1.wav"), 100)
        clip2 = create_deterministic_dummy_wav(os.path.join(self.test_audio_dir, "clip2.wav"), 100)
        output_file = "merged_test.mp3"

        result = proc.merge_audio_segments(
            audio_files=[clip1, clip2],
            output_filename_or_path=output_file,
            pause_ms=50
        )

        self.assertIn("merged_test.mp3", result["output_path"])
        self.assertEqual(result["format"], "mp3")
        self.assertTrue(os.path.isfile(result["output_path"]))
        self.assertTrue(result["output_path"].endswith(".mp3"))
        self.assertGreater(result["file_size"], 0)
    def test_ttsservice_dialogue_extraction_order_and_speakers(self):
        """Verify TTSService extracts Host and CoHost dialogue lines from all sections in order."""
        lines = tts_service.extract_dialogue_lines(DETERMINISTIC_MOCK_SCRIPT)
        self.assertGreater(len(lines), 0)
        # Check intro lines
        self.assertEqual(lines[0]["speaker"], "host")
        self.assertEqual(lines[0]["section"], "intro")
        self.assertEqual(lines[1]["speaker"], "cohost")
        self.assertEqual(lines[1]["section"], "intro")
        # Check segments lines
        self.assertEqual(lines[2]["speaker"], "host")
        self.assertIn("segment_", lines[2]["section"])
        self.assertEqual(lines[3]["speaker"], "cohost")
        # Check takeaways lines
        self.assertEqual(lines[4]["speaker"], "host")
        self.assertEqual(lines[4]["section"], "takeaways")
        self.assertEqual(lines[5]["speaker"], "cohost")
        # Check outro lines
        self.assertEqual(lines[6]["speaker"], "host")
        self.assertEqual(lines[6]["section"], "outro")
        self.assertEqual(lines[7]["speaker"], "cohost")

    def test_ttsservice_voice_configs_for_host_and_cohost(self):
        """Verify Host and CoHost have distinct voice configurations for each language."""
        for lang in ["english", "hindi", "odia", "hinglish"]:
            cfg = VOICE_CONFIGS.get(lang)
            self.assertIsNotNone(cfg, f"Missing voice config for {lang}")
            self.assertIn("host", cfg)
            self.assertIn("cohost", cfg)
            # Distinct configurations between host and cohost
            host_cfg = cfg["host"]
            cohost_cfg = cfg["cohost"]
            # Either different lang code or different TLD
            is_distinct = (host_cfg.get("lang") != cohost_cfg.get("lang")) or (host_cfg.get("tld") != cohost_cfg.get("tld"))
            self.assertTrue(is_distinct, f"Host and CoHost configs should be distinct for {lang}")

    def test_ttsservice_generates_mp3_end_to_end_all_languages(self):
        """Verify TTSService produces actual .mp3 files across English, Hindi, Odia, and Hinglish."""
        def dummy_synth(text, speaker, language, output_path):
            seg = AudioSegment.silent(duration=50, frame_rate=24000)
            seg.export(output_path, format="mp3")
            return output_path

        with patch.object(tts_service, "synthesize_line", side_effect=dummy_synth):
            for lang in ["english", "hindi", "odia", "hinglish"]:
                result = tts_service.generate_podcast_audio(
                    episode_id=self.episode_id,
                    script=DETERMINISTIC_MOCK_SCRIPT,
                    language=lang,
                    output_dir=self.test_audio_dir
                )
                self.assertEqual(result["format"], "mp3")
                self.assertEqual(result["language"], lang)
                self.assertTrue(result["filename"].endswith(".mp3"))
                self.assertTrue(os.path.isfile(result["full_path"]))
                self.assertGreater(result["file_size"], 0)
                self.assertGreater(result["duration_ms"], 0)

    def test_api_generate_audio_endpoint_with_tts_service_integration(self):
        """Verify /api/episodes/<id>/generate-audio and /api/episodes/<id>/audio work end-to-end with MP3."""
        def dummy_synth(text, speaker, language, output_path):
            seg = AudioSegment.silent(duration=50, frame_rate=24000)
            seg.export(output_path, format="mp3")
            return output_path

        with patch.object(tts_service, "synthesize_line", side_effect=dummy_synth):
            response = self.client.post(
                f"/api/episodes/{self.episode_id}/generate-audio",
                data=json.dumps({"language": "hinglish"}),
                content_type="application/json"
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["audio_status"], "completed")
            self.assertEqual(data["audio_language"], "hinglish")
            self.assertEqual(data["format"], "mp3")
            self.assertTrue(data["audio_path"].endswith(".mp3"))

            # Verify database persistence
            ep = get_episode(self.episode_id, db_path=self.test_db_path)
            self.assertEqual(ep["audio_status"], "completed")
            self.assertEqual(ep["audio_language"], "hinglish")
            self.assertEqual(ep["audio_path"], data["audio_path"])
            self.assertIsNotNone(ep["audio_generated_at"])
            self.assertIsNone(ep["audio_error"])

            # Verify GET audio stream for frontend player
            audio_res = self.client.get(f"/api/episodes/{self.episode_id}/audio")
            self.assertEqual(audio_res.status_code, 200)
            self.assertEqual(audio_res.content_type, "audio/mpeg")
            self.assertGreater(len(audio_res.data), 0)

    def test_odia_tts_provider_limitation_raises_error(self):
        """Verify that TTSService.synthesize_line for Odia transparently raises TTSSynthesisError when credentials not set."""
        with patch("backend.services.tts_service.SARVAM_API_KEY", ""):
            with patch.dict(os.environ, {"SARVAM_API_KEY": "", "TTS_API_KEY": ""}):
                with self.assertRaises(TTSSynthesisError) as ctx:
                    tts_service.synthesize_line(
                        text="Namaskar",
                        speaker="host",
                        language="odia",
                        output_path=os.path.join(self.test_audio_dir, "test_odia.mp3")
                    )
                self.assertIn("Odia ('or') speech synthesis is not supported", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


