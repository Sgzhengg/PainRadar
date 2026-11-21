import json
import tempfile
import unittest
from pathlib import Path

from painradar.indie.clean import is_noise
from painradar.indie.loader import build_contexts, load_threads
from painradar.indie.models import Comment, ContextBlock, Signal, Thread
from painradar.indie.reduce_stage import _score


class NoiseTests(unittest.TestCase):
    def test_short(self):
        self.assertTrue(is_noise("好用")[0])
        self.assertEqual(is_noise("好用")[1], "too_short")

    def test_emoji_only(self):
        self.assertTrue(is_noise("👍👍👍👍👍👍")[0])

    def test_at_only(self):
        self.assertTrue(is_noise("@张三 @李四 哈哈哈哈")[0])

    def test_ad(self):
        ok, reason = is_noise("想要同款的加V私我，链接在主页")
        self.assertTrue(ok)
        self.assertEqual(reason, "ad")

    def test_filler(self):
        self.assertTrue(is_noise("确实")[0])

    def test_good(self):
        ok, _ = is_noise("Smallpdf 每次导出都要重新登录，订阅还死贵")
        self.assertFalse(ok)


class LoaderTests(unittest.TestCase):
    def test_nested_thread(self):
        data = [
            {
                "note_id": "n1",
                "title": "有没有便宜的 PDF 工具",
                "desc": "受够了订阅",
                "url": "https://example.com/n1",
                "liked_count": 120,
                "comments": [
                    {
                        "comment_id": "c1",
                        "content": "Smallpdf 订阅太贵了，而且导出还限次数",
                        "like_count": 88,
                        "sub_comments": [
                            {"comment_id": "c2", "content": "我也是，后来改用本地的了", "like_count": 12}
                        ],
                    },
                    {"comment_id": "c3", "content": "👍👍👍", "like_count": 1},
                ],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            threads = load_threads(path)
        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0].title, "有没有便宜的 PDF 工具")
        self.assertEqual(threads[0].comments[0].likes, 88)
        self.assertEqual(len(threads[0].comments[0].replies), 1)

        blocks, stats = build_contexts(threads, top_comments=3)
        self.assertEqual(len(blocks), 1)
        self.assertIn("【原帖】", blocks[0].render())
        self.assertGreaterEqual(stats["kept_comments"], 1)
        self.assertGreaterEqual(stats["drop_too_short"], 1)


class ScoreTests(unittest.TestCase):
    def test_bounds(self):
        self.assertGreaterEqual(_score(1, 0, 0.0, 5, set()), 1.0)
        self.assertLessEqual(_score(200, 100000, 1.0, 1, {"竞品吐槽", "付费信号"}), 10.0)

    def test_ordering(self):
        low = _score(2, 5, 0.1, 4, {"竞品吐槽"})
        high = _score(20, 800, 0.9, 2, {"竞品吐槽", "付费信号"})
        self.assertGreater(high, low)


class ContextRenderTests(unittest.TestCase):
    def test_replies_rendered(self):
        block = ContextBlock(
            thread_id="t1",
            url="u",
            title="标题",
            body="正文",
            comments=[Comment("c1", "主评论内容很长很长", likes=10, replies=[Comment("c2", "回复内容也很长", likes=2)])],
        )
        text = block.render()
        self.assertIn("└回复", text)
        self.assertIn("赞10", text)


class FilterTests(unittest.TestCase):
    def test_off_domain_dropped(self):
        threads = [
            Thread("t1", "PDF 压缩工具推荐", "", comments=[Comment("c1", "这个压缩工具很好用但太贵了", likes=3)]),
            Thread("t2", "Windows 壁纸轮播失效", "", comments=[Comment("c2", "求一个替代软件，能自动换壁纸", likes=5)]),
        ]
        blocks, stats = build_contexts(threads, domain_terms=["pdf"])
        self.assertEqual(len(blocks), 1)
        self.assertEqual(stats["drop_off_domain"], 1)


if __name__ == "__main__":
    unittest.main()
