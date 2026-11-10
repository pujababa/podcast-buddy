import os
import sys
import socket
import unittest
from unittest.mock import patch, MagicMock
import requests

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import app
from backend.services.serpapi_service import (
    SerpAPIService,
    SerpAPIError,
    SerpAPIConfigurationError,
    SerpAPIAuthError,
    SerpAPIRateLimitError,
    SerpAPITimeoutError,
    SerpAPINetworkError,
    redact_api_key,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_TIMEOUT
)


class TestNewsDiscovery(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True

    # -------------------------------------------------------------------------
    # 1 & 2: Root & Health Endpoints
    # -------------------------------------------------------------------------
    def test_root_endpoint(self):
        """Verify GET / returns 200 and running status."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("app"), "Podcast Buddy")
        self.assertEqual(data.get("status"), "running")

    def test_health_endpoint(self):
        """Verify GET /health returns 200 and healthy status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "healthy")

    # -------------------------------------------------------------------------
    # 3: Empty & Invalid News Queries
    # -------------------------------------------------------------------------
    def test_news_search_missing_query(self):
        """Verify GET /api/news/search without 'q' parameter returns 400 Bad Request."""
        response = self.client.get("/api/news/search")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("required", data.get("error", "").lower())

    def test_news_search_empty_query(self):
        """Verify GET /api/news/search with whitespace 'q' returns 400 Bad Request."""
        response = self.client.get("/api/news/search?q=   ")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))

    def test_news_search_query_too_long(self):
        """Verify GET /api/news/search with query exceeding 200 characters returns 400."""
        long_query = "a" * 201
        response = self.client.get(f"/api/news/search?q={long_query}")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("exceeds", data.get("error", "").lower())

    # -------------------------------------------------------------------------
    # 4: News Route with Mocked SerpAPI Response
    # -------------------------------------------------------------------------
    @patch("backend.routes.news.serpapi_service.search_news")
    def test_news_search_successful_mocked(self, mock_search):
        """Verify GET /api/news/search?q=... returns normalized results when mocked."""
        mock_search.return_value = [
            {
                "id": "news-1",
                "title": "Breakthrough in AI Research",
                "publisher": "Tech Daily",
                "snippet": "Scientists report new models that learn faster.",
                "date": "2 hours ago",
                "url": "https://example.com/ai-breakthrough"
            },
            {
                "id": "news-2",
                "title": "Quantum Computing Advances",
                "publisher": "Science Post",
                "snippet": "New quantum processor tested in laboratory.",
                "date": "Yesterday",
                "url": "https://example.com/quantum-advances"
            }
        ]

        response = self.client.get("/api/news/search?q=artificial%20intelligence")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("query"), "artificial intelligence")
        self.assertEqual(data.get("total_results"), 2)
        self.assertEqual(len(data.get("results")), 2)
        self.assertEqual(data["results"][0]["publisher"], "Tech Daily")

    # -------------------------------------------------------------------------
    # 5: SerpAPI Service Normalization Tests
    # -------------------------------------------------------------------------
    def test_normalization_complete_and_partial_items(self):
        """Verify SerpAPIService safely normalizes both full and partial SerpAPI responses."""
        service = SerpAPIService(api_key="mock_key")
        raw_mock = {
            "news_results": [
                {
                    "title": "AI Breakthrough Announced",
                    "link": "https://news.example.com/ai",
                    "source": {"name": "Wired", "icon": "https://example.com/icon.png"},
                    "date": "1 hour ago",
                    "snippet": "A new generation of reasoning models has been demonstrated."
                },
                {
                    "title": "Global Tech Summit 2026",
                    "url": "https://news.example.com/summit",
                    "source": "TechCrunch",  # Source as plain string
                    # snippet and date missing intentionally
                }
            ]
        }

        normalized = service.normalize_results(raw_mock)
        self.assertEqual(len(normalized), 2)

        # First item checks
        self.assertEqual(normalized[0]["id"], "news-1")
        self.assertEqual(normalized[0]["title"], "AI Breakthrough Announced")
        self.assertEqual(normalized[0]["publisher"], "Wired")
        self.assertEqual(normalized[0]["url"], "https://news.example.com/ai")
        self.assertEqual(normalized[0]["date"], "1 hour ago")
        self.assertIn("reasoning models", normalized[0]["snippet"])

        # Second item checks (graceful defaults for missing fields)
        self.assertEqual(normalized[1]["id"], "news-2")
        self.assertEqual(normalized[1]["title"], "Global Tech Summit 2026")
        self.assertEqual(normalized[1]["publisher"], "TechCrunch")
        self.assertEqual(normalized[1]["url"], "https://news.example.com/summit")
        self.assertEqual(normalized[1]["date"], "")
        self.assertEqual(normalized[1]["snippet"], "")

    def test_normalization_sub_stories(self):
        """Verify SerpAPIService extracts nested sub-stories from SerpAPI clusters."""
        service = SerpAPIService(api_key="mock_key")
        raw_mock = {
            "news_results": [
                {
                    "title": "Major Policy Change",
                    "link": "https://news.example.com/policy",
                    "source": {"name": "Reuters"},
                    "stories": [
                        {
                            "title": "Market Reaction to Policy",
                            "link": "https://news.example.com/markets",
                            "source": {"name": "Bloomberg"},
                            "date": "30 mins ago"
                        }
                    ]
                }
            ]
        }

        normalized = service.normalize_results(raw_mock)
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["title"], "Major Policy Change")
        self.assertEqual(normalized[1]["title"], "Market Reaction to Policy")
        self.assertEqual(normalized[1]["publisher"], "Bloomberg")

    # -------------------------------------------------------------------------
    # 6: Missing API Key Handling
    # -------------------------------------------------------------------------
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_raises_configuration_error(self):
        """Verify SerpAPIService raises SerpAPIConfigurationError when no key is set."""
        service = SerpAPIService(api_key=None)
        with self.assertRaises(SerpAPIConfigurationError):
            service.get_api_key()

    @patch("backend.routes.news.serpapi_service.search_news")
    def test_route_handles_missing_api_key(self, mock_search):
        """Verify route returns 503 Service Unavailable when API key is missing."""
        mock_search.side_effect = SerpAPIConfigurationError("Key missing")
        response = self.client.get("/api/news/search?q=technology")
        self.assertEqual(response.status_code, 503)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("not configured", data.get("error", "").lower())

    # -------------------------------------------------------------------------
    # 7: SerpAPI / External API Failure Handling
    # -------------------------------------------------------------------------
    @patch("backend.routes.news.serpapi_service.search_news")
    def test_route_handles_timeout(self, mock_search):
        """Verify route returns 504 Gateway Timeout when search times out."""
        mock_search.side_effect = SerpAPITimeoutError("Request timed out")
        response = self.client.get("/api/news/search?q=science")
        self.assertEqual(response.status_code, 504)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("timed out", data.get("error", "").lower())

    @patch("backend.routes.news.serpapi_service.search_news")
    def test_route_handles_invalid_key_auth_error(self, mock_search):
        """Verify route returns 502 when SerpAPI returns 401/403 Invalid Key."""
        mock_search.side_effect = SerpAPIAuthError("Invalid API key")
        response = self.client.get("/api/news/search?q=business")
        self.assertEqual(response.status_code, 502)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("authentication", data.get("error", "").lower())

    @patch("backend.routes.news.serpapi_service.search_news")
    def test_route_handles_rate_limit_error(self, mock_search):
        """Verify route returns 429 when SerpAPI quota/rate limit is reached."""
        mock_search.side_effect = SerpAPIRateLimitError("Quota exceeded")
        response = self.client.get("/api/news/search?q=sports")
        self.assertEqual(response.status_code, 429)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("quota", data.get("error", "").lower())

    @patch("backend.routes.news.serpapi_service.search_news")
    def test_route_handles_network_error(self, mock_search):
        """Verify route returns 502 when network connection fails."""
        mock_search.side_effect = SerpAPINetworkError("Connection failed")
        response = self.client.get("/api/news/search?q=world")
        self.assertEqual(response.status_code, 502)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("network", data.get("error", "").lower())
        self.assertEqual(data.get("code"), "NETWORK_ERROR")

    # -------------------------------------------------------------------------
    # 8: Query Validation Edge Cases
    # -------------------------------------------------------------------------
    def test_empty_query_string_returns_code(self):
        """Verify ?q= returns 400 with EMPTY_QUERY code."""
        response = self.client.get("/api/news/search?q=")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "EMPTY_QUERY")

    def test_whitespace_query_returns_code(self):
        """Verify ?q=   returns 400 with WHITESPACE_QUERY code."""
        response = self.client.get("/api/news/search?q=%20%20%20")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "WHITESPACE_QUERY")

    def test_missing_query_returns_code(self):
        """Verify /api/news/search without query param returns MISSING_QUERY code."""
        response = self.client.get("/api/news/search")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "MISSING_QUERY")

    # -------------------------------------------------------------------------
    # 9: Outbound Request Timeout & Network Robustness
    # -------------------------------------------------------------------------
    def test_serpapi_service_timeout_is_tuple(self):
        """Verify SerpAPIService initializes with separate connect and read timeouts."""
        service = SerpAPIService(api_key="mock_key")
        self.assertIsInstance(service.timeout, tuple)
        self.assertEqual(len(service.timeout), 2)
        connect_timeout, read_timeout = service.timeout
        self.assertLessEqual(connect_timeout, 5.0, "Connection timeout must be short (<= 5s)")
        self.assertLessEqual(read_timeout, 10.0, "Read timeout must be short (<= 10s)")

    @patch("backend.services.serpapi_service.requests.get")
    def test_serpapi_request_uses_short_timeouts(self, mock_get):
        """Verify outbound HTTP request passes the short (connect, read) timeout tuple."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"news_results": []}
        mock_get.return_value = mock_resp

        service = SerpAPIService(api_key="mock_key")
        service.search_news("artificial intelligence")

        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        self.assertIn("timeout", kwargs)
        self.assertIsInstance(kwargs["timeout"], tuple)
        self.assertEqual(kwargs["timeout"], service.timeout)

    @patch("backend.services.serpapi_service.requests.get")
    def test_serpapi_connect_timeout_raises_timeout_error(self, mock_get):
        """Verify requests.exceptions.ConnectTimeout raises SerpAPITimeoutError."""
        mock_get.side_effect = requests.exceptions.ConnectTimeout("Connection timed out")
        service = SerpAPIService(api_key="mock_key")
        with self.assertRaises(SerpAPITimeoutError):
            service.search_news("technology")

    @patch("backend.services.serpapi_service.requests.get")
    def test_serpapi_read_timeout_raises_timeout_error(self, mock_get):
        """Verify requests.exceptions.ReadTimeout raises SerpAPITimeoutError."""
        mock_get.side_effect = requests.exceptions.ReadTimeout("Read timed out")
        service = SerpAPIService(api_key="mock_key")
        with self.assertRaises(SerpAPITimeoutError):
            service.search_news("technology")

    @patch("backend.services.serpapi_service.requests.get")
    def test_serpapi_dns_error_raises_network_error(self, mock_get):
        """Verify DNS failure (socket.gaierror) raises SerpAPINetworkError."""
        mock_get.side_effect = socket.gaierror(11001, "getaddrinfo failed")
        service = SerpAPIService(api_key="mock_key")
        with self.assertRaises(SerpAPINetworkError):
            service.search_news("technology")

    # -------------------------------------------------------------------------
    # 10: Invalid JSON & Malformed Response Handling
    # -------------------------------------------------------------------------
    @patch("backend.services.serpapi_service.requests.get")
    def test_serpapi_invalid_json_raises_error(self, mock_get):
        """Verify non-JSON response from SerpAPI raises SerpAPIError."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_resp

        service = SerpAPIService(api_key="mock_key")
        with self.assertRaises(SerpAPIError) as ctx:
            service.search_news("technology")
        self.assertIn("invalid response format", str(ctx.exception).lower())

    @patch("backend.services.serpapi_service.requests.get")
    def test_serpapi_unexpected_structure_raises_error(self, mock_get):
        """Verify unexpected response structure (e.g. list instead of dict) raises SerpAPIError."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = ["unexpected", "list", "response"]
        mock_get.return_value = mock_resp

        service = SerpAPIService(api_key="mock_key")
        with self.assertRaises(SerpAPIError) as ctx:
            service.search_news("technology")
        self.assertIn("unexpected response structure", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # 11: Empty Search Results Handling
    # -------------------------------------------------------------------------
    @patch("backend.services.serpapi_service.requests.get")
    def test_empty_news_results_returns_empty_list(self, mock_get):
        """Verify SerpAPIService returns [] when news_results is empty."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"news_results": []}
        mock_get.return_value = mock_resp

        service = SerpAPIService(api_key="mock_key")
        results = service.search_news("obscure search query")
        self.assertEqual(results, [])

    @patch("backend.services.serpapi_service.requests.get")
    def test_serpapi_google_no_results_error_handled_as_empty(self, mock_get):
        """Verify 'Google hasn't returned any results' is cleanly treated as empty results."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "error": "Google hasn't returned any results for this query."
        }
        mock_get.return_value = mock_resp

        service = SerpAPIService(api_key="mock_key")
        results = service.search_news("super rare term")
        self.assertEqual(results, [])

    @patch("backend.routes.news.serpapi_service.search_news")
    def test_route_returns_empty_results_cleanly(self, mock_search):
        """Verify GET /api/news/search returns 200 with total_results: 0 for empty results."""
        mock_search.return_value = []
        response = self.client.get("/api/news/search?q=nothingfound")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("total_results"), 0)
        self.assertEqual(data.get("results"), [])

    # -------------------------------------------------------------------------
    # 12: API Key Security & Redaction
    # -------------------------------------------------------------------------
    def test_redact_api_key_helper(self):
        """Verify redact_api_key masks actual key values."""
        secret = "secret_key_123456789"
        text = f"Error with api_key={secret} during request"
        redacted = redact_api_key(text, api_key=secret)
        self.assertNotIn(secret, redacted)
        self.assertIn("[REDACTED]", redacted)

    @patch("backend.services.serpapi_service.requests.get")
    def test_api_key_never_exposed_in_route_error(self, mock_get):
        """Verify API key never appears in Flask JSON error responses."""
        secret_key = "very_secret_serpapi_key_abc123"
        mock_get.side_effect = requests.exceptions.RequestException(
            f"https://serpapi.com/search.json?api_key={secret_key} failed"
        )

        with patch.dict(os.environ, {"SERPAPI_API_KEY": secret_key}):
            response = self.client.get("/api/news/search?q=test")
            self.assertEqual(response.status_code, 502)
            raw_text = response.get_data(as_text=True)
            self.assertNotIn(secret_key, raw_text)

    def test_env_is_ignored_by_git(self):
        """Verify .env is included in .gitignore."""
        gitignore_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".gitignore"))
        self.assertTrue(os.path.exists(gitignore_path))
        with open(gitignore_path, "r") as f:
            content = f.read()
        self.assertIn(".env", content)

    # -------------------------------------------------------------------------
    # 13: Server Responsiveness
    # -------------------------------------------------------------------------
    def test_health_check_responds_instantly(self):
        """Verify /health responds with 200 even after failed search attempts."""
        # Intentionally hit failing search first
        self.client.get("/api/news/search")
        # Ensure health endpoint remains completely responsive
        health_resp = self.client.get("/health")
        self.assertEqual(health_resp.status_code, 200)
        data = health_resp.get_json()
        self.assertEqual(data.get("status"), "healthy")


if __name__ == "__main__":
    unittest.main()
