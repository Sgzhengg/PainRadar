"""Register forward predictions for a category (prospective B set).

    python tools/forward_register.py --source var/gold.db --db var/forward.db \
        --category plant_care --months 12

Unlike the backtest, nothing is fitted to a past window: predictions are written
today, the outcome collection date is fixed in the database, and the check tool
refuses to run before that date (unless --force).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import category as get_category  # noqa: E402
from painradar.pipeline import run_category  # noqa: E402
from painradar.predictions import llm_queries, make_prediction, random_baseline, vocabulary  # noqa: E402
from painradar.store import Store  # noqa: E402


def _prepare(source: Path, target: Path, category: str) -> None:
    for p in (target, Path(str(target) + "-wal"), Path(str(target) + "-shm")):
        if p.exists():
            p.unlink()
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    src.backup(dst)
    dst.close()
    src.close()
    store = Store(target)
    conn = store._conn
    conn.execute("DELETE FROM items WHERE category != ?", (category,))
    for table in ("atoms", "clusters", "atom_cluster", "scores", "opportunities", "runs", "predictions", "outcomes"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    store.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="var/gold.db")
    ap.add_argument("--db", default="var/forward.db")
    ap.add_argument("--category", required=True)
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    spec = get_category(args.category)
    _prepare(Path(args.source), Path(args.db), args.category)
    store = Store(args.db)
    run = run_category(store, args.category, extractor_name="rule", min_size=3)
    t0 = date.today().isoformat()
    end = (date.fromisoformat(t0) + timedelta(days=30 * args.months)).isoformat()

    preds = []
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
        qs = llm_queries(c["label"], [a.quote for a in objs])
        pred = make_prediction(run.run_id, c["cluster_id"], objs, t0, end,
                               keywords=qs or None, domain_terms=spec.domain_terms)
        if pred:
            preds.append((pred, c["label"], len(objs)))

    if not preds:
        print("no domain-specific prediction could be built", file=sys.stderr)
        store.close()
        return 1

    # Pre-register the random baseline at the same time: 6 keyword sets drawn
    # from the same corpus, evaluated with the same procedure.
    import random

    all_atoms = store.atoms(run.run_id)
    from painradar.schema import PainAtom

    objs_all = [
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
        for a in all_atoms
    ]
    vocab = vocabulary(objs_all)
    rng = random.Random(42)
    baselines = [random_baseline(vocab, 3, rng) for _ in range(6)]

    store.insert_predictions(
        [
            {
                "prediction_id": p.prediction_id, "run_id": run.run_id, "category": args.category,
                "cluster_id": p.cluster_id, "t0": p.t0, "window_end": p.window_end,
                "keywords": p.keywords, "proposition": p.proposition, "mode": "forward",
            }
            for p, _, _ in preds
        ]
        + [
            {
                "prediction_id": f"base_{i:02d}", "run_id": run.run_id, "category": args.category,
                "cluster_id": "baseline", "t0": t0, "window_end": end,
                "keywords": kws, "proposition": "随机基线：" + " / ".join(kws), "mode": "baseline",
            }
            for i, kws in enumerate(baselines, start=1)
        ]
    )

    lines = [
        f"# 前向测试登记 — {spec.name}",
        "",
        f"- 登记日 T0：{t0} ｜ 回看日：{end}（{args.months} 个月）",
        f"- 训练语料：{run.stats['items']} 条评论 → {run.stats['atoms']} 原子 → {run.stats['clusters']} 簇",
        f"- 登记预测：{len(preds)} 条（域名门槛：{' / '.join(spec.domain_terms[:8])} …）",
        f"- 判定规则：预注册，跑之前不得修改；见 `docs/forward-protocol.md`",
        "",
        "| # | 簇 | 关键词 | 证据条数 |",
        "|---|---|---|---|",
    ]
    for i, (p, label, n) in enumerate(preds, start=1):
        lines.append(f"| {i} | {label[:30]} | {' / '.join(p.keywords)} | {n} |")

    lines += ["", "## 命题原文", ""]
    for p, _, _ in preds:
        lines.append(f"- `{p.prediction_id}` — {p.proposition}")

    lines += ["", "## 预注册基线（6 组，同流程）", ""]
    for i, kws in enumerate(baselines, start=1):
        lines.append(f"- `base_{i:02d}` — {' / '.join(kws)}")

    text = "\n".join(lines)
    out = Path(args.out) if args.out else ROOT / "docs" / f"forward-{args.category}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nwritten to {out}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
