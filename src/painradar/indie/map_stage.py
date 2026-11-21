"""Map stage: one strict, discard-heavy extraction pass over conversation blocks."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .llm import LLM, run_parallel
from .models import ContextBlock, Signal, SIGNAL_TYPES

SYSTEM = """你是一名毒舌但务实的独立产品经理。你只关心能变成产品的信号。

输入是一段社区对话（原帖标题、正文、评论、楼中楼回复），每条前面有赞数。

只提取以下 4 类信号，其余一律丢弃：
1. [竞品吐槽]：明确抱怨现有软件/工具难用、贵、有 Bug、功能缺失。
2. [求推荐/平替]：明确问"有没有什么软件能做……""求 XX 平替"。
3. [手工繁琐]：描述自己正在用笨拙、重复的方式处理某件事。
4. [付费信号]：提到价格、会员费、愿意花钱买断，或吐槽订阅太贵。

硬性规则：
- 每条信号必须引用评论原文中的一个连续片段（quote），不得改写、不得拼接。
- 广告、水军、纯情绪、纯表情、泛泛而谈（"希望更好用"）→ 不提取。
- 一条评论最多 1 条信号，一段对话最多 4 条。
- 没有合格信号就返回空数组，不要凑数。
- pain 不超过 20 个汉字，必须具体（对象 + 麻烦），不要写"体验不好"。

返回 JSON：
{"signals": [{"thread_id": "对话id", "type": "竞品吐槽|求推荐/平替|手工繁琐|付费信号",
  "pain": "具体痛点", "quote": "原文连续片段", "wtp": true|false}]}"""


def _find_likes(block: ContextBlock, quote: str) -> tuple[int, int, str]:
    """Locate the comment/reply that contains the quote; return (likes, replies, id)."""
    q = quote.strip()
    best = (0, 0, "")
    for comment in block.comments:
        if q and q in comment.text:
            return comment.likes, comment.reply_count, comment.comment_id
        for reply in comment.replies:
            if q and q in reply.text:
                return reply.likes, reply.reply_count, reply.comment_id
    # fall back: longest common substring not worth it; return zeros
    return best


def _parse_batch(llm: LLM, batch: list[ContextBlock]) -> list[Signal]:
    payload = {
        "conversations": [
            {"id": b.thread_id, "text": b.render(), "url": b.url} for b in batch
        ]
    }
    data = llm.chat_json(SYSTEM, json.dumps(payload, ensure_ascii=False), required=("signals",))
    by_id = {b.thread_id: b for b in batch}
    out: list[Signal] = []
    for i, raw in enumerate(data.get("signals") or []):
        if not isinstance(raw, dict):
            continue
        stype = str(raw.get("type") or "").strip()
        pain = str(raw.get("pain") or "").strip()
        quote = str(raw.get("quote") or "").strip()
        tid = str(raw.get("thread_id") or "").strip()
        if stype not in SIGNAL_TYPES or not pain or len(quote) < 10:
            continue
        block = by_id.get(tid)
        if block is None:
            continue
        likes, replies, cid = _find_likes(block, quote)
        if likes == 0 and replies == 0:
            # quote did not match a real comment: reject to keep evidence honest
            continue
        out.append(
            Signal(
                signal_id=f"{tid}-{i}",
                type=stype,
                pain=pain,
                quote=quote,
                likes=likes,
                replies=replies,
                url=block.url,
                thread_id=tid,
                comment_id=cid,
                wtp=bool(raw.get("wtp")),
                context=block.title,
            )
        )
    return out


def run_map(
    llm: LLM,
    blocks: list[ContextBlock],
    batch_size: int = 4,
    workers: int = 3,
) -> tuple[list[Signal], Counter]:
    stats: Counter = Counter()
    batches = [blocks[i : i + batch_size] for i in range(0, len(blocks), batch_size)]
    stats["batches"] = len(batches)

    def work(batch: list[ContextBlock]) -> list[Signal]:
        try:
            return _parse_batch(llm, batch)
        except Exception:  # noqa: BLE001
            stats["failed_batches"] += 1
            return []

    results = run_parallel(batches, work, workers=workers)
    signals: list[Signal] = []
    seen: set[tuple[str, str]] = set()
    for batch_signals in results:
        for sig in batch_signals:
            key = (sig.thread_id, sig.quote[:40])
            if key in seen:
                continue
            seen.add(key)
            signals.append(sig)
    stats["signals"] = len(signals)
    stats["with_wtp"] = sum(1 for s in signals if s.wtp)
    for sig in signals:
        stats[f"type_{sig.type}"] += 1
    return signals, stats
