"""Build a small per-category sample database for LLM extraction runs.

    python tools/sample_categories.py --source var/gold.db --db var/llm.db \
        --per-category 150 --categories sleep_tech,budgeting,plant_care

Keeps only items (no runs/atoms), sampled with a fixed seed for reproducibility.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.store import Store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="var/gold.db")
    ap.add_argument("--db", default="var/llm.db")
    ap.add_argument("--per-category", type=int, default=150)
    ap.add_argument("--categories", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    target = Path(args.db)
    for p in (target, Path(str(target) + "-wal"), Path(str(target) + "-shm")):
        if p.exists():
            p.unlink()

    src = sqlite3.connect(str(args.source))
    dst = sqlite3.connect(str(target))
    src.backup(dst)
    dst.close()
    src.close()

    store = Store(target)
    conn = store._conn
    conn.execute("DELETE FROM atoms")
    for table in ("clusters", "atom_cluster", "scores", "opportunities", "runs", "predictions", "outcomes"):
        conn.execute(f"DELETE FROM {table}")
    rng = random.Random(args.seed)

    for cat in cats:
        rows = conn.execute(
            "SELECT comment_uid FROM items WHERE category=? AND deleted_at IS NULL", (cat,)
        ).fetchall()
        uids = [r["comment_uid"] for r in rows]
        keep = set(rng.sample(uids, min(args.per_category, len(uids))))
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS keep(uid TEXT PRIMARY KEY)")
        conn.execute("DELETE FROM keep")
        conn.executemany("INSERT INTO keep(uid) VALUES(?)", [(u,) for u in keep])
        conn.execute(
            "DELETE FROM items WHERE category=? AND comment_uid NOT IN (SELECT uid FROM keep)", (cat,)
        )
        print(f"{cat}: sampled {len(keep)} of {len(uids)}")

    conn.execute(
        "DELETE FROM items WHERE category NOT IN (%s)" % ",".join("?" * len(cats)), cats
    )
    conn.commit()
    total = conn.execute("SELECT COUNT(rowid) FROM items").fetchone()[0]
    print(f"total items in {args.db}: {total}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
