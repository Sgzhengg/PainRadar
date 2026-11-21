"""Inter-annotator agreement for two label files.

    python tools/alpha.py --a data/goldset/pilot-labels.csv --b data/goldset/second-annotator.csv

Reports percent agreement, Cohen's kappa and Krippendorff's alpha (nominal) per field.
Also flags units where the two annotators disagree on validity or level.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def _read(path: str) -> dict[str, dict]:
    return {r["comment_uid"]: r for r in csv.DictReader(open(path, encoding="utf-8-sig"))}


def _agree(a: str, b: str) -> bool:
    return (a or "") == (b or "")


def _kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    if not n:
        return 0.0
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


def _alpha(pairs: list[tuple[str, str]]) -> float:
    """Krippendorff's alpha, two coders, nominal."""
    n = len(pairs)
    if not n:
        return 0.0
    do = sum(1 for a, b in pairs if a != b) / n
    counts: Counter[str] = Counter()
    for a, b in pairs:
        counts[a] += 1
        counts[b] += 1
    total = 2 * n
    de = 1 - sum((c / total) ** 2 for c in counts.values())
    return 1 - do / de if de > 0 else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    A, B = _read(args.a), _read(args.b)
    common = sorted(set(A) & set(B))
    fields = [
        ("有效痛点", lambda r: r.get("gold_valid", "")),
        ("L 级", lambda r: r.get("gold_level", "")),
        ("场景", lambda r: r.get("gold_scene", "")),
        ("绕行方案有无", lambda r: "1" if r.get("gold_workaround") else "0"),
        ("付费信号", lambda r: r.get("gold_wtp", "")),
    ]

    lines = [
        "# 双标注一致性",
        "",
        f"- A: `{args.a}`",
        f"- B: `{args.b}`",
        f"- 共同标注: {len(common)} 条",
        "",
        "| 字段 | 一致率 | Cohen κ | Krippendorff α |",
        "|---|---|---|---|",
    ]
    for label, get in fields:
        pairs = [(get(A[u]), get(B[u])) for u in common]
        agree = sum(1 for a, b in pairs if a == b) / len(pairs) if pairs else 0.0
        lines.append(f"| {label} | {agree:.1%} | {_kappa(pairs):.3f} | {_alpha(pairs):.3f} |")

    diffs = [u for u in common if A[u].get("gold_level") != B[u].get("gold_level")]
    lines += ["", f"## L 级分歧 {len(diffs)} 条", ""]
    for u in diffs[:20]:
        lines.append(f"- `{u}` A={A[u].get('gold_level')} B={B[u].get('gold_level')}")

    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
