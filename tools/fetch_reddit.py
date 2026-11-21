"""Collect Reddit evidence via the Arctic Shift archive into per-domain categories.

    python tools/fetch_reddit.py --db var/reddit.db --pages 5

Direct reddit.com JSON is 403 on this network; Arctic Shift is a public archive
with the same bodies. Comments are pulled per subreddit and filtered by optional
keywords so a big sub like r/homeassistant yields device-specific pain only.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.connectors.reddit_archive import RedditArchiveConnector  # noqa: E402
from painradar.pipeline import ingest_items  # noqa: E402
from painradar.store import Store  # noqa: E402

# (subreddit, category, keywords, kind)
PLAN = [
    ("petkit", "pet_water_fountain", (), "comments"),
    ("petlibro", "pet_water_fountain", (), "comments"),
    ("Petcube", "pet_water_fountain", (), "comments"),
    ("homeassistant", "custom_smart_home",
     ("petkit", "petlibro", "fountain", "litter", "feeder", "vacuum", "purifier", "smart lock", "offline"), "comments"),
    ("smarthome", "custom_smart_home", ("robot vacuum", "purifier", "lock", "offline", "firmware"), "comments"),
    ("robotvacuums", "custom_robot_vacuum", (), "comments"),
    ("roomba", "custom_robot_vacuum", (), "comments"),
    ("iRobot", "custom_robot_vacuum", (), "comments"),
    ("ecovacs", "custom_robot_vacuum", (), "comments"),
    ("dreame", "custom_robot_vacuum", (), "comments"),
    ("SmartLocks", "custom_smart_lock", (), "comments"),
    ("AirPurifiers", "custom_air_purifier", (), "comments"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/reddit.db")
    ap.add_argument("--pages", type=int, default=5)
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    store = Store(args.db)
    total = 0
    try:
        for subreddit, category, keywords, kind in PLAN:
            conn = RedditArchiveConnector(
                category=category,
                subreddit=subreddit,
                keywords=keywords,
                pages=args.pages,
                limit=args.limit,
                kind=kind,
            )
            try:
                result = ingest_items(store, conn.fetch(), category)
            except Exception as exc:  # noqa: BLE001 - one subreddit failing is fine
                print(f"  r/{subreddit:<18} FAILED {type(exc).__name__}: {exc}")
                time.sleep(2)
                continue
            total += result.inserted
            print(f"  r/{subreddit:<18} -> {category:<24} +{result.inserted} (seen {result.total})")
            time.sleep(1)
        for category, platform, n in store._conn.execute(
            "SELECT category, platform, COUNT(rowid) FROM items WHERE deleted_at IS NULL GROUP BY category, platform"
        ).fetchall():
            store.audit("tool", "fetch", platform, category, f'{{"items": {n}}}')
        print(f"\ninserted {total}")
        for category, platform, n in store._conn.execute(
            "SELECT category, platform, COUNT(rowid) FROM items WHERE deleted_at IS NULL GROUP BY category, platform"
        ).fetchall():
            print(f"  {category:<26} {platform:<10} {n}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
