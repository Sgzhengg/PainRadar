"""Tests for GitHub Issues and Hacker News connectors (offline)."""

from __future__ import annotations

import json
import unittest

from painradar.connectors.github_issues import GitHubIssueConnector
from painradar.connectors.hn import HNConnector
from painradar.net import HttpClient, Response


class Fake:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(url)
        return Response(200, {}, json.dumps(self.payload).encode())


def _client(payload) -> HttpClient:
    return HttpClient(user_agent="t", transport=Fake(payload), sleep=lambda _: None, rate_per_sec=1000)


GH = {
    "items": [
        {"id": 1, "title": "Integration fails after firmware 1.28", "body": "ImportError: cannot import name wrap",
         "html_url": "https://github.com/x/y/issues/1", "created_at": "2026-02-01T00:00:00Z",
         "user": {"login": "alice"}},
        {"id": 2, "title": "ok", "body": "", "html_url": "https://github.com/x/y/issues/2",
         "created_at": "2026-02-02T00:00:00Z", "user": {"login": "bob"}},
    ]
}

HN = {
    "hits": [
        {"objectID": "111", "comment_text": "I <b>returned</b> the fountain &amp; bought bowls",
         "created_at": "2026-03-01T00:00:00Z", "author": "carol"},
        {"objectID": "222", "comment_text": "short", "created_at": "2026-03-02T00:00:00Z", "author": "dave"},
    ]
}


class TestGitHub(unittest.TestCase):
    def test_fetch_maps_issues(self) -> None:
        conn = GitHubIssueConnector(category="pet", query="petkit", limit=10)
        conn.client = _client(GH)
        items = list(conn.fetch())
        self.assertEqual(len(items), 1)  # the empty body item is too short
        self.assertEqual(items[0].platform, "github")
        self.assertIn("Integration fails", items[0].text)
        self.assertEqual(items[0].published_at, "2026-02-01")
        self.assertEqual(items[0].author, "alice")


class TestHN(unittest.TestCase):
    def test_fetch_strips_html(self) -> None:
        conn = HNConnector(category="pet", query="fountain", limit=10)
        conn.client = _client(HN)
        items = list(conn.fetch())
        self.assertEqual(len(items), 1)
        self.assertNotIn("<b>", items[0].text)
        self.assertIn("&", items[0].text)
        self.assertEqual(items[0].url, "https://news.ycombinator.com/item?id=111")


class TestRedditArchive(unittest.TestCase):
    def test_fetch_filters_keywords(self) -> None:
        from painradar.connectors.reddit_archive import RedditArchiveConnector

        payload = {
            "data": [
                {"id": "a", "body": "my petkit fountain pump died after two months of use",
                 "created_utc": 1710000000, "permalink": "/r/petkit/a", "author": "u1"},
                {"id": "b", "body": "short", "created_utc": 1709990000,
                 "permalink": "/r/petkit/b", "author": "u2"},
                {"id": "c", "body": "totally unrelated comment about cooking pasta tonight",
                 "created_utc": 1709980000, "permalink": "/r/petkit/c", "author": "u3"},
            ]
        }
        conn = RedditArchiveConnector(
            category="pet", subreddit="petkit", keywords=("fountain",), pages=1
        )
        conn.client = _client(payload)
        items = list(conn.fetch())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].platform, "reddit")
        self.assertIn("fountain", items[0].text)
        self.assertTrue(items[0].url.endswith("/r/petkit/a"))

if __name__ == "__main__":
    unittest.main()
