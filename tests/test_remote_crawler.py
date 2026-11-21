import json
import tempfile
import unittest
from pathlib import Path

import httpx

from painradar.connectors.remote_mediacrawler import (
    NeedLoginError,
    RemoteMediaCrawler,
)
from painradar.store import Store

SAMPLE = [
    {
        "note_id": "n1",
        "title": "受够了 Smallpdf 的订阅",
        "desc": "每个月就转几个文件",
        "url": "https://example.com/n1",
        "liked_count": 342,
        "comments": [
            {
                "comment_id": "c1",
                "content": "取消订阅的入口根本找不到，只能发邮件",
                "like_count": 286,
                "sub_comments": [
                    {"comment_id": "c1r1", "content": "同求一个本地处理、一次买断的", "like_count": 74}
                ],
            },
            {"comment_id": "c2", "content": "👍👍👍", "like_count": 1},
        ],
    }
]


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


class RemoteCrawlerTests(unittest.TestCase):
    def test_start_poll_ingest(self):
        state = {"polls": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers.get("authorization"), "Bearer tok")
            path = request.url.path
            if path == "/api/crawl":
                body = json.loads(request.content)
                self.assertEqual(body["platform"], "xhs")
                self.assertEqual(body["keywords"], ["PDF 转换"])
                self.assertEqual(body["max_notes"], 30)
                return httpx.Response(200, json={"task_id": "t1", "status": "queued"})
            if path == "/api/tasks/t1":
                state["polls"] += 1
                if state["polls"] < 2:
                    return httpx.Response(200, json={"task_id": "t1", "status": "running", "progress": 40})
                return httpx.Response(200, json={"task_id": "t1", "status": "completed", "progress": 100})
            if path == "/api/tasks/t1/results":
                return httpx.Response(200, json={"data": SAMPLE})
            raise AssertionError(f"unexpected path {path}")

        crawler = RemoteMediaCrawler(base_url="https://crawler.test", token="tok", client=_client(handler))
        stages = []
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            store = Store(db)
            try:
                task = crawler.start_crawl("xhs", ["PDF 转换"], max_notes=30)
                self.assertEqual(task.task_id, "t1")
                result = crawler.poll_and_ingest(
                    "t1", "pet_water_fountain", store, interval=0,
                    on_stage=lambda name, extra: stages.append(name),
                )
                rows = store.items("pet_water_fountain")
            finally:
                store.close()

        self.assertEqual(result["inserted"], len(rows))
        self.assertGreater(len(rows), 0)
        self.assertEqual(max(r["likes"] for r in rows), 286)
        self.assertIn("crawling", stages)
        self.assertIn("ingesting", stages)

    def test_need_login(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"need_login": True})

        crawler = RemoteMediaCrawler(base_url="https://crawler.test", token="tok", client=_client(handler))
        with self.assertRaises(NeedLoginError):
            crawler.start_crawl("xhs", ["x"], max_notes=5)

    def test_unconfigured(self):
        crawler = RemoteMediaCrawler(base_url="", token="", client=_client(lambda r: httpx.Response(200)))
        health = crawler.health()
        self.assertFalse(health["ok"])


if __name__ == "__main__":
    unittest.main()
