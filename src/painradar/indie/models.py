"""Domain objects for the indie opportunity pipeline.

Deliberately separate from ``painradar.schema``: that model is comment-level and
has no engagement or thread context, which is exactly what this pipeline needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SIGNAL_TYPES = ("竞品吐槽", "求推荐/平替", "手工繁琐", "付费信号")


@dataclass
class Comment:
    comment_id: str
    text: str
    likes: int = 0
    replies: list["Comment"] = field(default_factory=list)
    parent_id: str = ""
    author: str = ""

    @property
    def reply_count(self) -> int:
        return len(self.replies)


@dataclass
class Thread:
    thread_id: str
    title: str
    body: str = ""
    url: str = ""
    likes: int = 0
    comments: list[Comment] = field(default_factory=list)


@dataclass
class ContextBlock:
    """One thread rendered as a conversation block for the model."""

    thread_id: str
    url: str
    title: str
    body: str
    comments: list[Comment]
    heat: int = 0

    def render(self, max_chars: int = 2000) -> str:
        lines = [f"【原帖】{self.title}"]
        if self.body:
            lines.append(f"【正文】{self.body[:400]}")
        lines.append("【评论与回复】")
        for i, c in enumerate(self.comments, start=1):
            lines.append(f"评论{i}（赞{c.likes}）：{c.text}")
            for j, r in enumerate(c.replies, start=1):
                lines.append(f"  └回复{j}（赞{r.likes}）：{r.text}")
        text = "\n".join(lines)
        return text[:max_chars]


@dataclass
class Signal:
    signal_id: str
    type: str
    pain: str
    quote: str
    likes: int
    replies: int
    url: str
    thread_id: str
    comment_id: str
    wtp: bool = False
    context: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "type": self.type,
            "pain": self.pain,
            "quote": self.quote,
            "likes": self.likes,
            "replies": self.replies,
            "url": self.url,
            "thread_id": self.thread_id,
            "comment_id": self.comment_id,
            "wtp": self.wtp,
        }


@dataclass
class Cluster:
    name: str
    signal_ids: list[str]
    pain_profile: str
    buyer: str
    scenario: str
    mvp: str
    monetization: str
    dev_difficulty: int = 3
    wtp_clarity: float = 0.0
    score: float = 0.0
    stats: dict[str, Any] = field(default_factory=dict)
    evidence: list[Signal] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pain_profile": self.pain_profile,
            "buyer": self.buyer,
            "scenario": self.scenario,
            "mvp": self.mvp,
            "monetization": self.monetization,
            "dev_difficulty": self.dev_difficulty,
            "wtp_clarity": self.wtp_clarity,
            "score": self.score,
            "stats": self.stats,
            "signals": [s.as_dict() for s in self.evidence],
        }
