"""Split the gold sheet into annotation batches, skipping already-labelled rows.

    python tools/split_batches.py --sheet data/goldset/pet_water_fountain-200.csv \
        --labels data/goldset/labels-55.csv --size 40
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

FIELDS = [
    "comment_uid", "app_id", "rating", "published_at", "text",
    "gold_valid", "gold_level", "gold_scene", "gold_obstacle",
    "gold_workaround", "gold_wtp", "gold_notes",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--labels", default=None, help="already-labelled CSV to skip")
    ap.add_argument("--size", type=int, default=40)
    ap.add_argument("--outdir", default="data/goldset/batches")
    args = ap.parse_args()

    labelled = set()
    if args.labels:
        labelled = {r["comment_uid"] for r in csv.DictReader(open(args.labels, encoding="utf-8-sig"))}

    rows = [r for r in csv.DictReader(open(args.sheet, encoding="utf-8-sig")) if r["comment_uid"] not in labelled]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("batch-*.csv"):
        old.unlink()

    n = 0
    for i in range(0, len(rows), args.size):
        n += 1
        chunk = rows[i : i + args.size]
        path = outdir / f"batch-{n:02d}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            for row in chunk:
                w.writerow({**row, "gold_valid": "", "gold_level": "", "gold_scene": "",
                            "gold_obstacle": "", "gold_workaround": "", "gold_wtp": "", "gold_notes": ""})
        print(f"{path}: {len(chunk)} rows")
    print(f"remaining {len(rows)} rows in {n} batch(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
