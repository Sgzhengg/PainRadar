import json
import tempfile
import unittest
from pathlib import Path

from painradar.connectors.mediacrawler import MediaCrawlerConnector
from painradar.pipeline import ingest_items
from painradar.store import Store


def _sample():
    return [
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
                {"comment_id": "c2", "content": "👍👍👍", "like_count": 2},
                {"comment_id": "c3", "content": "加V私我，链接在主页", "like_count": 0},
            ],
        }
    ]


class ConnectorTests(unittest.TestCase):
    def test_context_likes_and_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "xhs.json"
            path.write_text(json.dumps(_sample(), ensure_ascii=False), encoding="utf-8")
            conn = MediaCrawlerConnector(path=path, category="pet_water_fountain")
            items = list(conn.fetch())

        # emoji + ad dropped, top comment + its reply kept
        self.assertEqual(len(items), 2)
        self.assertEqual(conn.stats["dropped"], 2)
        first = next(i for i in items if i.item_id.endswith("c1"))
        self.assertEqual(first.likes, 286)
        self.assertEqual(first.replies, 1)
        self.assertIn("受够了 Smallpdf 的订阅", first.parent_context)
        self.assertIn("取消订阅的入口", first.parent_context)
        reply = next(i for i in items if i.item_id.endswith("c1r1"))
        self.assertIn("同求一个本地处理", reply.text)
        self.assertEqual(reply.likes, 74)

    def test_ingest_into_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            path = Path(tmp) / "xhs.json"
            path.write_text(json.dumps(_sample(), ensure_ascii=False), encoding="utf-8")
            store = Store(db)
            try:
                conn = MediaCrawlerConnector(path=path, category="pet_water_fountain")
                result = ingest_items(store, conn.fetch(), "pet_water_fountain")
                rows = store.items("pet_water_fountain")
            finally:
                store.close()
        self.assertEqual(result.inserted, 2)
        self.assertTrue(all(r["parent_context"] for r in rows))
        self.assertEqual(max(r["likes"] for r in rows), 286)


if __name__ == "__main__":
    unittest.main()
