"""Load MediaCrawler-style exports and build conversation context blocks."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .clean import is_noise
from .models import Comment, ContextBlock, Thread

POST_ID_KEYS = ("note_id", "post_id", "thread_id", "id", "aweme_id")
POST_TITLE_KEYS = ("title", "note_title", "desc", "content", "text")
POST_BODY_KEYS = ("desc", "content", "text", "body", "description")
POST_URL_KEYS = ("url", "note_url", "share_url", "link")
POST_LIKE_KEYS = ("liked_count", "like_count", "likes", "digg_count", "like_num", "liked")
COMMENT_TEXT_KEYS = ("content", "text", "comment", "review", "body", "desc")
COMMENT_ID_KEYS = ("comment_id", "cid", "id")
COMMENT_LIKE_KEYS = ("like_count", "liked_count", "likes", "digg_count", "like_num", "liked")
REPLY_KEYS = ("sub_comments", "replies", "children", "sub_comments_list")


def _first(d: dict[str, Any], keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        if key in d and d[key] not in (None, ""):
            return d[key]
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


def _parse_comment(raw: dict[str, Any], mapping: dict[str, str] | None = None) -> Comment:
    mapping = mapping or {}
    text = str(raw.get(mapping.get("text", "")) or _first(raw, COMMENT_TEXT_KEYS)).strip()
    cid = str(raw.get(mapping.get("id", "")) or _first(raw, COMMENT_ID_KEYS))
    likes = _int(raw.get(mapping.get("likes", "")) or _first(raw, COMMENT_LIKE_KEYS, 0))
    replies = []
    for key in REPLY_KEYS:
        nested = raw.get(key)
        if isinstance(nested, list):
            replies = [_parse_comment(x, mapping) for x in nested if isinstance(x, dict)]
            break
    return Comment(comment_id=cid, text=text, likes=likes, replies=replies)


def _parse_post(raw: dict[str, Any], mapping: dict[str, str] | None = None) -> Thread:
    mapping = mapping or {}
    pid = str(raw.get(mapping.get("id", "")) or _first(raw, POST_ID_KEYS))
    title = str(raw.get(mapping.get("title", "")) or _first(raw, POST_TITLE_KEYS, "")).strip()
    body = str(raw.get(mapping.get("body", "")) or _first(raw, POST_BODY_KEYS, "")).strip()
    url = str(raw.get(mapping.get("url", "")) or _first(raw, POST_URL_KEYS, ""))
    likes = _int(raw.get(mapping.get("likes", "")) or _first(raw, POST_LIKE_KEYS, 0))
    comments = []
    for key in ("comments", "comment_list", "comments_list"):
        nested = raw.get(key)
        if isinstance(nested, list):
            comments = [_parse_comment(c, mapping) for c in nested if isinstance(c, dict)]
            break
    return Thread(thread_id=pid, title=title, body=body, url=url, likes=likes, comments=comments)


def load_threads(path: str | Path, mapping: dict[str, str] | None = None) -> list[Thread]:
    """Load a JSON array, a single JSON object, or JSONL into Threads."""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig").strip()
    records: list[dict[str, Any]] = []
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        records = [x for x in data if isinstance(x, dict)]
    elif text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                records = [x for x in data["data"] if isinstance(x, dict)]
            elif isinstance(data, dict):
                records = [data]
        except json.JSONDecodeError:
            records = []
    if not records:
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

    threads: dict[str, Thread] = {}
    flat_comments: list[tuple[str, Comment]] = []
    for rec in records:
        if any(k in rec for k in ("comments", "comment_list", "comments_list")):
            thread = _parse_post(rec, mapping)
            if not thread.thread_id:
                thread.thread_id = str(len(threads))
            threads[thread.thread_id] = thread
        else:
            pid = str(_first(rec, POST_ID_KEYS, "unknown"))
            comment = _parse_comment(rec, mapping)
            flat_comments.append((pid, comment))
            if pid not in threads:
                threads[pid] = Thread(
                    thread_id=pid,
                    title=str(rec.get("post_title") or rec.get("title") or ""),
                    body=str(rec.get("post_body") or ""),
                    url=str(rec.get("post_url") or rec.get("url") or ""),
                    likes=_int(rec.get("post_likes") or 0),
                )

    for pid, comment in flat_comments:
        threads[pid].comments.append(comment)
    return list(threads.values())


def build_contexts(
    threads: list[Thread],
    top_comments: int = 4,
    min_comment_len: int = 6,
    max_comments_per_thread: int = 12,
    domain_terms: list[str] | None = None,
) -> tuple[list[ContextBlock], Counter]:
    """Filter noise, keep the most-liked comments (with their replies), build blocks."""
    stats: Counter = Counter()
    blocks: list[ContextBlock] = []
    domain = [d.lower() for d in (domain_terms or []) if d.strip()]
    for thread in threads:
        if domain:
            # filter on the post itself, not on comments: off-topic weekly threads
            # often mention "document" in passing.
            haystack = f"{thread.title} {thread.body}".lower()
            if not any(d in haystack for d in domain):
                stats["drop_off_domain"] += 1
                continue
        kept: list[Comment] = []
        for comment in thread.comments:
            noise, reason = is_noise(comment.text, min_len=min_comment_len)
            if noise:
                stats[f"drop_{reason}"] += 1
            else:
                kept.append(comment)
                stats["kept_comments"] += 1
            cleaned_replies = []
            for reply in comment.replies:
                r_noise, r_reason = is_noise(reply.text, min_len=min_comment_len)
                if r_noise:
                    stats[f"drop_reply_{r_reason}"] += 1
                    continue
                cleaned_replies.append(reply)
                stats["kept_replies"] += 1
            comment.replies = cleaned_replies
        if not kept and not thread.title:
            stats["drop_empty_thread"] += 1
            continue
        kept.sort(key=lambda c: (c.likes, c.reply_count), reverse=True)
        chosen = kept[:top_comments]
        # keep a few extra popular replies for context
        extra = [c for c in kept[top_comments:max_comments_per_thread]]
        chosen = chosen + extra
        heat = sum(c.likes for c in chosen) + thread.likes
        blocks.append(
            ContextBlock(
                thread_id=thread.thread_id,
                url=thread.url,
                title=thread.title,
                body=thread.body,
                comments=chosen,
                heat=heat,
            )
        )
        stats["contexts"] += 1
    blocks.sort(key=lambda b: b.heat, reverse=True)
    return blocks, stats
