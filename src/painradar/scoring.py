"""Scoring and market estimation.

PainScore is a weighted sum of five observable factors; OpportunityScore is a
weighted *geometric* mean so that a zero on any one dimension cannot be
compensated by strength elsewhere (plan §4.5). Every score ships with its
factor decomposition, and every market number is a P10/P50/P90 range with
graded assumptions and a sensitivity ranking — never a point estimate.
"""

from __future__ import annotations

import math
from datetime import datetime
from statistics import mean

from .config import CategorySpec, GRADE_LABEL, MarketSpec
from .schema import MarketEstimate, PainAtom, Score

PAIN_WEIGHTS = {
    "frequency": 0.30,
    "breadth": 0.25,
    "intensity": 0.20,
    "cost_clarity": 0.15,
    "persistence": 0.10,
}
OPP_WEIGHTS = {
    "pain": 0.30,
    "supply_gap": 0.20,
    "wtp": 0.20,
    "serviceability": 0.15,
    "timing": 0.15,
}
COMPETITION_EXP = 0.10


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def _clamp(x: float, lo: float = 0.02, hi: float = 0.99) -> float:
    return max(lo, min(hi, x))


def score_clusters(
    atoms_by_cluster: dict[str, list[PainAtom]],
    authors_by_atom: dict[str, str],
    dates_by_atom: dict[str, str] | None = None,
) -> list[Score]:
    """Compute pain and opportunity scores for every non-noise cluster."""
    dates_by_atom = dates_by_atom or {}
    raw: dict[str, dict[str, float]] = {}

    for cid, atoms in atoms_by_cluster.items():
        if cid == "noise" or not atoms:
            continue
        n = len(atoms)
        authors = {authors_by_atom.get(a.atom_id, "") for a in atoms}

        # Persistence: date span of the underlying comments, capped at 90 days.
        span_days = 0.0
        parsed = [d for d in (_parse_date(dates_by_atom.get(a.atom_id, "")) for a in atoms) if d]
        if len(parsed) >= 2:
            span_days = (max(parsed) - min(parsed)).days

        raw[cid] = {
            "frequency": math.log1p(n),
            "breadth": len({a for a in authors if a}) / n,
            "intensity": mean(a.intensity for a in atoms) / 5.0,
            "cost_clarity": sum(1 for a in atoms if a.cost_type in ("money", "time")) / n,
            "persistence": min(1.0, span_days / 90.0),
            "wtp": (
                sum(2 for a in atoms if a.wtp_level == "strong")
                + sum(1 for a in atoms if a.wtp_level == "weak")
            )
            / (2 * n),
            "wtp_observed": sum(
                1 for a in atoms if a.wtp_level != "none" or a.level in ("L3", "L4")
            )
            / n,
            "workaround": sum(1 for a in atoms if a.workaround) / n,
            "action": sum(1 for a in atoms if a.level in ("L3", "L4")) / n,
        }

    if not raw:
        return []

    max_freq = max(v["frequency"] for v in raw.values()) or 1.0
    max_breadth = max(v["breadth"] for v in raw.values()) or 1.0

    scores: list[Score] = []
    for cid, v in raw.items():
        factors = {
            "frequency": v["frequency"] / max_freq,
            "breadth": v["breadth"] / max_breadth,
            "intensity": v["intensity"],
            "cost_clarity": v["cost_clarity"],
            "persistence": v["persistence"],
        }
        pain = 100.0 * sum(PAIN_WEIGHTS[k] * factors[k] for k in PAIN_WEIGHTS)

        # Supply gap: heavy workaround use plus L3/L4 activity means the market
        # is patching around an unmet need. Illustrative heuristic until the
        # competitor-anchor connector lands (M2).
        supply_gap = _clamp(0.35 + 0.45 * v["workaround"] + 0.20 * v["action"])
        # Willingness to pay: explicit "would pay" signals plus the revealed
        # preference of people already buying/replacing (L3/L4). When almost no
        # atom carries a signal we shrink toward a neutral prior instead of
        # treating "no evidence" as "evidence of no demand".
        raw_wtp = 0.55 * v["wtp"] + 0.45 * v["action"]
        coverage = v["wtp_observed"]
        wtp = _clamp(0.5 + (raw_wtp - 0.5) * min(1.0, coverage * 2.0))
        serviceability = 0.70  # default assumption, grade D
        timing = 0.65  # default assumption, grade D
        competition = 0.60  # default assumption, grade D

        opp = 100.0 * (
            (_clamp(pain / 100.0) ** OPP_WEIGHTS["pain"])
            * (supply_gap ** OPP_WEIGHTS["supply_gap"])
            * (wtp ** OPP_WEIGHTS["wtp"])
            * (serviceability ** OPP_WEIGHTS["serviceability"])
            * (timing ** OPP_WEIGHTS["timing"])
        ) / (competition ** COMPETITION_EXP)

        factors_out = {
            **{k: round(factors[k], 4) for k in PAIN_WEIGHTS},
            "supply_gap": round(supply_gap, 4),
            "wtp": round(wtp, 4),
            "wtp_coverage": round(coverage, 4),
            "serviceability": serviceability,
            "timing": timing,
            "competition": competition,
        }
        contributions = {
            **{k: round(PAIN_WEIGHTS[k] * factors[k] * 100, 2) for k in PAIN_WEIGHTS},
            "supply_gap": round(OPP_WEIGHTS["supply_gap"] * supply_gap * 100, 2),
            "wtp": round(OPP_WEIGHTS["wtp"] * wtp * 100, 2),
        }
        tier = "强" if opp >= 60 else ("中" if opp >= 42 else "弱")
        scores.append(
            Score(
                cluster_id=cid,
                pain=pain,
                opportunity=opp,
                tier=tier,
                factors=factors_out,
                contributions=contributions,
            )
        )

    scores.sort(key=lambda s: s.opportunity, reverse=True)
    return scores


