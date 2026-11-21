"""Fetch hardware app reviews into separate domains.

    python tools/fetch_hardware.py --db var/hardware.db --pages 2

Robot vacuums, air purifiers and smart locks are hardware categories whose apps
carry device-layer pain (connection, firmware, scheduling) that general app
reviews barely cover. Each becomes its own domain so cross-domain analysis stays
honest.
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
from painradar.pipeline import ingest_items  # noqa: E402
from painradar.store import Store  # noqa: E402

CATEGORIES = [
    ("扫地机器人", "robot vacuum", 3),
    ("空气净化器", "air purifier", 3),
    ("智能门锁", "smart lock", 3),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/hardware.db")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--apps-per-category", type=int, default=3)
    args = ap.parse_args()

    store = Store(args.db)
    try:
        for name, term, _ in CATEGORIES:
            key = register_custom_category(name, term)
            try:
                apps = search_apps(term, limit=args.apps_per_category)
            except Exception as exc:  # noqa: BLE001
                print(f"{name}: search failed {exc}")
                continue
            print(f"\n{name} ({key}) <- {term}: {len(apps)} apps")
            for app in apps:
                conn = AppStoreConnector(
                    category=key, app_id=str(app["app_id"]), pages=args.pages
                )
                try:
                    result = ingest_items(store, list(conn.fetch()), key)
                except Exception as exc:  # noqa: BLE001
                    print(f"  {app['name'][:28]} FAILED {exc}")
                    continue
                print(f"  {app['name'][:28]:<28} +{result.inserted} (total {result.total})")
                time.sleep(0.5)
        rows = store._conn.execute(
            "SELECT category, COUNT(rowid) FROM items WHERE deleted_at IS NULL GROUP BY category"
        ).fetchall()
        for category, n in rows:
            store.audit("tool", "fetch", "appstore", category, f'{{"items": {n}}}')
        print("\ncategory totals:")
        for category, n in rows:
            print(f"  {category:<28} {n}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
