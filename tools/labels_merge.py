"""Merge annotation batches into one labels file.

    python tools/labels_merge.py --out data/goldset/labels.csv \
        data/goldset/pilot-labels.csv data/goldset/batch2-labels.csv

Deduplicates by ``comment_uid`` (later files win only if --override is passed).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

FIELDS = [
    "comment_uid", "gold_valid", "gold_level", "gold_scene",
    "gold_obstacle", "gold_workaround", "gold_wtp", "gold_notes",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--override", action="store_true")
    args = ap.parse_args()

    merged: dict[str, dict] = {}
    order: list[str] = []
    dupes = 0
    for path in args.inputs:
        for row in csv.DictReader(open(path, encoding="utf-8-sig")):
            uid = row["comment_uid"]
            if uid in merged:
                dupes += 1
                if not args.override:
                    continue
            else:
                order.append(uid)
            merged[uid] = {k: row.get(k, "") for k in FIELDS}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for uid in order:
            w.writerow(merged[uid])

    valid = sum(1 for r in merged.values() if r["gold_valid"] == "1")
    print(f"merged {len(merged)} labels from {len(args.inputs)} file(s); duplicates={dupes}; valid={valid}")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
