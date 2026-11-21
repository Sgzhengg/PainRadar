"""Validity pre-filter: is this text a genuine pain at all?

The gold-set pilot showed the LLM's only systematic error is calling praise or
off-topic reviews a pain. That is a *classification* problem, cheap to solve
before spending tokens: a lexicon + rating prior + negation handling.

The filter is deliberately conservative: it only rejects when praise or
off-topic evidence clearly outweighs complaint evidence. Anything uncertain
goes through to extraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import CategorySpec
from .lexicon import HELP_TERMS, NEGATORS, OFF_TOPIC, PAIN_TERMS, PRAISE_TERMS

WISH_TERMS = (
    "please", "wish", "needs", "would be nice", "should add", "hope they",
    "requested", "asked for", "feature request", "should have",
    "希望", "要是", "建议", "能不能",
)

CONTRAST = (" but ", " however ", " although ", " though ", "，但", "但是", "不过", "可是")
PRODUCT_NOUNS = ("feeder", "fountain", "litter", "camera", "bowl", "pump", "device", "collar")


@dataclass
class Verdict:
    valid: bool
    score: float
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {"valid": self.valid, "score": round(self.score, 2), "reasons": self.reasons}


def _negated(text: str, term: str) -> bool:
    """True when a praise term is preceded by a negator within ~14 chars."""
    start = 0
    while True:
        idx = text.find(term, start)
        if idx < 0:
            return False
        window = text[max(0, idx - 14) : idx]
        if any(n in window for n in NEGATORS):
            return True
        start = idx + 1


class ValidityFilter:
    def __init__(self, category: CategorySpec, threshold: float = 0.0):
        self.category = category
        self.threshold = threshold
        self.off_topic = tuple(OFF_TOPIC.get(category.key, ()))

    def judge(self, text: str, rating: float | None = None) -> Verdict:
        low = (text or "").lower()

        complaints = [t for t in PAIN_TERMS if t in low]
        praises = [t for t in PRAISE_TERMS if t in low and not _negated(low, t)]
        wishes = [t for t in WISH_TERMS if t in low]
        helps = [t for t in HELP_TERMS if t in low]
        off = [t for t in self.off_topic if t in low]

        score = 0.0
        reasons: list[str] = []
        if complaints:
            score += min(3, len(complaints)) * 1.0
            reasons.append("pain:" + ",".join(complaints[:3]))
        if praises:
            score -= min(3, len(praises)) * 1.0
            reasons.append("praise:" + ",".join(praises[:3]))
        if wishes:
            score += min(2, len(wishes)) * 0.5
            reasons.append("wish:" + ",".join(wishes[:2]))
        if helps:
            score += 0.5
            reasons.append("help")
        if off:
            # A single off-topic word in an otherwise product-specific review is
            # usually incidental (e.g. "insurance" mentioned inside an app
            # complaint), so the penalty is halved when product nouns appear.
            penalty = 2.0 if not any(n in low for n in PRODUCT_NOUNS) else 1.0
            score -= penalty * min(2, len(off))
            reasons.append("off-topic:" + ",".join(off[:2]))
        if complaints and any(c in low for c in CONTRAST):
            score += 1.0
            reasons.append("contrast")

        if rating is not None:
            try:
                r = float(rating)
            except (TypeError, ValueError):
                r = None
            if r is not None:
                if r <= 2:
                    score += 1.0
                    reasons.append("rating<=2")
                elif r >= 4:
                    score -= 0.5
                    reasons.append("rating>=4")

        return Verdict(valid=score > self.threshold, score=score, reasons=reasons)
