"""Temporal backtest for the B set.

    python tools/backtest.py --db var/backtest.db --source var/gold.db \
        --category pet_water_fountain --t0 2025-11-01 --months 12 --top 8

Builds a fresh DB containing only reviews published before T0, runs the
pipeline, turns the top clusters into predictions, then checks GitHub and the
App Store for products that appeared inside the outcome window. Random keyword
sets from the same corpus are used as a baseline.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.adjudicate import LLMAdjudicator  # noqa: E402
from painradar.config import category as get_category  # noqa: E402
from painradar.net import HttpClient  # noqa: E402
from painradar.outcomes import appstore_outcome, github_outcome  # noqa: E402
from painradar.pipeline import run_category  # noqa: E402
from painradar.predictions import llm_queries, make_prediction, random_baseline, vocabulary  # noqa: E402
from painradar.store import Store  # noqa: E402


def _add_months(iso: str, months: int) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    m += months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}-{min(d, 28):02d}"


def _prepare(source: Path, target: Path, t0: str) -> None:
    if target.exists():
        target.unlink()
    for suffix in ("-wal", "-shm"):
        p = Path(str(target) + suffix)
        if p.exists():
            p.unlink()
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    src.backup(dst)
    dst.close()
    src.close()
    # Store() applies CREATE IF NOT EXISTS, so older snapshots gain the new tables.
    store = Store(target)
    conn = store._conn
    conn.execute("DELETE FROM items WHERE published_at >= ?", (t0,))
    for table in ("atoms", "clusters", "atom_cluster", "scores", "opportunities", "runs", "predictions", "outcomes"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    store.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/backtest.db")
    ap.add_argument("--source", default="var/gold.db")
    ap.add_argument("--category", required=True)
    ap.add_argument("--t0", default="2025-11-01")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--extractor", default="rule", choices=["rule", "llm"])
    ap.add_argument("--queries", default="bigram", choices=["bigram", "llm"])
    ap.add_argument("--adjudicate", default="llm", choices=["none", "llm"])
    ap.add_argument("--baselines", type=int, default=10)
    ap.add_argument("--split-app", action="store_true", help="run one pipeline per app id")
    ap.add_argument("--min-app-items", type=int, default=60)
    ap.add_argument("--out", default="docs/backtest.md")
    args = ap.parse_args()

    t1 = _add_months(args.t0, args.months)
    _prepare(Path(args.source), Path(args.db), args.t0)
    store = Store(args.db)
    spec = get_category(args.category)
    all_items = store.items(args.category)

    def _app_of(item_id: str) -> str:
        parts = str(item_id).split("_")
        return parts[1] if len(parts) >= 3 and parts[0] == "as" else "unknown"

    if args.split_app:
        counts = Counter(_app_of(r["item_id"]) for r in all_items)
        apps: list[str | None] = [
            a for a, n in counts.most_common() if a != "unknown" and n >= args.min_app_items
        ]
        print(f"split by app: {len(apps)} apps with >= {args.min_app_items} items")
    else:
        apps = [None]

    preds = []
    runs = []
    total_items = total_atoms = total_clusters = 0
    for app in apps:
        run = run_category(
            store, args.category, extractor_name=args.extractor, min_size=3,
            apps=[app] if app else None,
        )
        runs.append((app, run))
        total_items += run.stats["items"]
        total_atoms += run.stats["atoms"]
        total_clusters += run.stats["clusters"]
        print(f"  {app or 'all'}: items={run.stats['items']} atoms={run.stats['atoms']} "
              f"clusters={run.stats['clusters']}")

        for c in store.clusters(run.run_id)[: args.top]:
            atoms = store.cluster_members(run.run_id, c["cluster_id"])
            from painradar.schema import PainAtom

            objs = [
                PainAtom(
                    atom_id=a["atom_id"], comment_uid=a["comment_uid"], quote=a["quote"],
                    span_start=a["span_start"], span_end=a["span_end"], match_score=a["match_score"],
                    scene=a["scene"], trigger=a["trigger"], job=a["job"], obstacle=a["obstacle"],
                    workaround=a["workaround"], cost_type=a["cost_type"], cost_estimate=a["cost_estimate"],
                    persona=a["persona"], intensity=a["intensity"], expression=a["expression"],
                    level=a["level"], wtp_level=a["wtp_level"], wtp_quote=a["wtp_quote"],
                    domain=a["domain"], confidence=a["confidence"], model_version=a["model_version"],
                    prompt_version=a["prompt_version"], taxonomy_version=a["taxonomy_version"],
                    run_id=a["run_id"],
                )
                for a in atoms
            ]
            pred = make_prediction(run.run_id, c["cluster_id"], objs, args.t0, t1,
                                   domain_terms=spec.domain_terms)
            if args.queries == "llm":
                qs = llm_queries(c["label"], [a.quote for a in objs])
                if qs:
                    pred = make_prediction(run.run_id, c["cluster_id"], objs, args.t0, t1,
                                           keywords=qs, domain_terms=spec.domain_terms)
            if pred:
                label = f"{app}:{c['label']}" if app else c["label"]
                preds.append((pred, label, objs, run.run_id))

    if not preds:
        print("no prediction could be built (generic keywords or no cluster)", file=sys.stderr)
        store.close()
        return 1

    store.insert_predictions(
        [
            {
                "prediction_id": p.prediction_id, "run_id": rid, "category": args.category,
                "cluster_id": p.cluster_id, "t0": p.t0, "window_end": p.window_end,
                "keywords": p.keywords, "proposition": p.proposition,
            }
            for p, _, _, rid in preds
        ]
    )

    client = HttpClient(user_agent="PainRadar/0.1 (research)", timeout=30, max_retries=2, rate_per_sec=0.15)
    adjudicator = None
    if args.adjudicate == "llm":
        try:
            adjudicator = LLMAdjudicator()
            print("semantic adjudication: LLM")
        except RuntimeError as exc:
            print(f"adjudication disabled: {exc}")

    rows = []
    for pred, label, _, _ in preds:
        gh = github_outcome(pred.keywords, args.t0, t1, client=client,
                            proposition=pred.proposition, adjudicator=adjudicator)
        ios = appstore_outcome(pred.keywords, args.t0, t1, client=client,
                               proposition=pred.proposition, adjudicator=adjudicator)
        hit = gh.hit or ios.hit
        for out in (gh, ios):
            store.insert_outcome(
                {
                    "prediction_id": pred.prediction_id, "source": out.source, "query": out.query,
                    "hit": out.hit, "evidence": out.evidence, "error": out.error,
                }
            )
        rows.append({"label": label, "pred": pred, "gh": gh, "ios": ios, "hit": hit})
        print(f"  {label[:28]:<28} kw={pred.keywords} gh={gh.hit} ios={ios.hit}")

    vocab = vocabulary([a for _, _, objs, _ in preds for a in objs])
    rng = random.Random(42)
    baseline_hits = 0
    baseline_n = 0
    baseline_errors = 0
    for i in range(args.baselines):
        kws = random_baseline(vocab, 4, rng)
        gh = github_outcome(kws, args.t0, t1, client=client, proposition=" / ".join(kws), adjudicator=adjudicator)
        ios = appstore_outcome(kws, args.t0, t1, client=client, proposition=" / ".join(kws), adjudicator=adjudicator)
        baseline_n += 1
        if gh.hit or ios.hit:
            baseline_hits += 1
        if gh.error or ios.error:
            baseline_errors += 1

    hits = sum(1 for r in rows if r["hit"])
    lines = [
        f"# 结局回测 — {args.category}",
        "",
        f"- T0：{args.t0} ｜ 窗口：{args.t0} → {t1}（{args.months} 个月）",
        f"- 训练集：{total_items} 条评论（T0 之前）→ {total_atoms} 个原子 → {total_clusters} 个簇"
        f"（{len(apps)} 组）",
        f"- 抽取器：`{args.extractor}` ｜ 关键词来源：`{args.queries}` ｜ 语义裁决：`{args.adjudicate}`",
        f"- 预测数：{len(rows)} ｜ 命中：{hits}（{hits / len(rows):.0%}）",
        f"- 随机基线：{baseline_n} 组，命中 {baseline_hits}（{baseline_hits / baseline_n:.0%}）"
        + (f"，错误 {baseline_errors} 组" if baseline_errors else ""),
        "",
        "| 簇 | 关键词 | GitHub 命中/候选 | App Store 命中/候选 | 命中 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label'][:30]} | {' / '.join(r['pred'].keywords)} | "
            f"{'✓' if r['gh'].hit else '—'} {r['gh'].scanned} | "
            f"{'✓' if r['ios'].hit else '—'} {r['ios'].scanned} | "
            f"{'✓' if r['hit'] else '—'} |"
        )

    lines += ["", "## 证据", ""]
    for r in rows:
        if not r["hit"]:
            continue
        lines.append(f"- **{r['label']}** — `{r['pred'].proposition}`")
        for e in (r["gh"].evidence + r["ios"].evidence)[:3]:
            verdict = f"（{e.get('match')}: {e.get('reason')}）" if e.get("match") else ""
            lines.append(f"  - {e.get('name')} · {e.get('url')} {verdict}")

    lines += [
        "",
        "## 解读与限制",
        "",
        f"- 这些预测在 {args.t0} 时点只能看到 {total_items} 条评论，样本很小；命中率只能当方向性参考。",
        "- 结局来源只有 GitHub 与 App Store，覆盖不到硬件众筹、线下服务与 B 端采购，真实命中率会被低估。",
        "- 随机基线使用同一语料词表，规模相同；若两者接近，说明关键词没有区分度，而不是「系统有效」。",
        "- 关键词来自评论原文，可能包含噪声词；证据链接需要人工复核后才算数。",
    ]

    text = "\n".join(lines)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nwritten to {out}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
