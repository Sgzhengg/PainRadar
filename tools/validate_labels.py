"""Validate a returned annotation batch before scoring.

    python tools/validate_labels.py --batch data/goldset/batches/batch-01.csv \
        --labels data/goldset/batch-01-annotator2.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import category as get_category  # noqa: E402
from painradar.labels import validate  # noqa: E402


def _read(path: str) -> list[dict]:
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--labels", required=True)
    args = ap.parse_args()

    scenes = set(get_category("pet_water_fountain").scenes)
    batch, labels = _read(args.batch), _read(args.labels)
    errors = validate(batch, labels, scenes)

    if not errors:
        valid = sum(1 for r in labels if (r.get("gold_valid") or "").strip() == "1")
        print(f"OK: {len(labels)} 行，有效痛点 {valid} 条，可以进入 alpha 计算")
        return 0

    print(f"发现 {len(errors)} 个问题：")
    for e in errors[:30]:
        print(" -", e)
    if len(errors) > 30:
        print(f" ... 其余 {len(errors) - 30} 条省略")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
