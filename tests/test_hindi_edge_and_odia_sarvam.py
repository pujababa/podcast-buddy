"""
tests/test_hindi_edge_and_odia_sarvam.py

Comprehensive test suite verifying:
1. Microsoft Edge Neural Hindi TTS (hi-IN-MadhurNeural, hi-IN-SwaraNeural)
2. Genuine Odia TTS provider interface via Sarvam AI (od-IN) with credentials handling
3. Gemini structured dialogue generation script verification (Devanagari for Hindi, Odia script for Odia)
4. End-to-end audio lifecycle, switching tracks, clearing stale audio, and failure states
"""

import os
import sys
import json
import base64
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydub import AudioSegment
from backend.app import app
import backend.models.database as db_module
from backend.models.database import (
    init_db,
    get_db_connection,
    create_episode,
    get_episode,
    update_episode_ai_intelligence,
    update_episode_podcast_script,
    update_episode_audio
)
from backend.services.tts_service import (
    tts_service,
    TTSService,
    VOICE_CONFIGS,
    normalize_language,
    TTSSynthesisError,
    TTSLanguageError
)
from backend.services.script_generator import (
    script_generator,
    generate_podcast_script,
    build_script_generation_prompt,
    validate_and_normalize_script,
    validate_script_language,
    ScriptValidationError,
    ScriptGenerationError
)
from backend.routes.episodes import enrich_episode_computed_fields

HINDI_DEVANAGARI_SCRIPT = {
    "intro": {
        "title": "आज का पॉडकास्ट",
        "lines": [
            {"speaker": "host", "text": "नमस्ते दोस्तों, पॉडकास्ट बडी में आप सभी का स्वागत है।"},
            {"speaker": "cohost", "text": "धन्यवाद! आज हम कृत्रिम बुद्धिमत्ता के नए विकास पर बात करेंगे।"}
        ]
    },
    "segments": [
        {
            "title": "मुख्य समाचार",
            "lines": [
                {"speaker": "host", "text": "प्रौद्योगिकी जगत में आज कई महत्वपूर्ण घोषणाएं हुई हैं।"},
                {"speaker": "cohost", "text": "जी हां, शोधकर्ताओं ने नए मॉडल्स के बारे में जानकारी साझा की है।"}
            ]
        }
    ],
    "key_takeaways": [
        {"speaker": "host", "text": "पहली मुख्य बात यह है कि मॉडल अधिक कुशल और तेज हैं।"},
        {"speaker": "cohost", "text": "और दूसरी बात यह कि स्थानीय भाषाओं में समझ काफी बेहतर हुई है।"}
    ],
    "outro": {
        "lines": [
            {"speaker": "host", "text": "आज के एपिसोड में बस इतना ही।"},
            {"speaker": "cohost", "text": "पॉडकास्ट बडी सुनने के लिए आपका बहुत-बहुत धन्यवाद।"}
        ]
    }
}

ODIA_SCRIPT_VALID = {
    "intro": {
        "title": "ଆଜିର ପଡ଼କାଷ୍ଟ",
        "lines": [
            {"speaker": "host", "text": "ନମସ୍କାର ବନ୍ଧୁଗଣ, ପଡ଼କାଷ୍ଟ ବଡିକୁ ସ୍ୱାଗତ।"},
            {"speaker": "cohost", "text": "ଧନ୍ୟବାଦ! ଆଜି ଆମେ ନୂତନ ଖବର ଉପରେ ଆଲୋଚନା କରିବା।"}
        ]
    },
    "segments": [
        {
            "title": "ମୁଖ୍ୟ ଖବର",
            "lines": [
                {"speaker": "host", "text": "ପ୍ରଯୁକ୍ତିବିଦ୍ୟା କ୍ଷେତ୍ରରେ ଅନେକ ପରିବର୍ତ୍ତନ ଦେଖାଦେଇଛି।"},
                {"speaker": "cohost", "text": "ହଁ, ଏହା ବହୁତ ଉପଯୋଗୀ ଏବଂ ଗୁରୁତ୍ୱପୂର୍ଣ୍ଣ ସୂଚନା।"}
            ]
        }
    ],
    "key_takeaways": [
        {"speaker": "host", "text": "ପ୍ରଥମ ବିନ୍ଦୁ ହେଉଛି ଉନ୍ନତ ପ୍ରଦର୍ଶନ।"},
        {"speaker": "cohost", "text": "ଦ୍ୱିତୀୟ ବିନ୍ଦୁ ହେଉଛି ସଠିକ୍ ପରିଚାଳନା।"}
    ],
    "outro": {
        "lines": [
            {"speaker": "host", "text": "ଆଜି ପାଇଁ ଏତିକି।"},
            {"speaker": "cohost", "text": "ପଡ଼କାଷ୍ଟ ବଡି ଶୁଣିଥିବାରୁ ଆପଣଙ୍କୁ ଅଶେଷ ଧନ୍ୟବାଦ।"}
        ]
    }
}

