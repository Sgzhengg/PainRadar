"""Build a MediaCrawler-shaped dataset from Arctic Shift (posts + comments with scores).

    python tools/build_reddit_dataset.py --subreddits pdf,software --out var/reddit_indie.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.net import HttpClient  # noqa: E402

BASE = "https://arctic-shift.photon-reddit.com/api"


def fetch_posts(c: HttpClient, sub: str, limit: int) -> list[dict]:
    data = c.get_json(f"{BASE}/posts/search", params={"subreddit": sub, "limit": limit, "sort": "desc"})
    return data.get("data", []) if isinstance(data, dict) else []


def fetch_comments(c: HttpClient, sub: str, pages: int) -> list[dict]:
    rows: list[dict] = []
    before = None
    for _ in range(pages):
        params = {"subreddit": sub, "limit": 100}
        if before:
            params["before"] = before
        try:
            data = c.get_json(f"{BASE}/comments/search", params=params)
        except Exception:  # noqa: BLE001
            break
        batch = data.get("data", []) if isinstance(data, dict) else []
        if not batch:
            break
        rows.extend(batch)
        oldest = min(int(r.get("created_utc") or 0) for r in batch)
        if not oldest:
            break
        before = oldest - 1
        time.sleep(0.5)
    return rows


def build(subs: list[str], posts_per_sub: int, comment_pages: int) -> list[dict]:
    client = HttpClient(user_agent="PainRadar/0.1", timeout=45, max_retries=1, rate_per_sec=0.5)
    out: list[dict] = []
    for sub in subs:
        posts = fetch_posts(client, sub, posts_per_sub)
        comments = fetch_comments(client, sub, comment_pages)
        by_link: dict[str, list[dict]] = {}
        for row in comments:
            link = str(row.get("link_id") or "").replace("t3_", "")
            if link:
                by_link.setdefault(link, []).append(row)
        kept = 0
        for post in posts:
            pid = str(post.get("id") or "")
            rows = by_link.get(pid, [])
            if len(rows) < 3:
                continue
            by_parent: dict[str, list[dict]] = {}
            top: list[dict] = []
            for row in rows:
                parent = str(row.get("parent_id") or "")
                if parent.startswith("t3_"):
                    top.append(row)
                else:
                    by_parent.setdefault(parent, []).append(row)
            comments = []
            for row in top:
                cid = str(row.get("id"))
                replies = [
                    {
                        "comment_id": str(r.get("id")),
                        "content": str(r.get("body") or ""),
                        "like_count": int(r.get("score") or 0),
                    }
                    for r in by_parent.get(f"t1_{cid}", [])
                ]
                comments.append(
                    {
                        "comment_id": cid,
                        "content": str(row.get("body") or ""),
                        "like_count": int(row.get("score") or 0),
                        "sub_comments": replies,
                    }
                )
            comments.sort(key=lambda x: x["like_count"], reverse=True)
            out.append(
                {
                    "note_id": pid,
                    "title": str(post.get("title") or ""),
                    "desc": str(post.get("selftext") or "")[:800],
                    "url": f"https://www.reddit.com{post.get('permalink') or ''}",
                    "liked_count": int(post.get("score") or 0),
                    "comments": comments,
                }
            )
            kept += 1
        print(f"r/{sub}: posts={len(posts)} comments={len(comments)} threads={kept}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subreddits", default="pdf,software")
    ap.add_argument("--posts", type=int, default=100)
    ap.add_argument("--comment-pages", type=int, default=3)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    subs = [s.strip() for s in args.subreddits.split(",") if s.strip()]
    data = build(subs, args.posts, args.comment_pages)
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written {args.out} threads={len(data)} comments={sum(len(t['comments']) for t in data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
