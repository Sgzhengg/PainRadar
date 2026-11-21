"""Connector and anchor tests — fully offline via an injected transport."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from painradar.anchors import AnchorObs, ItunesAnchor, import_csv, sample_coverage
from painradar.connectors.appstore import AppStoreConnector
from painradar.connectors.reddit import RedditConnector
from painradar.net import HttpClient, Response
from painradar.pipeline import ingest_items
from painradar.store import Store


class FakeTransport:
    """Prefix-matched fake HTTP transport."""

    def __init__(self, routes: dict[str, tuple[int, object]]):
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(url)
        for prefix, (status, payload) in self.routes.items():
            if prefix in url:
                raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                return Response(status, {}, raw)
        return Response(404, {}, b"{}")


def _client(routes: dict[str, tuple[int, object]]) -> HttpClient:
    return HttpClient(
        user_agent="test",
        transport=FakeTransport(routes),
        sleep=lambda _: None,
        rate_per_sec=1000,
    )


REDDIT_SEARCH = {
    "data": {
        "children": [
            {
                "kind": "t3",
                "data": {
                    "id": "p1",
                    "title": "Fountain pump is too loud at night",
                    "selftext": "I live in a studio and cannot sleep with it on.",
                    "permalink": "/r/cats/p1",
                    "created_utc": 1751328000,
                    "author": "alice",
                },
            }
        ]
    }
}

REDDIT_COMMENTS = [
    {"kind": "Listing"},
    {
        "data": {
            "children": [
                {
                    "kind": "t1",
                    "data": {
                        "id": "c1",
                        "body": "The motor noise keeps waking me up, I ended up moving it to the bathroom.",
                        "permalink": "/r/cats/p1/c1",
                        "created_utc": 1751414400,
                        "author": "bob",
                    },
                },
                {
                    "kind": "t1",
                    "data": {
                        "id": "c2",
                        "body": "[deleted]",
                        "permalink": "/r/cats/p1/c2",
                        "created_utc": 1751414400,
                        "author": "[deleted]",
                    },
                },
            ]
        }
    },
]

APPSTORE_FEED = {
    "feed": {
        "entry": [
            {"id": {"label": "app-meta"}, "im:name": {"label": "Fountain App"}},
            {
                "id": {"label": "r1"},
                "title": {"label": "Too loud"},
                "content": {"label": "The pump hum is unbearable at night and my cat stopped drinking."},
                "im:rating": {"label": "2"},
                "author": {"name": {"label": "carol"}},
                "updated": {"label": "2026-07-02T10:00:00-07:00"},
                "link": {"attributes": {"href": "https://apps.apple.com/review/r1"}},
            },
            {
                "id": {"label": "r2"},
                "title": {"label": "Mold"},
                "content": {"label": "Mold keeps growing in the corners and I have to scrub it weekly."},
                "im:rating": {"label": "1"},
                "author": {"name": {"label": "dave"}},
                "updated": {"label": "2026-07-03T10:00:00-07:00"},
                "link": {"attributes": {"href": "https://apps.apple.com/review/r2"}},
            },
        ]
    }
}

ITUNES_LOOKUP = {
    "resultCount": 1,
    "results": [
        {
            "trackName": "Pet Fountain",
            "averageUserRating": 3.9,
            "userRatingCount": 12345,
            "trackViewUrl": "https://apps.apple.com/app/id123",
        }
    ],
}


class TestRedditConnector(unittest.TestCase):
    def setUp(self):
        self.client = _client({
            "/r/cats/search.json": (200, REDDIT_SEARCH),
            "/comments/p1.json": (200, REDDIT_COMMENTS),
        })
        self.conn = RedditConnector(
            category="pet_water_fountain",
            query="fountain noise",
            subreddits=["cats"],
            limit=10,
            client=self.client,
        )

    def test_yields_post_and_comments(self):
        items = list(self.conn.fetch())
        self.assertEqual(len(items), 2)  # post + one valid comment (deleted skipped)
        post, comment = items
        self.assertEqual(post.platform, "reddit")
        self.assertIn("Fountain pump", post.text)
        self.assertEqual(comment.item_id, "t1_c1")
        self.assertIn("motor noise", comment.text)
        self.assertEqual(comment.published_at, "2025-07-02")

    def test_skips_deleted_authors(self):
        items = list(self.conn.fetch())
        self.assertTrue(all("deleted" not in (i.author or "") for i in items))

    def test_health_reports_mode(self):
        self.assertFalse(self.conn.health()["oauth"])


class TestAppStoreConnector(unittest.TestCase):
    def test_parses_reviews_and_skips_metadata(self):
        client = _client({"/rss/customerreviews/page=1/": (200, APPSTORE_FEED)})
        conn = AppStoreConnector(category="pet_water_fountain", app_id="123", pages=1, client=client)
        items = list(conn.fetch())
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].rating, 2.0)
        self.assertIn("Too loud", items[0].text)
        self.assertEqual(items[0].published_at, "2026-07-02")


class TestAnchors(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="painradar-anchor-"))
        self.store = Store(self.tmp / "a.db")

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_itunes_anchor(self):
        client = _client({"/lookup": (200, ITUNES_LOOKUP)})
        obs = ItunesAnchor(category="pet_water_fountain", app_id="123", client=client).fetch()
        self.assertEqual({o.metric for o in obs}, {"rating_count", "avg_rating"})
        self.assertTrue(all(o.grade == "A" for o in obs))

    def test_csv_import_and_coverage(self):
        path = self.tmp / "anchors.csv"
        path.write_text(
            "metric,value,source,as_of,url,grade,note\n"
            "rating_count,20000,keepa,2026-10-01,https://x,A,asin B0X\n"
            "price,29.99,keepa,2026-10-01,https://x,B,\n",
            encoding="utf-8",
        )
        n = import_csv(self.store, path, "pet_water_fountain")
        self.assertEqual(n, 2)
        rows = {r["metric"]: r for r in self.store.anchors("pet_water_fountain")}
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows["rating_count"]["grade"], "A")
        self.assertEqual(rows["rating_count"]["value"], 20000)

    def test_anchor_id_is_stable(self):
        a = AnchorObs("c", "itunes", "rating_count", 10, "2026-01-01")
        b = AnchorObs("c", "itunes", "rating_count", 10, "2026-01-01")
        self.assertEqual(a.anchor_id(), b.anchor_id())


class TestConnectorIngest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="painradar-conn-"))
        self.store = Store(self.tmp / "c.db")

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ingest_connector_output(self):
        client = _client({
            "/r/cats/search.json": (200, REDDIT_SEARCH),
            "/comments/p1.json": (200, REDDIT_COMMENTS),
        })
        conn = RedditConnector(
            category="pet_water_fountain", query="q", subreddits=["cats"], limit=5, client=client
        )
        result = ingest_items(self.store, conn.fetch(), "pet_water_fountain")
        self.assertEqual(result.inserted, 2)
        self.assertEqual(self.store.items("pet_water_fountain")[0]["platform"], "reddit")


if __name__ == "__main__":
    unittest.main()
