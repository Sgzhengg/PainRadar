import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "painradar-crawler"))

import runner as crawler_runner  # noqa: E402


class EnvCookieTests(unittest.TestCase):
    def test_env_cookie_becomes_cli_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            crawler = crawler_runner.MediaCrawlerRunner(home=tmp)
            crawler.cookie_dir = Path(tmp) / "cookies"
            os.environ["PLATFORM_COOKIES_XHS"] = "web_session=abc; a1=xyz"
            try:
                spec = crawler_runner.CrawlSpec(platform="xhs", keywords=["PDF"])
                cookies = crawler.resolve_cookies(spec)
                command = crawler.build_command(spec, cookies)
            finally:
                os.environ.pop("PLATFORM_COOKIES_XHS", None)

            self.assertIn("web_session=abc", cookies)
            self.assertIn("--cookies", command)
            self.assertEqual(command[command.index("--cookies") + 1], cookies)
            self.assertTrue((Path(tmp) / "cookies" / "xhs.txt").exists())

    def test_request_cookie_wins_over_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            crawler = crawler_runner.MediaCrawlerRunner(home=tmp)
            crawler.cookie_dir = Path(tmp) / "cookies"
            os.environ["PLATFORM_COOKIES_XHS"] = "web_session=env"
            try:
                spec = crawler_runner.CrawlSpec(
                    platform="xhs", keywords=["PDF"], cookies="web_session=request"
                )
                cookies = crawler.resolve_cookies(spec)
            finally:
                os.environ.pop("PLATFORM_COOKIES_XHS", None)
            self.assertIn("request", cookies)

    def test_headless_wrapper_forces_media_crawler_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            crawler = crawler_runner.MediaCrawlerRunner(home=tmp)
            crawler.cookie_dir = Path(tmp) / "cookies"
            crawler.template = "python main.py --platform {platform} --lt cookie --keywords {keywords}"
            spec = crawler_runner.CrawlSpec(platform="xhs", keywords=["PDF"])
            command = crawler.build_command(spec, "")

        self.assertIn("-c", command)
        wrapper = command[command.index("-c") + 1]
        self.assertIn("config.HEADLESS=True", wrapper)
        self.assertIn("config.ENABLE_CDP_MODE=False", wrapper)
        self.assertIn("--platform", command)


if __name__ == "__main__":
    unittest.main()
