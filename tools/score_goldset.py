"""Score extractors against the human-labelled pilot.

    python tools/score_goldset.py --db var/gold200.db --category pet_water_fountain \
        --labels data/goldset/pilot-labels.csv --out docs/goldset-pilot.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import DB_PATH, category as get_category  # noqa: E402
from painradar.store import Store  # noqa: E402
from painradar.taxonomy import classify_scene  # noqa: E402

LEVELS = ["L0", "L1", "L2", "L3", "L4"]


def _read_csv(path: Path) -> list[dict]:
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _latest_run(store: Store, category: str, prefix: str) -> str | None:
    for row in store._conn.execute(
        "SELECT run_id FROM runs WHERE category=? ORDER BY created_at DESC", (category,)
    ).fetchall():
        first = store._conn.execute(
            "SELECT model_version FROM atoms WHERE run_id=? LIMIT 1", (row["run_id"],)
        ).fetchone()
        if first and first["model_version"].startswith(prefix):
            return row["run_id"]
    return None


def _atoms(store: Store, run_id: str) -> dict[str, dict]:
    return {
        r["comment_uid"]: dict(r)
        for r in store._conn.execute("SELECT * FROM atoms WHERE run_id=?", (run_id,)).fetchall()
    }


def _bigrams(text: str) -> set[str]:
    t = "".join(ch for ch in text.lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    return {t[i : i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t}


def _overlap(a: str, b: str) -> float:
    """Containment (|A∩B| / min), which tolerates different lengths."""
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / min(len(A), len(B))


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def _kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    if not n:
        return 0.0
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


def _score(gold: list[dict], atoms: dict[str, dict]) -> dict:
    tp = fp = fn = tn = 0
    level_pairs: list[tuple[str, str]] = []
    scene_hit = scene_tot = 0
    wa_tp = wa_fp = wa_fn = 0
    obs_hit = obs_tot = 0
    obs_nonempty = 0
    disagreements: list[str] = []

    for row in gold:
        uid = row["comment_uid"]
        g_valid = row["gold_valid"] == "1"
        atom = atoms.get(uid)
        p_valid = atom is not None
        if g_valid and p_valid:
            tp += 1
        elif g_valid and not p_valid:
            fn += 1
        elif not g_valid and p_valid:
            fp += 1
        else:
            tn += 1

        if g_valid and p_valid:
            g_level, p_level = row["gold_level"], atom["level"]
            level_pairs.append((g_level, p_level))
            if g_level != p_level:
                disagreements.append(f"{uid}: level gold={g_level} pred={p_level} · {atom['obstacle'][:50]}")
            g_scene = row["gold_scene"] or "其他场景"
            scene_tot += 1
            if atom["scene"] == g_scene:
                scene_hit += 1
            elif len(disagreements) < 12:
                disagreements.append(f"{uid}: scene gold={g_scene} pred={atom['scene']}")

            g_wa = bool(row["gold_workaround"])
            p_wa = bool(atom["workaround"])
            if g_wa and p_wa:
                wa_tp += 1
            elif p_wa:
                wa_fp += 1
            elif g_wa:
                wa_fn += 1

            if row["gold_obstacle"]:
                obs_tot += 1
                if _overlap(row["gold_obstacle"], atom["obstacle"] or atom["quote"]) >= 0.2:
                    obs_hit += 1
            if atom["obstacle"]:
                obs_nonempty += 1

    p, r, f = _prf(tp, fp, fn)
    wa_p, wa_r, wa_f = _prf(wa_tp, wa_fp, wa_fn)
    exact = sum(1 for a, b in level_pairs if a == b)
    within = sum(1 for a, b in level_pairs if abs(LEVELS.index(a) - LEVELS.index(b)) <= 1)
    return {
        "valid_precision": p,
        "valid_recall": r,
        "valid_f1": f,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "level_n": len(level_pairs),
        "level_acc": exact / len(level_pairs) if level_pairs else 0.0,
        "level_within1": within / len(level_pairs) if level_pairs else 0.0,
        "kappa": _kappa(level_pairs),
        "scene_acc": scene_hit / scene_tot if scene_tot else 0.0,
        "wa_f1": wa_f,
        "obstacle_support": obs_hit / obs_tot if obs_tot else 0.0,
        "obstacle_nonempty": obs_nonempty / len(level_pairs) if level_pairs else 0.0,
        "disagreements": disagreements,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--category", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--remap-scene", action="store_true", help="recompute scene with taxonomy v2")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    gold = _read_csv(Path(args.labels))
    store = Store(args.db)
    spec = get_category(args.category)

    runs = {
        "rule": _latest_run(store, args.category, "extract-rule"),
        "llm": _latest_run(store, args.category, "extract-llm"),
    }
    results = {}
    for name, run_id in runs.items():
        if not run_id:
            continue
        atoms = _atoms(store, run_id)
        if args.remap_scene:
            for atom in atoms.values():
                atom["scene"] = classify_scene(f"{atom['quote']} {atom['obstacle']}", spec)
        results[name] = (run_id, _score(gold, atoms))

    if not results:
        print("no rule/llm runs found", file=sys.stderr)
        return 1

    n = len(gold)
    valid = sum(1 for g in gold if g["gold_valid"] == "1")
    lines = [
        f"# 金标试点评分 — {args.category}",
        "",
        f"- 标注条数：{n}（其中有效痛点 {valid} 条，占 {valid / n:.0%}）",
        f"- 标注人：内部 1 人（非盲复核见限制）",
        "",
        "| 指标 | " + " | ".join(results) + " |",
        "|---|" + "---|" * len(results),
    ]

    def row(label: str, key: str, pct: bool = True) -> str:
        cells = []
        for name in results:
            v = results[name][1][key]
            cells.append(f"{v:.1%}" if pct else f"{v:.2f}")
        return f"| {label} | " + " | ".join(cells) + " |"

    lines += [
        row("有效痛点 P", "valid_precision"),
        row("有效痛点 R", "valid_recall"),
        row("有效痛点 F1", "valid_f1"),
        row("L 级完全一致", "level_acc"),
        row("L 级 ±1 一致", "level_within1"),
        row("L 级 kappa", "kappa", pct=False),
        row("场景一致", "scene_acc"),
        row("绕行方案 F1", "wa_f1"),
        row("阻碍字段非空", "obstacle_nonempty"),
        row("阻碍可支撑率（跨语言仅参考）", "obstacle_support"),
    ]

    for name, (run_id, res) in results.items():
        lines += [
            "",
            f"**{name}** `{run_id}` — TP {res['tp']} / FP {res['fp']} / FN {res['fn']} / TN {res['tn']}",
        ]

    lines += ["", "## 分歧样例（前 12 条）", ""]
    for name, (_, res) in results.items():
        lines.append(f"### {name}")
        lines += [f"- {d}" for d in res["disagreements"][:6]] or ["- 无"]
        lines.append("")

    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"\nwritten to {args.out}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
