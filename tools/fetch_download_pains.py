"""Collect pain evidence around downloading / saving / archiving media.

    python tools/fetch_download_pains.py --db var/download.db --pages 2

This corpus is the capability circle of a downloader (Grabber): parse failures,
interrupted downloads, quality/format, batch queues, subtitles, audio extraction,
site compatibility, storage/organization, rights.

Sources: App Store reviews of downloader apps, Reddit archive, Hacker News.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import register_custom_category  # noqa: E402
from painradar.connectors.appstore import AppStoreConnector, search_apps  # noqa: E402
from painradar.connectors.hn import HNConnector  # noqa: E402
from painradar.connectors.reddit_archive import RedditArchiveConnector  # noqa: E402
from painradar.pipeline import ingest_items  # noqa: E402
from painradar.store import Store  # noqa: E402

APP_TERMS = [
    "video downloader",
    "save video",
    "offline video",
    "video saver",
    "download videos",
]
SUBREDDITS = ["DataHoarder", "VideoEditing", "podcasting", "PleX", "youtubedl", "archivists"]
HN_QUERIES = ["youtube-dl", "archive youtube", "download videos", "offline video"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/download.db")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--apps-per-term", type=int, default=2)
    ap.add_argument("--hn-limit", type=int, default=50)
    args = ap.parse_args()

    key = register_custom_category("下载与收藏", "media download and archiving")
    store = Store(args.db)
    total = 0
    try:
        for term in APP_TERMS:
            try:
                apps = search_apps(term, limit=args.apps_per_term)
            except Exception:  # noqa: BLE001
                continue
            for app in apps:
                conn = AppStoreConnector(category=key, app_id=str(app["app_id"]), pages=args.pages)
                try:
                    result = ingest_items(store, conn.fetch(), key)
                except Exception:  # noqa: BLE001
                    continue
                total += result.inserted
                print(f"  appstore {term:<18} {app['name'][:20]:<20} +{result.inserted}")
                time.sleep(0.4)

        for subreddit in SUBREDDITS:
            conn = RedditArchiveConnector(category=key, subreddit=subreddit, pages=args.pages, limit=100)
            try:
                result = ingest_items(store, conn.fetch(), key)
            except Exception:  # noqa: BLE001
                continue
            total += result.inserted
            print(f"  reddit r/{subreddit:<16} +{result.inserted}")
            time.sleep(1)

        for query in HN_QUERIES:
            conn = HNConnector(category=key, query=query, limit=args.hn_limit)
            try:
                result = ingest_items(store, conn.fetch(), key)
            except Exception:  # noqa: BLE001
                continue
            total += result.inserted
            print(f"  hn {query:<18} +{result.inserted}")
            time.sleep(1)

        print(f"\ninserted {total}")
        for category, platform, n in store._conn.execute(
            "SELECT category, platform, COUNT(rowid) FROM items WHERE deleted_at IS NULL GROUP BY category, platform"
        ).fetchall():
            print(f"  {category:<22} {platform:<12} {n}")
            store.audit("tool", "fetch", platform, category, f'{{"items": {n}}}')
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
