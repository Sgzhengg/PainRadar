"""Collect developer-tool pain evidence into separate domains.

    python tools/fetch_devtools.py --db var/devtools.db --pages 2

Why this corpus: consumer-app reviews produced service-shaped demands (hardware,
vendor support). People who already pay for software complain about *tool*
friction instead — that shape is what a solo developer can ship.

Sources: GitHub issue search, Hacker News comments, Reddit archive.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import register_custom_category  # noqa: E402
from painradar.connectors.github_issues import GitHubIssueConnector  # noqa: E402
from painradar.connectors.hn import HNConnector  # noqa: E402
from painradar.connectors.reddit_archive import RedditArchiveConnector  # noqa: E402
from painradar.pipeline import ingest_items  # noqa: E402
from painradar.store import Store  # noqa: E402

GITHUB_QUERIES = {
    "dev": ["vscode extension", "docker desktop", "homebrew formula", "git client"],
    "prod": ["obsidian plugin", "raycast extension", "notion api", "alfred workflow"],
}
HN_QUERIES = {
    "dev": ["docker desktop", "vscode", "homebrew"],
    "prod": ["obsidian", "raycast", "notion"],
}
REDDIT = [
    ("selfhosted", "dev"),
    ("devops", "dev"),
    ("webdev", "dev"),
    ("macapps", "prod"),
    ("ObsidianMD", "prod"),
    ("Notion", "prod"),
    ("raycastapp", "prod"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/devtools.db")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--github-limit", type=int, default=30)
    ap.add_argument("--hn-limit", type=int, default=60)
    args = ap.parse_args()

    categories = {
        "dev": register_custom_category("开发工具", "developer tools"),
        "prod": register_custom_category("生产力工具", "productivity tools"),
    }
    store = Store(args.db)
    total = 0
    try:
        for slug, queries in GITHUB_QUERIES.items():
            key = categories[slug]
            for query in queries:
                conn = GitHubIssueConnector(category=key, query=query, limit=args.github_limit)
                try:
                    result = ingest_items(store, conn.fetch(), key)
                except Exception as exc:  # noqa: BLE001
                    print(f"  github {query!r}: FAILED {type(exc).__name__}")
                    time.sleep(8)
                    continue
                total += result.inserted
                print(f"  github {query!r:<22} -> {key:<22} +{result.inserted}")
                time.sleep(6)

        for slug, queries in HN_QUERIES.items():
            key = categories[slug]
            for query in queries:
                conn = HNConnector(category=key, query=query, limit=args.hn_limit)
                try:
                    result = ingest_items(store, conn.fetch(), key)
                except Exception:  # noqa: BLE001
                    continue
                total += result.inserted
                print(f"  hn     {query!r:<22} -> {key:<22} +{result.inserted}")
                time.sleep(1)

        for subreddit, slug in REDDIT:
            key = categories[slug]
            conn = RedditArchiveConnector(
                category=key, subreddit=subreddit, pages=args.pages, limit=100
            )
            try:
                result = ingest_items(store, conn.fetch(), key)
            except Exception:  # noqa: BLE001
                continue
            total += result.inserted
            print(f"  reddit r/{subreddit:<16} -> {key:<22} +{result.inserted}")
            time.sleep(1)

        print(f"\ninserted {total}")
        for category, platform, n in store._conn.execute(
            "SELECT category, platform, COUNT(rowid) FROM items WHERE deleted_at IS NULL GROUP BY category, platform"
        ).fetchall():
            print(f"  {category:<22} {platform:<12} {n}")
            store.audit("tool", "fetch", platform, category, f'{{"items": {n}}}')
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
