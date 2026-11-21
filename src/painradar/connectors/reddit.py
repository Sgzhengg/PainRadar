"""Reddit connector.

Two modes, same output:

* **OAuth** (recommended): set ``REDDIT_CLIENT_ID``, ``REDDIT_CLIENT_SECRET``,
  ``REDDIT_USERNAME``, ``REDDIT_PASSWORD``. Script-app password grant.
* **Public JSON**: no credentials, lower rate limit, intended for small samples
  and demos only. Reddit's terms still apply; keep volume low.

Comments are fetched per post (``depth=1``) because that is where pain lives;
each comment becomes its own ``RawItem`` so evidence can point at it directly.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator

from ..net import HttpClient, HttpError
from ..schema import RawItem, Tier

REDDIT_UA = os.environ.get(
    "REDDIT_USER_AGENT", "PainRadar/0.1 (research; contact: set REDDIT_USER_AGENT)"
)


@dataclass
class RedditConnector:
    category: str
    query: str
    subreddits: list[str]
    limit: int = 25
    include_comments: bool = True
    comments_per_post: int = 30
    sort: str = "relevance"
    time_filter: str = "year"
    client: HttpClient | None = None

    platform = "reddit"
    tier: Tier = Tier.A

    _token: str | None = field(default=None, init=False, repr=False)
    _token_expiry: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = HttpClient(
                user_agent=REDDIT_UA,
                rate_per_sec=1.2 if os.environ.get("REDDIT_CLIENT_ID") else 0.2,
            )

    # -- auth --------------------------------------------------------------
    @property
    def _oauth_enabled(self) -> bool:
        return bool(os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"))

    def _access_token(self) -> str | None:
        if not self._oauth_enabled:
            return None
        if self._token and self._token_expiry > datetime.now(timezone.utc).timestamp():
            return self._token
        cid = os.environ["REDDIT_CLIENT_ID"]
        secret = os.environ["REDDIT_CLIENT_SECRET"]
        basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        payload = {"grant_type": "client_credentials"}
        user = os.environ.get("REDDIT_USERNAME")
        if user and os.environ.get("REDDIT_PASSWORD"):
            payload = {
                "grant_type": "password",
                "username": user,
                "password": os.environ["REDDIT_PASSWORD"],
            }
        data = self.client.post_form(  # type: ignore[union-attr]
            "https://www.reddit.com/api/v1/access_token",
            payload,
            headers={"Authorization": f"Basic {basic}"},
        )
        assert isinstance(data, dict)
        self._token = data.get("access_token")
        self._token_expiry = datetime.now(timezone.utc).timestamp() + float(data.get("expires_in", 3600)) - 60
        return self._token

    # -- fetching ----------------------------------------------------------
    def _base(self) -> str:
        return "https://oauth.reddit.com" if self._oauth_enabled else "https://www.reddit.com"

    def _headers(self) -> dict[str, str]:
        token = self._access_token()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _search(self, subreddit: str) -> list[dict]:
        url = f"{self._base()}/r/{subreddit}/search.json"
        params = {
            "q": self.query,
            "restrict_sr": "1",
            "sort": self.sort,
            "t": self.time_filter,
            "limit": self.limit,
            "raw_json": "1",
        }
        data = self.client.get_json(url, params=params, headers=self._headers())  # type: ignore[union-attr]
        assert isinstance(data, dict)
        return [c["data"] for c in data.get("data", {}).get("children", []) if c.get("kind") == "t3"]

    def _comments(self, post_id: str) -> list[dict]:
        url = f"{self._base()}/comments/{post_id}.json"
        params = {"limit": self.comments_per_post, "depth": 1, "raw_json": "1"}
        data = self.client.get_json(url, params=params, headers=self._headers())  # type: ignore[union-attr]
        if not isinstance(data, list) or len(data) < 2:
            return []
        children = data[1].get("data", {}).get("children", [])
        return [c["data"] for c in children if c.get("kind") == "t1"]

    def fetch(self) -> Iterator[RawItem]:
        seen: set[str] = set()
        for sub in self.subreddits:
            try:
                posts = self._search(sub)
            except HttpError as exc:
                if exc.status in (401, 403, 404):
                    continue
                raise
            for post in posts:
                text = "\n\n".join(x for x in (post.get("title", ""), post.get("selftext", "")) if x).strip()
                if len(text) >= 30:
                    item = self._item(post, text, f"t3_{post.get('id')}")
                    if item:
                        seen.add(item.item_id)
                        yield item
                if not self.include_comments:
                    continue
                try:
                    comments = self._comments(str(post.get("id")))
                except HttpError:
                    continue
                for c in comments:
                    body = (c.get("body") or "").strip()
                    if body in ("[deleted]", "[removed]") or len(body) < 30:
                        continue
                    item = self._item(c, body, f"t1_{c.get('id')}")
                    if item and item.item_id not in seen:
                        seen.add(item.item_id)
                        yield item

    def _item(self, obj: dict, text: str, item_id: str) -> RawItem | None:
        permalink = obj.get("permalink") or ""
        created = obj.get("created_utc")
        published = (
            datetime.fromtimestamp(float(created), tz=timezone.utc).strftime("%Y-%m-%d")
            if created
            else "1970-01-01"
        )
        author = str(obj.get("author") or "")
        if author in ("[deleted]", "AutoModerator"):
            return None
        return RawItem(
            platform="reddit",
            item_id=item_id,
            url=f"https://www.reddit.com{permalink}" if permalink else "",
            text=text,
            published_at=published,
            category=self.category,
            author=author,
            tier=Tier.A,
            tos_basis="official_api" if self._oauth_enabled else "public_json",
        )

    def health(self) -> dict[str, object]:
        return {
            "platform": "reddit",
            "oauth": self._oauth_enabled,
            "subreddits": self.subreddits,
            "query": self.query,
            "limit": self.limit,
        }
