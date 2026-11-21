"""Render a run as a single self-contained HTML dashboard.

    python tools/build_html.py --db var/gold200.db --category pet_water_fountain \
        --out reports/ui-demo.html

No server, no JS dependencies: the file opens by double-click and can be
screenshotted headlessly.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import category as get_category  # noqa: E402
from painradar.store import Store  # noqa: E402

SOLO_CSS = """
.solo{margin:6px 0 14px;font-size:13px;padding:5px 10px;border-radius:8px;display:inline-block}
.solo.low{background:#ecfdf5;color:#047857}
.solo.mid{background:#fffbeb;color:#b45309}
.solo.high{background:#fef2f2;color:#b91c1c}
"""

FACTOR_LABEL = {
    "frequency": "频次",
    "breadth": "人群广度",
    "intensity": "情绪强度",
    "cost_clarity": "代价清晰度",
    "persistence": "持续性",
    "supply_gap": "供给缺口",
    "wtp": "付费信号",
    "serviceability": "可服务性",
    "timing": "时机",
    "competition": "竞争密度",
}

CSS = """
:root{--ink:#14181f;--muted:#5b6675;--line:#e6e9ef;--bg:#f6f7fb;--card:#fff;
--accent:#4f46e5;--strong:#0f766e;--mid:#b45309;--weak:#6b7280;--warn:#b91c1c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
line-height:1.6}
.wrap{max-width:1120px;margin:0 auto;padding:36px 24px 72px}
header{background:linear-gradient(135deg,#1e1b4b,#4338ca 55%,#6366f1);color:#fff;
border-radius:20px;padding:32px 36px;box-shadow:0 18px 40px rgba(67,56,202,.22)}
header .eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;opacity:.75}
header h1{margin:8px 0 6px;font-size:30px;font-weight:700}
header .sub{opacity:.85;font-size:14px}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
.chip{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);
border-radius:999px;padding:6px 14px;font-size:13px}
.chip b{font-weight:600}
.section{margin-top:38px}
.section h2{font-size:19px;margin:0 0 14px}
.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.sum-item{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.sum-item .rank{font-size:12px;color:var(--muted)}
.sum-item .t{font-weight:600;margin:6px 0}
.sum-item .d{font-size:13px;color:var(--muted)}
.cards{display:grid;grid-template-columns:1fr;gap:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:26px 28px;
box-shadow:0 2px 10px rgba(20,24,31,.04)}
.card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.card h3{margin:0;font-size:21px}
.tier{font-size:12px;font-weight:700;padding:5px 12px;border-radius:999px;white-space:nowrap}
.tier.strong{background:#ccfbf1;color:var(--strong)}
.tier.mid{background:#fef3c7;color:var(--mid)}
.tier.weak{background:#f3f4f6;color:var(--weak)}
.one-liner{margin:14px 0 18px;font-size:15px;color:#2b3444}
.scores{display:flex;gap:26px;margin:16px 0 8px}
.score .n{font-size:30px;font-weight:700;line-height:1}
.score .l{font-size:12px;color:var(--muted);margin-top:4px}
.bars{margin:18px 0 8px;display:grid;grid-template-columns:repeat(2,1fr);gap:8px 26px}
.bar{display:flex;align-items:center;gap:10px;font-size:13px}
.bar .name{width:82px;color:var(--muted);flex:none}
.bar .track{flex:1;height:7px;background:#eef0f5;border-radius:999px;overflow:hidden;display:block}
.bar .fill{height:100%;background:linear-gradient(90deg,#6366f1,#22d3ee);border-radius:999px;display:block}
.bar .val{width:34px;text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
blockquote{margin:16px 0;padding:14px 18px;background:#f8fafc;border-left:3px solid #c7d2fe;
border-radius:0 10px 10px 0;color:#334155;font-size:14px}
blockquote .meta{display:block;margin-top:6px;color:var(--muted);font-size:12px}
.kv{display:grid;grid-template-columns:120px 1fr;gap:6px 16px;font-size:14px;margin-top:14px}
.kv .k{color:var(--muted)}
.warn{margin-top:14px;padding:10px 14px;border-radius:10px;background:#fef2f2;color:var(--warn);font-size:13px}
.market{margin-top:16px;display:flex;align-items:baseline;gap:12px}
.market .big{font-size:22px;font-weight:700}
.market .rng{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);
border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}
th{background:#f9fafb;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:none}
footer{margin-top:44px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:18px}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:999px;background:#eef2ff;color:#4338ca}
"""


def _money(v: float) -> str:
    if v >= 1e8:
        return f"${v / 1e8:.2f} 亿"
    if v >= 1e4:
        return f"${v / 1e4:.1f} 万"
    return f"${v:,.0f}"


def _tier_class(tier: str) -> str:
    return {"强": "strong", "中": "mid"}.get(tier, "weak")


def _app_label(item_id: object, spec) -> str:
    parts = str(item_id or "").split("_")
    app = parts[1] if len(parts) >= 3 and parts[0] == "as" else ""
    return spec.app_names.get(app, app)


def _bar(name: str, value: float) -> str:
    pct = max(0.0, min(1.0, float(value))) * 100
    return (
        f'<div class="bar"><span class="name">{html.escape(name)}</span>'
        f'<span class="track"><span class="fill" style="width:{pct:.0f}%"></span></span>'
        f'<span class="val">{float(value):.2f}</span></div>'
    )


def render(store: Store, run_id: str | None, spec_key: str) -> str:
    spec = get_category(spec_key)
    run = (
        store._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if run_id
        else store._conn.execute(
            "SELECT * FROM runs WHERE category=? ORDER BY created_at DESC LIMIT 1", (spec_key,)
        ).fetchone()
    )
    if run is None:
        raise SystemExit(f"no run for {spec_key}")

    stats = json.loads(run["stats_json"])
    opps = store.opportunities(run["run_id"])
    scores = {
        r["cluster_id"]: r
        for r in store._conn.execute("SELECT * FROM scores WHERE run_id=?", (run["run_id"],)).fetchall()
    }
    levels = stats.get("levels", {})
    total_levels = sum(levels.values()) or 1
    l2_share = sum(levels.get(k, 0) for k in ("L2", "L3", "L4")) / total_levels
    noise = stats.get("noise_rate", 0)
    generated = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")

    parts: list[str] = []
    parts.append("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>")
    parts.append(f"<title>{html.escape(spec.name)} · 机会雷达</title><style>{CSS}{SOLO_CSS}</style></head><body>")
    parts.append("<div class='wrap'>")

    parts.append("<header>")
    parts.append("<div class='eyebrow'>PainRadar · 机会雷达</div>")
    parts.append(f"<h1>{html.escape(spec.name)}</h1>")
    parts.append(
        f"<div class='sub'>运行 <code>{html.escape(run['run_id'])}</code> · 生成于 {generated} · "
        f"抽取器 <b>{html.escape(str(stats.get('extractor')))}</b></div>"
    )
    parts.append("<div class='chips'>")
    for label, value in (
        ("扫描评论", stats.get("items")),
        ("痛点原子", stats.get("atoms")),
        ("机会簇", stats.get("clusters")),
        ("噪声率", f"{noise:.0%}"),
        ("L2+ 证据", f"{l2_share:.0%}"),
    ):
        parts.append(f"<span class='chip'>{label} <b>{html.escape(str(value))}</b></span>")
    parts.append("</div></header>")

    # summary
    if opps:
        parts.append("<div class='section'><h2>一页结论</h2><div class='summary'>")
        for i, o in enumerate(opps[:3], start=1):
            parts.append(
                "<div class='sum-item'>"
                f"<div class='rank'>#{i} · 机会 {html.escape(o['opportunity_tier'])} / 痛感 {html.escape(o['pain_tier'])}</div>"
                f"<div class='t'>{html.escape(o['title'])}</div>"
                f"<div class='d'>{html.escape(o['one_liner'])}</div></div>"
            )
        parts.append("</div></div>")

    parts.append("<div class='section'><h2>机会卡</h2><div class='cards'>")
    for idx, o in enumerate(opps, start=1):
        score = scores.get(o["cluster_id"])
        factors = json.loads(score["factors_json"]) if score else {}
        try:
            solo = json.loads(o["solo_fit_json"] or "{}")
        except (KeyError, ValueError):
            solo = {}
        members = store.cluster_members(run["run_id"], o["cluster_id"])
        ladder: dict[str, int] = {}
        for m in members:
            ladder[m["level"]] = ladder.get(m["level"], 0) + 1
        l2_members = sum(v for k, v in ladder.items() if k in ("L2", "L3", "L4"))
        low_l2 = bool(members) and l2_members / len(members) < 0.2

        parts.append("<div class='card'>")
        parts.append("<div class='card-head'>")
        parts.append(f"<h3>{idx}. {html.escape(o['title'])}</h3>")
        parts.append(
            f"<span class='tier {_tier_class(o['opportunity_tier'])}'>机会 {html.escape(o['opportunity_tier'])}</span>"
        )
        parts.append("</div>")
        parts.append(f"<div class='one-liner'>{html.escape(o['one_liner'])}</div>")
        if solo.get("level"):
            cls = {"低": "low", "中": "mid", "高": "high"}.get(solo["level"], "mid")
            parts.append(
                f"<div class='solo {cls}'>⚡ {html.escape(str(solo.get('mvp_days', '')))} 可做 · "
                f"{html.escape(str(solo.get('form', '')))} · {html.escape(str(solo.get('monetization', '')))}"
                f"（难度 {html.escape(str(solo.get('level')))}）</div>"
            )

        parts.append("<div class='scores'>")
        if score:
            parts.append(f"<div class='score'><div class='n'>{score['pain']:.0f}</div><div class='l'>痛感 / 100</div></div>")
            parts.append(
                f"<div class='score'><div class='n'>{score['opportunity']:.0f}</div><div class='l'>机会 / 100</div></div>"
            )
        parts.append(f"<div class='score'><div class='n'>{len(members)}</div><div class='l'>证据条数</div></div>")
        parts.append("</div>")

        if factors:
            parts.append("<div class='bars'>")
            for key, label in FACTOR_LABEL.items():
                if key in factors and key != "wtp_coverage":
                    parts.append(_bar(label, factors[key]))
            parts.append("</div>")

        if members:
            m = members[0]
            parts.append("<blockquote>")
            parts.append(html.escape(m["quote"]))
            parts.append(
                f"<span class='meta'>{html.escape(str(m['platform']))} · "
                f"{html.escape(_app_label(m['item_id'], spec))} · {html.escape(str(m['published_at']))} · "
                f"置信度 {m['confidence']:.2f} · 梯子 {html.escape(str(m['level']))}"
                + (f" · 👍 {m['likes']}" if "likes" in m.keys() and m["likes"] else "")
                + "</span>"
            )
            parts.append("</blockquote>")

        parts.append("<div class='kv'>")
        parts.append(f"<span class='k'>人群</span><span>{html.escape(o['persona'] or '待补')}</span>")
        parts.append(
            f"<span class='k'>现有替代</span><span>{html.escape(o['workaround'] or '未观察到明确替代')}</span>"
        )
        parts.append(
            f"<span class='k'>证据梯子</span><span>{' / '.join(f'{k} {v}' for k, v in sorted(ladder.items())) or '—'}</span>"
        )
        parts.append("</div>")

        parts.append("<div class='market'>")
        parts.append(f"<span class='big'>{_money(o['market_mid'])}</span>")
        parts.append(
            f"<span class='rng'>SOM 中值 · 区间 {_money(o['market_low'])} – {_money(o['market_high'])}</span>"
        )
        parts.append("</div>")

        if low_l2:
            parts.append(
                "<div class='warn'>该簇以纯抱怨（L1）为主，缺少绕行方案或付费信号。先做人群验证，不要直接据此立项。</div>"
            )
        if factors.get("wtp_coverage", 1) < 0.05:
            parts.append(
                "<div class='warn'>付费信号覆盖率接近 0：分数按中性先验 0.5 处理，只能解读为“尚未观测到”。</div>"
            )

        parts.append("</div>")
    parts.append("</div></div>")

    anchor_rows = store.anchors(spec.key)
    if anchor_rows:
        parts.append("<div class='section'><h2>外部锚</h2><table><tr><th>指标</th><th>数值</th><th>来源</th><th>等级</th></tr>")
        for a in anchor_rows[:10]:
            parts.append(
                f"<tr><td>{html.escape(str(a['metric']))}</td><td>{a['value']:,.0f}</td>"
                f"<td>{html.escape(str(a['source']))}</td><td>{html.escape(str(a['grade']))}</td></tr>"
            )
        parts.append("</table></div>")

    parts.append(
        "<footer>读法：先看分母与噪声率，再看证据，最后看市场区间。"
        "任何没有外部锚的数字只当假设；L1 为主的卡片不要直接立项。</footer>"
    )
    parts.append("</div></body></html>")
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/gold200.db")
    ap.add_argument("--category", default="pet_water_fountain")
    ap.add_argument("--run", default=None)
    ap.add_argument("--out", default="reports/ui-demo.html")
    args = ap.parse_args()

    store = Store(args.db)
    text = render(store, args.run, args.category)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"written {out} ({len(text) / 1024:.0f} KB)")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