# ---------------------------------------------------------------------------
# Market estimation


def _triple_product(spec: MarketSpec, pick: str) -> float:
    def v(t) -> float:
        return getattr(t, pick)

    return (
        v(spec.population)
        * v(spec.penetration)
        * v(spec.reachability)
        * v(spec.conversion)
        * v(spec.arpu)
    )


def estimate_market(spec: MarketSpec, category: CategorySpec) -> MarketEstimate:
    """Monte-Carlo the bottom-up product of five triangular assumptions.

    Multiplying the low of every assumption at once produces a fantasy range
    (two orders of magnitude wide). Sampling the joint distribution and taking
    P10/P50/P90 gives a band that a human can actually argue with.
    """
    import random

    rng = random.Random(42)
    samples: list[float] = []
    for _ in range(20_000):
        samples.append(
            rng.triangular(spec.population.low, spec.population.high, spec.population.mid)
            * rng.triangular(spec.penetration.low, spec.penetration.high, spec.penetration.mid)
            * rng.triangular(spec.reachability.low, spec.reachability.high, spec.reachability.mid)
            * rng.triangular(spec.conversion.low, spec.conversion.high, spec.conversion.mid)
            * rng.triangular(spec.arpu.low, spec.arpu.high, spec.arpu.mid)
        )
    samples.sort()
    n = len(samples)
    low = samples[int(0.10 * n)]
    mid = samples[int(0.50 * n)]
    high = samples[int(0.90 * n)]

    assumptions = [
        {"name": "目标人群规模", "key": "population", "low": spec.population.low, "mid": spec.population.mid, "high": spec.population.high, "grade": "C", "note": "待替换为 A 级统计"},
        {"name": "痛点渗透率", "key": "penetration", "low": spec.penetration.low, "mid": spec.penetration.mid, "high": spec.penetration.high, "grade": "D", "note": "待用评论渗透率与访谈校准"},
        {"name": "可触达率", "key": "reachability", "low": spec.reachability.low, "mid": spec.reachability.mid, "high": spec.reachability.high, "grade": "D", "note": "渠道覆盖假设"},
        {"name": "年购买转化率", "key": "conversion", "low": spec.conversion.low, "mid": spec.conversion.mid, "high": spec.conversion.high, "grade": "D", "note": "待用类比产品校准"},
        {"name": "客单价", "key": "arpu", "low": spec.arpu.low, "mid": spec.arpu.mid, "high": spec.arpu.high, "grade": "C", "note": "竞品定价页"},
    ]

    sensitivity = []
    for a in assumptions:
        key = a["key"]
        base = getattr(spec, key)
        lo_spec = MarketSpec(**{**spec.__dict__, key: type(base)(base.low, base.low, base.low)})
        hi_spec = MarketSpec(**{**spec.__dict__, key: type(base)(base.high, base.high, base.high)})
        lo_val = _triple_product(lo_spec, "mid")
        hi_val = _triple_product(hi_spec, "mid")
        sensitivity.append(
            {
                "name": a["name"],
                "delta": round(hi_val - lo_val, 2),
                "low_effect": round(lo_val, 2),
                "high_effect": round(hi_val, 2),
            }
        )
    sensitivity.sort(key=lambda x: abs(x["delta"]), reverse=True)

    falsifier = (
        f"若 12 个月内该品类实际年购买转化率低于 {spec.conversion.mid * 0.5:.1%}"
        f"（当前中值 {spec.conversion.mid:.1%}），或客单价低于 {spec.arpu.mid * 0.6:.0f}"
        f"（当前中值 {spec.arpu.mid:.0f}），则本区间作废，需重新采集证据。"
    )

    return MarketEstimate(
        low=low,
        mid=mid,
        high=high,
        currency=spec.currency,
        assumptions=[{**a, "grade_label": GRADE_LABEL[a["grade"]]} for a in assumptions],
        sensitivity=sensitivity,
        falsifier=falsifier + f"（{category.name}）",
    )


