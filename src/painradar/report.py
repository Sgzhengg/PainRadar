"""Report rendering: Markdown (always) and DOCX (optional).

The report is where the product's promise is kept or broken, so it leads with
the denominators, shows the evidence verbatim, and prints the falsifier next to
the market range.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import GRADE_LABEL, REPORT_DIR, category as get_category
from .store import Store

FACTOR_LABEL = {
    "frequency": "频次",
    "breadth": "人群广度",
    "intensity": "情绪强度",
    "cost_clarity": "代价清晰度",
    "persistence": "持续性",
    "supply_gap": "供给缺口",
    "wtp": "付费信号",
    "wtp_coverage": "付费信号覆盖率",
    "serviceability": "可服务性",
    "timing": "时机",
    "competition": "竞争强度",
}


def _money(value: float, currency: str = "USD") -> str:
    symbol = "$" if currency == "USD" else "¥"
    if value >= 1_000_000:
        return f"{symbol}{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{symbol}{value / 1_000:.0f}K"
    return f"{symbol}{value:.0f}"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_assumption(key: str, value: float) -> str:
    if key in ("penetration", "reachability", "conversion", "share"):
        return f"{value * 100:.1f}%"
    if key == "population":
        return f"{value:,.0f}"
    if key == "arpu":
        return f"${value:,.0f}"
    return f"{value:,.0f}"


def render_markdown(store: Store, run_id: str, out_dir: Path | None = None) -> Path:
    run = store._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise SystemExit(f"run not found: {run_id}")
    stats = json.loads(run["stats_json"])
    spec = get_category(run["category"])
    opps = store.opportunities(run_id)
    scores = {
        r["cluster_id"]: r
        for r in store._conn.execute("SELECT * FROM scores WHERE run_id=?", (run_id,)).fetchall()
    }

    generated = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    add = lines.append

    add(f"# {spec.name} · 机会雷达报告")
    add("")
    add(f"> 品类：{spec.name}（`{spec.key}`）｜ 运行：`{run_id}` ｜ 生成：{generated}")
    if stats.get("synthetic", False):
        add("> 数据性质：**演示数据集**（合成样本），不可用于对外定价或投放。")
    else:
        add("> 数据性质：**真实公开数据**（App Store RSS / Reddit 公开接口），仍受样本覆盖限制。")
    add("")

    # --- denominators -----------------------------------------------------
    add("## 0. 数据与分母")
    add("")
    add("| 指标 | 数值 |")
    add("|---|---|")
    add(f"| 平台 | {', '.join(stats.get('platforms', []))} |")
    add(f"| 时间窗 | {stats.get('window', ['', ''])[0]} → {stats.get('window', ['', ''])[1]} |")
    add(f"| 扫描评论 | {stats.get('items', 0)} |")
    add(f"| 入库痛点原子 | {stats.get('atoms', 0)} |")
    add(f"| 簇数 | {stats.get('clusters', 0)} |")
    add(f"| 噪声率 | {_pct(stats.get('noise_rate', 0))} |")
    levels_all = stats.get("levels", {})
    total_levels = sum(levels_all.values()) or 1
    l2_plus = sum(levels_all.get(k, 0) for k in ("L2", "L3", "L4")) / total_levels
    add(f"| L2+ 证据占比 | {_pct(l2_plus)} |")
    add(f"| 抽取器 | `{stats.get('extractor')}` ｜ 阈值 {stats.get('threshold')} ｜ 最小簇 {stats.get('min_size')} |")
    add("")
    levels = stats.get("levels", {})
    if levels:
        add("**痛点梯子分布**：" + "，".join(f"{k} {v}" for k, v in sorted(levels.items())))
        add("")

    # --- summary ----------------------------------------------------------
    add("## 1. 一页结论")
    add("")
    if not opps:
        add("尚无满足条件的机会簇。")
    else:
        for i, o in enumerate(opps[:3], start=1):
            add(f"{i}. **{o['title']}**（机会 {o['opportunity_tier']} / 痛感 {o['pain_tier']}）—— {o['one_liner']}")
    add("")
    add("> 读法：先看分母与噪声率，再看证据，最后看市场区间。任何没有外部锚的数字，只当假设。")
    add("")

    # --- cards ------------------------------------------------------------
    add("## 2. 机会卡")
    add("")
    for idx, o in enumerate(opps, start=1):
        score = scores.get(o["cluster_id"])
        factors = json.loads(score["factors_json"]) if score else {}
        members = store.cluster_members(run_id, o["cluster_id"])

        add(f"### 2.{idx} {o['title']}")
        add("")
        add(f"**一句话**：{o['one_liner']}")
        add("")
        add("| 维度 | 结论 |")
        add("|---|---|")
        add(f"| 痛感 | {o['pain_tier']}（{score['pain']:.1f}/100） |" if score else "| 痛感 | — |")
        add(f"| 机会 | {o['opportunity_tier']}（{score['opportunity']:.1f}/100） |" if score else "| 机会 | — |")
        add(f"| 人群 | {o['persona'] or '待补'} |")
        add(f"| 现有替代 | {o['workaround'] or '未观察到明确替代方案'} |")
        add(f"| 市场区间（SOM，分摊后） | {_money(o['market_low'])} – {_money(o['market_high'])}（中值 {_money(o['market_mid'])}） |")
        add(f"| 证据条数 | {len(members)} |")
        ladder = {}
        for m in members:
            ladder[m["level"]] = ladder.get(m["level"], 0) + 1
        add("| 证据梯子 | " + " / ".join(f"{k} {v}" for k, v in sorted(ladder.items())) + " |")
        add("")
        member_l2 = sum(v for k, v in ladder.items() if k in ("L2", "L3", "L4"))
        if members and member_l2 / len(members) < 0.2:
            add("> ⚠ 该簇以纯抱怨（L1）为主，缺少绕行方案或付费信号。"
                "先做人群验证，不要直接据此立项。")
            add("")

        add("**证据（原文可回源）**")
        add("")
        for m in members[:3]:
            add(f"> {m['quote']}")
            add(f"> — {m['platform']} · {m['published_at']} · 置信度 {m['confidence']:.2f} · 梯子 {m['level']}")
            if m["url"]:
                add(f"> <{m['url']}>")
            add("")
        if not members:
            add("_无可用证据_")
            add("")

        if factors:
            add("**评分因子**")
            add("")
            add("| 因子 | 取值 |")
            add("|---|---|")
            for key, label in FACTOR_LABEL.items():
                if key in factors:
                    add(f"| {label} | {factors[key]:.2f} |")
            add("")
            if factors.get("wtp_coverage", 0) < 0.05:
                cov_pct = factors.get("wtp_coverage", 0) * 100
                add(f"> 付费信号覆盖率仅 {cov_pct:.1f}%：样本中几乎没有明确的付费表达，"
                    "分数按中性先验 0.5 处理，**不应解读为「没有付费意愿」**，只能解读为「尚未观测到」。")
                add("")

        add("**市场估算（三路交叉中的自下而上）**")
        add("")
        add("| 假设 | 低 | 中 | 高 | 来源等级 |")
        add("|---|---|---|---|---|")
        for a in json.loads(o["assumptions_json"]):
            grade = a.get("grade", "D")
            add(f"| {a['name']} | {_fmt_assumption(a['key'], a['low'])} | "
                f"{_fmt_assumption(a['key'], a['mid'])} | {_fmt_assumption(a['key'], a['high'])} | {grade} |")
        add("")
        sens = json.loads(o["sensitivity_json"])[:3]
        if sens:
            add("**敏感性（影响最大的前 3 项）**：" + "；".join(
                f"{s['name']} ±{abs(s['delta']):,.0f}" for s in sens
            ))
            add("")
        add(f"**证伪条件**：{o['falsifier']}")
        add("")

        add("**7 天验证包**")
        add("")
        add("| 假设 | 实验 | 阈值 | 周期/成本 |")
        add("|---|---|---|---|")
        for v in json.loads(o["validation_json"]):
            add(f"| {v['hypothesis']} | {v['experiment']} | {v['threshold']} | {v['cost']} |")
        add("")

    # --- anchors ----------------------------------------------------------
    add("## 3. 外部锚")
    add("")
    anchor_rows = store.anchors(spec.key)
    if anchor_rows:
        add("| 来源 | 指标 | 数值 | 观测日 | 等级 | 备注 |")
        add("|---|---|---|---|---|---|")
        for a in anchor_rows:
            value = f"{a['value']:.2f}" if a["metric"] == "avg_rating" else f"{a['value']:,.0f}"
            add(f"| {a['source']} | {a['metric']} | {value} | {a['as_of']} | {a['grade']} | {a['note']} |")
        add("")
        from .anchors import sample_coverage

        cov = sample_coverage(store, spec.key, run_id)
        if cov:
            add(
                f"**样本覆盖率**：本次扫描 {cov['sample']:,.0f} 条，锚定评论量 {cov['population']:,.0f} 条，"
                f"覆盖 {cov['coverage'] * 100:.2f}%。覆盖率越低，结论越应被当作假设而非普查。"
            )
            add("")
    else:
        add("未接入外部锚。市场区间目前只来自自下而上的假设，等级为 C/D，**不可用于对外定价**。")
        add("")

    # --- table ------------------------------------------------------------
    add("## 4. 全量机会清单")
    add("")
    add("| # | 机会 | 痛感 | 机会 | 市场中值 | 证据数 |")
    add("|---|---|---|---|---|---|")
    for i, o in enumerate(opps, start=1):
        add(f"| {i} | {o['title']} | {o['pain_tier']} | {o['opportunity_tier']} | {_money(o['market_mid'])} | "
            f"{len(store.cluster_members(run_id, o['cluster_id']))} |")
    add("")

    # --- method / limits --------------------------------------------------
    add("## 5. 方法与限制")
    add("")
    add("- **抽取**：规则抽取器（离线、确定性）。每条原子必须通过原文锚定（exact/normalized/fuzzy），失败即丢弃。")
    add("- **聚类**：在归一化槽位（场景/目标/阻碍/替代）上做 TF-IDF + 平均连接层次聚类，噪声率如实披露。")
    add("- **评分**：痛感为加权和，机会为几何平均；对外只给三档，内部保留连续分。")
    add("- **市场**：自下而上（人群 × 渗透 × 触达 × 转化 × 客单价），输出 P10/P50/P90；分摊到簇按声量份额。")
    add("- **限制**：演示数据为合成样本；市场假设多为 C/D 级；供给缺口与竞争强度尚未接入外部锚。")
    add("- **合规**：仅使用用户提供/授权数据；PII 在入库前脱敏；原文仅存片段与哈希。")
    add("")
    add("---")
    add(f"_由 PainRadar v0.1 生成 · {GRADE_LABEL['D']} 假设需在 M1 用 A/B 级证据替换。_")
    add("")

    out_dir = out_dir or REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{spec.key}-{run_id}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def render_docx(store: Store, run_id: str, md_path: Path | None = None) -> Path | None:
    """Minimal DOCX export (optional dependency: python-docx)."""
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError:
        return None

    run = store._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    stats = json.loads(run["stats_json"])
    spec = get_category(run["category"])
    opps = store.opportunities(run_id)

    doc = Document()
    doc.add_heading(f"{spec.name} · 机会雷达报告", level=0)
    doc.add_paragraph(f"品类 {spec.name}（{spec.key}）｜运行 {run_id}")
    doc.add_paragraph(
        f"扫描 {stats.get('items')} 条评论，入库 {stats.get('atoms')} 条痛点原子，"
        f"{stats.get('clusters')} 个簇，噪声率 {stats.get('noise_rate', 0) * 100:.1f}%。"
    )
    doc.add_paragraph("数据性质：演示数据集（合成样本），不可用于对外定价。")

    for i, o in enumerate(opps, start=1):
        doc.add_heading(f"{i}. {o['title']}（机会 {o['opportunity_tier']}）", level=1)
        doc.add_paragraph(o["one_liner"])
        doc.add_paragraph(f"市场区间：${o['market_low']:,.0f} – ${o['market_high']:,.0f}（中值 ${o['market_mid']:,.0f}）")
        doc.add_paragraph("证据：")
        for m in store.cluster_members(run_id, o["cluster_id"])[:3]:
            p = doc.add_paragraph(m["quote"], style="Intense Quote")
            p.add_run(f"\n— {m['platform']} · {m['published_at']}").font.size = Pt(8)
        doc.add_paragraph(f"证伪条件：{o['falsifier']}")

    out = (md_path.parent if md_path else REPORT_DIR) / f"{spec.key}-{run_id}.docx"
    doc.save(out)
    return out
