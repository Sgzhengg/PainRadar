import json
import unittest

import httpx

from painradar.store import CloudflareD1Store, D1Connection, Store, SQLiteStore


class D1StoreTests(unittest.TestCase):
    def _connection(self):
        seen = {"queries": 0, "last_sql": ""}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["queries"] += 1
            body = json.loads(request.content)
            sql = (body.get("sql") or "").strip()
            seen["last_sql"] = sql
            params = body.get("params") or []
            if sql.upper().startswith("PRAGMA"):
                return httpx.Response(200, json={"success": True, "result": [{"results": []}]})
            if sql.upper().startswith("SELECT") and "FROM runs" in sql:
                row = {
                    "run_id": "r1",
                    "category": params[0] if params else "cat",
                    "created_at": "2026-11-21T00:00:00Z",
                    "stats_json": "{}",
                }
                return httpx.Response(200, json={"success": True, "result": [{"results": [row]}]})
            return httpx.Response(200, json={"success": True, "result": [{"results": []}]})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        return D1Connection("acc", "db", "token", client=client), seen

    def test_bootstrap_and_run_roundtrip(self):
        conn, seen = self._connection()
        store = CloudflareD1Store(conn)
        self.assertTrue(seen["queries"] > 0)  # schema created

        store.save_run("r1", "pet_water_fountain", {"items": 3})
        row = store.latest_run("pet_water_fountain")
        self.assertIsNotNone(row)
        self.assertEqual(row["run_id"], "r1")

    def test_insert_item_returns_true(self):
        conn, _ = self._connection()
        store = CloudflareD1Store(conn)
        ok = store.insert_item(
            {
                "comment_uid": "cm_1",
                "platform": "xhs",
                "item_id": "n1_c1",
                "url": "https://example.com/1",
                "published_at": "2026-11-01",
                "lang": "zh",
                "category": "pet_water_fountain",
                "text_masked": "取消订阅入口找不到",
                "text_sha": "sha1",
                "author_key": "a1",
                "rating": None,
                "tier": "A",
                "tos_basis": "user_provided",
                "minhash_json": "[]",
                "duplicate_of": None,
                "ingested_at": "2026-11-21",
                "parent_context": "原帖",
                "likes": 10,
                "replies": 1,
                "post_id": "n1",
            }
        )
        self.assertTrue(ok)

    def test_d1_errors_are_typed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"success": False, "errors": [{"message": "bad sql"}]})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        conn = D1Connection("acc", "db", "token", client=client)
        from painradar.store import StoreError

        with self.assertRaises(StoreError):
            conn.execute("SELECT 1")

    def test_sqlite_remains_default(self):
        store = Store(":memory:")
        self.assertIsInstance(store, SQLiteStore)
        store.close()


if __name__ == "__main__":
    unittest.main()
