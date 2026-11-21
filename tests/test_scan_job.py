import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from painradar.api.jobs import JobRegistry
from painradar.store import Store


class FakeCrawler:
    def start_crawl(self, **kwargs):
        return SimpleNamespace(task_id="task_fake")

    def poll_and_ingest(self, task_id, category, store, on_stage=None):
        if on_stage:
            on_stage("crawling", {"progress": 50})
        return {"inserted": 3, "rows": 3, "task_id": task_id}


class FakeReadinessCrawler(FakeCrawler):
    def platforms(self):
        return [
            {"platform": "xhs", "ready": True},
            {"platform": "bili", "ready": False},
        ]


def fake_run_category(store, category, **kwargs):
    return SimpleNamespace(run_id="run_scan", stats={"atoms": 6})


class TrendScanJobTests(unittest.TestCase):
    def test_scan_loops_platforms_and_clusters_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "scan.db"
            Store(db).close()
            registry = JobRegistry([str(db)], min_size=1)
            with patch(
                "painradar.connectors.remote_mediacrawler.RemoteMediaCrawler",
                FakeCrawler,
            ), patch("painradar.api.jobs.run_category", fake_run_category):
                job = registry.submit_trend_scan(
                    category="custom_trending_scan",
                    platforms=["xhs", "bili"],
                    keywords=["太难用"],
                    max_notes=5,
                )
                for _ in range(100):
                    if job.status in ("done", "failed"):
                        break
                    time.sleep(0.05)

        self.assertEqual(job.status, "done", job.error)
        self.assertEqual(job.run_id, "run_scan")
        self.assertEqual(job.stats["inserted"], 6)
        self.assertEqual(len(job.stats["platforms"]), 2)
        self.assertEqual(job.stats["extraction"], {"atoms": 6})

    def test_scan_skips_unready_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "scan.db"
            Store(db).close()
            registry = JobRegistry([str(db)], min_size=1)
            with patch(
                "painradar.connectors.remote_mediacrawler.RemoteMediaCrawler",
                FakeReadinessCrawler,
            ), patch("painradar.api.jobs.run_category", fake_run_category):
                job = registry.submit_trend_scan(
                    category="custom_trending_scan",
                    platforms=["xhs", "bili"],
                    keywords=["太难用"],
                    max_notes=5,
                )
                for _ in range(100):
                    if job.status in ("done", "failed"):
                        break
                    time.sleep(0.05)

        self.assertEqual(job.status, "done", job.error)
        self.assertEqual(job.stats["inserted"], 3)
        bili = [p for p in job.stats["platforms"] if p["platform"] == "bili"][0]
        self.assertIn("未配置", bili["error"])


if __name__ == "__main__":
    unittest.main()
