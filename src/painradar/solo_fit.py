"""Score demands on "can one person ship and support this".

Rubric mirrors the constraints of a solo, AI-assisted developer:

* third_party_actionable — can an independent product change the outcome at all?
* leverage               — does the product fix the problem, or only monitor it?
* competition_gap        — is the space already crowded by free/OS/giant tools?
* software_only          — no hardware/firmware/vendor access needed?
* zero_onboarding        — usable without setup calls?
* no_docs                — no customer knowledge base required?
* low_ops                — no 24/7 monitoring/SLA?
* frequency              — how often does one buyer hit this?
* self_serve_pay         — self-serve purchase (one-time or cheap sub)?

Each 1-5; weighted total 0-100. Justifications are required, results cached.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .net import HttpClient

RUBRIC_SYSTEM = """你是独立开发者的顾问。给一条需求打分：一个"单人 + AI 辅助"的软件开发者
能不能把它做成产品并长期维护。

九个维度，各 1-5（5 = 最适合单人）：

1. third_party_actionable：独立开发者能否做出产品来缓解或替代？
   根因在厂商自己的应用/固件/云里、第三方无法介入 → 1-2；
   第三方能做一个独立工具/服务/替代品 → 4-5。
2. leverage：产品能显著改变结果吗？
   只能"监控/提醒/展示" → 1-2；能真正消除障碍（替代、绕过、自动化） → 4-5。
3. competition_gap：竞争空隙。
   已有系统自带功能或成熟免费/巨头产品 → 1-2；现有方案明显不好用或没有 → 4-5。
4. software_only：技术上纯软件可解？需要硬件/固件/厂商配合 → 1-2。
5. zero_onboarding：陌生人装上就用？需要逐客户配置/培训 → 1-2。
6. no_docs：不依赖客户提供文档/知识库？需要建库喂资料 → 1-2。
7. low_ops：不需要 7×24 运维/SLA/电信资源？需要 → 1-2。
8. frequency：同一买家多久遇到一次？一年一次 2 分，每天 5 分。
9. self_serve_pay：能自助付费（买断或低价订阅）？只能靠销售/合同 → 1-2。

每个维度给一句理由（≤30 字），不要空泛；再给一句总评（≤40 字）。
返回 JSON：{"scores": {"third_party_actionable": 5, "leverage": 4, "competition_gap": 4,
"software_only": 4, "zero_onboarding": 5, "no_docs": 5, "low_ops": 5,
"frequency": 2, "self_serve_pay": 4},
"reasons": {"third_party_actionable": "...", "leverage": "...", "competition_gap": "...",
"software_only": "...", "zero_onboarding": "...", "no_docs": "...", "low_ops": "...",
"frequency": "...", "self_serve_pay": "..."},
"summary": "..."}"""

RUBRICS: dict[str, str] = {}
WEIGHTS_BY_PROFILE: dict[str, dict[str, float]] = {}


WEIGHTS = {
    "third_party_actionable": 0.20,
    "leverage": 0.15,
    "competition_gap": 0.15,
    "software_only": 0.10,
    "zero_onboarding": 0.10,
    "no_docs": 0.05,
    "low_ops": 0.10,
    "frequency": 0.05,
    "self_serve_pay": 0.10,
}


RUBRIC_B2B = """你是独立开发者的顾问。给一条 B 端需求打分：一个"单人 + AI 辅助"的软件开发者
能不能把它做成小企业愿意付费的产品。

九个维度，各 1-5（5 = 最适合单人做 B 端）：

1. third_party_actionable：独立开发者能否做出产品缓解或替代？根因在客户自有系统/厂商内部 → 1-2。
2. leverage：能真正消除障碍，还是只能监控/提醒？只能监控 → 1-2。
3. competition_gap：竞争空隙。已被巨头 SaaS 或系统自带占满 → 1-2。
4. software_only：纯软件可解？需要硬件/上门服务 → 1-2。
5. zero_onboarding：商家能否自己注册就用？需要实施/迁移顾问 → 1-2。
6. no_docs：不依赖商家提供文档/知识库？需要建库喂资料 → 1-2。
7. low_ops：不需要 7×24 运维/SLA → 1-2。
8. buyer_budget：买家是否已经在为软件付费（有预算习惯）？从没买过软件 → 1-2。
9. recurring_need：这个需求是否每月甚至每天出现（决定订阅能否续费）？一年一次 → 2。

每个维度一句理由（≤30 字），再给总评（≤40 字）。
返回 JSON：{"scores": {"third_party_actionable": 5, "leverage": 4, "competition_gap": 4,
"software_only": 5, "zero_onboarding": 5, "no_docs": 5, "low_ops": 5,
"buyer_budget": 5, "recurring_need": 4},
"reasons": {"third_party_actionable": "...", "leverage": "...", "competition_gap": "...",
"software_only": "...", "zero_onboarding": "...", "no_docs": "...", "low_ops": "...",
"buyer_budget": "...", "recurring_need": "..."},
"summary": "..."}"""

WEIGHTS_B2B = {
    "third_party_actionable": 0.20,
    "leverage": 0.15,
    "competition_gap": 0.10,
    "software_only": 0.10,
    "zero_onboarding": 0.10,
    "no_docs": 0.10,
    "low_ops": 0.10,
    "buyer_budget": 0.10,
    "recurring_need": 0.05,
}


RUBRIC_AI = """你是独立开发者的顾问，判断一条需求是否适合用"AI 原生工具"重做掉现有 SaaS。

