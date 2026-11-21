"""Deep-dive corpus for one category: PDF tools.

    python tools/fetch_pdf.py --db var/pdf.db --pages 2

Depth means: many apps in the same category, so the pain map covers the whole
category rather than one vendor. Sources: App Store reviews across the top PDF
apps, plus Reddit mentions.
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
from painradar.connectors.reddit_archive import RedditArchiveConnector  # noqa: E402
from painradar.pipeline import ingest_items  # noqa: E402
from painradar.store import Store  # noqa: E402

TERMS = ["pdf editor", "pdf scanner", "pdf converter", "pdf reader", "pdf fill sign"]
REDDIT = [("PDF", ()), ("software", ("pdf",)), ("macapps", ("pdf",)), ("productivity", ("pdf",))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/pdf.db")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--apps-per-term", type=int, default=2)
    ap.add_argument("--reddit-pages", type=int, default=2)
    args = ap.parse_args()

    key = register_custom_category("PDF 工具", "pdf tools")
    store = Store(args.db)
    total = 0
    seen = set()
    try:
        for term in TERMS:
            try:
                apps = search_apps(term, limit=args.apps_per_term)
            except Exception:  # noqa: BLE001
                continue
            for app in apps:
                app_id = str(app["app_id"])
                if app_id in seen:
                    continue
                seen.add(app_id)
                conn = AppStoreConnector(category=key, app_id=app_id, pages=args.pages)
                try:
                    result = ingest_items(store, conn.fetch(), key)
                except Exception:  # noqa: BLE001
                    continue
                total += result.inserted
                print(f"  appstore {app['name'][:26]:<26} +{result.inserted}")
                time.sleep(0.4)

        for subreddit, keywords in REDDIT:
            conn = RedditArchiveConnector(
                category=key,
                subreddit=subreddit,
                keywords=keywords,
                pages=args.reddit_pages,
                limit=100,
            )
            try:
                result = ingest_items(store, conn.fetch(), key)
            except Exception:  # noqa: BLE001
                continue
            total += result.inserted
            print(f"  reddit r/{subreddit:<14} +{result.inserted}")
            time.sleep(1)

        print(f"\ninserted {total}")
        for category, platform, n in store._conn.execute(
            "SELECT category, platform, COUNT(rowid) FROM items WHERE deleted_at IS NULL GROUP BY category, platform"
        ).fetchall():
            print(f"  {category:<18} {platform:<10} {n}")
            store.audit("tool", "fetch", platform, category, f'{{"items": {n}}}')
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
