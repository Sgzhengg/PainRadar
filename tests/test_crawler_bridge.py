import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "painradar-crawler"))

import runner as crawler_runner  # noqa: E402
import storage as crawler_storage  # noqa: E402
import app as bridge  # noqa: E402


class CookieTests(unittest.TestCase):
    def test_string_cookie(self):
        cookies = crawler_runner.parse_cookies("a=1; b=2", "xhs")
        self.assertEqual([c["name"] for c in cookies], ["a", "b"])
        self.assertEqual(cookies[0]["domain"], ".xiaohongshu.com")

    def test_list_cookie(self):
        raw = [{"name": "sid", "value": "x"}]
        self.assertEqual(crawler_runner.parse_cookies(raw, "xhs"), raw)
        self.assertIsNone(crawler_runner.parse_cookies("", "xhs"))


class CollectTests(unittest.TestCase):
    def test_merges_note_and_comment_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            data = home / "data" / "xhs" / "json"
            data.mkdir(parents=True)
            (data / "search_contents.json").write_text(
                json.dumps([{
                    "note_id": "n1",
                    "title": "受够了 Smallpdf",
                    "desc": "每月只转几个文件",
                    "url": "https://example.com/n1",
                    "liked_count": 342,
                }], ensure_ascii=False),
                encoding="utf-8",
            )
            (data / "search_comments.json").write_text(
                json.dumps([{
                    "comment_id": "c1",
                    "note_id": "n1",
                    "content": "取消入口找不到",
                    "like_count": 286,
                }], ensure_ascii=False),
                encoding="utf-8",
            )
            crawler = crawler_runner.MediaCrawlerRunner(home=str(home))
            crawler.data_dir = home / "data"
            notes = crawler.collect(started=time.time() - 10, max_notes=10)

        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["note_id"], "n1")
        self.assertEqual(notes[0]["comments"][0]["content"], "取消入口找不到")
        self.assertEqual(notes[0]["comments"][0]["like_count"], 286)

    def test_note_without_comments_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            data = home / "data"
            data.mkdir()
            (data / "notes.json").write_text(
                json.dumps([{"note_id": "n1", "title": "t"}]), encoding="utf-8"
            )
            crawler = crawler_runner.MediaCrawlerRunner(home=str(home))
            crawler.data_dir = data
            self.assertEqual(crawler.collect(time.time() - 10, 10), [])


class NeedLoginTests(unittest.TestCase):
    def test_need_login_output_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            crawler = crawler_runner.MediaCrawlerRunner(home=tmp)
            crawler.template = (
                f'"{sys.executable}" -c "print(\'需要登录\')"'
            )
            spec = crawler_runner.CrawlSpec(platform="xhs", keywords=["x"])
            with self.assertRaises(crawler_runner.NeedLoginError):
                crawler.run(spec)


