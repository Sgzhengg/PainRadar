"""Fetch second-hand listings (Reddit swap subs) for a product.

    python tools/fetch_secondhand.py --product "Apple Watch" \
        --keywords "apple watch,series,ultra" \
        --subreddits appleswap,hardwareswap --pages 6 \
        --out var/secondhand/apple-watch.jsonl

Why: a for-sale post is behavior evidence — the seller owned it, and the listing
usually says why they are letting it go ("barely used", "bought last month").
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.net import HttpClient  # noqa: E402

BASE = "https://arctic-shift.photon-reddit.com/api"


def fetch_posts(client: HttpClient, subreddit: str, pages: int, limit: int = 100) -> list[dict]:
    rows: list[dict] = []
    before: int | None = None
    for _ in range(pages):
        params: dict[str, object] = {"subreddit": subreddit, "limit": limit, "sort": "desc"}
        if before is not None:
            params["before"] = before
        try:
            data = client.get_json(f"{BASE}/posts/search", params=params)
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
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--keywords", required=True)
    ap.add_argument("--subreddits", required=True)
    ap.add_argument("--pages", type=int, default=6)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    keywords = [k.strip().lower() for k in args.keywords.split(",") if k.strip()]
    client = HttpClient(user_agent="PainRadar/0.1", timeout=45, max_retries=1, rate_per_sec=0.4)

    seen: set[str] = set()
    out: list[dict] = []
    for sub in [s.strip() for s in args.subreddits.split(",") if s.strip()]:
        posts = fetch_posts(client, sub, args.pages)
        kept = 0
        for p in posts:
            text = f"{p.get('title') or ''}. {p.get('selftext') or ''}".strip()
            low = text.lower()
            if not any(k in low for k in keywords):
                continue
            if len(text) < 40:
                continue
            key = text[:120]
            if key in seen:
                continue
            seen.add(key)
            out.append({"text": text[:2000], "url": f"https://www.reddit.com{p.get('permalink') or ''}"})
            kept += 1
        print(f"  r/{sub}: {len(posts)} posts -> {kept} matched")

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n", encoding="utf-8")
    print(f"written {dest} ({len(out)} listings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
