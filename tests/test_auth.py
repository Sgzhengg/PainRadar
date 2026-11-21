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

    def test_page_serves_login_form(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("访问密码", res.text)
        self.assertIn('action="/login"', res.text)

    def test_login_form_sets_cookie(self):
        res = self.client.post(
            "/login", data={"password": "s3cret"}, follow_redirects=False
        )
        self.assertEqual(res.status_code, 303)
        self.assertIn("pr_auth=", res.headers.get("set-cookie", ""))
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("app.js", page.text)

    def test_wrong_login_rejected(self):
        res = self.client.post("/login", data={"password": "nope"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("密码不正确", res.text)

    def test_wrong_password_rejected(self):
        res = self.client.get("/api/runs", auth=("me", "wrong"))
        self.assertEqual(res.status_code, 401)

    def test_basic_auth_sets_30_day_cookie(self):
        res = self.client.get("/api/runs", auth=("me", "s3cret"))
        self.assertEqual(res.status_code, 200)
        cookie = res.headers.get("set-cookie", "")
        self.assertIn("pr_auth=", cookie)
        self.assertIn("Max-Age=2592000", cookie)
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
