"""Recompute levels with the deterministic tree and compare with gold.

    python tools/rescore_levels.py --db var/gold200.db --category pet_water_fountain \
        --labels data/goldset/pilot-labels.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.levels import LevelInput, resolve_level  # noqa: E402
from painradar.store import Store  # noqa: E402

LEVELS = ["L0", "L1", "L2", "L3", "L4"]


def _latest(store: Store, category: str, prefix: str) -> str | None:
    for row in store._conn.execute(
        "SELECT run_id FROM runs WHERE category=? ORDER BY created_at DESC", (category,)
    ).fetchall():
        first = store._conn.execute(
            "SELECT model_version FROM atoms WHERE run_id=? LIMIT 1", (row["run_id"],)
        ).fetchone()
        if first and first["model_version"].startswith(prefix):
            return row["run_id"]
    return None


def _metrics(pairs: list[tuple[str, str]]) -> tuple[float, float, Counter]:
    exact = sum(1 for a, b in pairs if a == b) / len(pairs) if pairs else 0.0
    within = sum(1 for a, b in pairs if abs(LEVELS.index(a) - LEVELS.index(b)) <= 1) / len(pairs) if pairs else 0.0
    confusion = Counter((g, p) for g, p in pairs if g != p)
    return exact, within, confusion


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--labels", required=True)
    args = ap.parse_args()

    store = Store(args.db)
    labels = {r["comment_uid"]: r for r in csv.DictReader(open(args.labels, encoding="utf-8-sig"))}

    for name, prefix in (("rule", "extract-rule"), ("llm", "extract-llm")):
        run_id = _latest(store, args.category, prefix)
        if not run_id:
            continue
        atoms = {r["comment_uid"]: dict(r) for r in store._conn.execute(
            "SELECT * FROM atoms WHERE run_id=?", (run_id,)
        ).fetchall()}

        before: list[tuple[str, str]] = []
        after: list[tuple[str, str]] = []
        changes = Counter()
        for uid, gold in labels.items():
            if gold["gold_valid"] != "1" or uid not in atoms:
                continue
            a = atoms[uid]
            g = gold["gold_level"]
            before.append((g, a["level"]))
            refined = resolve_level(
                LevelInput(
                    obstacle=a["obstacle"],
                    workaround=a["workaround"],
                    cost_type=a["cost_type"],
                    cost_estimate=a["cost_estimate"],
                    declared=a["level"],
                    text=a["quote"],
                )
            )
            after.append((g, refined))
            if refined != a["level"]:
                changes[f"{a['level']}->{refined}"] += 1

        eb, wb, cb = _metrics(before)
        ea, wa, ca = _metrics(after)
        print(f"[{name}] n={len(after)}  before: exact={eb:.1%} ±1={wb:.1%}  after: exact={ea:.1%} ±1={wa:.1%}")
        print(f"  changes: {dict(changes)}")
        print(f"  after confusion: {dict(ca)}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
