"""Developer utility: inspect the latest run for a category.

    python tools/inspect_run.py --category pet_water_fountain
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import DB_PATH  # noqa: E402
from painradar.store import Store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", required=True)
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--atoms", action="store_true")
    args = ap.parse_args()

    store = Store(args.db)
    run = store.latest_run(args.category)
    if not run:
        print("no run")
        return 1
    print(f"run={run['run_id']} category={run['category']}")
    print(json.dumps(json.loads(run["stats_json"]), ensure_ascii=False, indent=2))

    for c in store.clusters(run["run_id"]):
        srow = store._conn.execute(
            "SELECT * FROM scores WHERE run_id=? AND cluster_id=?", (run["run_id"], c["cluster_id"])
        ).fetchone()
        extra = f" pain={srow['pain']:.1f} opp={srow['opportunity']:.1f} tier={srow['tier']}" if srow else ""
        print(f"\n[{c['cluster_id']}] size={c['size']} label={c['label']}{extra}")
        for m in store.cluster_members(run["run_id"], c["cluster_id"])[:6]:
            print(f"   - {m['level']} {m['scene']!r} | {m['obstacle'][:40]!r} | {m['workaround'][:30]!r}")

    if args.atoms:
        print("\n-- atoms --")
        for a in store.atoms(run["run_id"]):
            print(f"{a['atom_id']} {a['level']} {a['match_score']:<10} {a['scene']!r} :: {a['obstacle'][:50]!r}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
