"""Compare two discovery snapshots (e.g. sample corpus vs full corpus).

    python tools/compare_discovery.py --old var/discovery-v1-sample.json \
        --new var/discovery.json --out docs/discovery-diff.md

Matches demands by label (exact), reports added / removed / score and coverage
changes. No fuzzy matching: a renamed demand counts as removed + added, which is
the honest reading when the taxonomy itself was rebuilt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    demands = data.get("demands", data if isinstance(data, list) else [])
    return {"meta": data if isinstance(data, dict) else {}, "demands": {d["label"]: d for d in demands}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", default="docs/discovery-diff.md")
    args = ap.parse_args()

    old, new = _load(args.old), _load(args.new)
    o, n = old["demands"], new["demands"]
    added = sorted(set(n) - set(o))
    removed = sorted(set(o) - set(n))
    common = sorted(set(o) & set(n))

    lines = [
        "# 需求发现：抽样 vs 全量对比",
        "",
        f"- 旧：`{args.old}`（{len(o)} 条需求）",
        f"- 新：`{args.new}`（{len(n)} 条需求）",
        "",
        f"## 保持不变（{len(common)} 条）",
        "",
        "| 需求 | 证据 旧→新 | 域数 旧→新 | 分数 旧→新 |",
        "|---|---|---|---|",
    ]
    for label in common:
        a, b = o[label], n[label]
        lines.append(
            f"| {label} | {a['size']} → {b['size']} | {len(a.get('domains', {}))} → {len(b.get('domains', {}))} "
            f"| {a['score']:.0f} → {b['score']:.0f} |"
        )

    lines += ["", f"## 新增（{len(added)} 条）", ""]
    for label in added:
        d = n[label]
        lines.append(f"- **{label}** — {d['size']} 条证据，跨 {len(d.get('domains', {}))} 个域，{d['score']:.0f} 分")
    if not added:
        lines.append("- 无")

    lines += ["", f"## 消失（{len(removed)} 条）", ""]
    for label in removed:
        d = o[label]
        lines.append(f"- {label} — 旧快照 {d['size']} 条证据，{d['score']:.0f} 分")
    if not removed:
        lines.append("- 无")

    text = "\n".join(lines)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nwritten {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
