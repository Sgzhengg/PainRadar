"""Evaluate the validity filter on the gold pilot and tune its threshold.

    python tools/eval_validity.py --db var/gold200.db --category pet_water_fountain \
        --labels data/goldset/pilot-labels.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import category as get_category  # noqa: E402
from painradar.store import Store  # noqa: E402
from painradar.validity import ValidityFilter  # noqa: E402


def _latest_run(store: Store, category: str, prefix: str) -> str | None:
    for row in store._conn.execute(
        "SELECT run_id FROM runs WHERE category=? ORDER BY created_at DESC", (category,)
    ).fetchall():
        first = store._conn.execute(
            "SELECT model_version FROM atoms WHERE run_id=? LIMIT 1", (row["run_id"],)
        ).fetchone()
        if first and first["model_version"].startswith(prefix):
            return row["run_id"]
    return None


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--labels", required=True)
    args = ap.parse_args()

    spec = get_category(args.category)
    store = Store(args.db)
    items = {r["comment_uid"]: dict(r) for r in store.items(args.category)}
    labels = list(csv.DictReader(open(args.labels, encoding="utf-8-sig")))

    runs = {
        "rule": _latest_run(store, args.category, "extract-rule"),
        "llm": _latest_run(store, args.category, "extract-llm"),
    }
    atoms = {
        name: {r["comment_uid"] for r in store._conn.execute("SELECT comment_uid FROM atoms WHERE run_id=?", (rid,)).fetchall()}
        for name, rid in runs.items()
        if rid
    }

    print(f"pilot={len(labels)} valid={sum(1 for r in labels if r['gold_valid']=='1')}")
    print(f"{'th':>5} | {'filter P':>9} {'R':>6} {'F1':>6} | " + " | ".join(f"{n}+filter F1" for n in atoms))
    for th in (-2.5, -2.0, -1.5, -1.2, -1.0, -0.6, 0.0, 0.5):
        vf = ValidityFilter(spec, threshold=th)
        tp = fp = fn = tn = 0
        combined: dict[str, list[int]] = {name: [0, 0, 0] for name in atoms}
        for row in labels:
            uid = row["comment_uid"]
            gold = row["gold_valid"] == "1"
            it = items.get(uid, {})
            v = vf.judge(it.get("text_masked", ""), it.get("rating"))
            if gold and v.valid:
                tp += 1
            elif v.valid and not gold:
                fp += 1
            elif gold and not v.valid:
                fn += 1
            else:
                tn += 1
            for name, uids in atoms.items():
                pred = v.valid and uid in uids
                c = combined[name]
                if gold and pred:
                    c[0] += 1
                elif pred and not gold:
                    c[1] += 1
                elif gold and not pred:
                    c[2] += 1
        p, r, f = _prf(tp, fp, fn)
        cells = []
        for name in atoms:
            _, _, cf = _prf(*combined[name])
            cells.append(f"{cf:>12.1%}")
        print(f"{th:>5} | {p:>9.1%} {r:>6.1%} {f:>6.1%} | " + " | ".join(cells))
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
