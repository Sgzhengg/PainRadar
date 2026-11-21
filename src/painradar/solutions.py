"""Turn a discovered demand into concrete solution concepts.

The point is not to brainstorm freely: every solution must name the mechanism
that removes the *observed* obstacle, the buyer segment it serves, an MVP scope,
a price hypothesis, and a falsifiable 7-day validation. Generic advice
("improve UX") is rejected by the schema.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .net import HttpClient

SOLVE_SYSTEM = """你是产品负责人，为一个已被证据验证的需求设计 3 个**可落地**的解决方案。

输入会给你：需求、定义、分数、证据量、来源域、分域买家、若干原文证据。

每个方案必须：
1. 针对证据里出现的**具体障碍**，不是泛泛的"优化体验"；
   并在 evidence_index 里写出它对应第几条证据（从 0 开始）；
2. 说清谁来买；why_now 只能引用给定的趋势数据或证据，**不要编造发布会、销量、市场规模**；
3. 给出 2 周内能做完的 MVP（3-5 条，具体到功能）；
4. 给出价格假设（一次性/订阅，具体数字）；
5. 给出 7 天可验证的实验（假设、动作、阈值、时长）；
   价格一律用 {{CURRENCY}} 计价，写具体数字；
   buyer 必须直接取自输入的 buyers 值，**不要新增设备型号或人群**；正文不要编造具体产品名、销量或融资；
6. 写清最大风险，以及"现有玩家为什么不做"。

禁止：空话、无法验证的承诺、需要自建硬件的重方案（除非证据强烈支持）。

返回 JSON：
{"solutions": [
  {"name": "不超过 10 字",
   "evidence_index": 0,
   "pitch": "一句话卖点",
   "mechanism": "它如何消除障碍（对应哪条证据）",
   "buyer": "具体买家",
   "mvp": ["...", "..."],
   "pricing": "一次性 ¥X / 订阅 ¥X/月",
   "price_band": "低/中/高",
   "why_now": "为什么现在",
   "risks": ["...", "..."],
   "validation": {"hypothesis": "...", "experiment": "...", "threshold": "...", "duration": "7 天"},
   "feasibility": 1
  }
]}
feasibility 是 1-5（5 = 两周能上线）。"""

RANK_SYSTEM = """你是独立开发者，只能先做一件事。给定一条需求和 3 个候选方案，
请按"两周内最可能验证出付费意愿"排序。