MOCK_INTELLIGENCE = {
    "overview": "Technology models are advancing rapidly.",
    "key_points": ["First point verified.", "Second point verified."],
    "important_facts": ["Fact 1 verified."],
    "entities": [{"name": "AI Lab", "type": "organization", "context": "Researcher"}],
    "topics": ["Technology", "AI"],
    "source_insights": [{"source_id": "s1", "summary": "Summary", "key_claims": ["Claim"]}],
    "confidence": "high",
    "limitations": ["Based on sources."]
}


class TestHindiEdgeNeuralTTS(unittest.TestCase):
    """Test 1: Verification of Microsoft Edge Neural Hindi TTS integration."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tts = TTSService(output_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_hindi_voice_configuration(self):
        """Verify Hindi voice configuration uses verified Microsoft Edge Neural voices."""
        hi_cfg = VOICE_CONFIGS.get("hindi")
        self.assertIsNotNone(hi_cfg)
        self.assertEqual(hi_cfg["host"]["voice"], "hi-IN-MadhurNeural")
        self.assertEqual(hi_cfg["host"]["gender"], "male")
        self.assertEqual(hi_cfg["host"]["provider"], "edge-tts")
        self.assertEqual(hi_cfg["cohost"]["voice"], "hi-IN-SwaraNeural")
        self.assertEqual(hi_cfg["cohost"]["gender"], "female")
        self.assertEqual(hi_cfg["cohost"]["provider"], "edge-tts")

    def test_real_edge_tts_hindi_audio_generation(self):
        """Perform real speech synthesis using edge-tts with Devanagari Hindi text."""
        out_host = os.path.join(self.temp_dir.name, "host_hindi_test.mp3")
        out_cohost = os.path.join(self.temp_dir.name, "cohost_hindi_test.mp3")

        # Synthesize Host turn in Devanagari
        path1 = self.tts.synthesize_line(
            text="नमस्ते, पॉडकास्ट बडी में आपका स्वागत है।",
            speaker="host",
            language="hindi",
            output_path=out_host
        )
        self.assertTrue(os.path.exists(path1))
        self.assertGreater(os.path.getsize(path1), 5000)

        # Synthesize CoHost turn in Devanagari
        path2 = self.tts.synthesize_line(
            text="धन्यवाद, आज की मुख्य खबरों का विश्लेषण करते हैं।",
            speaker="cohost",
            language="hindi",
            output_path=out_cohost
        )
        self.assertTrue(os.path.exists(path2))
        self.assertGreater(os.path.getsize(path2), 5000)

        # Validate MP3 audio with pydub
        seg1 = AudioSegment.from_file(path1, format="mp3")
        seg2 = AudioSegment.from_file(path2, format="mp3")
        self.assertGreater(len(seg1), 500)  # At least 0.5 seconds
        self.assertGreater(len(seg2), 500)


class TestOdiaTTSProvider(unittest.TestCase):
    """Test 2: Verification of genuine Odia TTS provider interface via Sarvam AI."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tts = TTSService(output_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_odia_voice_configuration(self):
        """Verify Odia voice configuration targets Sarvam AI Bulbul provider with od-IN."""
        odia_cfg = VOICE_CONFIGS.get("odia")
        self.assertIsNotNone(odia_cfg)
        self.assertEqual(odia_cfg["host"]["provider"], "sarvam")
        self.assertEqual(odia_cfg["host"]["target_language_code"], "od-IN")
        self.assertEqual(odia_cfg["cohost"]["provider"], "sarvam")
        self.assertEqual(odia_cfg["cohost"]["target_language_code"], "od-IN")

    def test_odia_tts_without_credentials_reports_exact_setup_requirement(self):
        """Verify that when SARVAM_API_KEY is not configured, a clear error reports setup instructions."""
        out_file = os.path.join(self.temp_dir.name, "odia_no_key.mp3")
        with patch("backend.services.tts_service.SARVAM_API_KEY", ""):
            with patch.dict(os.environ, {"SARVAM_API_KEY": "", "TTS_API_KEY": ""}):
                with self.assertRaises(TTSSynthesisError) as ctx:
                    self.tts.synthesize_line(
                        text="ନମସ୍କାର ବନ୍ଧୁଗଣ",
                        speaker="host",
                        language="odia",
                        output_path=out_file
                    )
            err_msg = str(ctx.exception)
            self.assertIn("Odia", err_msg)
            self.assertIn("Sarvam AI", err_msg)
            self.assertIn("SARVAM_API_KEY", err_msg)
            self.assertIn("dashboard.sarvam.ai", err_msg)

    def test_odia_tts_with_mocked_sarvam_api(self):
        """Verify that when SARVAM_API_KEY is present, request payload and audio bytes are correctly processed."""
        out_file = os.path.join(self.temp_dir.name, "odia_mocked.mp3")
        # 1-second silent MP3 encoded as base64
        dummy_mp3 = AudioSegment.silent(duration=500, frame_rate=22050)
        temp_export = os.path.join(self.temp_dir.name, "dummy.mp3")
        dummy_mp3.export(temp_export, format="mp3")
        with open(temp_export, "rb") as f:
            b64_audio = base64.b64encode(f.read()).decode("utf-8")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"audios": [b64_audio]}

        with patch("backend.services.tts_service.SARVAM_API_KEY", "mock-sarvam-key"):
            with patch.dict(os.environ, {"SARVAM_API_KEY": "mock-sarvam-key"}):
                with patch("requests.post", return_value=mock_resp) as mock_post:
                    path = self.tts.synthesize_line(
                        text="ନମସ୍କାର ବନ୍ଧୁଗଣ",
                        speaker="host",
                        language="odia",
                        output_path=out_file
                    )
                    self.assertTrue(os.path.exists(path))
                    self.assertGreater(os.path.getsize(path), 0)

                    # Verify payload sent to Sarvam AI
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    headers = call_args[1]["headers"]
                    payload = call_args[1]["json"]
                    self.assertEqual(headers["api-subscription-key"], "mock-sarvam-key")
                    self.assertEqual(payload["target_language_code"], "od-IN")
                    self.assertEqual(payload["text"], "ନମସ୍କାର ବନ୍ଧୁଗଣ")

    def test_odia_tts_invalid_credentials_error_message(self):
        """Verify that invalid/expired credentials report actionable error and never expose secret."""
        out_file = os.path.join(self.temp_dir.name, "odia_invalid_key.mp3")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized: Invalid subscription key super-secret-sarvam-key-12345"

        with patch("backend.services.tts_service.SARVAM_API_KEY", "super-secret-sarvam-key-12345"):
            with patch.dict(os.environ, {"SARVAM_API_KEY": "super-secret-sarvam-key-12345"}):
                with patch("requests.post", return_value=mock_resp):
                    with self.assertRaises(TTSSynthesisError) as ctx:
                        self.tts.synthesize_line(
                            text="ନମସ୍କାର",
                            speaker="host",
                            language="odia",
                            output_path=out_file
                        )
                    err_msg = str(ctx.exception)
                    self.assertIn("authentication failed", err_msg.lower())
                    self.assertIn("dashboard.sarvam.ai", err_msg)
                    # Ensure secret key is strictly NOT exposed in exception
                    self.assertNotIn("super-secret-sarvam-key-12345", err_msg)

    def test_odia_tts_rate_limit_error_message(self):
        """Verify that 429 response reports rate limit / quota exceeded."""
        out_file = os.path.join(self.temp_dir.name, "odia_rate_limit.mp3")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"

        with patch("backend.services.tts_service.SARVAM_API_KEY", "mock-sarvam-key"):
            with patch("requests.post", return_value=mock_resp):
                with self.assertRaises(TTSSynthesisError) as ctx:
                    self.tts.synthesize_line(
                        text="ନମସ୍କାର",
                        speaker="host",
                        language="odia",
                        output_path=out_file
                    )
                err_msg = str(ctx.exception)
                self.assertIn("rate limit", err_msg.lower())
                self.assertIn("dashboard.sarvam.ai", err_msg)

    def test_odia_tts_secret_key_redacted_in_exceptions(self):
        """Verify that network exceptions containing API keys are redacted before surfacing."""
        import requests
        out_file = os.path.join(self.temp_dir.name, "odia_net_err.mp3")
        sensitive_key = "super-secret-sarvam-key-99999"

        with patch("backend.services.tts_service.SARVAM_API_KEY", sensitive_key):
            with patch.dict(os.environ, {"SARVAM_API_KEY": sensitive_key}):
                with patch("requests.post", side_effect=requests.RequestException(f"Connection error with key {sensitive_key}")):
                    with self.assertRaises(TTSSynthesisError) as ctx:
                        self.tts.synthesize_line(
                            text="ନମସ୍କାର",
                            speaker="host",
                            language="odia",
                            output_path=out_file
                        )
                    err_msg = str(ctx.exception)
                    self.assertNotIn(sensitive_key, err_msg)
                    self.assertIn("[REDACTED_API_KEY]", err_msg)

    def test_dynamic_env_reload_for_sarvam_api_key(self):
        """Verify that when os.environ or .env provides SARVAM_API_KEY, it is dynamically resolved."""
        out_file = os.path.join(self.temp_dir.name, "odia_dyn.mp3")
        dummy_mp3 = AudioSegment.silent(duration=500, frame_rate=22050)
        temp_export = os.path.join(self.temp_dir.name, "dummy_dyn.mp3")
        dummy_mp3.export(temp_export, format="mp3")
        with open(temp_export, "rb") as f:
            b64_audio = base64.b64encode(f.read()).decode("utf-8")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"audios": [b64_audio]}

        with patch("backend.services.tts_service.SARVAM_API_KEY", ""):
            with patch.dict(os.environ, {"SARVAM_API_KEY": "runtime-injected-key"}):
                with patch("requests.post", return_value=mock_resp) as mock_post:
                    path = self.tts.synthesize_line(
                        text="ଶୁଭ ସକାଳ",
                        speaker="host",
                        language="odia",
                        output_path=out_file
                    )
                    self.assertTrue(os.path.exists(path))
                    mock_post.assert_called_once()
                    self.assertEqual(mock_post.call_args[1]["headers"]["api-subscription-key"], "runtime-injected-key")


