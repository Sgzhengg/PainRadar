"""Level resolution: turn the L0–L4 ladder into a deterministic tree.

The gold pilot showed the only real disagreement is L1 vs L2, i.e. whether the
text contains an *action the user took* to get around the obstacle. That is a
classification of the workaround string, not a judgement call for the model.

Decision tree:

    no obstacle                         -> L0
    already paid for a solution         -> L4  (declared by extractor)
    priced / compared / tried a solution-> L3  (declared by extractor)
    workaround is a substitute          -> L2
    workaround is a self-rescue action  -> L2
    workaround is escalation only       -> L1  (contacting support is a reaction,
                                                not a substitute)
    otherwise                           -> L1
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SUBSTITUTE = (
    "switched to", "switch to", "replaced with", "replaced it", "bought a", "bought an",
    "bought another", "purchased a", "instead", "alternative", "use a different",
    "using a different", "diy", "third-party", "aftermarket",
    "换成", "改用", "换了一个", "买了一个", "买了另一个", "用别的", "替代",
)

SELF_RESCUE = (
    "reset", "restart", "reconnect", "reboot", "unplug", "re-pair", "repair",
    "tape", "taped", "wedge", "foil", "zip tie", "manual", "manually", "by hand",
    "clean", "scrub", "soak", "vinegar", "bowl", "extension cord", "adjust", "tighten",
    "move", "moved", "moving", "relocate", "relocating", "put it", "placed",
    "turn it off", "turned it off",
    "top up", "refill", "filter",
    "重启", "重置", "重连", "拔插", "手动", "清洗", "刷", "拆", "垫", "绑", "粘", "凑合",
    "搬到", "挪", "关掉", "调小", "加满", "换水",
)

ESCALATION = (
    "support", "customer service", "contact", "emailed", "email", "called", "phone",
    "refund", "return", "review", "complain", "ticket", "warranty", "replacement",
    "客服", "售后", "投诉", "联系", "退货", "退款", "保修",
)

_ACTION_VERB = re.compile(
    r"\b(reset|restart|reconnect|unplug|tape|wedge|clean|scrub|soak|switch|replace|buy|bought|use|move|put|run)\b"
)


@dataclass
class LevelInput:
    obstacle: str
    workaround: str = ""
    cost_type: str = ""
    cost_estimate: str = ""
    declared: str = ""
    text: str = ""


def classify_workaround(workaround: str, text: str = "") -> str:
    """substitute / self_rescue / escalation / none.

    When an explicit workaround string is present, trust its markers. When it is
    empty, fall back to the quote but require an action verb, so that a review
    merely mentioning "clean" is not treated as a workaround.
    """
    if workaround:
        hay = workaround.lower()
        if any(k in hay for k in SUBSTITUTE):
            return "substitute"
        if any(k in hay for k in SELF_RESCUE):
            return "self_rescue"
        if any(k in hay for k in ESCALATION):
            return "escalation"
        return "none"

    hay = (text or "").lower()
    if any(k in hay for k in SUBSTITUTE):
        return "substitute"
    if any(k in hay for k in SELF_RESCUE) and _ACTION_VERB.search(hay):
        return "self_rescue"
    if any(k in hay for k in ESCALATION):
        return "escalation"
    return "none"


def resolve_level(inp: LevelInput) -> str:
    if not (inp.obstacle or "").strip():
        return "L0"
    declared = (inp.declared or "").upper()
    if declared == "L4":
        return "L4"
    if declared == "L3":
        return "L3"
    kind = classify_workaround(inp.workaround, inp.text if not inp.workaround else "")
    if kind in ("substitute", "self_rescue"):
        return "L2"
    return "L1"


def level_from_workaround_type(wtype: str, declared: str = "", has_obstacle: bool = True) -> str:
    """Same tree, but driven by the model's explicit workaround type."""
    if not has_obstacle:
        return "L0"
    declared = (declared or "").upper()
    if declared in ("L3", "L4"):
        return declared
    return "L2" if (wtype or "").lower() in ("substitute", "self_rescue") else "L1"
