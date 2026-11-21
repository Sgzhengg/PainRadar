"""Apple App Store review connector.

Uses the public customer-reviews RSS feed — no key, no login:

    https://itunes.apple.com/{country}/rss/customerreviews/page={n}/id={app_id}/sortby=mostrecent/json

The feed returns one metadata entry (the app itself) followed by review
entries. Reviews are short but high-signal: a 1–2 star review usually names the
obstacle and the workaround in the same sentence.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterator

from ..net import HttpClient, HttpError
from ..schema import RawItem, Tier

APPSTORE_UA = "PainRadar/0.1 (research)"


def search_apps(term: str, country: str = "us", limit: int = 5, client: HttpClient | None = None) -> list[dict]:
    """Resolve a search term to App Store apps (id, name, rating count)."""
    client = client or HttpClient(user_agent=APPSTORE_UA, rate_per_sec=0.5)
    data = client.get_json(
        "https://itunes.apple.com/search",
        params={"term": term, "country": country, "entity": "software", "limit": limit},
    )
    if not isinstance(data, dict):
        return []
    out = []
    for r in data.get("results", []):
        out.append(
            {
                "app_id": str(r.get("trackId", "")),
                "name": r.get("trackName", ""),
                "rating_count": r.get("userRatingCount", 0),
                "avg_rating": r.get("averageUserRating", 0),
                "url": r.get("trackViewUrl", ""),
                "genre": r.get("primaryGenreName", ""),
            }
        )
    return out


@dataclass
class AppStoreConnector:
    category: str
    app_id: str
    country: str = "us"
    pages: int = 3
    sort: str = "mostrecent"
    client: HttpClient | None = None

    platform = "appstore"
    tier: Tier = Tier.A

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = HttpClient(user_agent=APPSTORE_UA, rate_per_sec=0.5)

    def _page_url(self, page: int) -> str:
        return (
            f"https://itunes.apple.com/{self.country}/rss/customerreviews/"
            f"page={page}/id={self.app_id}/sortby={self.sort}/json"
        )

    def fetch(self) -> Iterator[RawItem]:
        for page in range(1, max(1, self.pages) + 1):
            try:
                data = self.client.get_json(self._page_url(page))  # type: ignore[union-attr]
            except HttpError:
                break
            if not isinstance(data, dict):
                break
            entries = data.get("feed", {}).get("entry", [])
            if isinstance(entries, dict):
                entries = [entries]
            if not entries:
                break
            produced = 0
            for entry in entries:
                item = self._parse(entry)
                if item:
                    produced += 1
                    yield item
            if produced == 0:
                break  # last page returned only the app metadata entry

    def _parse(self, entry: dict) -> RawItem | None:
        rating = entry.get("im:rating", {}).get("label")
        if rating is None:
            return None  # app metadata entry
        body = (entry.get("content", {}).get("label") or "").strip()
        title = (entry.get("title", {}).get("label") or "").strip()
        text = f"{title}. {body}".strip() if title else body
        if len(text) < 30:
            return None
        review_id = (entry.get("id", {}) or {}).get("label") or ""
        author = ((entry.get("author", {}) or {}).get("name", {}) or {}).get("label") or ""
        updated = ((entry.get("updated", {}) or {}).get("label") or "")[:10]
        link = ((entry.get("link", {}) or {}).get("attributes", {}) or {}).get("href") or ""
        return RawItem(
            platform="appstore",
            item_id=(
                f"as_{self.app_id}_{review_id}"
                if review_id
                else "as_" + hashlib.sha256(text.encode()).hexdigest()[:16]
            ),
            url=link,
            text=text,
            published_at=updated or "1970-01-01",
            category=self.category,
            author=author,
            rating=float(rating),
            tier=Tier.A,
            tos_basis="public_rss",
        )

    def health(self) -> dict[str, object]:
        return {"platform": "appstore", "app_id": self.app_id, "country": self.country, "pages": self.pages}
