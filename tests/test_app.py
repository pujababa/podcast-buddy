import sys
import os
import unittest

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import app


class TestPodcastBuddy(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True

    def test_root_endpoint(self):
        """Test GET / redirects to /app."""
        response = self.client.get("/")
        self.assertIn(response.status_code, (301, 302))
        self.assertEqual(response.headers.get("Location"), "/app")

    def test_health_endpoint(self):
        """Test GET /health returns 200 and healthy status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        data = response.get_json()
        self.assertEqual(data.get("app"), "Podcast Buddy")
        self.assertEqual(data.get("status"), "healthy")

    def test_frontend_serving(self):
        """Test frontend route serves index.html."""
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Podcast Buddy", response.data)
        self.assertIn(b"AI-Powered Podcast &amp; News Discovery Assistant", response.data)


if __name__ == "__main__":
    unittest.main()
