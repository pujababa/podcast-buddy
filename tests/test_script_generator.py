import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import app
import backend.models.database as db_module
from backend.models.database import (
    init_db,
    get_db_connection,
    create_episode,
    get_episode,
    list_episodes,
    update_episode_ai_intelligence,
    update_episode_podcast_script
)
from backend.services.llm_service import (
    GeminiService,
    gemini_service,
    extract_and_parse_json,
    GeminiConfigurationError,
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiServiceError,
    GeminiResponseError
)
from backend.services.script_generator import (
    PodcastScriptGenerator,
    generate_podcast_script,
    validate_and_normalize_script,
    validate_dialogue_line,
    ScriptGenerationError,
    ScriptValidationError,
    ALLOWED_SPEAKERS
)

DETERMINISTIC_MOCK_INTELLIGENCE = {
    "overview": "Artificial intelligence continues to develop rapidly across multiple areas.",
    "key_points": [
        "Point one regarding breakthrough models.",
        "Point two regarding efficiency gains."
    ],
    "important_facts": [
        "Fact one verified across reporting."
    ],
    "entities": [
        {
            "name": "Example Organization",
            "type": "organization",
            "context": "Mentioned in the supplied source."
        }
    ],
    "topics": [
        "Artificial Intelligence",
        "Technology"
    ],
    "source_insights": [
        {
            "source_id": "test-src-1",
            "summary": "First source summary.",
            "key_claims": ["Breakthrough announced."]
        }
    ],
    "confidence": "high",
    "limitations": [
        "Based strictly on supplied source information."
    ]
}

DETERMINISTIC_MOCK_SCRIPT = {
    "intro": {
        "title": "AI News Today",
        "lines": [
            {
                "speaker": "host",
                "text": "Welcome back to Podcast Buddy."
            },
            {
                "speaker": "cohost",
                "text": "Today we're breaking down the latest AI developments."
            }
        ]
    },
    "segments": [
        {
            "title": "Main Story",
            "lines": [
                {
                    "speaker": "host",
                    "text": "Let's start with the main development."
                },
                {
                    "speaker": "cohost",
                    "text": "The supplied sources highlight several important points."
                }
            ]
        }
    ],
    "key_takeaways": [
        {
            "speaker": "host",
            "text": "The first takeaway is the scale of the development."
        },
        {
            "speaker": "cohost",
            "text": "The second is how the sources describe its impact."
        }
    ],
    "outro": {
        "lines": [
            {
                "speaker": "host",
                "text": "That's today's breakdown."
            },
            {
                "speaker": "cohost",
                "text": "Thanks for listening to Podcast Buddy."
            }
        ]
    }
}


