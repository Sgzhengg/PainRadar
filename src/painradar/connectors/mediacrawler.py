"""MediaCrawler export connector.

Consumes the JSON / JSONL / CSV files produced by MediaCrawler for
Xiaohongshu, Bilibili, Zhihu and Douyin, and yields one :class:`RawItem` per
comment/reply with the thread context preserved in ``parent_context``.

Design notes
------------
* Field names differ per platform, so we auto-detect with alias lists; callers
  can override with a ``field_map``.
* The quote gate downstream requires the quote to be inside ``text``; therefore
  ``text`` is always the single comment, never the whole thread. The thread is
  carried separately in ``parent_context``.
* Short/emoji/ad comments are dropped here (same rules as the indie pipeline)
  so they never reach the model.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..indie.clean import is_noise
from ..schema import RawItem, Tier
from .base import registry

POST_ID_KEYS = ("note_id", "post_id", "thread_id", "aweme_id", "article_id", "question_id", "id")
TITLE_KEYS = ("title", "note_title", "desc", "content", "question_title", "text")
BODY_KEYS = ("desc", "content", "text", "body", "article_content")
URL_KEYS = ("url", "note_url", "share_url", "link", "post_url")
POST_LIKES_KEYS = ("liked_count", "like_count", "likes", "digg_count", "voteup_count", "like_num")
COMMENT_TEXT_KEYS = ("content", "text", "comment", "review", "body", "reply_content")
COMMENT_ID_KEYS = ("comment_id", "cid", "id", "rpid")
COMMENT_LIKES_KEYS = ("like_count", "liked_count", "likes", "digg_count", "like_num", "voteup_count")
REPLY_KEYS = ("sub_comments", "replies", "children", "sub_comments_list", "sub_replies")
PUBLISHED_KEYS = ("published_at", "create_time", "ctime", "time", "created_at", "publish_time")


@dataclass
class ParsedComment:
    comment_id: str
    text: str
    likes: int = 0
    replies: list["ParsedComment"] = field(default_factory=list)


@dataclass
class ParsedThread:
    post_id: str
    title: str
    body: str
    url: str
    likes: int
    comments: list[ParsedComment]
    published_at: str = ""
    platform: str = "mediacrawler"


def _first(d: dict[str, Any], keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        value = d.get(key)
        if value not in (None, ""):
            return value
    return default


def _int(value: Any) -> int:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if value.endswith("万"):
                return int(float(value[:-1]) * 10000)
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _detect_platform(rec: dict[str, Any]) -> str:
    if "note_id" in rec or "note_url" in rec:
        return "xiaohongshu"
    if "bvid" in rec or "aid" in rec or "oid" in rec:
        return "bilibili"
    if "question_id" in rec or "answer_id" in rec:
        return "zhihu"
    if "aweme_id" in rec:
        return "douyin"
    return "mediacrawler"


def _parse_comment(raw: dict[str, Any], field_map: dict[str, str] | None = None) -> ParsedComment:
    fm = field_map or {}
    text = str(raw.get(fm.get("text", "")) or _first(raw, COMMENT_TEXT_KEYS, "")).strip()
    cid = str(raw.get(fm.get("id", "")) or _first(raw, COMMENT_ID_KEYS, ""))
    likes = _int(raw.get(fm.get("likes", "")) or _first(raw, COMMENT_LIKES_KEYS, 0))
    replies: list[ParsedComment] = []
    for key in REPLY_KEYS:
        nested = raw.get(key)
        if isinstance(nested, list):
            replies = [_parse_comment(x, field_map) for x in nested if isinstance(x, dict)]
            break
    return ParsedComment(comment_id=cid, text=text, likes=likes, replies=replies)


def _parse_thread(raw: dict[str, Any], field_map: dict[str, str] | None = None) -> ParsedThread:
    fm = field_map or {}
    post_id = str(raw.get(fm.get("post_id", "")) or _first(raw, POST_ID_KEYS, ""))
    title = str(raw.get(fm.get("title", "")) or _first(raw, TITLE_KEYS, "")).strip()
    body = str(raw.get(fm.get("body", "")) or _first(raw, BODY_KEYS, "")).strip()
    url = str(raw.get(fm.get("url", "")) or _first(raw, URL_KEYS, ""))
    likes = _int(raw.get(fm.get("post_likes", "")) or _first(raw, POST_LIKES_KEYS, 0))
    published = str(_first(raw, PUBLISHED_KEYS, ""))
    comments: list[ParsedComment] = []
    for key in ("comments", "comment_list", "comments_list"):
        nested = raw.get(key)
        if isinstance(nested, list):
            comments = [_parse_comment(c, field_map) for c in nested if isinstance(c, dict)]
            break
    return ParsedThread(
        post_id=post_id,
        title=title,
        body=body,
        url=url,
        likes=likes,
        comments=comments,
        published_at=published,
        platform=_detect_platform(raw),
    )


def _load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return [row for row in csv.DictReader(fh)]
    if text.startswith("["):
        data = json.loads(text)
        return [x for x in data if isinstance(x, dict)]
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            inner = data.get("data")
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
            return [data]
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records


class MediaCrawlerConnector:
    """Turn a MediaCrawler export into RawItems with thread context."""

    platform = "mediacrawler"
    tier = Tier.A

    def __init__(
        self,
        path: str | Path,
        category: str,
        field_map: dict[str, str] | None = None,
        min_len: int = 6,
        top_comments: int = 3,
        max_context_chars: int = 1200,
        tos_basis: str = "user_provided",
        tier: Tier = Tier.A,
    ) -> None:
        self.path = Path(path)
        self.category = category
        self.field_map = field_map or {}
        self.min_len = min_len
        self.top_comments = top_comments
        self.max_context_chars = max_context_chars
        self.tos_basis = tos_basis
        self.tier = tier
        self.stats = {"threads": 0, "comments": 0, "kept": 0, "dropped": 0}

    # -- context -------------------------------------------------------
    def _context(self, thread: ParsedThread, parent: ParsedComment | None = None) -> str:
        parts = [f"【原帖】{thread.title}"]
        if thread.body:
            parts.append(f"【正文】{thread.body[:400]}")
        ranked = sorted(thread.comments, key=lambda c: c.likes, reverse=True)[: self.top_comments]
        for i, comment in enumerate(ranked, start=1):
            parts.append(f"评论{i}（赞{comment.likes}）：{comment.text}")
        if parent is not None and parent.text:
            parts.append(f"【当前评论所在楼层】{parent.text}")
        return "\n".join(parts)[: self.max_context_chars]

    def _items(self, thread: ParsedThread) -> Iterable[RawItem]:
        base_url = thread.url

        def emit(comment: ParsedComment, parent: ParsedComment | None) -> Iterable[RawItem]:
            self.stats["comments"] += 1
            noise, _ = is_noise(comment.text, min_len=self.min_len)
            if noise:
                self.stats["dropped"] += 1
            else:
                self.stats["kept"] += 1
                yield RawItem(
                    platform=thread.platform,
                    item_id=f"{thread.post_id}_{comment.comment_id}",
                    url=base_url,
                    text=comment.text,
                    published_at=thread.published_at,
                    category=self.category,
                    tier=self.tier,
                    tos_basis=self.tos_basis,
                    parent_context=self._context(thread, parent),
                    likes=comment.likes,
                    replies=len(comment.replies),
                    post_id=thread.post_id,
                )
            for reply in comment.replies:
                yield from emit(reply, comment)

        for comment in thread.comments:
            yield from emit(comment, None)

    def fetch(self) -> Iterable[RawItem]:
        records = _load_records(self.path)
        for rec in records:
            if not any(k in rec for k in ("comments", "comment_list", "comments_list")):
                # flat comment row: wrap it as a one-comment thread
                thread = ParsedThread(
                    post_id=str(_first(rec, POST_ID_KEYS, "post")),
                    title=str(rec.get("post_title") or rec.get("title") or ""),
                    body=str(rec.get("post_body") or ""),
                    url=str(rec.get("post_url") or rec.get("url") or ""),
                    likes=_int(rec.get("post_likes") or 0),
                    comments=[_parse_comment(rec, self.field_map)],
                    published_at=str(_first(rec, PUBLISHED_KEYS, "")),
                    platform=_detect_platform(rec),
                )
            else:
                thread = _parse_thread(rec, self.field_map)
            self.stats["threads"] += 1
            yield from self._items(thread)

    def health(self) -> dict[str, object]:
        return {
            "platform": self.platform,
            "path": str(self.path),
            "exists": self.path.exists(),
            **self.stats,
        }


registry.register(
    "mediacrawler",
    lambda path, category, **kw: MediaCrawlerConnector(path=path, category=category, **kw),
)
