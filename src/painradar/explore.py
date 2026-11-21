"""Conversational, evidence-grounded exploration.

The existing pipeline starts from a category and produces clusters. This module
starts from a vague interest (or none) and uses real comments to provoke a
conversation: one observation, two or three directions, one question. The user
reacts, and the next round narrows.

Sessions are plain JSON files under ``var/explore_sessions`` so they survive
restarts on the Zeabur volume without a schema migration.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from .config import VAR_DIR
from .store import Store

SESSION_DIR = VAR_DIR / "explore_sessions"
MEMORY_PATH = VAR_DIR / "explore_memory.json"


def _load_memory() -> dict[str, Any]:
    if not MEMORY_PATH.exists():
        return {"directions": [], "payments": []}
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except ValueError:
        return {"directions": [], "payments": []}
    data.setdefault("directions", [])
    data.setdefault("payments", [])
    return data


def _save_memory(data: dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["directions"] = data["directions"][-100:]
    data["payments"] = data["payments"][-100:]
    data["updated_at"] = time.time()
    MEMORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def relevant_memory(seed: str, limit: int = 8) -> list[dict[str, Any]]:
    data = _load_memory()
    tokens = _seed_tokens(seed)
    entries = list(data["directions"]) + list(data["payments"])
    if tokens:
        matched = [
            e for e in entries
            if any(tok in f"{e.get('seed', '')} {e.get('title', '')} {e.get('direction', '')}".lower()
                   for tok in tokens)
        ]
    else:
        matched = entries[-limit:]
    return matched[-limit:]


def remember_validation(session: dict[str, Any], result: dict[str, Any]) -> None:
    data = _load_memory()
    seed = str(session.get("seed", ""))
    title = str(result.get("direction") or "")
    entry = {
        "seed": seed,
        "title": title,
        "verdict": result.get("verdict", ""),
        "summary": result.get("summary", ""),
        "run_id": (result.get("metrics") or {}).get("run_id", ""),
        "at": time.time(),
    }
    data["directions"] = [
        e for e in data["directions"]
        if not (e.get("seed") == seed and e.get("title") == title)
    ]
    data["directions"].append(entry)
    _save_memory(data)


def remember_payment(session: dict[str, Any], answer: str) -> None:
    if not answer.strip():
        return
    directions = []
    for msg in reversed(session.get("messages", [])):
        if msg.get("role") == "assistant" and msg.get("directions"):
            directions = msg["directions"]
            break
    data = _load_memory()
    seed = str(session.get("seed", ""))
    title = str((directions[0] if directions else {}).get("title", ""))
    data["payments"] = [
        e for e in data["payments"]
        if not (e.get("seed") == seed and e.get("direction") == title)
    ]
    data["payments"].append({
        "seed": seed,
        "direction": title,
        "answer": answer.strip()[:120],
        "at": time.time(),
    })
    _save_memory(data)




SYSTEM = """你是一位产品发现教练，不是报告生成器。你在和一位独立开发者对话，
帮他从模糊兴趣走到一个值得做的产品方向。

规则：
1. 必须用真实评论作为证据；每条方向都要引用 evidence 的 id，不能编造。
2. 一次只问一个最关键的问题，不要一次抛五个问题。
3. 优先指出评论里的矛盾、代价、绕路、替代方案为什么不够好。
4. 方向要具体：谁、在什么场景、因为什么现有方案不行、最小切口是什么。
5. 避免“做一个平台/AI 助手/一站式解决方案”这种空话。
6. 如果用户说“不知道”，就给 2-3 个差异很大的方向让他挑，而不是继续追问。
7. 用户点“不感兴趣”的方向不要再提；用户说“有点意思”的方向要往下深挖。
8. 如果 payload.memory 里有上次验证结论：被削弱的方向不要再推荐；被支持的方向可以深入。
9. 语气像合伙人，不像咨询报告；中文，短句。

返回 JSON：
{
  "reflection": "一句观察，指出证据里的矛盾或机会（≤60字）",
  "directions": [
    {"title": "≤12字方向名", "who": "具体人群", "pain": "具体阻碍",
     "wedge": "最小产品切口", "why_now": "为什么现在值得做",
     "evidence_ids": [1,2]}
  ],
  "question": "一个具体问题（≤60字）",
  "probe": {
    "kind": "direction|counterfactual|payment|substitute|competition",
    "question": "一个更尖锐的追问（≤60字）",
    "why": "为什么现在问这个（≤30字）",
    "chips": ["可选回复1", "可选回复2", "可选回复3"]
  },
  "chips": ["可选回复1", "可选回复2", "可选回复3"]
}
只返回 JSON。

