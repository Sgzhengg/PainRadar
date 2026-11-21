"""Markdown business report: ranked opportunities with evidence chains."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Cluster, Signal


def _fmt_likes(n: int) -> str:
    return f"{n:,}"


def render_report(
    keyword: str,
    clusters: list[Cluster],
    signals: list[Signal],
    input_stats: dict[str, Any],
    token_stats: dict[str, int],
    source: str = "",
) -> str:
    lines: list[str] = []
    total = input_stats.get("threads", 0)
    kept = input_stats.get("kept_comments", 0) + input_stats.get("kept_replies", 0)
    dropped = sum(v for k, v in input_stats.items() if k.startswith("drop_"))
    lines.append(f"# 商机研报：{keyword}")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 数据源：{source or '未标注'}")
    lines.append(
        f"> 输入：{total} 个对话 ｜ 保留评论 {kept} 条 ｜ 规则过滤 {dropped} 条 ｜ "
        f"有效信号 {len(signals)} 条 ｜ token {token_stats.get('total_tokens', 0):,}"
    )
    lines.append("")
    if not clusters:
        lines.append("本次没有提取到合格信号。建议放宽关键词、扩大样本，或降低最短评论长度。")
        return "\n".join(lines) + "\n"

    lines.append("## 商机总览")
    lines.append("")
    lines.append("| # | 商机 | 评分 | 提及 | 最高赞 | 变现 | 难度 |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, c in enumerate(clusters, start=1):
        lines.append(
            f"| {i} | {c.name} | **{c.score}** | {c.stats.get('mentions', 0)} | "
            f"{_fmt_likes(c.stats.get('max_likes', 0))} | {c.monetization or '—'} | "
            f"{'★' * c.dev_difficulty} |"
        )
    lines.append("")

    for i, c in enumerate(clusters, start=1):
        flag = " ｜ 样本不足，仅作线索" if c.stats.get("mentions", 0) < 2 else ""
        lines.append(f"## {i}. {c.name}（{c.score}/10）{flag}")
        lines.append("")
        lines.append(f"**痛点画像**：{c.pain_profile or '—'}")
        lines.append("")
        lines.append("| 要素 | 说明 |")
        lines.append("|---|---|")
        lines.append(f"| 谁会付钱 | {c.buyer or '—'} |")
        lines.append(f"| 使用场景 | {c.scenario or '—'} |")
        lines.append(f"| 变现模式 | {c.monetization or '—'} |")
        lines.append(f"| 开发难度 | {'★' * c.dev_difficulty}（{c.dev_difficulty}/5） |")
        lines.append(f"| 付费明确度 | {c.wtp_clarity:.2f} |")
        lines.append("")
        lines.append("**证据链（按赞数排序）**")
        lines.append("")
        for j, s in enumerate(c.evidence, start=1):
            lines.append(f"{j}. > {s.quote}")
            link = f" [原帖]({s.url})" if s.url else ""
            lines.append(
                f"   — `{s.type}` ｜ 赞 {_fmt_likes(s.likes)} ｜ 回复 {s.replies}{link}"
            )
        if not c.evidence:
            lines.append("（无高赞证据，需人工复核）")
        lines.append("")
        if c.mvp:
            lines.append(f"**MVP 切入点（1–2 周）**：{c.mvp}")
            lines.append("")
        types = Counter(s.type for s in c.evidence) if c.evidence else Counter()
        if types:
            lines.append("信号构成：" + "，".join(f"{k} ×{v}" for k, v in types.items()))
            lines.append("")

    lines.append("## 方法与局限")
    lines.append("")
    lines.append("- 清洗：长度 < 6 字、纯表情、纯 @、广告引流词直接丢弃；")
    lines.append("- 上下文：原帖标题/正文 + 高赞评论 + 楼中楼回复一起送入模型；")
    lines.append("- 提取：只保留 4 类信号（竞品吐槽/求推荐/手工繁琐/付费信号），其余丢弃；")
    lines.append("- 评分：提及频次 30% + 最高赞 20% + 付费明确度 20% + 开发难度 20% + 信号多样性 10%；")
    lines.append("- 局限：评分是排序工具，不是市场验证；证据引用需人工抽查；样本受来源平台影响。")
    return "\n".join(lines) + "\n"


def write_report(path: str | Path, markdown: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(markdown, encoding="utf-8")
    return p
