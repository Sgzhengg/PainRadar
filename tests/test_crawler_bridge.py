import json
import sys
import tempfile
import time
import unittest
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


if __name__ == "__main__":
    unittest.main()
