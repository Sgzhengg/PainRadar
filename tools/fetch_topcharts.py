"""Fetch App Store Top Charts apps and their reviews into a broad corpus.

    python tools/fetch_topcharts.py --db var/topcharts.db --apps 40 --pages 2

Picks apps across distinct genres (max 3 per genre) so the corpus spans 10+
categories, registers a generic category for them, then pulls public RSS reviews.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import register_custom_category  # noqa: E402
from painradar.connectors.appstore import AppStoreConnector  # noqa: E402
from painradar.net import HttpClient  # noqa: E402
from painradar.pipeline import ingest_items  # noqa: E402
from painradar.store import Store  # noqa: E402

TOP_FREE = "https://rss.applemarketingtools.com/api/v2/us/apps/top-free/100/apps.json"
FALLBACK = "https://itunes.apple.com/us/rss/topfreeapplications/limit=100/json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/topcharts.db")
    ap.add_argument("--apps", type=int, default=40)
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--per-genre", type=int, default=3)
    ap.add_argument("--country", default="us")
    args = ap.parse_args()

    client = HttpClient(user_agent="PainRadar/0.1", timeout=60, max_retries=2, rate_per_sec=0.4)
    try:
        data = client.get_json(TOP_FREE)
        results = data.get("feed", {}).get("results", [])
    except Exception as exc:
        print(f"marketing feed failed ({exc}); using iTunes fallback")
        data = client.get_json(FALLBACK)
        results = [
            {
                "id": e["id"]["attributes"]["im:id"],
                "name": e["im:name"]["label"],
                "genres": [{"name": e["category"]["attributes"]["label"]}],
            }
            for e in data.get("feed", {}).get("entry", [])
        ]
    print(f"top-free returned {len(results)} apps")

    by_genre: dict[str, list[dict]] = defaultdict(list)
    for app in results:
        genres = app.get("genres") or []
        genre = genres[0].get("name") if genres else "Unknown"
        if len(by_genre[genre]) < args.per_genre:
            by_genre[genre].append(app)

    picked = []
    for genre, apps in by_genre.items():
        picked.extend({**a, "_genre": genre} for a in apps)
    picked.sort(key=lambda a: results.index(next(r for r in results if r["id"] == a["id"])))
    picked = picked[: args.apps]
    print(f"picked {len(picked)} apps across {len({a['_genre'] for a in picked})} genres")

    key = register_custom_category("应用总榜", "app store top charts")
    store = Store(args.db)
    total = 0
    for i, app in enumerate(picked, start=1):
        connector = AppStoreConnector(category=key, app_id=str(app["id"]), pages=args.pages)
        try:
            result = ingest_items(store, list(connector.fetch()), key)
        except Exception as exc:  # noqa: BLE001 - keep going on a single app
            print(f"  [{i}/{len(picked)}] {app['name'][:30]} FAILED {exc}")
            continue
        total += result.inserted
        print(f"  [{i}/{len(picked)}] {app['name'][:30]:<30} {app['_genre'][:18]:<18} +{result.inserted}")

    rows = store._conn.execute(
        "SELECT COUNT(rowid) FROM items WHERE category=? AND deleted_at IS NULL", (key,)
    ).fetchone()[0]
    store.audit("tool", "fetch", "appstore", key, f'{{"items": {rows}, "apps": {len(picked)}}}')
    genres = Counter()
    for app in picked:
        genres[app["_genre"]] += 1
    print(f"\ncategory={key} items={rows} inserted={total}")
    print("genres:", ", ".join(f"{g}({n})" for g, n in genres.most_common()))
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