压力测试顺序（重要）：
- 用户还没选方向时：kind=direction，先让他挑一条；
- 选定方向后第一轮：kind=counterfactual，问“如果这个痛点是假的，最可能的原因是什么”；
- 第二轮：kind=payment，问“谁会第一个掏钱、愿意付多少、现在这笔预算花在哪”；
- 之后：kind=substitute 或 competition，问“他们为什么不会一直用 Excel/微信群凑合”。
不要一次问两个问题；不要把 payment 放在 direction 之前。"""


def _llm(messages: list[dict[str, str]], temperature: float = 0.7) -> dict[str, Any] | None:
    base = os.environ.get("PAINRADAR_LLM_BASE_URL", "").rstrip("/")
    model = os.environ.get("PAINRADAR_LLM_MODEL", "")
    key = os.environ.get("PAINRADAR_LLM_API_KEY", "")
    if not base or not model:
        return None
    try:
        response = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"} if key else {},
            json={
                "model": model,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
                "messages": messages,
            },
            timeout=90,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content[content.find("{"): content.rfind("}") + 1])
    except Exception:  # noqa: BLE001
        return None


def _seed_tokens(seed: str) -> list[str]:
    """Cheap bilingual tokenizer: PDF, 合并, 报价单, pdf工具..."""
    low = (seed or "").lower().strip()
    if not low:
        return []
    parts = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", low)
    tokens: set[str] = set(parts)
    for part in parts:
        if len(part) > 2 and all("\u4e00" <= ch <= "\u9fff" for ch in part):
            tokens.update(part[i:i + 2] for i in range(len(part) - 1))
    return [t for t in tokens if len(t) >= 2]


def collect_evidence(
    db_paths: list[str],
    category: str | None = None,
    limit: int = 24,
    seed: str = "",
) -> list[dict[str, Any]]:
    rows: list[Any] = []
    for path in db_paths:
        store = Store(path)
        try:
            rows.extend(store.sample_atoms(limit=max(limit * 5, 120), category=category or None))
        finally:
            store.close()

    tokens = _seed_tokens(seed)

    def relevance(row: Any) -> int:
        blob = f"{row['quote']} {row['scene']} {row['cluster_label']} {row['category']}".lower()
        return sum(1 for token in tokens if token in blob)

    rows.sort(
        key=lambda r: (relevance(r), int(r["likes"] or 0), int(r["intensity"] or 0)),
        reverse=True,
    )
    if tokens:
        rows = [r for r in rows if relevance(r) > 0]

    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        quote = str(row["quote"] or "").strip()
        if not quote or quote in seen:
            continue
        seen.add(quote)
        evidence.append({
            "id": len(evidence) + 1,
            "quote": quote[:180],
            "likes": int(row["likes"] or 0),
            "scene": str(row["scene"] or ""),
            "level": str(row["level"] or ""),
            "cluster": str(row["cluster_label"] or ""),
            "persona": str(row["persona"] or ""),
        })
        if len(evidence) >= limit:
            break
    return evidence


def _session_path(session_id: str) -> Path:
    return SESSION_DIR / f"{session_id}.json"


def save_session(session: dict[str, Any]) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session["updated_at"] = time.time()
    _session_path(session["session_id"]).write_text(
        json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_session(session_id: str) -> dict[str, Any] | None:
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _probe(turn_index: int, seed: str = "") -> dict[str, Any]:
    label = f"「{seed}」" if seed else "这个方向"
    if turn_index <= 0:
        return {
            "kind": "direction",
            "question": "这三条里，哪一条最像你身边真实发生的事？",
            "why": "先确认方向，再往下挖",
            "chips": ["第一条", "第二条", "第三条", "都不是"],
        }
    if turn_index == 1:
        return {
            "kind": "counterfactual",
            "question": f"假设{label}这个痛点其实不成立——最可能的原因是什么？",
            "why": "先试着证伪，避免自嗨",
            "chips": ["他们其实能忍", "有免费替代", "不是高频问题", "我说不好"],
        }
    if turn_index == 2:
        return {
            "kind": "payment",
            "question": "如果现在收 ¥199/年，谁会第一个掏钱？这笔预算现在花在哪？",
            "why": "付费意愿比“觉得有用”更可靠",
            "chips": ["老板会买", "员工自费", "走公司报销", "没人会付"],
        }
    return {
        "kind": "substitute",
        "question": "他们现在用 Excel/微信群凑合，为什么不会一直凑合下去？",
        "why": "找出现有替代方案撑不住的那条缝",
        "chips": ["量大了会崩", "出错代价高", "老板开始盯", "监管要求"],
    }


def _fallback_directions(
    evidence: list[dict[str, Any]],
    seed: str = "",
    memory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not evidence:
        label = f"「{seed}」" if seed else "这个方向"
        return {
            "reflection": f"当前语料里没有搜到和{label}直接相关的评论。",
            "directions": [{
                "title": "先抓一批相关评论",
                "who": "你熟悉的行业人群",
                "pain": "没有证据时，任何方向都只是猜测",
                "wedge": f"用「抓取新商机」抓 20-50 条{label}相关评论，再回来探索",
                "why_now": "先把真实抱怨喂进来，比现在硬想更有效",
                "evidence_ids": [],
            }],
            "question": f"要不要先去抓一批{label}的评论？",
            "probe": {
                "kind": "fetch",
                "question": f"先去抓 20-50 条{label}评论，还是换个更大的关键词？",
                "why": "没有证据时先补数据",
                "chips": ["好，先去抓", "换个更大的关键词"],
            },
            "chips": ["好，先去抓", "换个更大的关键词", "用现有语料随便看看"],
        }
    memory = memory or []
    weakened = {str(m.get("title", "")) for m in memory if m.get("verdict") == "weakens" and m.get("title")}
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        key = item["cluster"] or item["scene"] or "未分类"
        groups.setdefault(key, []).append(item)
    if weakened and len(groups) > 1:
        filtered = {
            k: v for k, v in groups.items()
            if not any(w in k or k in w for w in weakened)
        }
        if filtered:
            groups = filtered
    ranked = sorted(
        groups.items(),
        key=lambda kv: max((x["likes"] for x in kv[1]), default=0),
        reverse=True,
    )[:3]

    directions = []
    for label, items in ranked:
        best = items[0]
        direction = {
            "title": (label or "一个具体场景")[:12],
            "who": best.get("persona") or "这个场景里的高频用户",
            "pain": best["quote"][:50],
            "wedge": f"把「{best['scene'] or label}」里反复出现的人工步骤做成一步式工具",
            "why_now": f"{len(items)} 条 L2+ 证据，最高赞 {best['likes']}",
            "evidence_ids": [x["id"] for x in items[:3]],
        }
        for memo in memory:
            if memo.get("title") and (memo["title"] in direction["title"] or direction["title"] in memo["title"]):
                direction["memory_note"] = "上次验证：" + (
                    "支持" if memo.get("verdict") == "supports" else
                    "削弱" if memo.get("verdict") == "weakens" else "样本不足"
                )
                break
        directions.append(direction)
    if not directions:
        directions = [{
            "title": "先找一个具体场景",
            "who": "你熟悉的一类人",
            "pain": "目前还没有足够评论证据，需要先抓一批",
            "wedge": "先用「抓取新商机」导入一个小红书/App Store 评论样本",
            "why_now": "没有证据时，任何方向都只是猜测",
            "evidence_ids": [],
        }]
    reflection = "我先从评论里挑了几条最高赞的抱怨；先不急着定产品，看哪条最像你身边真实发生的事。"
    if weakened:
        reflection = f"上次「{sorted(weakened)[0]}」被数据削弱过，这次我先避开它。" + reflection
    if seed:
        reflection = f"我先按「{seed}」筛了一遍评论，挑出这几条最相关的抱怨。"
    return {
        "reflection": reflection,
        "directions": directions,
        "question": "这三条里，哪一条你看完最有感觉？为什么？",
        "chips": [d["title"] for d in directions[:3]] + ["都不是，我说个别的"],
    }


def _coach_payload(session: dict[str, Any], user_message: str, reaction: dict[str, Any] | None) -> str:
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in session.get("messages", [])[-8:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    payload = {
        "seed": session.get("seed", ""),
        "mode": session.get("mode", "b2c"),
        "turn_index": sum(1 for m in session.get("messages", []) if m.get("role") == "assistant"),
        "memory": session.get("memory", []),
        "reactions": session.get("reactions", [])[-8:],
        "evidence": session.get("evidence", []),
        "user_message": user_message,
        "reaction": reaction,
        "history": history,
    }
    return json.dumps(payload, ensure_ascii=False)


def _attach_quotes(directions: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> None:
    by_id = {e["id"]: e for e in evidence}
    for direction in directions:
        quotes = []
        for eid in direction.get("evidence_ids", [])[:3]:
            item = by_id.get(int(eid)) if str(eid).isdigit() else None
            if item:
                quotes.append({"quote": item["quote"], "likes": item["likes"], "id": item["id"]})
        direction["evidence"] = quotes


def _round(session: dict[str, Any], user_message: str = "", reaction: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    if session.get("evidence"):
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": _coach_payload(session, user_message, reaction)},
        ]
        data = _llm(messages)
    if not isinstance(data, dict) or not isinstance(data.get("directions"), list) or not data["directions"]:
        data = _fallback_directions(
            session.get("evidence", []),
            session.get("seed", ""),
            session.get("memory", []),
        )

    directions = data.get("directions", [])[:3]
    for direction in directions:
        direction.setdefault("evidence_ids", [])
        direction.setdefault("evidence", [])
    _attach_quotes(directions, session.get("evidence", []))
    for direction in directions:
        for memo in session.get("memory", []):
            if memo.get("title") and (memo["title"] in direction.get("title", "") or direction.get("title", "") in memo["title"]):
                direction["memory_note"] = "上次验证：" + (
                    "支持" if memo.get("verdict") == "supports" else
                    "削弱" if memo.get("verdict") == "weakens" else "样本不足"
                )
                break

    turn_index = sum(1 for m in session.get("messages", []) if m.get("role") == "assistant")
    probe = data.get("probe") if isinstance(data.get("probe"), dict) else None
    if not probe or not probe.get("question"):
        probe = _probe(turn_index, session.get("seed", ""))
    probe["chips"] = [str(c) for c in (probe.get("chips") or [])][:4]

    result = {
        "reflection": str(data.get("reflection") or "").strip(),
        "directions": directions,
        "question": str(data.get("question") or probe["question"]).strip(),
        "probe": probe,
        "chips": [str(c) for c in (data.get("chips") or [])][:4],
    }
    session.setdefault("messages", []).append({
        "role": "assistant",
        "content": f"{result['reflection']}\n\n{result['question']}".strip(),
        "directions": directions,
        "chips": result["chips"],
        "probe": result["probe"],
        "ts": time.time(),
    })
    save_session(session)
    return result


def start_session(
    db_paths: list[str],
    seed: str = "",
    mode: str = "b2c",
    category: str | None = None,
) -> dict[str, Any]:
    evidence = collect_evidence(db_paths, category=category, seed=seed)
    session = {
        "session_id": uuid.uuid4().hex[:12],
        "seed": seed.strip(),
        "mode": mode if mode in ("b2c", "b2b") else "b2c",
        "category": category or "",
        "evidence": evidence,
        "memory": relevant_memory(seed),
        "messages": [{
            "role": "user",
            "content": seed.strip() or "我还没有明确方向，想从评论里找找看。",
            "ts": time.time(),
        }],
        "reactions": [],
        "created_at": time.time(),
    }
    round_data = _round(session)
    return {**session, **round_data}


def add_turn(
    session_id: str,
    message: str = "",
    reaction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session = load_session(session_id)
    if session is None:
        raise KeyError("unknown session")
    if message.strip():
        last_probe = None
        for msg in reversed(session.get("messages", [])):
            if msg.get("role") == "assistant" and msg.get("probe"):
                last_probe = msg["probe"]
                break
        if last_probe and last_probe.get("kind") == "payment":
            remember_payment(session, message.strip())
        session["messages"].append({"role": "user", "content": message.strip(), "ts": time.time()})
    if reaction:
        session.setdefault("reactions", []).append({**reaction, "ts": time.time()})
    round_data = _round(session, message.strip(), reaction)
    return {**session, **round_data}


def converge(session_id: str) -> dict[str, Any]:
    session = load_session(session_id)
    if session is None:
        raise KeyError("unknown session")
    evidence = session.get("evidence", [])
    by_id = {e["id"]: e for e in evidence}
    last_directions = []
    for msg in reversed(session.get("messages", [])):
        if msg.get("role") == "assistant" and msg.get("directions"):
            last_directions = msg["directions"]
            break
    chosen = last_directions[0] if last_directions else {}

    quotes = []
    for eid in chosen.get("evidence_ids", [])[:3]:
        item = by_id.get(int(eid)) if str(eid).isdigit() else None
        if item:
            quotes.append(item)

    if not quotes:
        quotes = evidence[:3]

    lines = [
        f"# 探索结论：{session.get('seed') or '未命名方向'}",
        "",
        f"**方向**：{chosen.get('title', '待定')}",
        f"**人群**：{chosen.get('who', '待定')}",
        f"**痛点**：{chosen.get('pain', '待定')}",
        f"**最小切口**：{chosen.get('wedge', '待定')}",
        "",
        "## 评论证据",
    ]
    for item in quotes:
        lines.append(f"- “{item['quote']}” （👍 {item['likes']}）")
    lines += [
        "",
        "## 历史验证记忆",
        *([f"- 上次「{m.get('title')}」：{m.get('verdict')} — {m.get('summary')}" for m in session.get("memory", [])[:3]] or ["- 暂无"]),
        "",
        "## 付费假设（需要当面验证）",
        f"- 目标买家是否愿意为「{chosen.get('title', '这个方向')}」支付 ¥199–999/年？",
        "- 不要只问“愿不愿意”，要问“这笔钱现在从哪个预算出、谁签字”。",
        "",
        "## 下一步验证（7 天）",
        "1. 找 3 个符合“人群”描述的人聊 15 分钟，确认这个阻碍真实存在。",
        "2. 用落地页/演示视频描述“最小切口”，看是否有人愿意留联系方式。",
        "3. 若 3 人里至少 2 人主动追问价格或试用，再进入 MVP。",
        "",
        "> 这是探索阶段的假设，不是已验证的市场结论。",
    ]
    markdown = "\n".join(lines)
    session["conclusion"] = markdown
    save_session(session)
    return {"session_id": session_id, "markdown": markdown, "chosen": chosen}

def record_validation(
    session_id: str,
    category: str,
    category_name: str,
    platform: str,
    keywords: list[str],
    job_id: str,
) -> dict[str, Any]:
    session = load_session(session_id)
    if session is None:
        raise KeyError("unknown session")
    session["validation"] = {
        "category": category,
        "category_name": category_name,
        "platform": platform,
        "keywords": keywords,
        "job_id": job_id,
        "started_at": time.time(),
    }
    save_session(session)
    return session


def _verdict(metrics: dict[str, Any]) -> str:
    atoms = int(metrics.get("atoms") or 0)
    share = float(metrics.get("l2_share") or 0.0)
    if atoms >= 8 and share >= 0.30:
        return "supports"
    if atoms >= 5 and share < 0.20:
        return "weakens"
    return "insufficient"


def reflect_validation(session_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
    session = load_session(session_id)
    if session is None:
        raise KeyError("unknown session")

    last_directions = []
    for msg in reversed(session.get("messages", [])):
        if msg.get("role") == "assistant" and msg.get("directions"):
            last_directions = msg["directions"]
            break
    direction = last_directions[0] if last_directions else {}
    verdict = _verdict(metrics)

    summary = ""
    next_question = ""
    if verdict == "supports":
        summary = (
            f"新抓到的 {metrics.get('atoms')} 条里，L2+ 占 {round(float(metrics.get('l2_share') or 0) * 100)}%，"
            f"且出现了「{(metrics.get('clusters') or [{}])[0].get('label', '相关场景')}」这样的聚集。"
            "这次验证支持你的假设。"
        )
        next_question = "信号够强了：你愿意先找 3 个这样的人聊，还是先做落地页？"
    elif verdict == "weakens":
        summary = (
            f"新抓到的 {metrics.get('atoms')} 条里，L2+ 只有 {round(float(metrics.get('l2_share') or 0) * 100)}%，"
            "大部分是泛泛抱怨，缺少具体代价/绕行。这次验证削弱了这个方向。"
        )
        next_question = "要不要换一个方向，或者把关键词收窄到更具体的场景？"
    else:
        summary = (
            f"这次只拿到 {metrics.get('atoms')} 条有效原子，样本太少，"
            "既不能支持也不能否定。"
        )
        next_question = "先扩大关键词或换平台再抓一轮，还是先聊几个真人？"

    data = None
    if session.get("evidence") or metrics.get("quotes"):
        messages = [
            {"role": "system", "content": (
                "你在评审一次产品假设验证。根据新抓取的数据判断假设："
                "supports/weakens/insufficient，必须引用数字或原话，给一个下一步问题。"
                "返回 JSON，字段为 verdict、summary、next_question。"
            )},
            {"role": "user", "content": json.dumps({
                "direction": direction,
                "seed": session.get("seed"),
                "metrics": metrics,
            }, ensure_ascii=False)},
        ]
        data = _llm(messages, temperature=0.3)
    if isinstance(data, dict) and data.get("verdict") in ("supports", "weakens", "insufficient"):
        verdict = data["verdict"]
        summary = str(data.get("summary") or summary)
        next_question = str(data.get("next_question") or next_question)

    result = {
        "verdict": verdict,
        "summary": summary,
        "next_question": next_question,
        "metrics": metrics,
        "direction": direction.get("title", ""),
    }
    session["validation_result"] = result
    remember_validation(session, result)
    session.setdefault("messages", []).append({
        "role": "assistant",
        "content": f"验证结果：{summary}\n\n{next_question}",
        "validation": result,
        "ts": time.time(),
    })
    save_session(session)
    return result