十一个维度，各 1-5（5 = 最适合 AI 重耕）：

1. workflow_frequency：这个动作多久发生一次？每天 5、每月 3、一年一次 1。
2. incumbent_saas：是否已有明确收费的 SaaS 在做，且价格高/体验差？
3. ai_core：现有 SaaS 的核心价值是否主要是"文本/数据处理"（录入、分类、总结、核对）？
4. harness_resistance：通用 AI Harness（用户在对话框里丢文件、让 Agent 处理）
   能不能直接替代这个产品？
   如果用户把文件丢给 Agent 就能做完 → 1-2；
   如果需要持久状态、审计留痕、多用户协作、系统集成、责任承担 → 4-5。
5. incumbent_bundling：现有记账/ERP/报账系统是否已经把这件事内置了？
   已内置（如发票扫描、自动对账）→ 1-2；还没有 → 4-5。
6. third_party_actionable：独立开发者能否做出替代品而不被平台封堵？
7. data_portability：用户数据能否导出/重建（切换成本低）？
8. zero_onboarding：能否自助注册就用，不需要实施顾问？
9. low_ops：是否不需要 7×24 运维/SLA？
10. competition_gap：现有 AI 替代品是否还很少？
11. monetization：能否用"买断/低价订阅"替代原 SaaS 的高价订阅？

每个维度一句理由（≤30 字），再给总评（≤40 字）。
返回 JSON：{"scores": {"workflow_frequency": 5, "incumbent_saas": 5, "ai_core": 5,
"harness_resistance": 2, "incumbent_bundling": 2, "third_party_actionable": 4,
"data_portability": 4, "zero_onboarding": 5, "low_ops": 5, "competition_gap": 4,
"monetization": 4},
"reasons": {"workflow_frequency": "...", "incumbent_saas": "...", "ai_core": "...",
"harness_resistance": "...", "incumbent_bundling": "...", "third_party_actionable": "...",
"data_portability": "...", "zero_onboarding": "...", "low_ops": "...",
"competition_gap": "...", "monetization": "..."},
"summary": "..."}"""

WEIGHTS_AI = {
    "workflow_frequency": 0.10,
    "incumbent_saas": 0.10,
    "ai_core": 0.15,
    "harness_resistance": 0.20,
    "incumbent_bundling": 0.15,
    "third_party_actionable": 0.10,
    "data_portability": 0.05,
    "zero_onboarding": 0.05,
    "low_ops": 0.05,
    "competition_gap": 0.03,
    "monetization": 0.02,
}


@dataclass
class SoloFit:
    scores: dict[str, int] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    total: int = 0

    def as_dict(self) -> dict:
        return {
            "scores": self.scores,
            "reasons": self.reasons,
            "summary": self.summary,
            "total": self.total,
            "weights": WEIGHTS,
        }


def _total(scores: dict[str, int], weights: dict[str, float] | None = None) -> int:
    weights = weights or WEIGHTS
    raw = sum(weights[k] * scores.get(k, 1) for k in weights)
    return int(round((raw - 1) / 4 * 100))


def _parse(payload: dict, weights: dict[str, float] | None = None) -> SoloFit | None:
    weights = weights or WEIGHTS
    scores = payload.get("scores") or {}
    if not all(k in scores for k in weights):
        return None
    clean = {}
    for k in weights:
        try:
            v = int(scores[k])
        except (TypeError, ValueError):
            return None
        clean[k] = max(1, min(5, v))
    return SoloFit(
        scores=clean,
        reasons={k: str(v) for k, v in (payload.get("reasons") or {}).items()},
        summary=str(payload.get("summary") or ""),
        total=_total(clean, weights),
    )


class SoloFitScorer:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        cache_path: Path | None = None,
        profile: str = "consumer",
    ) -> None:
        self.profile = profile
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
            {k: demand.get(k) for k in ("label", "definition", "size", "score")},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256((f"solofit-v4|{self.profile}|" + blob).encode()).hexdigest()[:16]

    def score(self, demand: dict) -> SoloFit:
        key = self._key(demand)
        if key in self.cache:
            parsed = _parse(self.cache[key], WEIGHTS_BY_PROFILE.get(self.profile, WEIGHTS))
            if parsed:
                return parsed
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": RUBRICS.get(self.profile, RUBRIC_SYSTEM)},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "demand": demand.get("label"),
                            "definition": demand.get("definition"),
                            "evidence_size": demand.get("size"),
                            "domains": list((demand.get("domains") or {}).keys()),
                            "buyers": demand.get("buyer_by_domain") or {},
                            "quotes": [e.get("quote") for e in (demand.get("examples") or [])[:3]],
                        },
                        ensure_ascii=False,
                    ),
                },
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
        weights = WEIGHTS_BY_PROFILE.get(self.profile, WEIGHTS)
        parsed = _parse(raw, weights)
        if parsed is None:
            parsed = SoloFit(
                scores={k: 1 for k in weights},
                reasons={k: "评分失败" for k in weights},
                summary="LLM 评分不可用，按最低分处理",
                total=0,
            )
        else:
            if self.cache_path:
                self.cache[key] = raw
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return parsed


RUBRICS.update({"consumer": RUBRIC_SYSTEM, "b2b": RUBRIC_B2B, "ai_saas": RUBRIC_AI})
WEIGHTS_BY_PROFILE.update({"consumer": WEIGHTS, "b2b": WEIGHTS_B2B, "ai_saas": WEIGHTS_AI})
