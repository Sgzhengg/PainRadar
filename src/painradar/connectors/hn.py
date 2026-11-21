"""Hacker News comments connector (Algolia API).

Free, key-free, and reachable where Reddit is not. HN comments are tech-leaning
but they do contain first-hand product complaints ("I returned the robot vacuum
after two weeks because...").

User-supplied text is HTML; tags are stripped, entities unescaped.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Iterator

from ..net import HttpClient
from ..schema import RawItem, Tier

TAG_RE = re.compile(r"<[^>]+>")


def _plain(text: str) -> str:
    return html.unescape(TAG_RE.sub(" ", text or "")).strip()


@dataclass
class HNConnector:
    category: str
    query: str
    limit: int = 100
    tags: str = "comment"  # comment | story

    platform = "hackernews"
    tier: Tier = Tier.B
    client: HttpClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = HttpClient(user_agent="PainRadar/0.1", timeout=30, max_retries=1, rate_per_sec=0.5)

    def fetch(self) -> Iterator[RawItem]:
        data = self.client.get_json(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": self.query,
                "tags": self.tags,
                "hitsPerPage": min(100, max(1, self.limit)),
            },
        )
        for hit in data.get("hits", [])[: self.limit]:
            if self.tags == "comment":
                text = _plain(hit.get("comment_text") or "")
                title = ""
            else:
                text = f"{_plain(hit.get('title') or '')}. {_plain(hit.get('story_text') or '')}".strip()
                title = ""
            if len(text) < 20:
                continue
            object_id = hit.get("objectID") or ""
            yield RawItem(
                platform=self.platform,
                item_id=str(object_id),
                url=f"https://news.ycombinator.com/item?id={object_id}",
                text=text,
                published_at=(hit.get("created_at") or "")[:10],
                category=self.category,
                author=hit.get("author") or "",
                tier=self.tier,
                tos_basis="hn_algolia_api",
            )

    def health(self) -> dict[str, object]:
        return {"source": "hackernews", "query": self.query, "limit": self.limit, "tags": self.tags}
