"""Core domain objects.

Everything the pipeline derives is immutable: a new extraction produces a new
atom row with a fresh ``run_id`` and (when it replaces an earlier row) a
``supersedes`` pointer. That is what makes "replay any historical conclusion"
possible, and it is the reason the evidence ledger is append-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Tier(str, Enum):
    """Platform admission tier (plan §6.3).

    A: official API or written licence.
    B: anonymous public, low rate, robots-allowed, sunset clause applies.
    C: login wall / robots-disallowed / requires bypass — never ingested.
    """

    A = "A"
    B = "B"
    C = "C"


class Level(str, Enum):
    """Pain ladder (plan §4.1). Only L2+ reaches clusters, scores or cards."""

    L0 = "L0"  # pure emotion
    L1 = "L1"  # describes a phenomenon, no obstacle
    L2 = "L2"  # obstacle + workaround
    L3 = "L3"  # priced / compared / tried and failed
    L4 = "L4"  # already paid, or explicitly buying


class MatchScore(str, Enum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY = "fuzzy"


@dataclass(slots=True)
class RawItem:
    """One comment as delivered by a connector, before any processing."""

    platform: str
    item_id: str
    url: str
    text: str
    published_at: str
    category: str
    author: str = ""
    lang: str = ""
    rating: float | None = None
    tier: Tier = Tier.A
    tos_basis: str = "official_api"
    # thread context for LLM extraction; the quote is still gated on ``text``
    parent_context: str = ""
    # engagement, used for hotness ranking in the UI / outreach export
    likes: int = 0
    replies: int = 0
    post_id: str = ""


@dataclass(slots=True)
class PainAtom:
    """A structured pain unit extracted from one comment.

    ``quote`` is always a verbatim slice of the scrubbed comment text, located
    at ``span_start``/``span_end``. The span gate guarantees this before the
    atom is persisted; an atom without a valid span is dropped, never repaired.
    """

    atom_id: str
    comment_uid: str
    quote: str
    span_start: int
    span_end: int
    match_score: str
    scene: str
    trigger: str
    job: str
    obstacle: str
    workaround: str
    cost_type: str
    cost_estimate: str
    persona: str
    intensity: int
    expression: str
    level: str
    wtp_level: str
    wtp_quote: str
    domain: str
    confidence: float
    model_version: str
    prompt_version: str
    taxonomy_version: str
    run_id: str
    supersedes: str | None = None
    canonical_pain: str = ""
    buyer_role: str = ""  # 老板 / 管理者 / 员工 / 不确定（B 端模式）
    b2b_score: int = 0  # 0-3，决策者身份信号强度

    def signature(self) -> str:
        """Text used for clustering — slots, not the raw sentence."""
        return " | ".join(
            part for part in (self.scene, self.job, self.obstacle, self.workaround) if part
        )


@dataclass(slots=True)
class Cluster:
    cluster_id: str
    label: str
    members: list[str] = field(default_factory=list)
    medoid_atom_id: str = ""
    size: int = 0
    noise: bool = False
    solo_fit: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Score:
    """Scores plus the factor decomposition that produced them."""

    cluster_id: str
    pain: float
    opportunity: float
    tier: str
    factors: dict[str, float]
    contributions: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "pain": round(self.pain, 2),
            "opportunity": round(self.opportunity, 2),
            "tier": self.tier,
            "factors": {k: round(v, 4) for k, v in self.factors.items()},
            "contributions": {k: round(v, 4) for k, v in self.contributions.items()},
        }


@dataclass(slots=True)
class MarketEstimate:
    """Three-path market estimate expressed as a range, never a point."""

    low: float
    mid: float
    high: float
    currency: str
    assumptions: list[dict[str, Any]]
    sensitivity: list[dict[str, Any]]
    falsifier: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "low": round(self.low, 2),
            "mid": round(self.mid, 2),
            "high": round(self.high, 2),
            "currency": self.currency,
            "assumptions": self.assumptions,
            "sensitivity": self.sensitivity,
            "falsifier": self.falsifier,
        }
