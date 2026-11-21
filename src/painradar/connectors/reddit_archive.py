"""Reddit via the Arctic Shift archive (no OAuth required).

Direct reddit.com JSON returns 403 from this network, and OAuth needs app
credentials. Arctic Shift exposes a public Reddit archive with the same post and
comment bodies, which is enough for evidence collection.

Pagination: the API caps a page at 100 items; ``before`` (epoch seconds) walks
backwards. Results are filtered locally by optional keywords because the archive
does not support full-text search on comments.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Iterator

from ..net import HttpClient
from ..schema import RawItem, Tier

BASE = "https://arctic-shift.photon-reddit.com/api"
TAG_RE = re.compile(r"<[^>]+>")


def _plain(text: str) -> str:
    return html.unescape(TAG_RE.sub(" ", text or "")).strip()


@dataclass
class RedditArchiveConnector:
    category: str
    subreddit: str
    keywords: tuple[str, ...] = ()
    pages: int = 5
    limit: int = 100
    kind: str = "comments"  # comments | posts

    platform = "reddit"
    tier = Tier.A
    client: HttpClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = HttpClient(user_agent="PainRadar/0.1", timeout=45, max_retries=1, rate_per_sec=0.4)

    def fetch(self) -> Iterator[RawItem]:
        before: int | None = None
        for _ in range(max(1, self.pages)):
            params: dict[str, object] = {
                "subreddit": self.subreddit,
                "limit": min(100, self.limit),
                "sort": "desc",
            }
            if before is not None:
                params["before"] = before
            try:
                data = self.client.get_json(f"{BASE}/{self.kind}/search", params=params)
            except Exception:  # noqa: BLE001 - archive can be flaky
                break
            rows = data.get("data", []) if isinstance(data, dict) else []
            if not rows:
                break
            oldest = None
            for row in rows:
                created = int(row.get("created_utc") or 0)
                oldest = created if oldest is None else min(oldest, created)
                if self.kind == "comments":
                    text = _plain(row.get("body") or "")
                else:
                    text = _plain(f"{row.get('title') or ''}. {row.get('selftext') or ''}")
                if len(text) < 20:
                    continue
                if self.keywords and not any(k.lower() in text.lower() for k in self.keywords):
                    continue
                permalink = row.get("permalink") or ""
                created_iso = (
                    __import__("datetime").datetime.fromtimestamp(
                        created, __import__("datetime").timezone.utc
                    ).date().isoformat()
                    if created
                    else ""
                )
                yield RawItem(
                    platform=self.platform,
                    item_id=str(row.get("id") or ""),
                    url=f"https://www.reddit.com{permalink}" if permalink else "",
                    text=text,
                    published_at=created_iso,
                    category=self.category,
                    author=row.get("author") or "",
                    tier=self.tier,
                    tos_basis="arctic_shift_archive",
                )
            if oldest is None:
                break
            before = oldest - 1

    def health(self) -> dict[str, object]:
        return {
            "source": "reddit_archive",
            "subreddit": self.subreddit,
            "kind": self.kind,
            "pages": self.pages,
        }
