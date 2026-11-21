"""Extract purchase tenure from second-hand listings and compute time-to-resell.

    python tools/tenure_mine.py --inputs var/secondhand/apple-watch.jsonl,var/secondhand/vr.jsonl \
        --out docs/decay-tenure.md

Only listings that mention when they bought it are usable; the rest are reported
as silent. Output: distribution of months between purchase and listing.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path

NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "couple": 2, "few": 3, "several": 4,
}

PATTERNS = [
    re.compile(r"\b(?:bought|purchased|got it|got this|had it|owned it|used it)\b[^.]{0,40}?\b(\d{1,2}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|couple|few|several)\s+(day|week|month|year)s?\s+(?:ago|old)\b", re.I),
    re.compile(r"\b(?:bought|purchased|got it|got this|had it|owned it|used it)\b[^.]{0,40}?\b(\d{1,2}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(day|week|month|year)s?\s+(?:of use|in)\b", re.I),
    re.compile(r"\b(?:bought|purchased|got it|got this|had it|owned it)\b[^.]{0,30}?\blast\s+(week|month|year)\b", re.I),
    re.compile(r"\b(?:bought|purchased|got it|got this|ordered)\b[^.]{0,30}?\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(20\d{2})?\b", re.I),
    re.compile(r"\b(?:bought|purchased|since|owned since)\b[^.]{0,20}?\b(20\d{2})\b", re.I),
    re.compile(r"\b(?:bought|purchased)\b[^.]{0,20}?\bthis year\b", re.I),
]

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_tenure_months(text: str) -> float | None:
    import datetime as _dt

    now = _dt.datetime.now()

    for i, pat in enumerate(PATTERNS):
        m = pat.search(text)
        if not m:
            continue

        if i == 2:  # last week/month/year
            word = m.group(1).lower()
            return {"week": 0.25, "month": 1.0, "year": 12.0}[word]

        if i == 3:  # bought in March [2025]
            mon = MONTHS.get(m.group(1).lower()[:3])
            year = int(m.group(2)) if m.group(2) else now.year
            if mon is None:
                continue
            months = (now.year - year) * 12 + (now.month - mon)
            if months < 0:
                months += 12
            return round(float(months), 1)

        if i == 4:  # bought 2024
            year = int(m.group(1))
            months = (now.year - year) * 12 + 6
            if months < 0:
                continue
            return round(float(months), 1)

        if i == 5:  # this year
            return round(float(now.month), 1)

        raw = m.group(1).lower()
        unit = m.group(2).lower()
        n = float(raw) if raw.isdigit() else NUMBER_WORDS.get(raw)
        if n is None:
            continue
        factor = {"day": 1 / 30, "week": 1 / 4.33, "month": 1.0, "year": 12.0}[unit]
        return round(n * factor, 1)

    return None


def bucket(months: float) -> str:
    if months <= 1:
        return "≤1 个月"
    if months <= 3:
        return "1–3 个月"
    if months <= 6:
        return "3–6 个月"
    if months <= 12:
        return "6–12 个月"
    return ">12 个月"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = []
    for spec in args.inputs.split(","):
        spec = spec.strip()
        if not spec:
            continue
        path = Path(spec)
        name = path.stem
        texts = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                texts.append(json.loads(line).get("text", ""))
            except ValueError:
                continue
        tenures = [(parse_tenure_months(t), t) for t in texts]
        known = [(m, t) for m, t in tenures if m is not None]
        rows.append((name, len(texts), known))

    lines = ["# 弃用时长：从购买到挂牌", "", "> 只统计明确写了购买时间的挂牌；未写的不计入。", ""]
    lines += ["| 产品 | 挂牌 | 写明时长 | 中位数 | P25 | P75 |", "|---|---|---|---|---|---|"]
    for name, total, known in rows:
        vals = [m for m, _ in known]
        if len(vals) >= 2:
            q = statistics.quantiles(vals, n=4)
            lines.append(
                f"| {name} | {total} | {len(vals)} | {statistics.median(vals):.1f} 月 | "
                f"{q[0]:.1f} | {q[2]:.1f} |"
            )
        elif vals:
            lines.append(f"| {name} | {total} | {len(vals)} | {vals[0]:.1f} 月 | — | — |")
        else:
            lines.append(f"| {name} | {total} | 0 | — | — | — |")

    lines += ["", "## 分布", ""]
    for name, total, known in rows:
        if not known:
            continue
        counter = Counter(bucket(m) for m, _ in known)
        lines.append(f"### {name}")
        lines.append("")
        lines.append("| 区间 | 条数 |")
        lines.append("|---|---|")
        for k in ("≤1 个月", "1–3 个月", "3–6 个月", "6–12 个月", ">12 个月"):
            if counter.get(k):
                lines.append(f"| {k} | {counter[k]} |")
        lines.append("")

    lines += ["## 例子", ""]
    for name, total, known in rows:
        shown = 0
        for m, t in known:
            if shown >= 3:
                break
            snippet = re.sub(r"\s+", " ", t)[:140]
            lines.append(f"- **{name}**（{m} 月）：{snippet}")
            shown += 1
    lines.append("")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
