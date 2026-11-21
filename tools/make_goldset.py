"""Build a stratified gold-set sheet for human annotation.

    python tools/make_goldset.py --db var/gold.db --category pet_water_fountain --n 200

Outputs (under data/goldset/):
  <category>-<n>.csv          full sheet, model columns empty
  <category>-<n>-pilot.csv    small blind pilot (text + ids only)
  <category>-<n>-meta.json    sampling parameters and stratum counts

The sheet is *model-blind* on purpose: the annotator fills ``gold_*`` columns
without seeing what the rule or LLM extractor said. Model columns are joined
later by ``score_goldset.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import DB_PATH  # noqa: E402
from painradar.store import Store  # noqa: E402

FIELDS = [
    "comment_uid", "app_id", "rating", "published_at", "text",
    "gold_valid", "gold_level", "gold_scene", "gold_obstacle",
    "gold_workaround", "gold_wtp", "gold_notes",
]


def _app_id(item_id: str) -> str:
    parts = item_id.split("_")
    return parts[1] if len(parts) >= 3 and parts[0] == "as" else "unknown"


def _bucket_rating(rating: object) -> str:
    if rating is None:
        return "na"
    try:
        r = float(rating)
    except (TypeError, ValueError):
        return "na"
    if r <= 2:
        return "neg"
    if r < 4:
        return "mid"
    return "pos"


def _latest_rule_run(store: Store, category: str) -> str | None:
    for row in store._conn.execute(
        "SELECT run_id FROM runs WHERE category=? ORDER BY created_at DESC", (category,)
    ).fetchall():
        first = store._conn.execute(
            "SELECT model_version FROM atoms WHERE run_id=? LIMIT 1", (row["run_id"],)
        ).fetchone()
        if first and first["model_version"].startswith("extract-rule"):
            return row["run_id"]
    return None


def _allocate(sizes: dict[str, int], n: int) -> dict[str, int]:
    total = sum(sizes.values())
    if total <= n:
        return dict(sizes)
    quotas = {k: n * v / total for k, v in sizes.items()}
    out = {k: int(v) for k, v in quotas.items()}
    remain = n - sum(out.values())
    for k, _ in sorted(quotas.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True)[:remain]:
        out[k] += 1
    return {k: min(v, sizes[k]) for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--category", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--pilot", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    store = Store(args.db)
    run_id = _latest_rule_run(store, args.category)
    if not run_id:
        raise SystemExit("no rule run found; run `painradar run` first")

    levels: dict[str, str] = {}
    for a in store._conn.execute(
        "SELECT comment_uid, level FROM atoms WHERE run_id=?", (run_id,)
    ).fetchall():
        levels[a["comment_uid"]] = a["level"]

    items = store.items(args.category)
    strata: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        level = levels.get(it["comment_uid"], "none")
        lvl_bucket = "L2+" if level in ("L2", "L3", "L4") else ("L1" if level == "L1" else "none")
        key = f"{_bucket_rating(it['rating'])}|{lvl_bucket}"
        strata[key].append(
            {
                "comment_uid": it["comment_uid"],
                "app_id": _app_id(it["item_id"]),
                "rating": "" if it["rating"] is None else int(it["rating"]),
                "published_at": it["published_at"],
                "text": it["text_masked"],
                "level": level,
            }
        )

    rng = random.Random(args.seed)
    for rows in strata.values():
        rng.shuffle(rows)

    sizes = {k: len(v) for k, v in strata.items()}
    quotas = _allocate(sizes, args.n)
    picked: list[dict] = []
    for key, quota in quotas.items():
        picked.extend(strata[key][:quota])
    rng.shuffle(picked)

    out_dir = Path(args.out) if args.out else ROOT / "data" / "goldset"
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet = out_dir / f"{args.category}-{args.n}.csv"
    with sheet.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in picked:
            w.writerow({**row, "gold_valid": "", "gold_level": "", "gold_scene": "",
                        "gold_obstacle": "", "gold_workaround": "", "gold_wtp": "", "gold_notes": ""})

    pilot = picked[: args.pilot]
    pilot_path = out_dir / f"{args.category}-{args.n}-pilot.csv"
    with pilot_path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in pilot:
            w.writerow({**row, "gold_valid": "", "gold_level": "", "gold_scene": "",
                        "gold_obstacle": "", "gold_workaround": "", "gold_wtp": "", "gold_notes": ""})

    meta = {
        "category": args.category,
        "db": str(args.db),
        "rule_run": run_id,
        "requested": args.n,
        "selected": len(picked),
        "pilot": len(pilot),
        "seed": args.seed,
        "strata": {k: {"available": sizes[k], "picked": quotas[k]} for k in sorted(sizes)},
        "apps": dict(Counter(r["app_id"] for r in picked)),
        "levels": dict(Counter(r["level"] for r in picked)),
    }
    (out_dir / f"{args.category}-{args.n}-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"sheet : {sheet} ({len(picked)} rows)")
    print(f"pilot : {pilot_path} ({len(pilot)} rows)")
    print(json.dumps({"apps": meta["apps"], "levels": meta["levels"]}, ensure_ascii=False))
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
