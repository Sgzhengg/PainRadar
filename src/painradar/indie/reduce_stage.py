"""Reduce stage: cluster signals into opportunities and score them 1-10."""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any

from .llm import LLM
from .models import Cluster, Signal

SYSTEM = """你是独立产品经理。下面是从社区对话中提取的有效信号（JSON 列表，含 id/type/pain/quote/likes/wtp）。

把它们按"同一个核心需求"聚类，输出最多 8 类。要求：
- 每条信号必须且只能属于一类；不得遗漏。
- name ≤ 12 字，是需求名，不是产品名。
- pain_profile：谁在什么场景下遇到什么麻烦（≤60 字）。
- buyer：谁会掏钱（具体人群，不写"用户"）。
- mvp：1–2 周能交付的单一核心功能（≤40 字），不要说"做一个平台"。
- monetization：买断 / 订阅 / 按次，三选一。
- dev_difficulty：1–5，1 最易，5 最难。
- wtp_clarity：0–1，信号里付费意图有多明确。

返回 JSON：
{"clusters": [{"name": "...", "signal_ids": ["id1", "id2"], "pain_profile": "...",
  "buyer": "...", "scenario": "...", "mvp": "...", "monetization": "买断",
  "dev_difficulty": 2, "wtp_clarity": 0.6}]}"""


def _score(mentions: int, max_likes: int, wtp: float, difficulty: int, types: set[str]) -> float:
    freq = min(1.0, math.log10(1 + mentions) / math.log10(51))
    heat = min(1.0, math.log10(1 + max_likes) / math.log10(1001))
    dev = max(0.0, min(1.0, 1 - (max(1, min(5, difficulty)) - 1) / 4))
    div = len(types & {"竞品吐槽", "求推荐/平替", "手工繁琐", "付费信号"}) / 4
    raw = 0.30 * freq + 0.20 * heat + 0.20 * max(0.0, min(1.0, wtp)) + 0.20 * dev + 0.10 * div
    return round(max(1.0, min(10.0, raw * 10)), 1)


def run_reduce(llm: LLM, signals: list[Signal], max_evidence: int = 3) -> list[Cluster]:
    if not signals:
        return []
    # keep the strongest signals if the list is huge, but never drop a signal silently
    payload = [
        {
            "id": s.signal_id,
            "type": s.type,
            "pain": s.pain,
            "quote": s.quote,
            "likes": s.likes,
            "wtp": s.wtp,
        }
        for s in signals
    ]
    data = llm.chat_json(SYSTEM, json.dumps(payload, ensure_ascii=False), required=("clusters",))
    by_id = {s.signal_id: s for s in signals}
    claimed: set[str] = set()
    clusters: list[Cluster] = []
    for raw in data.get("clusters") or []:
        ids = [str(x) for x in (raw.get("signal_ids") or []) if str(x) in by_id]
        ids = [x for x in ids if x not in claimed]
        if not ids:
            continue
        claimed.update(ids)
        members = [by_id[x] for x in ids]
        types = {m.type for m in members}
        mentions = len(members)
        max_likes = max(m.likes for m in members)
        wtp = float(raw.get("wtp_clarity") or 0)
        difficulty = int(raw.get("dev_difficulty") or 3)
        cluster = Cluster(
            name=str(raw.get("name") or "未命名").strip(),
            signal_ids=ids,
            pain_profile=str(raw.get("pain_profile") or "").strip(),
            buyer=str(raw.get("buyer") or "").strip(),
            scenario=str(raw.get("scenario") or "").strip(),
            mvp=str(raw.get("mvp") or "").strip(),
            monetization=str(raw.get("monetization") or "").strip(),
            dev_difficulty=difficulty,
            wtp_clarity=max(0.0, min(1.0, wtp)),
            stats={
                "mentions": mentions,
                "max_likes": max_likes,
                "sum_likes": sum(m.likes for m in members),
                "types": sorted(types),
                "wtp_signals": sum(1 for m in members if m.wtp),
            },
        )
        cluster.score = _score(mentions, max_likes, cluster.wtp_clarity, difficulty, types)
        cluster.evidence = sorted(members, key=lambda m: (m.likes, m.replies), reverse=True)[:max_evidence]
        clusters.append(cluster)

    # any signal the model forgot still deserves a bucket
    leftovers = [s for s in signals if s.signal_id not in claimed]
    if leftovers:
        types = {s.type for s in leftovers}
        cluster = Cluster(
            name="未归类信号",
            signal_ids=[s.signal_id for s in leftovers],
            pain_profile="模型未归类的残余信号，需人工复核。",
            buyer="",
            scenario="",
            mvp="",
            monetization="",
            dev_difficulty=3,
            wtp_clarity=0.0,
            stats={
                "mentions": len(leftovers),
                "max_likes": max(s.likes for s in leftovers),
                "sum_likes": sum(s.likes for s in leftovers),
                "types": sorted(types),
                "wtp_signals": sum(1 for s in leftovers if s.wtp),
            },
        )
        cluster.score = _score(
            len(leftovers), cluster.stats["max_likes"], 0.0, 3, types
        )
        cluster.evidence = sorted(leftovers, key=lambda s: s.likes, reverse=True)[:max_evidence]
        clusters.append(cluster)

    clusters.sort(key=lambda c: c.score, reverse=True)
    return clusters