class TestGeminiScriptLanguageValidation(unittest.TestCase):
    """Test 3: Verification that Gemini output is verified for actual script characters."""

    def test_hindi_script_validation_accepts_devanagari(self):
        """Verify valid Devanagari Hindi script passes validation."""
        result = validate_and_normalize_script(HINDI_DEVANAGARI_SCRIPT, language="hindi")
        self.assertEqual(result["language"], "hindi")
        self.assertEqual(len(result["segments"]), 1)

    def test_hindi_script_validation_rejects_latin_script(self):
        """Verify English/Latin script pretending to be Hindi is rejected with ScriptValidationError."""
        latin_hindi = {
            "intro": {
                "title": "Intro",
                "lines": [
                    {"speaker": "host", "text": "Namaste dosto, welcome to Podcast Buddy."},
                    {"speaker": "cohost", "text": "Dhanyawaad, aaj hum AI ke bare me baat karenge."}
                ]
            },
            "segments": [
                {
                    "title": "Segment",
                    "lines": [
                        {"speaker": "host", "text": "Ye news bohot important hai."},
                        {"speaker": "cohost", "text": "Bilkool sahi kaha aapne."}
                    ]
                }
            ],
            "key_takeaways": [
                {"speaker": "host", "text": "Pehla takeaway ye hai."},
                {"speaker": "cohost", "text": "Dusra takeaway ye hai."}
            ],
            "outro": {
                "lines": [
                    {"speaker": "host", "text": "Shukriya."},
                    {"speaker": "cohost", "text": "Alvida."}
                ]
            }
        }
        with self.assertRaises(ScriptValidationError) as ctx:
            validate_and_normalize_script(latin_hindi, language="hindi")
        self.assertIn("Devanagari script", str(ctx.exception))

    def test_odia_script_validation_accepts_odia(self):
        """Verify valid Odia script passes validation."""
        result = validate_and_normalize_script(ODIA_SCRIPT_VALID, language="odia")
        self.assertEqual(result["language"], "odia")
        self.assertEqual(len(result["segments"]), 1)

    def test_odia_script_validation_rejects_non_odia_script(self):
        """Verify Latin script pretending to be Odia is rejected with ScriptValidationError."""
        latin_odia = {
            "intro": {
                "title": "Intro",
                "lines": [
                    {"speaker": "host", "text": "Namaskar bandhugan, welcome to Podcast Buddy."},
                    {"speaker": "cohost", "text": "Dhanyabad, aji ame khabar suniba."}
                ]
            },
            "segments": [
                {
                    "title": "Segment",
                    "lines": [
                        {"speaker": "host", "text": "Aji bohut bhal khabar achhi."},
                        {"speaker": "cohost", "text": "Haa, eha bohut dorkar."}
                    ]
                }
            ],
            "key_takeaways": [
                {"speaker": "host", "text": "Pratham katha."},
                {"speaker": "cohost", "text": "Ditiya katha."}
            ],
            "outro": {
                "lines": [
                    {"speaker": "host", "text": "Dhanyabad."},
                    {"speaker": "cohost", "text": "Aji pain etiki."}
                ]
            }
        }
        with self.assertRaises(ScriptValidationError) as ctx:
            validate_and_normalize_script(latin_odia, language="odia")
        self.assertIn("Odia script", str(ctx.exception))

    def test_empty_and_malformed_script_rejected(self):
        """Verify empty responses and malformed payloads are rejected."""
        with self.assertRaises(ScriptValidationError):
            validate_and_normalize_script({})
        with self.assertRaises(ScriptValidationError):
            validate_and_normalize_script({"intro": {}})
        with self.assertRaises(ScriptValidationError):
            validate_and_normalize_script({"intro": {"lines": [{"speaker": "invalid_spk", "text": "hi"}]}})


