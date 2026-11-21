"""Check forward predictions after their registered window ends.

    python tools/forward_check.py --db var/forward.db --category plant_care

Refuses to run before the pre-registered date unless --force is passed, so the
result cannot be peeked at early.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.adjudicate import LLMAdjudicator  # noqa: E402
from painradar.net import HttpClient  # noqa: E402
from painradar.outcomes import appstore_outcome, github_outcome  # noqa: E402
from painradar.store import Store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/forward.db")
    ap.add_argument("--category", required=True)
    ap.add_argument("--now", default=date.today().isoformat())
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--adjudicate", default="llm", choices=["none", "llm"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    store = Store(args.db)
    rows = store._conn.execute(
        "SELECT * FROM predictions WHERE category=? AND mode IN ('forward','baseline')"
        " ORDER BY mode, prediction_id",
        (args.category,),
    ).fetchall()
    if not rows:
        print("no forward predictions registered", file=sys.stderr)
        store.close()
        return 1

    end = max(r["window_end"] for r in rows)
    if args.now < end and not args.force:
        days = (date.fromisoformat(end) - date.fromisoformat(args.now)).days
        print(f"window ends {end}; {days} day(s) left. Use --force only for a dry run.")
        store.close()
        return 2

    adjudicator = None
    if args.adjudicate == "llm":
        try:
            adjudicator = LLMAdjudicator()
        except RuntimeError as exc:
            print(f"adjudication disabled: {exc}")
    client = HttpClient(user_agent="PainRadar/0.1 (research)", timeout=30, max_retries=2, rate_per_sec=0.15)

    lines = [f"# 前向测试结果 — {args.category}", "", f"- 检查日：{args.now} ｜ 窗口结束：{end}", ""]
    lines += ["| 类型 | 预测 | 关键词 | GitHub | App Store | 命中 |", "|---|---|---|---|---|---|"]
    counts = {"forward": [0, 0], "baseline": [0, 0]}
    for r in rows:
        keywords = json.loads(r["keywords_json"])
        gh = github_outcome(keywords, r["t0"], r["window_end"], client=client,
                            proposition=r["proposition"], adjudicator=adjudicator)
        ios = appstore_outcome(keywords, r["t0"], r["window_end"], client=client,
                               proposition=r["proposition"], adjudicator=adjudicator)
        hit = gh.hit or ios.hit
        mode = r["mode"]
        counts.setdefault(mode, [0, 0])
        counts[mode][1] += 1
        counts[mode][0] += 1 if hit else 0
        for out in (gh, ios):
            store.insert_outcome(
                {
                    "prediction_id": r["prediction_id"], "source": out.source, "query": out.query,
                    "hit": out.hit, "evidence": out.evidence, "error": out.error,
                }
            )
        lines.append(
            f"| {mode} | {r['prediction_id']} | {' / '.join(keywords)} | "
            f"{'✓' if gh.hit else '—'} | {'✓' if ios.hit else '—'} | {'✓' if hit else '—'} |"
        )

    fh, fn = counts.get("forward", [0, 0])
    bh, bn = counts.get("baseline", [0, 0])
    lines += ["", f"**预测命中 {fh}/{fn}；基线命中 {bh}/{bn}**", ""]
    for r in rows:
        outs = store.outcomes(r["prediction_id"])
        for o in outs:
            for e in json.loads(o["evidence_json"])[:2]:
                lines.append(f"- {r['prediction_id']} · {o['source']} · {e.get('name')} · {e.get('url')}")

    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"written to {args.out}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
