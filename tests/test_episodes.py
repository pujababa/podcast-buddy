import os
import sys
import tempfile
import unittest
import sqlite3
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
    delete_episode,
    DatabaseError
)


class TestPhase4DatabaseAndEpisodes(unittest.TestCase):
    def setUp(self):
        # Create a temporary SQLite database for each test to ensure isolation
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.test_db_path = os.path.join(self.temp_dir.name, "test_podcast_buddy.db")
        
        # Patch the module-level DATABASE_PATH
        self.db_patcher = patch.object(db_module, "DATABASE_PATH", self.test_db_path)
        self.db_patcher.start()
        
        # Initialize test database
        init_db(self.test_db_path)
        
        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True

    def tearDown(self):
        self.db_patcher.stop()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. Database Initialization Tests
    # -------------------------------------------------------------------------
    def test_database_initialization_creates_tables(self):
        """Verify that init_db creates episodes and episode_sources tables."""
        conn = get_db_connection(self.test_db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()

        self.assertIn("episodes", tables)
        self.assertIn("episode_sources", tables)

    def test_database_reinitialization_is_idempotent(self):
        """Verify that calling init_db again does not destroy existing data."""
        articles = [
            {
                "id": "news-1",
                "title": "Article 1",
                "publisher": "Tech Daily",
                "snippet": "Summary 1",
                "date": "2026-10-06",
                "url": "https://example.com/art1"
            }
        ]
        created = create_episode("Original Title", "Description", articles, db_path=self.test_db_path)
        self.assertIsNotNone(created.get("id"))

        # Re-run initialization
        init_db(self.test_db_path)

        # Confirm data still persists
        ep = get_episode(created["id"], db_path=self.test_db_path)
        self.assertIsNotNone(ep)
        self.assertEqual(ep["title"], "Original Title")
        self.assertEqual(len(ep["sources"]), 1)

    # -------------------------------------------------------------------------
    # 2. POST /api/episodes - Success Cases
    # -------------------------------------------------------------------------
    def test_create_episode_success(self):
        """Verify POST /api/episodes with valid data returns 201 and created episode."""
        payload = {
            "title": "AI News Digest",
            "description": "Weekly highlights in artificial intelligence.",
            "articles": [
                {
                    "id": "news-1",
                    "title": "New Frontier in Machine Learning",
                    "publisher": "AI Journal",
                    "snippet": "Researchers announce breakthroughs in reasoning.",
                    "date": "1 hour ago",
                    "url": "https://example.com/ml-breakthrough"
                },
                {
                    "id": "news-2",
                    "title": "Robotics in 2026",
                    "publisher": "RoboNews",
                    "snippet": "Automated labs scale across biotech.",
                    "date": "Yesterday",
                    "url": "https://example.com/robotics-2026"
                }
            ]
        }

        response = self.client.post("/api/episodes", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        
        episode = data.get("episode")
        self.assertIsNotNone(episode)
        self.assertEqual(episode.get("title"), "AI News Digest")
        self.assertEqual(episode.get("description"), "Weekly highlights in artificial intelligence.")
        self.assertEqual(episode.get("status"), "draft")
        self.assertIn("created_at", episode)
        self.assertIn("updated_at", episode)

        # Verify sources
        sources = episode.get("sources")
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["article_id"], "news-1")
        self.assertEqual(sources[0]["title"], "New Frontier in Machine Learning")
        self.assertEqual(sources[0]["publisher"], "AI Journal")
        self.assertEqual(sources[0]["url"], "https://example.com/ml-breakthrough")
        self.assertEqual(sources[1]["article_id"], "news-2")

    # -------------------------------------------------------------------------
    # 3. POST /api/episodes - Validation Failures (4xx)
    # -------------------------------------------------------------------------
    def test_create_episode_missing_title(self):
        """Verify 400 when 'title' is missing."""
        payload = {
            "articles": [{"id": "1", "title": "T", "publisher": "P", "url": "https://ex.com"}]
        }
        response = self.client.post("/api/episodes", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "MISSING_TITLE")

    def test_create_episode_empty_title(self):
        """Verify 400 when 'title' is empty or whitespace only."""
        for empty in ("", "   ", "\t\n"):
            payload = {
                "title": empty,
                "articles": [{"id": "1", "title": "T", "publisher": "P", "url": "https://ex.com"}]
            }
            response = self.client.post("/api/episodes", json=payload)
            self.assertEqual(response.status_code, 400)
            data = response.get_json()
            self.assertEqual(data.get("code"), "EMPTY_TITLE")

    def test_create_episode_title_too_long(self):
        """Verify 400 when title exceeds 200 characters."""
        payload = {
            "title": "A" * 201,
            "articles": [{"id": "1", "title": "T", "publisher": "P", "url": "https://ex.com"}]
        }
        response = self.client.post("/api/episodes", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data.get("code"), "TITLE_TOO_LONG")

    def test_create_episode_description_too_long(self):
        """Verify 400 when description exceeds 1000 characters."""
        payload = {
            "title": "Valid Title",
            "description": "D" * 1001,
            "articles": [{"id": "1", "title": "T", "publisher": "P", "url": "https://ex.com"}]
        }
        response = self.client.post("/api/episodes", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data.get("code"), "DESCRIPTION_TOO_LONG")

    def test_create_episode_missing_articles(self):
        """Verify 400 when 'articles' field is omitted."""
        payload = {"title": "Valid Title"}
        response = self.client.post("/api/episodes", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data.get("code"), "MISSING_ARTICLES")

    def test_create_episode_empty_articles_array(self):
        """Verify 400 when 'articles' is an empty list."""
        payload = {"title": "Valid Title", "articles": []}
        response = self.client.post("/api/episodes", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data.get("code"), "EMPTY_ARTICLES")

    def test_create_episode_invalid_articles_type(self):
        """Verify 400 when 'articles' is not an array."""
        payload = {"title": "Valid Title", "articles": "not-a-list"}
        response = self.client.post("/api/episodes", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data.get("code"), "INVALID_ARTICLES_TYPE")

    def test_create_episode_invalid_article_object(self):
        """Verify 400 when an article item is not a dictionary or missing required keys."""
        # Case A: Article is not a dict
        payload1 = {"title": "Valid", "articles": ["just-a-string"]}
        resp1 = self.client.post("/api/episodes", json=payload1)
        self.assertEqual(resp1.status_code, 400)
        self.assertEqual(resp1.get_json().get("code"), "INVALID_ARTICLE")

        # Case B: Missing article id
        payload2 = {"title": "Valid", "articles": [{"title": "T", "publisher": "P", "url": "https://ex.com"}]}
        resp2 = self.client.post("/api/episodes", json=payload2)
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("id", resp2.get_json().get("error", "").lower())

        # Case C: Missing article title
        payload3 = {"title": "Valid", "articles": [{"id": "1", "publisher": "P", "url": "https://ex.com"}]}
        resp3 = self.client.post("/api/episodes", json=payload3)
        self.assertEqual(resp3.status_code, 400)
        self.assertIn("title", resp3.get_json().get("error", "").lower())

        # Case D: Missing publisher
        payload4 = {"title": "Valid", "articles": [{"id": "1", "title": "T", "url": "https://ex.com"}]}
        resp4 = self.client.post("/api/episodes", json=payload4)
        self.assertEqual(resp4.status_code, 400)
        self.assertIn("publisher", resp4.get_json().get("error", "").lower())

    def test_create_episode_invalid_url(self):
        """Verify 400 when article URL is invalid or malformed."""
        invalid_urls = [
            "",
            "   ",
            "not-a-url",
            "ftp://example.com/file",
            "javascript:alert(1)",
            "http://",
            "https://"
        ]
        for bad_url in invalid_urls:
            payload = {
                "title": "Title",
                "articles": [
                    {
                        "id": "1",
                        "title": "T",
                        "publisher": "P",
                        "url": bad_url
                    }
                ]
            }
            response = self.client.post("/api/episodes", json=payload)
            self.assertEqual(response.status_code, 400, f"Expected 400 for bad URL '{bad_url}'")
            data = response.get_json()
            self.assertEqual(data.get("code"), "INVALID_ARTICLE")

    # -------------------------------------------------------------------------
    # 4. GET /api/episodes/<id> Tests
    # -------------------------------------------------------------------------
    def test_get_existing_episode(self):
        """Verify GET /api/episodes/<id> returns 200 and full episode details."""
        articles = [
            {"id": "a-1", "title": "Title 1", "publisher": "Pub 1", "url": "https://ex.com/1"},
            {"id": "a-2", "title": "Title 2", "publisher": "Pub 2", "url": "https://ex.com/2"}
        ]
        created = create_episode("Episode X", "Desc X", articles, db_path=self.test_db_path)
        ep_id = created["id"]

        response = self.client.get(f"/api/episodes/{ep_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        
        ep = data.get("episode")
        self.assertEqual(ep["id"], ep_id)
        self.assertEqual(ep["title"], "Episode X")
        self.assertEqual(len(ep["sources"]), 2)

    def test_get_missing_episode_returns_404(self):
        """Verify GET /api/episodes/<non_existent_id> returns 404."""
        response = self.client.get("/api/episodes/999999")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "NOT_FOUND")

    # -------------------------------------------------------------------------
    # 5. GET /api/episodes (List) Tests
    # -------------------------------------------------------------------------
    def test_list_episodes_sorted_newest_first(self):
        """Verify GET /api/episodes returns all episodes sorted newest first."""
        articles = [{"id": "1", "title": "T", "publisher": "P", "url": "https://ex.com"}]
        
        ep1 = create_episode("Old Episode", "", articles, db_path=self.test_db_path)
        ep2 = create_episode("New Episode", "", articles, db_path=self.test_db_path)

        response = self.client.get("/api/episodes")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("total"), 2)

        episodes = data.get("episodes")
        # Newest (ep2) must be first
        self.assertEqual(episodes[0]["id"], ep2["id"])
        self.assertEqual(episodes[1]["id"], ep1["id"])

    # -------------------------------------------------------------------------
    # 6. DELETE /api/episodes/<id> Tests
    # -------------------------------------------------------------------------
    def test_delete_existing_episode_and_cascading_sources(self):
        """Verify DELETE /api/episodes/<id> deletes the episode and its sources."""
        articles = [
            {"id": "a-1", "title": "T1", "publisher": "P1", "url": "https://ex.com/1"},
            {"id": "a-2", "title": "T2", "publisher": "P2", "url": "https://ex.com/2"}
        ]
        created = create_episode("To Delete", "", articles, db_path=self.test_db_path)
        ep_id = created["id"]

        # Confirm sources exist in DB
        conn = get_db_connection(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM episode_sources WHERE episode_id = ?", (ep_id,))
        self.assertEqual(cursor.fetchone()["cnt"], 2)
        conn.close()

        # Delete episode
        response = self.client.delete(f"/api/episodes/{ep_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

        # Confirm episode is gone (404)
        get_resp = self.client.get(f"/api/episodes/{ep_id}")
        self.assertEqual(get_resp.status_code, 404)

        # Confirm sources are gone from database
        conn = get_db_connection(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM episode_sources WHERE episode_id = ?", (ep_id,))
        self.assertEqual(cursor.fetchone()["cnt"], 0)
        conn.close()

    def test_delete_missing_episode_returns_404(self):
        """Verify DELETE on non-existent episode returns 404."""
        response = self.client.delete("/api/episodes/999999")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "NOT_FOUND")

    def test_delete_does_not_affect_unrelated_episodes(self):
        """Verify deleting one episode leaves other episodes completely intact."""
        articles = [{"id": "1", "title": "T", "publisher": "P", "url": "https://ex.com"}]
        ep1 = create_episode("Keep Me", "", articles, db_path=self.test_db_path)
        ep2 = create_episode("Delete Me", "", articles, db_path=self.test_db_path)

        self.client.delete(f"/api/episodes/{ep2['id']}")

        # Ep1 should still be present
        rem = get_episode(ep1["id"], db_path=self.test_db_path)
        self.assertIsNotNone(rem)
        self.assertEqual(rem["title"], "Keep Me")

    # -------------------------------------------------------------------------
    # 7. Transaction Safety & Rollback Tests
    # -------------------------------------------------------------------------
    def test_transaction_rollback_on_failure(self):
        """Verify that a database error during source insertion rolls back the entire episode creation."""
        articles = [
            {"id": "a-1", "title": "T1", "publisher": "P1", "url": "https://ex.com/1"},
            {"id": "a-2", "title": "T2", "publisher": "P2", "url": "https://ex.com/2"}
        ]
        
        # Count episodes before
        conn = get_db_connection(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM episodes")
        initial_count = cursor.fetchone()["cnt"]

        # Create a trigger that aborts any insertion into episode_sources
        conn.execute("""
            CREATE TRIGGER fail_sources_insert
            BEFORE INSERT ON episode_sources
            BEGIN
                SELECT RAISE(FAIL, 'Simulated database write failure');
            END;
        """)
        conn.commit()
        conn.close()

        # Attempt to create episode; should raise DatabaseError due to the trigger
        with self.assertRaises(DatabaseError):
            create_episode("Failing Episode", "Desc", articles, db_path=self.test_db_path)

        # Confirm no orphan episode was left committed in episodes table
        conn = get_db_connection(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM episodes")
        final_count = cursor.fetchone()["cnt"]
        conn.close()

        self.assertEqual(final_count, initial_count, "Rollback failed: partial episode record was committed!")

    # -------------------------------------------------------------------------
    # 8. Regression & Health Endpoint Tests
    # -------------------------------------------------------------------------
    def test_root_endpoint_persists(self):
        """Verify GET / returns 200 with Podcast Buddy info."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("app"), "Podcast Buddy")
        self.assertEqual(data.get("status"), "running")

    def test_health_endpoint_persists(self):
        """Verify GET /health returns 200 and healthy status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "healthy")

    @patch("backend.routes.news.serpapi_service.search_news")
    def test_phase3_news_route_persists(self, mock_search):
        """Verify GET /api/news/search still functions alongside Phase 4 endpoints."""
        mock_search.return_value = [
            {
                "id": "news-1",
                "title": "Quantum Computing Update",
                "publisher": "Tech Post",
                "snippet": "New QPU launched.",
                "date": "Today",
                "url": "https://example.com/quantum"
            }
        ]
        response = self.client.get("/api/news/search?q=quantum")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("total_results"), 1)


if __name__ == "__main__":
    unittest.main()