# ---------------------------------------------------------------------------
# Solo-developer feasibility (task 3)

_HARDWARE_WORDS = ("硬件", "门锁", "传感器", "电池", "供应链", "安装", "摄像头", "材料", "涂层", "设备")
_OPS_WORDS = ("客服", "人工", "审核", "运营", "售后", "培训", "代做", "服务", "交付")


def assess_solo_fit(atoms: list[PainAtom]) -> dict:
    """Can one developer ship an MVP fast, and in what form?"""
    text = " ".join(
        f"{a.canonical_pain} {a.obstacle} {a.job} {a.workaround}" for a in atoms
    )
    heavy = any(w in text for w in _HARDWARE_WORDS)
    ops = any(w in text for w in _OPS_WORDS)
    if heavy:
        return {
            "level": "高",
            "mvp_days": "1 月+",
            "form": "硬件 + App（不建议 solo）",
            "monetization": "买断",
            "score": 0.2,
            "note": "涉及硬件/供应链/现场安装，一人难以闭环",
        }
    if ops:
        return {
            "level": "中",
            "mvp_days": "2–4 周",
            "form": "轻量 SaaS / 小程序",
            "monetization": "订阅",
            "score": 0.5,
            "note": "含人工运营或服务交付，需控制支持成本",
        }
    form = "轻量 App"
    if any(w in text for w in ("浏览器", "网页", "插件", "Chrome")):
        form = "浏览器插件"
    elif any(w in text for w in ("微信", "小程序", "移动端", "iPhone", "安卓")):
        form = "小程序"
    elif any(w in text for w in ("脚本", "命令行", "批量", "自动化")):
        form = "脚本 / CLI"
    return {
        "level": "低",
        "mvp_days": "3–10 天",
        "form": form,
        "monetization": "买断",
        "score": 0.9,
        "note": "纯软件、无供应链，适合先做最小闭环",
    }
