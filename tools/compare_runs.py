"""Compare two runs (rule vs LLM) on the same corpus.

    python tools/compare_runs.py --db var/llm-real.db --category pet_water_fountain

Picks the latest rule run and latest LLM run unless --a/--b are given.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import DB_PATH  # noqa: E402
from painradar.store import Store  # noqa: E402


def _runs(store: Store, category: str) -> list[dict]:
    out = []
    for run in store._conn.execute(
        "SELECT * FROM runs WHERE category=? ORDER BY created_at DESC", (category,)
    ).fetchall():
        first = store._conn.execute(
            "SELECT model_version FROM atoms WHERE run_id=? LIMIT 1", (run["run_id"],)
        ).fetchone()
        if not first:
            continue
        model = first["model_version"]
        kind = "llm" if model.startswith("extract-llm") else "rule"
        out.append({"run_id": run["run_id"], "created_at": run["created_at"], "kind": kind,
                    "stats": json.loads(run["stats_json"])})
    return out


def _metrics(store: Store, run_id: str) -> dict:
    atoms = store._conn.execute("SELECT * FROM atoms WHERE run_id=?", (run_id,)).fetchall()
    n = len(atoms)
    levels = Counter(a["level"] for a in atoms)
    quotes = [len(a["quote"]) for a in atoms]
    obstacles = [len(a["obstacle"]) for a in atoms]
    return {
        "atoms": n,
        "levels": dict(levels),
        "l2_plus": (levels.get("L2", 0) + levels.get("L3", 0) + levels.get("L4", 0)) / n if n else 0,
        "avg_conf": sum(a["confidence"] for a in atoms) / n if n else 0,
        "workaround": sum(1 for a in atoms if a["workaround"]) / n if n else 0,
        "cost": sum(1 for a in atoms if a["cost_type"]) / n if n else 0,
        "persona": sum(1 for a in atoms if a["persona"]) / n if n else 0,
        "wtp": sum(1 for a in atoms if a["wtp_level"] != "none") / n if n else 0,
        "avg_quote": sum(quotes) / n if n else 0,
        "avg_obstacle": sum(obstacles) / n if n else 0,
        "models": dict(Counter(a["model_version"] for a in atoms)),
    }


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--category", required=True)
    ap.add_argument("--a", default=None, help="run id (default: latest rule)")
    ap.add_argument("--b", default=None, help="run id (default: latest llm)")
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    store = Store(args.db)
    runs = _runs(store, args.category)
    a_id = args.a or next((r["run_id"] for r in runs if r["kind"] == "rule"), None)
    b_id = args.b or next((r["run_id"] for r in runs if r["kind"] == "llm"), None)
    if not a_id or not b_id:
        print("need one rule run and one llm run", file=sys.stderr)
        return 1

    a, b = _metrics(store, a_id), _metrics(store, b_id)
    sa = next(r["stats"] for r in runs if r["run_id"] == a_id)
    sb = next(r["stats"] for r in runs if r["run_id"] == b_id)

    rows = [
        ("items", sa["items"], sb["items"]),
        ("atoms", a["atoms"], b["atoms"]),
        ("atoms/item", f"{a['atoms'] / max(1, sa['items']):.2f}", f"{b['atoms'] / max(1, sb['items']):.2f}"),
        ("L2+ share", _fmt_pct(a["l2_plus"]), _fmt_pct(b["l2_plus"])),
        ("avg confidence", f"{a['avg_conf']:.2f}", f"{b['avg_conf']:.2f}"),
        ("has workaround", _fmt_pct(a["workaround"]), _fmt_pct(b["workaround"])),
        ("has cost", _fmt_pct(a["cost"]), _fmt_pct(b["cost"])),
        ("has persona", _fmt_pct(a["persona"]), _fmt_pct(b["persona"])),
        ("has wtp", _fmt_pct(a["wtp"]), _fmt_pct(b["wtp"])),
        ("avg quote chars", f"{a['avg_quote']:.0f}", f"{b['avg_quote']:.0f}"),
        ("avg obstacle chars", f"{a['avg_obstacle']:.0f}", f"{b['avg_obstacle']:.0f}"),
        ("clusters", sa["clusters"], sb["clusters"]),
        ("noise rate", _fmt_pct(sa["noise_rate"]), _fmt_pct(sb["noise_rate"])),
    ]

    lines = [
        f"# Rule vs LLM — {args.category}",
        "",
        f"- A (rule): `{a_id}`",
        f"- B (llm):  `{b_id}`",
        "",
        "| metric | A (rule) | B (llm) |",
        "|---|---|---|",
    ]
    lines += [f"| {name} | {va} | {vb} |" for name, va, vb in rows]

    ext = sb.get("extraction", {})
    if ext:
        lines += [
            "",
            "**LLM extraction stats**",
            "",
            f"- calls: {ext.get('calls')}",
            f"- tokens in/out: {ext.get('tokens_in')} / {ext.get('tokens_out')}",
            f"- fallback: {ext.get('fallback')} {ext.get('reasons')}",
            f"- disagree: {ext.get('disagree')}",
            f"- errors: {ext.get('errors')}",
        ]
    lines += ["", f"**model versions (B)**: `{json.dumps(b['models'], ensure_ascii=False)}`", ""]

    for label, run_id in (("A (rule)", a_id), ("B (llm)", b_id)):
        lines += [f"## Samples — {label}", ""]
        sample = store._conn.execute(
            "SELECT quote, level, scene, obstacle, workaround, confidence FROM atoms WHERE run_id=? ORDER BY atom_id LIMIT ?",
            (run_id, args.samples),
        ).fetchall()
        for s in sample:
            lines.append(f"- [{s['level']}] {s['scene']} · {s['obstacle'][:90]!r} · wa={s['workaround'][:40]!r} · conf={s['confidence']:.2f}")
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