class TestPodcastScriptGenerator(unittest.TestCase):
    """Automated tests for Phase 6 Podcast Script Generation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "test_podcast_buddy.db")

        # Patch default DB path in database module
        self.db_patcher = patch.object(db_module, "DATABASE_PATH", self.db_path)
        self.db_patcher.start()

        # Reset cached client on gemini_service to guarantee complete test isolation
        gemini_service.reset_client()

        # Initialize test database
        init_db(self.db_path)

        # Flask test client
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        # Create a sample episode with sources and completed intelligence
        sample_articles = [
            {
                "id": "art-1",
                "title": "AI Breakthrough Announced",
                "publisher": "Tech Daily",
                "snippet": "Researchers announced a new AI architecture today.",
                "date": "2026-10-06",
                "url": "https://example.com/ai-news"
            }
        ]
        created = create_episode(
            title="Episode 1: AI Future",
            description="Discussing latest AI updates",
            articles=sample_articles,
            db_path=self.db_path
        )
        self.episode_id = created["id"]

        # Mark intelligence as completed
        update_episode_ai_intelligence(
            episode_id=self.episode_id,
            ai_status="completed",
            intelligence=DETERMINISTIC_MOCK_INTELLIGENCE,
            generated_at="2026-10-06T12:00:00Z",
            db_path=self.db_path
        )

    def tearDown(self):
        self.db_patcher.stop()
        gemini_service.reset_client()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # =========================================================================
    # 1. Success Tests
    # =========================================================================
    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_successful_script_generation(self, mock_gen):
        """Episode with valid AI intelligence generates script successfully."""
        mock_gen.return_value = DETERMINISTIC_MOCK_SCRIPT

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["episode_id"], self.episode_id)
        self.assertEqual(data["script_status"], "completed")
        self.assertIsNotNone(data["script_generated_at"])
        self.assertIn("podcast_script", data)

        script = data["podcast_script"]
        self.assertIn("intro", script)
        self.assertIn("segments", script)
        self.assertIn("key_takeaways", script)
        self.assertIn("outro", script)
        self.assertEqual(len(script["segments"]), 1)
        self.assertEqual(len(script["key_takeaways"]), 2)

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_script_saved_in_database(self, mock_gen):
        """Database stores valid script, completed status, and timestamp."""
        mock_gen.return_value = DETERMINISTIC_MOCK_SCRIPT

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")
        self.assertEqual(resp.status_code, 200)

        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertIsNotNone(ep)
        self.assertEqual(ep["script_status"], "completed")
        self.assertIsNotNone(ep["script_generated_at"])
        self.assertEqual(ep["podcast_script"]["intro"]["title"], "AI News Today")
        self.assertEqual(len(ep["podcast_script"]["intro"]["lines"]), 2)

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_get_episode_includes_podcast_script(self, mock_gen):
        """GET /api/episodes/<id> returns script_status, script_generated_at, and podcast_script."""
        mock_gen.return_value = DETERMINISTIC_MOCK_SCRIPT

        self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        resp = self.client.get(f"/api/episodes/{self.episode_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        ep = data["episode"]
        self.assertEqual(ep["script_status"], "completed")
        self.assertIsNotNone(ep["script_generated_at"])
        self.assertIsInstance(ep["podcast_script"], dict)

    def test_get_episode_script_null_before_generation(self):
        """Before script generation, podcast_script is null and script_status is 'not_started'."""
        resp = self.client.get(f"/api/episodes/{self.episode_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        ep = data["episode"]
        self.assertEqual(ep["script_status"], "not_started")
        self.assertIsNone(ep["podcast_script"])
        self.assertIsNone(ep.get("script_generated_at"))

    # =========================================================================
    # 2. Preconditions & Validation
    # =========================================================================
    def test_invalid_episode_id_404(self):
        """Non-existent episode returns 404."""
        resp = self.client.post("/api/episodes/99999/generate-script")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"].lower())

    def test_episode_without_ai_intelligence_returns_400(self):
        """Episode without completed AI intelligence returns 400 error."""
        # Create a fresh episode with no AI intelligence
        fresh = create_episode(
            title="Fresh Episode",
            description="",
            articles=[{"id": "a1", "title": "T1", "publisher": "P1", "url": "https://example.com"}],
            db_path=self.db_path
        )
        resp = self.client.post(f"/api/episodes/{fresh['id']}/generate-script")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Generate AI intelligence before generating the podcast script.")

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_invalid_speaker_rejected(self, mock_gen):
        """Reject scripts containing unauthorized speakers (e.g. 'guest')."""
        invalid_script = dict(DETERMINISTIC_MOCK_SCRIPT)
        invalid_script["intro"] = {
            "title": "Intro",
            "lines": [
                {"speaker": "guest", "text": "Hello, I am a guest."}
            ]
        }
        mock_gen.return_value = invalid_script

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 502)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("invalid", data["error"].lower())

        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")
        self.assertIsNone(ep["podcast_script"])

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_empty_dialogue_text_rejected(self, mock_gen):
        """Reject scripts containing empty dialogue text."""
        invalid_script = dict(DETERMINISTIC_MOCK_SCRIPT)
        invalid_script["intro"] = {
            "title": "Intro",
            "lines": [
                {"speaker": "host", "text": "   "}
            ]
        }
        mock_gen.return_value = invalid_script

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 502)
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_missing_required_section_rejected(self, mock_gen):
        """Reject script missing required sections (e.g. missing 'key_takeaways')."""
        invalid_script = {
            "intro": DETERMINISTIC_MOCK_SCRIPT["intro"],
            "segments": DETERMINISTIC_MOCK_SCRIPT["segments"],
            "outro": DETERMINISTIC_MOCK_SCRIPT["outro"]
        }
        mock_gen.return_value = invalid_script

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 502)
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_malformed_json_rejected(self, mock_gen):
        """Reject response when Gemini output is not valid JSON."""
        mock_gen.side_effect = GeminiResponseError("Malformed JSON returned by Gemini: Expecting value: line 1 column 1 (char 0)")

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 502)
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")
        self.assertIsNone(ep["podcast_script"])

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_markdown_fenced_json_parsed(self, mock_gen):
        """Safely extract and parse JSON wrapped in markdown code fences."""
        fenced_json = f"```json\n{json.dumps(DETERMINISTIC_MOCK_SCRIPT)}\n```"
        parsed = extract_and_parse_json(fenced_json)
        self.assertEqual(parsed["intro"]["title"], "AI News Today")
        mock_gen.return_value = parsed

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["script_status"], "completed")

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_invalid_field_type_rejected(self, mock_gen):
        """Reject script when a field has the wrong type (e.g. segments is a string)."""
        invalid_script = dict(DETERMINISTIC_MOCK_SCRIPT)
        invalid_script["segments"] = "Not a list"
        mock_gen.return_value = invalid_script

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 502)
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")

    # =========================================================================
    # 3. Controlled Errors & Service Failures
    # =========================================================================
    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_missing_api_key_returns_503(self, mock_gen):
        """Missing GEMINI_API_KEY returns controlled 503 error."""
        mock_gen.side_effect = GeminiConfigurationError("GEMINI_API_KEY is not configured on the server.")

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 503)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("configured", data["error"].lower())
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_gemini_timeout_returns_504(self, mock_gen):
        """Gemini timeout exception returns controlled 504 error."""
        mock_gen.side_effect = GeminiTimeoutError("The request to Gemini timed out.")

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 504)
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_gemini_rate_limit_returns_429(self, mock_gen):
        """Gemini quota/rate limit error returns controlled 429."""
        mock_gen.side_effect = GeminiRateLimitError("Gemini search quota or rate limit exceeded.")

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 429)
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_gemini_auth_error_returns_502(self, mock_gen):
        """Gemini authentication failure returns controlled 502."""
        mock_gen.side_effect = GeminiAuthenticationError("Authentication with Gemini failed.")

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 502)
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_gemini_network_error_returns_502(self, mock_gen):
        """Network/connection error returns controlled 502."""
        mock_gen.side_effect = GeminiServiceError("Unable to connect to the Gemini service.")

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 502)
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")

    @patch("backend.services.script_generator.gemini_service.generate_structured_json")
    def test_unexpected_gemini_error_returns_500(self, mock_gen):
        """Unexpected Gemini error returns controlled 500 without leaking stack traces."""
        mock_gen.side_effect = RuntimeError("Fatal internal error in runtime")

        resp = self.client.post(f"/api/episodes/{self.episode_id}/generate-script")

        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertNotIn("Traceback", data.get("error", ""))
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertEqual(ep["script_status"], "failed")

    # =========================================================================
    # 4. Database Safety & Regression
    # =========================================================================
    def test_phase4_and_phase5_data_intact(self):
        """Verify that existing Phase 4 sources and Phase 5 AI intelligence remain intact."""
        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertIsNotNone(ep)
        self.assertEqual(ep["title"], "Episode 1: AI Future")
        self.assertEqual(ep["ai_status"], "completed")
        self.assertIsNotNone(ep["intelligence"])
        self.assertEqual(len(ep["sources"]), 1)
        self.assertEqual(ep["sources"][0]["article_id"], "art-1")

    def test_database_migration_idempotent(self):
        """Calling init_db multiple times preserves existing tables, columns, and data."""
        init_db(self.db_path)
        init_db(self.db_path)

        ep = get_episode(self.episode_id, db_path=self.db_path)
        self.assertIsNotNone(ep)
        self.assertEqual(ep["title"], "Episode 1: AI Future")
        self.assertEqual(ep["script_status"], "not_started")

    def test_regression_root_and_health(self):
        """Verify Phase 1 root and health endpoints remain functional."""
        root_resp = self.client.get("/")
        self.assertEqual(root_resp.status_code, 200)
        root_data = root_resp.get_json()
        self.assertEqual(root_data["status"], "running")

        health_resp = self.client.get("/health")
        self.assertEqual(health_resp.status_code, 200)
        health_data = health_resp.get_json()
        self.assertEqual(health_data["status"], "healthy")

    # =========================================================================
    # 5. Direct Unit Tests on PodcastScriptGenerator Service
    # =========================================================================
    def test_direct_script_generator_service_call(self):
        """Direct invocation of PodcastScriptGenerator with a mocked GeminiService."""
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.generate_structured_json.return_value = DETERMINISTIC_MOCK_SCRIPT

        generator = PodcastScriptGenerator(service=mock_gemini)
        episode_data = {"title": "Test Title", "description": "Test Desc"}
        script = generator.generate_podcast_script(episode_data, DETERMINISTIC_MOCK_INTELLIGENCE)

        self.assertIn("intro", script)
        self.assertIn("segments", script)
        self.assertIn("key_takeaways", script)
        self.assertIn("outro", script)
        mock_gemini.generate_structured_json.assert_called_once()

    def test_direct_script_generator_rejects_missing_intelligence(self):
        """PodcastScriptGenerator raises ScriptGenerationError if intelligence is missing."""
        generator = PodcastScriptGenerator()
        with self.assertRaises(ScriptGenerationError):
            generator.generate_podcast_script({"title": "Test"}, None)

    def test_validate_dialogue_line_direct(self):
        """Dialogue line validator requires host or cohost and non-empty text."""
        # Valid
        valid_line = validate_dialogue_line({"speaker": "HOST", "text": "Hello world"}, "test")
        self.assertEqual(valid_line["speaker"], "host")
        self.assertEqual(valid_line["text"], "Hello world")

        # Invalid speaker
        with self.assertRaises(ScriptValidationError):
            validate_dialogue_line({"speaker": "guest", "text": "Hello"}, "test")

        # Empty text
        with self.assertRaises(ScriptValidationError):
            validate_dialogue_line({"speaker": "host", "text": ""}, "test")

        # Non-dict
        with self.assertRaises(ScriptValidationError):
            validate_dialogue_line("just text", "test")


if __name__ == "__main__":
    unittest.main()
