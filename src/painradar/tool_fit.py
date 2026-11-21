"""Match a concrete tool's capabilities against discovered demands.

Different question from solo-fit: not "can one person build a business here",
but "does *this* tool solve *that* pain, legally and for the users it supports".
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .net import HttpClient

MATCH_SYSTEM = """你是产品顾问。给定一个已经做出来的工具，和一条用户痛点，
判断"这个工具能不能解决这条痛点"。

七个维度，各 1-5：

1. capability_match：工具的能力能否直接消除这条痛点里的障碍？
   直接解决 5；只能部分缓解 3；无关 1。
2. coverage：这条痛点涉及的场景里，工具有能力处理的比例有多少？大多数 5，少数 1-2。
3. rights_ok：用户用这个工具做这件事，是否合法/符合平台条款？
   完全合法 5；灰区 3；明显侵权或违反条款 1-2。
4. buyer_reachable：这类用户能否在公开社区/市场被触达？
5. wtp：这类用户为工具付费的意愿。
6. competition：竞争空隙（已有免费/成熟工具 → 1-2）。
7. device_fit：工具支持的设备/系统与目标用户是否匹配？
   完全匹配 5；一半用户用不了 2-3；完全不支持 1。

另外给出：
- verdict: "full"（能解决）/ "partial"（部分）/ "no"（不能）
- gap: 工具要补什么才能解决（没有就空字符串）

返回 JSON：{"scores": {"capability_match": 5, "coverage": 4, "rights_ok": 5,
"buyer_reachable": 4, "wtp": 4, "competition": 3, "device_fit": 3},
"reasons": {"capability_match": "...", "coverage": "...", "rights_ok": "...",
"buyer_reachable": "...", "wtp": "...", "competition": "...", "device_fit": "..."},
"verdict": "full", "gap": "..."}"""

WEIGHTS = {
    "capability_match": 0.30,
    "coverage": 0.15,
    "rights_ok": 0.20,
    "buyer_reachable": 0.10,
    "wtp": 0.10,
    "competition": 0.10,
    "device_fit": 0.05,
}


@dataclass
class MatchResult:
    scores: dict[str, int] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    verdict: str = "no"
    gap: str = ""
    total: int = 0

    def as_dict(self) -> dict:
        return {
            "scores": self.scores,
            "reasons": self.reasons,
            "verdict": self.verdict,
            "gap": self.gap,
            "total": self.total,
            "weights": WEIGHTS,
        }


def _total(scores: dict[str, int]) -> int:
    raw = sum(WEIGHTS[k] * scores.get(k, 1) for k in WEIGHTS)
    return int(round((raw - 1) / 4 * 100))


def _parse(payload: dict) -> MatchResult | None:
    scores = payload.get("scores") or {}
    if not all(k in scores for k in WEIGHTS):
        return None
    clean = {}
    for k in WEIGHTS:
        try:
            v = int(scores[k])
        except (TypeError, ValueError):
            return None
        clean[k] = max(1, min(5, v))
    verdict = str(payload.get("verdict") or "no")
    if verdict not in ("full", "partial", "no"):
        verdict = "no"
    return MatchResult(
        scores=clean,
        reasons={k: str(v) for k, v in (payload.get("reasons") or {}).items()},
        verdict=verdict,
        gap=str(payload.get("gap") or ""),
        total=_total(clean),
    )


class ToolMatcher:
    def __init__(
        self,
        tool: dict,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        cache_path: Path | None = None,
    ) -> None:
        self.tool = tool
        self.model = model or os.environ.get("PAINRADAR_LLM_MODEL", "deepseek-chat")
        self.base_url = (base_url or os.environ.get("PAINRADAR_LLM_BASE_URL", "https://api.deepseek.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("PAINRADAR_LLM_API_KEY", "")
        self.client = HttpClient(user_agent="PainRadar/0.1", timeout=90, max_retries=1, rate_per_sec=0.5)
        self.cache_path = cache_path
        self.cache: dict = {}
        if cache_path and cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except ValueError:
                self.cache = {}

    def _key(self, demand: dict) -> str:
        blob = json.dumps(
            {
                "tool": self.tool.get("name"),
                "demand": demand.get("label"),
                "definition": demand.get("definition"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(("match-v1|" + blob).encode()).hexdigest()[:16]

    def match(self, demand: dict) -> MatchResult:
        key = self._key(demand)
        cached = self.cache.get(key)
        if cached:
            parsed = _parse(cached)
            if parsed:
                return parsed

        payload = {
            "tool": self.tool,
            "demand": demand.get("label"),
            "definition": demand.get("definition"),
            "domains": list((demand.get("domains") or {}).keys()),
            "buyers": demand.get("buyer_by_domain") or {},
            "quotes": [e.get("quote") for e in (demand.get("examples") or [])[:4]],
        }
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": MATCH_SYSTEM},
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
            raw = json.loads(content[content.find("{"): content.rfind("}") + 1])
        except Exception:  # noqa: BLE001
            raw = {}

        parsed = _parse(raw)
        if parsed is None:
            parsed = MatchResult(
                scores={k: 1 for k in WEIGHTS},
                reasons={k: "匹配失败" for k in WEIGHTS},
                verdict="no",
                gap="LLM 不可用",
                total=0,
            )
        elif self.cache_path:
            self.cache[key] = raw
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return parsed