考虑：证据匹配度、实现难度、买家是否够得着、定价是否容易验证。
返回 JSON：{"ranking": [{"name": "方案名", "rank": 1, "reason": "不超过 40 字"}]}
rank 从 1 开始，覆盖全部方案，不要新增方案。"""


@dataclass
class Solution:
    name: str
    pitch: str
    mechanism: str
    buyer: str
    mvp: list[str] = field(default_factory=list)
    pricing: str = ""
    price_band: str = ""
    why_now: str = ""
    risks: list[str] = field(default_factory=list)
    validation: dict = field(default_factory=dict)
    feasibility: int = 3
    evidence_index: int | None = None

    def valid(self, quote_count: int = 0) -> bool:
        v = self.validation
        if quote_count and (self.evidence_index is None or not (0 <= self.evidence_index < quote_count)):
            return False
        return bool(
            self.name
            and self.pitch
            and self.mechanism
            and self.mvp
            and self.pricing
            and v.get("hypothesis")
            and v.get("experiment")
            and v.get("threshold")
        )


def _parse(payload: dict, quote_count: int = 0) -> list[Solution]:
    out: list[Solution] = []
    for raw in payload.get("solutions", []) if isinstance(payload, dict) else []:
        try:
            sol = Solution(
                name=str(raw.get("name", "")).strip(),
                pitch=str(raw.get("pitch", "")).strip(),
                mechanism=str(raw.get("mechanism", "")).strip(),
                buyer=str(raw.get("buyer", "")).strip(),
                mvp=[str(x).strip() for x in (raw.get("mvp") or []) if str(x).strip()],
                pricing=str(raw.get("pricing", "")).strip(),
                price_band=str(raw.get("price_band", "")).strip(),
                why_now=str(raw.get("why_now", "")).strip(),
                risks=[str(x).strip() for x in (raw.get("risks") or []) if str(x).strip()],
                validation=raw.get("validation") or {},
                feasibility=int(raw.get("feasibility") or 3),
                evidence_index=raw.get("evidence_index"),
            )
        except (TypeError, ValueError):
            continue
        if sol.valid(quote_count):
            out.append(sol)
    return out


class SolutionGenerator:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        cache_path: Path | None = None,
        currency: str = "USD",
    ) -> None:
        self.model = model or os.environ.get("PAINRADAR_LLM_MODEL", "deepseek-chat")
        self.base_url = (base_url or os.environ.get("PAINRADAR_LLM_BASE_URL", "https://api.deepseek.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("PAINRADAR_LLM_API_KEY", "")
        self.client = HttpClient(user_agent="PainRadar/0.1", timeout=120, max_retries=1, rate_per_sec=0.5)
        self.currency = currency.upper()
        self.cache_path = cache_path
        self.cache: dict = {}
        if cache_path and cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except ValueError:
                self.cache = {}

    def _key(self, demand: dict) -> str:
        blob = json.dumps(
            {k: demand.get(k) for k in ("label", "definition", "size", "score")},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256((f"solve-v4|{self.currency}|" + blob).encode()).hexdigest()[:16]

    def _call(self, payload: dict) -> dict:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SOLVE_SYSTEM.replace("{{CURRENCY}}", self.currency)},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        try:
            resp = self.client.post_json(
                f"{self.base_url}/chat/completions",
                body,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
            content = resp["choices"][0]["message"]["content"]  # type: ignore[index]
            return json.loads(content[content.find("{"): content.rfind("}") + 1])
        except Exception:  # noqa: BLE001
            return {}

    def for_demand(self, demand: dict) -> list[Solution]:
        key = self._key(demand)
        quotes = [e.get("quote") for e in (demand.get("examples") or [])[:5]]
        cached = self.cache.get(key)
        if cached:
            return _parse(cached, len(quotes))
        payload = {
            "demand": demand.get("label"),
            "definition": demand.get("definition"),
            "score": demand.get("score"),
            "evidence_size": demand.get("size"),
            "domains": list((demand.get("domains") or {}).keys()),
            "buyers": demand.get("buyer_by_domain") or {},
            "currency": self.currency,
            "quotes": quotes,
            "levels": [e.get("level") for e in (demand.get("examples") or [])[:5]],
        }
        raw = self._call(payload)
        solutions = _parse(raw, len(quotes))
        if solutions and self.cache_path:
            self.cache[key] = raw
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return solutions

    def rank(self, demand: dict, solutions: list[Solution]) -> dict:
        """Return {"name": ..., "reason": ..., "ranking": [...]} using one LLM call."""
        names = [s.name for s in solutions]
        key = self._key(demand) + ":rank:" + "|".join(names)
        cached = self.cache.get(key)
        if cached and cached.get("ranking"):
            return cached
        payload = {
            "demand": demand.get("label"),
            "definition": demand.get("definition"),
            "buyers": demand.get("buyer_by_domain") or {},
            "solutions": [
                {
                    "name": s.name,
                    "mechanism": s.mechanism,
                    "pricing": s.pricing,
                    "feasibility": s.feasibility,
                    "mvp": s.mvp,
                    "risks": s.risks,
                }
                for s in solutions
            ],
        }
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": RANK_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        result: dict = {}
        try:
            resp = self.client.post_json(
                f"{self.base_url}/chat/completions",
                body,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
            content = resp["choices"][0]["message"]["content"]  # type: ignore[index]
            parsed = json.loads(content[content.find("{"): content.rfind("}") + 1])
            ranking = [r for r in (parsed.get("ranking") or []) if r.get("name") in names]
            ranking.sort(key=lambda r: int(r.get("rank") or 99))
            if ranking:
                result = {
                    "name": ranking[0]["name"],
                    "reason": ranking[0].get("reason", ""),
                    "ranking": ranking,
                }
        except Exception:  # noqa: BLE001
            result = {}

        if not result:  # deterministic fallback: highest feasibility, then fewer MVP items
            ordered = sorted(solutions, key=lambda s: (-s.feasibility, len(s.mvp)))
            result = {
                "name": ordered[0].name,
                "reason": "回退规则：可行性最高、MVP 最少（LLM 排序不可用）",
                "ranking": [
                    {"name": s.name, "rank": i, "reason": ""} for i, s in enumerate(ordered, 1)
                ],
            }

        if self.cache_path:
            self.cache[key] = result
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return result


def render_markdown(demand: dict, solutions: list[Solution], recommended: dict | None = None) -> str:
    lines = [
        f"# 解决方案：{demand.get('label')}",
        "",
        f"> 需求分数 {demand.get('score')} ｜ 证据 {demand.get('size')} 条 ｜ "
        f"跨 {len(demand.get('domains') or {})} 个域 ｜ 定义：{demand.get('definition') or ''}",
        "",
        "| # | 方案 | 买家 | 价格假设 | 可行性 |",
        "|---|---|---|---|---|",
    ]
    for i, s in enumerate(solutions, 1):
        lines.append(f"| {i} | {s.name} | {s.buyer} | {s.pricing} | {s.feasibility}/5 |")
    if recommended:
        lines += ["", f"**建议先做**：{recommended.get('name')} —— {recommended.get('reason', '')}"]
    lines.append("")
    for i, s in enumerate(solutions, 1):
        lines += [
            f"## {i}. {s.name}",
            "",
            f"**一句话**：{s.pitch}",
            "",
            f"**机制**：{s.mechanism}",
            "",
            *(
                [f"> 对应证据：{demand['examples'][s.evidence_index].get('quote')}"]
                if s.evidence_index is not None
                and (demand.get("examples") or [])
                and 0 <= s.evidence_index < len(demand["examples"])
                else []
            ),
            "",
            f"**买家**：{s.buyer}　**定价**：{s.pricing}（{s.price_band}）",
            "",
            f"**为什么现在**：{s.why_now}",
            "",
            "**MVP（两周）**：",
            *[f"- {x}" for x in s.mvp],
            "",
            "**7 天验证**：",
            f"- 假设：{s.validation.get('hypothesis', '')}",
            f"- 实验：{s.validation.get('experiment', '')}",
            f"- 阈值：{s.validation.get('threshold', '')}",
            f"- 周期：{s.validation.get('duration', '7 天')}",
            "",
            "**风险**：",
            *[f"- {x}" for x in s.risks],
            "",
        ]
    return "\n".join(lines) + "\n"