class TestEndToEndAudioWorkflow(unittest.TestCase):
    """Test 4: End-to-end testing of generation, storage, DB status, and track switching."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "test_workflow.db")
        self.audio_dir = os.path.join(self.temp_dir.name, "generated_audio")
        os.makedirs(self.audio_dir, exist_ok=True)

        self.db_patcher = patch.object(db_module, "DATABASE_PATH", self.db_path)
        self.db_patcher.start()

        self.audio_patcher = patch("backend.routes.episodes.AUDIO_OUTPUT_DIR", self.audio_dir)
        self.audio_patcher.start()

        self.tts_audio_patcher = patch.object(tts_service, "output_dir", self.audio_dir)
        self.tts_audio_patcher.start()

        init_db(self.db_path)

        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        # Create base episode
        ep = create_episode(
            title="E2E Test Episode",
            description="Testing multi-language audio tracks",
            articles=[{
                "article_id": "art-1",
                "title": "Article 1",
                "publisher": "Tech Daily",
                "snippet": "AI innovations advancing.",
                "url": "https://example.com/art1"
            }],
            db_path=self.db_path
        )
        self.ep_id = ep["id"]

        # Mark intelligence and script completed
        update_episode_ai_intelligence(self.ep_id, "completed", MOCK_INTELLIGENCE, db_path=self.db_path)
        update_episode_podcast_script(self.ep_id, "completed", HINDI_DEVANAGARI_SCRIPT, db_path=self.db_path)

    def tearDown(self):
        self.tts_audio_patcher.stop()
        self.audio_patcher.stop()
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_hindi_audio_generation_e2e(self):
        """Verify real Hindi audio generation, file storage, database state, and API retrieval."""
        res = self.client.post(
            f"/api/episodes/{self.ep_id}/generate-audio",
            data=json.dumps({"language": "hindi"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["audio_language"], "hindi")
        self.assertEqual(data["audio_status"], "completed")

        # Verify file existence on disk
        audio_filename = data["audio_path"]
        audio_abs = os.path.join(self.audio_dir, audio_filename)
        self.assertTrue(os.path.isfile(audio_abs))
        self.assertGreater(os.path.getsize(audio_abs), 10000)

        # Verify DB status
        ep = get_episode(self.ep_id, db_path=self.db_path)
        self.assertEqual(ep["audio_status"], "completed")
        self.assertEqual(ep["audio_language"], "hindi")

        # Verify streaming endpoint with ?lang=hindi
        stream_res = self.client.get(f"/api/episodes/{self.ep_id}/audio?lang=hindi")
        self.assertEqual(stream_res.status_code, 200)
        self.assertEqual(stream_res.content_type, "audio/mpeg")

    def test_switching_language_clears_stale_audio(self):
        """Verify that requesting an ungenerated language returns 404 rather than serving stale tracks."""
        # 1. Create genuine Hindi file on disk
        hi_filename = f"episode_{self.ep_id}_hindi_20261014_100000.mp3"
        hi_path = os.path.join(self.audio_dir, hi_filename)
        dummy_mp3 = AudioSegment.silent(duration=1000, frame_rate=22050)
        dummy_mp3.export(hi_path, format="mp3")

        update_episode_audio(
            self.ep_id,
            audio_status="completed",
            audio_language="hindi",
            audio_path=hi_filename,
            db_path=self.db_path
        )

        # 2. Hindi track request must succeed
        res_hi = self.client.get(f"/api/episodes/{self.ep_id}/audio?lang=hindi")
        self.assertEqual(res_hi.status_code, 200)

        # 3. Odia track request (not yet generated) must return 404 LANGUAGE_TRACK_NOT_FOUND
        res_odia = self.client.get(f"/api/episodes/{self.ep_id}/audio?lang=odia")
        self.assertEqual(res_odia.status_code, 404)
        odia_data = res_odia.get_json()
        self.assertEqual(odia_data["code"], "LANGUAGE_TRACK_NOT_FOUND")

    def test_failed_audio_generation_never_marked_audio_ready(self):
        """Verify that if audio generation fails, database and computed flags never mark Audio Ready."""
        with patch.object(tts_service, "synthesize_line", side_effect=TTSSynthesisError("Simulated provider failure")):
            res = self.client.post(
                f"/api/episodes/{self.ep_id}/generate-audio",
                data=json.dumps({"language": "hindi"}),
                content_type="application/json"
            )
            self.assertEqual(res.status_code, 502)

            # Check DB record
            ep = get_episode(self.ep_id, db_path=self.db_path)
            self.assertEqual(ep["audio_status"], "failed")

            # Check computed field enricher
            enriched = enrich_episode_computed_fields(ep)
            self.assertFalse(enriched["audio_ready"])
            self.assertNotIn("hindi", enriched["available_audio_languages"])

    def test_end_to_end_odia_audio_generation_and_playback(self):
        """Verify end-to-end Odia audio synthesis route and playback streaming with genuine Odia script."""
        # 1. Update episode script to genuine Odia dialogue
        odia_script = {
            "intro": {
                "lines": [
                    {"speaker": "Host", "text": "ନମସ୍କାର, ଆଜିର ପୋଡକାଷ୍ଟକୁ ସ୍ୱାଗତ।"},
                    {"speaker": "CoHost", "text": "ଧନ୍ୟବାଦ, ଆଜି ଆମେ ଏକ ଗୁରୁତ୍ୱପୂର୍ଣ୍ଣ ବିଷୟରେ ଆଲୋଚନା କରିବା।"}
                ]
            },
            "segments": [
                {
                    "title": "ମୁଖ୍ୟ ବିଷୟ",
                    "lines": [
                        {"speaker": "Host", "text": "ଆଜିର ବଜାର ବିଶ୍ଳେଷଣ ଉପରେ ଦୃଷ୍ଟି ଦେବା।"},
                        {"speaker": "CoHost", "text": "ବ୍ୟାଙ୍କିଙ୍ଗ ଏବଂ ଆର୍ଥିକ କ୍ଷେତ୍ରରେ ଉତ୍ସାହ ଦେଖାଯାଇଛି।"}
                    ]
                }
            ],
            "key_takeaways": [
                {"speaker": "Host", "text": "ପ୍ରଥମ ନିଷ୍କର୍ଷ ହେଉଛି ବଜାର ସୁଦୃଢ଼ ରହିଛି।"},
                {"speaker": "CoHost", "text": "ଦ୍ୱିତୀୟରେ ନିବେଶକମାନେ ସଚେତନ ରହିବା ଉଚିତ।"}
            ],
            "outro": {
                "lines": [
                    {"speaker": "Host", "text": "ଆମ ସହିତ ଯୋଡ଼ି ହୋଇଥିବାରୁ ଧନ୍ୟବାଦ।"},
                    {"speaker": "CoHost", "text": "ପରବର୍ତ୍ତୀ ଅଧ୍ୟାୟରେ ପୁଣି ଦେଖାହେବ, ଶୁଭଦିନ।"}
                ]
            }
        }
        update_episode_podcast_script(
            episode_id=self.ep_id,
            script_status="completed",
            podcast_script=odia_script,
            db_path=self.db_path
        )

        # 2. Mock Sarvam synthesis return bytes
        dummy_mp3 = AudioSegment.silent(duration=500, frame_rate=22050)
        temp_export = os.path.join(self.temp_dir.name, "odia_clip.mp3")
        dummy_mp3.export(temp_export, format="mp3")
        with open(temp_export, "rb") as f:
            b64_audio = base64.b64encode(f.read()).decode("utf-8")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"audios": [b64_audio]}

        with patch("backend.services.tts_service.SARVAM_API_KEY", "valid-odia-sarvam-key"):
            with patch("requests.post", return_value=mock_resp):
                res = self.client.post(
                    f"/api/episodes/{self.ep_id}/generate-audio",
                    data=json.dumps({"language": "odia"}),
                    content_type="application/json"
                )
                self.assertEqual(res.status_code, 200)
                data = res.get_json()
                self.assertTrue(data["success"])
                self.assertEqual(data["audio_language"], "odia")
                self.assertEqual(data["audio_status"], "completed")

                # Verify file existence on disk
                audio_filename = data["audio_path"]
                audio_abs = os.path.join(self.audio_dir, audio_filename)
                self.assertTrue(os.path.isfile(audio_abs))
                self.assertGreater(os.path.getsize(audio_abs), 1000)

                # Verify streaming endpoint with ?lang=odia
                stream_res = self.client.get(f"/api/episodes/{self.ep_id}/audio?lang=odia")
                self.assertEqual(stream_res.status_code, 200)
                self.assertIn(stream_res.content_type, ("audio/mpeg", "audio/wav"))

                # Verify episode computed fields include odia
                ep = get_episode(self.ep_id, db_path=self.db_path)
                enriched = enrich_episode_computed_fields(ep)
                self.assertTrue(enriched["audio_ready"])
                self.assertIn("odia", enriched["available_audio_languages"])


if __name__ == "__main__":
    unittest.main()
