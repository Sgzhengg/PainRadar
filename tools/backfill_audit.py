"""Backfill provenance audit rows for databases collected before auditing.

    python tools/backfill_audit.py            # every var/*.db
    python tools/backfill_audit.py var/reddit.db

For each (category, platform) pair without an existing audit row, insert one
marked ``backfill`` with the observed item count. It cannot recover the original
fetch time or parameters — it only records what the database currently holds.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.store import Store  # noqa: E402


def backfill(path: Path) -> int:
    store = Store(path)
    added = 0
    try:
        pairs = store._conn.execute(
            "SELECT category, platform, COUNT(rowid) AS n FROM items"
            " WHERE deleted_at IS NULL GROUP BY category, platform"
        ).fetchall()
        for row in pairs:
            category, platform, n = row["category"], row["platform"], row["n"]
            exists = store._conn.execute(
                "SELECT 1 FROM audit WHERE object_type=? AND object_id=? LIMIT 1",
                (platform, category),
            ).fetchone()
            if exists:
                continue
            store.audit(
                "backfill",
                "fetch",
                platform,
                category,
                json.dumps({"items": n, "note": "backfilled from existing rows"}, ensure_ascii=False),
            )
            added += 1
    finally:
        store.close()
    return added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dbs", nargs="*")
    args = ap.parse_args()

    paths = [Path(p) for p in args.dbs] if args.dbs else sorted((ROOT / "var").glob("*.db"))
    for path in paths:
        try:
            n = backfill(path)
        except Exception as exc:  # noqa: BLE001
            print(f"{path.name:<22} skipped: {exc}")
            continue
        print(f"{path.name:<22} +{n} audit rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
