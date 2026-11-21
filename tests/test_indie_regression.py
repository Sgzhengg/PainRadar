import tempfile
import unittest
from pathlib import Path

from painradar.indie.cli import main
from painradar.indie.llm import LLM, LLMError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "indie_demo.json"
CACHE = ROOT / "tests" / "fixtures" / "indie_cache"


class OfflineReplayTests(unittest.TestCase):
    def test_offline_run_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"
            code = main(
                [
                    "--input", str(FIXTURE),
                    "--keyword", "回归样例",
                    "--cache-dir", str(CACHE),
                    "--model", "deepseek-chat",
                    "--offline",
                    "--workers", "1",
                    "--out", str(out),
                ]
            )
            self.assertEqual(code, 0)
            report = out.read_text(encoding="utf-8")

        # cleaning must drop the emoji / @ / ad comments and keep replies
        self.assertIn("有效信号 7 条", report)
        self.assertIn("保留评论 11 条", report)

        # the three clusters from the frozen model response
        self.assertIn("PDF本地买断工具", report)
        self.assertIn("扫描件表格转Excel", report)
        self.assertIn("6.3", report)

        # evidence must carry a verbatim quote and a link
        self.assertIn("网页里根本没入口", report)
        self.assertIn("https://example.com/posts/demo-1", report)

        # rank order is score-descending
        first = report.index("PDF本地买断工具")
        second = report.index("扫描件表格转Excel")
        self.assertLess(first, second)

    def test_offline_cache_miss_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = LLM(cache_dir=tmp, offline=True)
            try:
                with self.assertRaises(LLMError):
                    llm.chat_json("system", "user-with-no-cache", required=("x",))
            finally:
                llm.close()


if __name__ == "__main__":
    unittest.main()
