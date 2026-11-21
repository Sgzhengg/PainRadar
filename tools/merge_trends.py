"""Attach Google Trends momentum to demand cards in a discovery snapshot.

    python tools/merge_trends.py --snapshot var/discovery.json \
        --trends var/trends.json --terms var/demand_terms.json

The trend signal is *relative* (0-100 within each term's own series), so only the
change between the first and last quarter of the window is used. A demand with
several terms gets the mean change of those terms.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="var/discovery.json")
    ap.add_argument("--trends", default="var/trends.json")
    ap.add_argument("--terms", default="var/demand_terms.json")
    args = ap.parse_args()

    snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    trends = json.loads(Path(args.trends).read_text(encoding="utf-8"))
    mapping = json.loads(Path(args.terms).read_text(encoding="utf-8"))
    series = trends.get("series", {})

    merged = 0
    for d in snap.get("demands", []):
        terms = mapping.get(d["label"]) or []
        rows = []
        for term in terms:
            entry = series.get(term)
            if not entry:
                continue
            s = entry.get("summary") or {}
            metric = s.get("trend_pct")
            if metric is None:
                metric = s.get("change_pct")
            if metric is None:
                continue
            rows.append({"term": term, "change_pct": metric, "mean": s.get("mean"),
                         "peak_date": s.get("peak_date"), "latest": s.get("latest")})
        if not rows:
            continue
        avg = round(sum(r["change_pct"] for r in rows) / len(rows), 1)
        d["market_trend"] = {
            "change_pct": avg,
            "terms": rows,
            "geo": trends.get("geo", ""),
            "timeframe": trends.get("timeframe", ""),
            "generated_at": trends.get("generated_at", ""),
        }
        merged += 1
        direction = "上升" if avg >= 5 else ("下降" if avg <= -5 else "平稳")
        print(f"{d['label']:<18} {avg:>7.1f}%  {direction}")

    Path(args.snapshot).write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nmerged {merged} demands -> {args.snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
