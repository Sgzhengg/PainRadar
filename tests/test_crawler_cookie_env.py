import json
import os
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "painradar-crawler"))

import runner as crawler_runner  # noqa: E402


class EnvCookieTests(unittest.TestCase):
    def test_platform_cookie_env_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            crawler = crawler_runner.MediaCrawlerRunner(home=tmp)
            crawler.cookie_dir = Path(tmp) / "cookies"
            os.environ["PLATFORM_COOKIES_XHS"] = "sid=abc; uid=1"
            try:
                crawler._write_cookies(
                    crawler_runner.CrawlSpec(platform="xhs", keywords=["x"])
                )
            finally:
                os.environ.pop("PLATFORM_COOKIES_XHS", None)

            target = Path(tmp) / "browser_data" / "xhs_cookies.json"
            self.assertTrue(target.exists())
            cookies = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(cookies[0]["name"], "sid")
            self.assertEqual(cookies[0]["value"], "abc")


if __name__ == "__main__":
    unittest.main()
