"""Collect small-business operations pain.

    python tools/fetch_smb.py --db var/smb.db --pages 2

Why: consumer and developer corpora produced demands a solo developer cannot
defend. Small businesses pay for software, do not clone it, and their pain is
workflow-shaped (invoicing, scheduling, inventory, reconciliation).

Sources:
* Reddit archive — owner/operator subreddits
* App Store reviews of SMB SaaS (QuickBooks, Jobber, Square, FreshBooks, ...)
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

SUBREDDITS = [
    "smallbusiness",
    "Entrepreneur",
    "Bookkeeping",
    "Accounting",
    "ecommerce",
    "Shopify",
    "AmazonSeller",
    "restaurateur",
    "Contractor",
]

APP_TERMS = [
    "quickbooks",
    "jobber",
    "square point of sale",
    "freshbooks",
    "shopify",
    "wave accounting",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/smb.db")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--app-pages", type=int, default=2)
    ap.add_argument("--skip-reddit", action="store_true")
    ap.add_argument("--skip-apps", action="store_true")
    args = ap.parse_args()

    key = register_custom_category("小企业运营", "small business operations")
    store = Store(args.db)
    total = 0
    try:
        if not args.skip_reddit:
            for subreddit in SUBREDDITS:
                conn = RedditArchiveConnector(
                    category=key, subreddit=subreddit, pages=args.pages, limit=100
                )
                try:
                    result = ingest_items(store, conn.fetch(), key)
                except Exception:  # noqa: BLE001
                    continue
                total += result.inserted
                print(f"  reddit r/{subreddit:<16} +{result.inserted}")
                time.sleep(1)

        if not args.skip_apps:
            for term in APP_TERMS:
                try:
                    apps = search_apps(term, limit=1)
                except Exception:  # noqa: BLE001
                    continue
                for app in apps:
                    conn = AppStoreConnector(
                        category=key, app_id=str(app["app_id"]), pages=args.app_pages
                    )
                    try:
                        result = ingest_items(store, conn.fetch(), key)
                    except Exception:  # noqa: BLE001
                        continue
                    total += result.inserted
                    print(f"  appstore {term:<22} +{result.inserted}")
                    time.sleep(0.5)

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