class FakeRunner:
    home = "/tmp/fake-media-crawler"

    def run(self, spec, on_progress=None):
        if on_progress:
            on_progress("crawling", 50, "fake")
        return [{
            "note_id": "n1",
            "title": "fake",
            "desc": "",
            "url": "https://example.com/n1",
            "liked_count": 10,
            "comments": [{"comment_id": "c1", "content": "太麻烦", "like_count": 10, "sub_comments": []}],
        }]


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        bridge.store = crawler_storage.TaskStore(base / "tasks.db")
        bridge.RESULT_DIR = base / "results"
        bridge.RESULT_DIR.mkdir()
        bridge.runner = FakeRunner()
        bridge.API_TOKEN = "tok"
        self.client = TestClient(bridge.app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_requires_token(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.post("/api/crawl", json={}).status_code, 401)

    def test_crawl_lifecycle(self):
        headers = {"Authorization": "Bearer tok"}
        res = self.client.post(
            "/api/crawl",
            headers=headers,
            json={"platform": "xhs", "keywords": ["PDF"], "max_notes": 5},
        )
        self.assertEqual(res.status_code, 202)
        task_id = res.json()["task_id"]

        for _ in range(50):
            status = self.client.get(f"/api/tasks/{task_id}", headers=headers).json()
            if status["status"] in ("completed", "failed"):
                break
            time.sleep(0.05)
        self.assertEqual(status["status"], "completed", status)

        results = self.client.get(f"/api/tasks/{task_id}/results", headers=headers)
        self.assertEqual(results.status_code, 200)
        self.assertEqual(results.json()[0]["note_id"], "n1")


class BlockingRunner:
    home = "/tmp/blocking"

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, spec, on_progress=None):
        self.started.set()
        self.release.wait(10)
        return [{
            "note_id": "n1", "title": "t", "desc": "", "url": "https://example.com/n1",
            "liked_count": 1,
            "comments": [{"comment_id": "c1", "content": "x", "like_count": 1, "sub_comments": []}],
        }]


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        bridge.store = crawler_storage.TaskStore(base / "tasks.db")
        bridge.RESULT_DIR = base / "results"
        bridge.RESULT_DIR.mkdir()
        bridge.API_TOKEN = "tok"
        self.runner = BlockingRunner()
        bridge.runner = self.runner
        self.old_slots = bridge.TASK_SLOTS
        bridge.TASK_SLOTS = threading.BoundedSemaphore(1)
        self.client = TestClient(bridge.app)

    def tearDown(self):
        self.runner.release.set()
        bridge.TASK_SLOTS = self.old_slots
        self.tmp.cleanup()

    def test_second_concurrent_task_is_rejected(self):
        headers = {"Authorization": "Bearer tok"}
        first = self.client.post(
            "/api/crawl", headers=headers,
            json={"platform": "xhs", "keywords": ["PDF"], "max_notes": 5},
        )
        self.assertEqual(first.status_code, 202)
        self.assertTrue(self.runner.started.wait(5))

        second = self.client.post(
            "/api/crawl", headers=headers,
            json={"platform": "xhs", "keywords": ["PDF"], "max_notes": 5},
        )
        self.assertEqual(second.status_code, 429)

        self.runner.release.set()
        task_id = first.json()["task_id"]
        for _ in range(50):
            status = self.client.get(f"/api/tasks/{task_id}", headers=headers).json()
            if status["status"] in ("completed", "failed"):
                break
            time.sleep(0.05)
        self.assertEqual(status["status"], "completed", status)


class PlatformStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old_profile = bridge.PROFILE_ROOT
        self.old_cookie = bridge.COOKIE_DIR
        self.old_token = bridge.API_TOKEN
        bridge.PROFILE_ROOT = base / "browser_data"
        bridge.COOKIE_DIR = base / "cookies"
        bridge.PROFILE_ROOT.mkdir()
        bridge.COOKIE_DIR.mkdir()
        bridge.API_TOKEN = "tok"
        self.client = TestClient(bridge.app)

    def tearDown(self):
        bridge.PROFILE_ROOT = self.old_profile
        bridge.COOKIE_DIR = self.old_cookie
        bridge.API_TOKEN = self.old_token
        self.tmp.cleanup()

    def test_cookie_file_marks_platform_ready(self):
        (bridge.COOKIE_DIR / "xhs.txt").write_text("web_session=x", encoding="utf-8")
        res = self.client.get("/api/platforms", headers={"Authorization": "Bearer tok"})
        self.assertEqual(res.status_code, 200, res.text)
        items = {p["platform"]: p for p in res.json()["platforms"]}
        self.assertEqual(len(items), 7)
        self.assertTrue(items["xhs"]["ready"])
        self.assertEqual(items["xhs"]["cookie_source"], "file")
        self.assertFalse(items["dy"]["ready"])

    def test_env_cookie_marks_platform_ready(self):
        with patch.dict(os.environ, {"PLATFORM_COOKIES_DY": "sessionid=x"}):
            res = self.client.get("/api/platforms", headers={"Authorization": "Bearer tok"})
        items = {p["platform"]: p for p in res.json()["platforms"]}
        self.assertTrue(items["dy"]["ready"])
        self.assertEqual(items["dy"]["cookie_source"], "env")

    def test_set_cookie_marks_platform_ready(self):
        res = self.client.post(
            "/api/platforms/xhs/cookie",
            headers={"Authorization": "Bearer tok"},
            json={"cookie": "web_session=abc"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue((bridge.COOKIE_DIR / "xhs.txt").exists())
        status = self.client.get("/api/platforms", headers={"Authorization": "Bearer tok"}).json()
        xhs = [p for p in status["platforms"] if p["platform"] == "xhs"][0]
        self.assertTrue(xhs["ready"])
        self.assertEqual(xhs["cookie_source"], "file")


if __name__ == "__main__":
    unittest.main()
