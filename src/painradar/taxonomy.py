"""Scene classification (taxonomy v2).

The first gold-set pass exposed the real problem: "App 与连接" was a catch-all
because almost every review mentions the app, so it absorbed ads, support and
feature requests. v2 removes generic words ("app", "outage") from that bucket,
adds four specific buckets, and orders the dictionary from specific to general.

Order matters: the first bucket with a matching term wins.
"""

from __future__ import annotations

import re

from .config import CategorySpec

_WORD = re.compile(r"[a-z0-9]")


def _matches(hay: str, needle: str) -> bool:
    if _WORD.search(needle):
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", hay) is not None
    return needle in hay


def classify_scene(text: str, category: CategorySpec, default: str = "其他场景") -> str:
    hay = (text or "").lower()
    for label, needles in category.scenes.items():
        for needle in needles:
            if _matches(hay, needle.lower()):
                return label
    return default
