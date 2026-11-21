import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from painradar.api.app import create_app


class AdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "auth.db"
        self.env = patch.dict(os.environ, {"PAINRADAR_ADMIN_PASSWORD": "s3cret"})
        self.env.start()
        self.client = TestClient(create_app([str(self.db)]))

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_health_is_public(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_api_requires_auth(self):
        res = self.client.get("/api/runs")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Basic", res.headers.get("www-authenticate", ""))

    def test_page_requires_auth(self):
        self.assertEqual(self.client.get("/").status_code, 401)

    def test_wrong_password_rejected(self):
        res = self.client.get("/api/runs", auth=("me", "wrong"))
        self.assertEqual(res.status_code, 401)

    def test_basic_auth_sets_30_day_cookie(self):
        res = self.client.get("/api/runs", auth=("me", "s3cret"))
        self.assertEqual(res.status_code, 200)
        cookie = res.headers.get("set-cookie", "")
        self.assertIn("pr_auth=", cookie)
        self.assertIn("Max-Age=2592000", cookie)
        # cookie keeps the session without re-sending credentials
        self.assertEqual(self.client.get("/api/runs").status_code, 200)

    def test_logout_clears_cookie(self):
        self.client.get("/api/runs", auth=("me", "s3cret"))
        self.assertEqual(self.client.get("/api/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/runs").status_code, 401)

    def test_static_assets_stay_public(self):
        self.assertEqual(self.client.get("/static/app.js").status_code, 200)


class NoPasswordTests(unittest.TestCase):
    def test_no_password_means_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"PAINRADAR_ADMIN_PASSWORD": ""}):
                client = TestClient(create_app([str(Path(tmp) / "open.db")]))
                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.get("/api/runs").status_code, 200)


if __name__ == "__main__":
    unittest.main()
