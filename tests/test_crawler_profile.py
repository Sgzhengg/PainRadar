import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "painradar-crawler"))

import app as bridge  # noqa: E402


def _zip(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buf.getvalue()


class ProfileUploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        bridge.PROFILE_ROOT = base / "browser_data"
        bridge.PROFILE_ROOT.mkdir()
        bridge.API_TOKEN = "tok"
        self.client = TestClient(bridge.app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_requires_token(self):
        res = self.client.post(
            "/api/profiles/xhs",
            files={"file": ("p.zip", _zip({"a.txt": "x"}), "application/zip")},
        )
        self.assertEqual(res.status_code, 401)

    def test_upload_and_list(self):
        payload = _zip({"xhs_user_data_dir/Default/Cookies": "sid=1"})
        res = self.client.post(
            "/api/profiles/xhs",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("profile.zip", payload, "application/zip")},
        )
        self.assertEqual(res.status_code, 200, res.text)
        dest = bridge.PROFILE_ROOT / "xhs_user_data_dir" / "Default" / "Cookies"
        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_text(encoding="utf-8"), "sid=1")

        listed = self.client.get("/api/profiles", headers={"Authorization": "Bearer tok"}).json()
        self.assertIn("xhs", [p["platform"] for p in listed["profiles"]])

    def test_zip_slip_rejected(self):
        payload = _zip({"../evil.txt": "x"})
        res = self.client.post(
            "/api/profiles/xhs",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("evil.zip", payload, "application/zip")},
        )
        self.assertEqual(res.status_code, 400)

    def test_bad_platform(self):
        res = self.client.post(
            "/api/profiles/weibo",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("p.zip", _zip({"a": "x"}), "application/zip")},
        )
        self.assertEqual(res.status_code, 400)


class PainRadarProxyTests(unittest.TestCase):
    def test_proxy_without_crawler_url(self):
        from painradar.api.app import create_app

        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app([str(Path(tmp) / "p.db")]))
            res = client.post(
                "/api/crawler/profiles/xhs",
                files={"file": ("p.zip", _zip({"a": "x"}), "application/zip")},
            )
            self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
