"""Remove off-topic apps from a category corpus.

    python tools/purge_apps.py --db var/gold200.db --category pet_water_fountain --dry-run
    python tools/purge_apps.py --db var/gold200.db --category pet_water_fountain

Defaults to ``CategorySpec.excluded_apps``; ``--apps`` overrides it.
Soft delete cascades to atoms, so reports and the UI stop seeing the rows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import category as get_category  # noqa: E402
from painradar.store import Store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--apps", default="", help="comma-separated app ids; defaults to config")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec = get_category(args.category)
    apps = tuple(a.strip() for a in args.apps.split(",") if a.strip()) or spec.excluded_apps
    if not apps:
        print("no excluded apps configured for this category")
        return 0

    store = Store(args.db)
    preview = []
    for app in apps:
        n = store._conn.execute(
            "SELECT COUNT(rowid) FROM items WHERE category=? AND item_id LIKE ? AND deleted_at IS NULL",
            (args.category, f"as_{app}_%"),
        ).fetchone()[0]
        preview.append((app, n))
        print(f"{app}: {n} items")

    if args.dry_run:
        print("dry run; nothing deleted")
        store.close()
        return 0

    total = store.soft_delete_apps(args.category, apps)
    print(f"deleted {total} items (cascade to atoms)")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
