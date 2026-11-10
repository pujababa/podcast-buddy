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
    list_episodes
)
from backend.services.llm_service import (
    GeminiService,
    GeminiError,
    GeminiConfigurationError,
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiServiceError,
    GeminiResponseError,
    extract_and_parse_json,
    validate_and_normalize_intelligence,
    build_news_analysis_prompt,
    redact_api_key
)

DETERMINISTIC_MOCK_INTELLIGENCE = {
    "overview": "Artificial intelligence continues to develop rapidly across multiple areas.",
    "key_points": [
        "Point one",
        "Point two"
    ],
    "important_facts": [
        "Fact one"
    ],
    "entities": [
        {
            "name": "Example Organization",
            "type": "organization",
            "context": "Mentioned in the supplied source."
        }
    ],
    "topics": [
        "Artificial Intelligence"
    ],
    "source_insights": [
        {
            "source_id": "test-source-1",
            "summary": "Test source summary.",
            "key_claims": [
                "Test claim."
            ]
        }
    ],
    "confidence": "medium",
    "limitations": [
        "Based only on supplied source information."
    ]
}


class TestPhase5GeminiIntelligence(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for each test
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.test_db_path = os.path.join(self.temp_dir.name, "test_podcast_buddy.db")

        # Patch DATABASE_PATH
        self.db_patcher = patch.object(db_module, "DATABASE_PATH", self.test_db_path)
        self.db_patcher.start()

        # Initialize schema
        init_db(self.test_db_path)

        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True

        # Pre-seed a test episode with sources
        self.test_articles = [
            {
                "id": "test-source-1",
                "title": "Autonomous AI Agents Evolve",
                "publisher": "Tech Digest",
                "snippet": "New frameworks enable multi-step workflows.",
                "date": "2 hours ago",
                "url": "https://example.com/ai-agents"
            },
            {
                "id": "test-source-2",
                "title": "Quantum Hybrid Systems",
                "publisher": "Science Chronicle",
                "snippet": "Engineers test low-latency quantum coprocessors.",
                "date": "Yesterday",
                "url": "https://example.com/quantum-hybrid"
            }
        ]
        self.episode = create_episode(
            title="Tech Briefing",
            description="AI & Quantum advancements",
            articles=self.test_articles,
            db_path=self.test_db_path
        )
        self.episode_id = self.episode["id"]

    def tearDown(self):
        self.db_patcher.stop()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. Configuration & Key Security Tests
    # -------------------------------------------------------------------------
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_gemini_api_key_raises_configuration_error(self):
        """Verify GeminiService raises GeminiConfigurationError when GEMINI_API_KEY is not set."""
        service = GeminiService(api_key=None)
        with self.assertRaises(GeminiConfigurationError):
            service.get_api_key()

    @patch("backend.routes.episodes.gemini_service.generate_news_intelligence")
    def test_missing_api_key_returns_503_and_no_key_exposure(self, mock_gen):
        """Verify POST /generate-intelligence returns 503 and never leaks API keys."""
        mock_gen.side_effect = GeminiConfigurationError("GEMINI_API_KEY is not configured.")
        
        dummy_key = "MOCK_GEMINI_API_KEY_FOR_TESTING_ONLY_12345"
        with patch.dict(os.environ, {"GEMINI_API_KEY": dummy_key}):
            response = self.client.post(f"/api/episodes/{self.episode_id}/generate-intelligence")
            self.assertEqual(response.status_code, 503)
            data = response.get_json()
            self.assertFalse(data.get("success"))
            self.assertEqual(data.get("code"), "CONFIG_ERROR")
            
            # Check key is never exposed
            raw_text = response.get_data(as_text=True)
            self.assertNotIn(dummy_key, raw_text)

    def test_redact_api_key_masks_secrets(self):
        """Verify redact_api_key masks actual key patterns."""
        key = "AIza" + "SyD-mockSecretToken1234567890abcdef"
        msg = f"Failed to connect using api_key={key} in call"
        clean = redact_api_key(msg, key)
        self.assertNotIn(key, clean)
        self.assertIn("[REDACTED", clean)

    # -------------------------------------------------------------------------
    # 2. Success Path Tests
    # -------------------------------------------------------------------------
    @patch("backend.routes.episodes.gemini_service.generate_news_intelligence")
    def test_generate_intelligence_success(self, mock_gen):
        """Verify valid mocked Gemini response generates and saves intelligence with status completed."""
        mock_gen.return_value = DETERMINISTIC_MOCK_INTELLIGENCE

        response = self.client.post(f"/api/episodes/{self.episode_id}/generate-intelligence")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("episode_id"), self.episode_id)
        self.assertEqual(data.get("ai_status"), "completed")
        self.assertIsNotNone(data.get("ai_generated_at"))

        intelligence = data.get("intelligence")
        self.assertEqual(intelligence["overview"], DETERMINISTIC_MOCK_INTELLIGENCE["overview"])
        self.assertEqual(len(intelligence["key_points"]), 2)
        self.assertEqual(intelligence["confidence"], "medium")

        # Verify persisted state in database
        persisted = get_episode(self.episode_id, db_path=self.test_db_path)
        self.assertEqual(persisted["ai_status"], "completed")
        self.assertIsNotNone(persisted["ai_generated_at"])
        self.assertIsNotNone(persisted["intelligence"])
        self.assertEqual(persisted["intelligence"]["overview"], DETERMINISTIC_MOCK_INTELLIGENCE["overview"])

    # -------------------------------------------------------------------------
    # 3. Validation & Edge Cases
    # -------------------------------------------------------------------------
    def test_generate_intelligence_invalid_episode_id_returns_404(self):
        """Verify 404 when episode ID does not exist."""
        response = self.client.post("/api/episodes/999999/generate-intelligence")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "NOT_FOUND")

    def test_generate_intelligence_episode_with_no_sources_returns_400(self):
        """Verify 400 when episode has no associated sources."""
        # Create an episode with 1 source, then delete that source directly
        empty_ep = create_episode("No Sources", "", [{"id": "1", "title": "T", "publisher": "P", "url": "https://ex.com"}], db_path=self.test_db_path)
        conn = get_db_connection(self.test_db_path)
        conn.execute("DELETE FROM episode_sources WHERE episode_id = ?", (empty_ep["id"],))
        conn.commit()
        conn.close()

        response = self.client.post(f"/api/episodes/{empty_ep['id']}/generate-intelligence")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "NO_SOURCES")

    def test_extract_and_parse_json_markdown_fences(self):
        """Verify JSON surrounded by markdown code fences is cleanly extracted."""
        fenced = '```json\n{"overview": "Test overview", "key_points": []}\n```'
        parsed = extract_and_parse_json(fenced)
        self.assertEqual(parsed["overview"], "Test overview")

    def test_malformed_json_raises_gemini_response_error(self):
        """Verify malformed JSON raises GeminiResponseError."""
        bad_json = "This is not valid json at all"
        with self.assertRaises(GeminiResponseError):
            extract_and_parse_json(bad_json)

    def test_missing_required_fields_raises_response_error(self):
        """Verify missing 'overview' or 'key_points' raises GeminiResponseError."""
        incomplete_data = {"key_points": ["Point 1"]}  # missing overview
        with self.assertRaises(GeminiResponseError):
            validate_and_normalize_intelligence(incomplete_data)

    def test_wrong_field_types_raises_response_error(self):
        """Verify non-list key_points raises GeminiResponseError."""
        bad_types = {"overview": "Valid", "key_points": "not a list", "important_facts": []}
        with self.assertRaises(GeminiResponseError):
            validate_and_normalize_intelligence(bad_types)

    # -------------------------------------------------------------------------
    # 4. Error Handling & Failure States
    # -------------------------------------------------------------------------
    @patch("backend.routes.episodes.gemini_service.generate_news_intelligence")
    def test_gemini_timeout_marks_failed_and_returns_504(self, mock_gen):
        """Verify GeminiTimeoutError marks episode as 'failed' and returns 504."""
        mock_gen.side_effect = GeminiTimeoutError("Request timed out.")
        response = self.client.post(f"/api/episodes/{self.episode_id}/generate-intelligence")
        self.assertEqual(response.status_code, 504)
        data = response.get_json()
        self.assertEqual(data.get("code"), "TIMEOUT_ERROR")

        # Episode state must be marked failed
        ep = get_episode(self.episode_id, db_path=self.test_db_path)
        self.assertEqual(ep["ai_status"], "failed")
        self.assertIsNone(ep["intelligence"])

    @patch("backend.routes.episodes.gemini_service.generate_news_intelligence")
    def test_gemini_auth_error_marks_failed_and_returns_502(self, mock_gen):
        """Verify GeminiAuthenticationError marks episode as 'failed' and returns 502."""
        mock_gen.side_effect = GeminiAuthenticationError("Invalid API key.")
        response = self.client.post(f"/api/episodes/{self.episode_id}/generate-intelligence")
        self.assertEqual(response.status_code, 502)
        data = response.get_json()
        self.assertEqual(data.get("code"), "AUTH_ERROR")

        ep = get_episode(self.episode_id, db_path=self.test_db_path)
        self.assertEqual(ep["ai_status"], "failed")

    @patch("backend.routes.episodes.gemini_service.generate_news_intelligence")
    def test_gemini_rate_limit_marks_failed_and_returns_429(self, mock_gen):
        """Verify GeminiRateLimitError marks episode as 'failed' and returns 429."""
        mock_gen.side_effect = GeminiRateLimitError("Quota exceeded.")
        response = self.client.post(f"/api/episodes/{self.episode_id}/generate-intelligence")
        self.assertEqual(response.status_code, 429)
        data = response.get_json()
        self.assertEqual(data.get("code"), "RATE_LIMIT_ERROR")

        ep = get_episode(self.episode_id, db_path=self.test_db_path)
        self.assertEqual(ep["ai_status"], "failed")

    @patch("backend.routes.episodes.gemini_service.generate_news_intelligence")
    def test_gemini_service_error_marks_failed_and_returns_502(self, mock_gen):
        """Verify GeminiServiceError marks episode as 'failed' and returns 502."""
        mock_gen.side_effect = GeminiServiceError("Connection refused.")
        response = self.client.post(f"/api/episodes/{self.episode_id}/generate-intelligence")
        self.assertEqual(response.status_code, 502)
        data = response.get_json()
        self.assertEqual(data.get("code"), "SERVICE_ERROR")

        ep = get_episode(self.episode_id, db_path=self.test_db_path)
        self.assertEqual(ep["ai_status"], "failed")

    @patch("backend.routes.episodes.gemini_service.generate_news_intelligence")
    def test_gemini_response_error_marks_failed_and_returns_502(self, mock_gen):
        """Verify GeminiResponseError marks episode as 'failed' and returns 502."""
        mock_gen.side_effect = GeminiResponseError("Malformed JSON.")
        response = self.client.post(f"/api/episodes/{self.episode_id}/generate-intelligence")
        self.assertEqual(response.status_code, 502)
        data = response.get_json()
        self.assertEqual(data.get("code"), "RESPONSE_ERROR")

        ep = get_episode(self.episode_id, db_path=self.test_db_path)
        self.assertEqual(ep["ai_status"], "failed")
        self.assertIsNone(ep["intelligence"])

    # -------------------------------------------------------------------------
    # 5. GET /api/episodes & /api/episodes/<id> Includes AI Fields
    # -------------------------------------------------------------------------
    def test_get_episode_includes_ai_status_and_null_intelligence_initially(self):
        """Verify GET /api/episodes/<id> contains ai_status: 'not_started' and intelligence: null."""
        response = self.client.get(f"/api/episodes/{self.episode_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        ep = data.get("episode")
        self.assertEqual(ep.get("ai_status"), "not_started")
        self.assertIsNone(ep.get("intelligence"))
        self.assertIsNone(ep.get("ai_generated_at"))

    @patch("backend.routes.episodes.gemini_service.generate_news_intelligence")
    def test_get_episode_includes_generated_intelligence_after_completion(self, mock_gen):
        """Verify GET /api/episodes/<id> returns the full intelligence object after generation."""
        mock_gen.return_value = DETERMINISTIC_MOCK_INTELLIGENCE
        self.client.post(f"/api/episodes/{self.episode_id}/generate-intelligence")

        response = self.client.get(f"/api/episodes/{self.episode_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        ep = data.get("episode")
        self.assertEqual(ep.get("ai_status"), "completed")
        self.assertIsNotNone(ep.get("intelligence"))
        self.assertEqual(ep["intelligence"]["overview"], DETERMINISTIC_MOCK_INTELLIGENCE["overview"])

    def test_list_episodes_includes_ai_status(self):
        """Verify GET /api/episodes includes ai_status on each episode."""
        response = self.client.get("/api/episodes")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        episodes = data.get("episodes")
        self.assertGreaterEqual(len(episodes), 1)
        self.assertEqual(episodes[0].get("ai_status"), "not_started")

    # -------------------------------------------------------------------------
    # 6. Regression & Health Endpoint Tests
    # -------------------------------------------------------------------------
    def test_root_endpoint_persists(self):
        """Verify GET / returns 200 running status."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "running")

    def test_health_endpoint_persists(self):
        """Verify GET /health returns 200 healthy status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "healthy")


if __name__ == "__main__":
    unittest.main()
