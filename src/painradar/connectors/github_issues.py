"""GitHub Issues connector.

Product-integration issues are a genuinely different channel from app reviews:
smart-home users report device pain in issue trackers (Home Assistant, custom
bridges), including problems the vendor app never fixes.

Uses the public search API (unauthenticated: 10 requests/min, 60/hour).
Set ``GITHUB_TOKEN`` to raise the limits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterator

from ..net import HttpClient
from ..schema import RawItem, Tier

GITHUB_UA = "PainRadar/0.1 (research)"


@dataclass
class GitHubIssueConnector:
    category: str
    query: str
    limit: int = 50
    sort: str = "created"

    platform = "github"
    tier: Tier = Tier.B
    client: HttpClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = HttpClient(user_agent=GITHUB_UA, timeout=30, max_retries=1, rate_per_sec=0.2)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def fetch(self) -> Iterator[RawItem]:
        data = self.client.get_json(
            "https://api.github.com/search/issues",
            params={
                "q": f"{self.query} is:issue",
                "sort": self.sort,
                "order": "desc",
                "per_page": min(100, max(1, self.limit)),
            },
            headers=self._headers(),
        )
        for item in data.get("items", [])[: self.limit]:
            title = item.get("title") or ""
            body = (item.get("body") or "")[:3000]
            text = f"{title}. {body}".strip()
            if len(text) < 20:
                continue
            yield RawItem(
                platform=self.platform,
                item_id=str(item.get("id")),
                url=item.get("html_url") or "",
                text=text,
                published_at=(item.get("created_at") or "")[:10],
                category=self.category,
                author=((item.get("user") or {}).get("login") or ""),
                tier=self.tier,
                tos_basis="github_public_search",
            )

    def health(self) -> dict[str, object]:
        return {"source": "github", "query": self.query, "limit": self.limit}
