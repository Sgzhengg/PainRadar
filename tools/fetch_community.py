"""Collect community evidence into two domains: pet devices and smart home.

    python tools/fetch_community.py --db var/community.db \
        --pet-category pet_water_fountain --home-category custom_smart_home \
        --per-query 40

GitHub Issues (public search) and Hacker News (Algolia) are both key-free.
Keeping the two domains apart matters: "robot vacuum" evidence must not be
counted as pet-device evidence.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import register_custom_category  # noqa: E402
from painradar.connectors.github_issues import GitHubIssueConnector  # noqa: E402
from painradar.connectors.hn import HNConnector  # noqa: E402
from painradar.pipeline import ingest_items  # noqa: E402
from painradar.store import Store  # noqa: E402

PET_GITHUB = ["petkit", "petlibro", "cat fountain", "litter box", "litter robot", "pet feeder", "smart pet"]
HOME_GITHUB = ["robot vacuum", "smart home device", "smart plug", "security camera", "air purifier"]

PET_HN = ["pet water fountain", "litter box", "automatic feeder"]
HOME_HN = ["robot vacuum", "smart home device", "smart plug", "air purifier"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/community.db")
    ap.add_argument("--pet-category", default="pet_water_fountain")
    ap.add_argument("--home-category", default="")
    ap.add_argument("--per-query", type=int, default=40)
    ap.add_argument("--hn-limit", type=int, default=60)
    args = ap.parse_args()

    if not args.home_category:
        args.home_category = register_custom_category("智能家居", "smart home")
        print(f"registered smart-home category: {args.home_category}")

    store = Store(args.db)
    totals = {"github": 0, "hn": 0}
    try:
        jobs = [(q, args.pet_category, "github") for q in PET_GITHUB]
        jobs += [(q, args.home_category, "github") for q in HOME_GITHUB]
        jobs += [(q, args.pet_category, "hn") for q in PET_HN]
        jobs += [(q, args.home_category, "hn") for q in HOME_HN]

        for query, category, channel in jobs:
            try:
                conn = (
                    GitHubIssueConnector(category=category, query=query, limit=args.per_query)
                    if channel == "github"
                    else HNConnector(category=category, query=query, limit=args.hn_limit)
                )
                result = ingest_items(store, conn.fetch(), category)
            except Exception as exc:  # noqa: BLE001 - one query failing is fine
                print(f"  {channel} {query!r} FAILED {type(exc).__name__}: {exc}")
                time.sleep(8 if channel == "github" else 1)
                continue
            totals[channel] += result.inserted
            print(f"  {channel:<10} {query!r:<22} -> {category:<24} +{result.inserted}")
            time.sleep(6 if channel == "github" else 1)

        rows = store._conn.execute(
            "SELECT category, platform, COUNT(rowid) FROM items WHERE deleted_at IS NULL GROUP BY category, platform"
        ).fetchall()
        for category, platform, n in rows:
            store.audit("tool", "fetch", platform, category, f'{{"items": {n}}}')
        print("\ninserted:", totals)
        for category, platform, n in rows:
            print(f"  {category:<26} {platform:<12} {n}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
