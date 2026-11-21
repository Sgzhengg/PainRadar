"""HTTP API tests (FastAPI TestClient)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from painradar.api.app import create_app
from painradar.pipeline import ingest_file, run_category
from painradar.store import Store

ROWS = [
    ("The pump noise is terrible at night. I ended up moving it to the bathroom.", "u1"),
    ("At night the motor noise keeps waking me up. I use a towel under it.", "u2"),
    ("Loud pump noise at night, so I switched to bowls in the bedroom.", "u3"),
    ("Mold keeps growing in the corners. I scrub it with a toothbrush twice a week.", "u4"),
    ("The basin is hard to clean and mold builds up. I use a bottle brush now.", "u5"),
    ("Cleaning takes forever because mold grows under the seal. I soak it in vinegar.", "u6"),
]


class TestApi(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="painradar-api-"))
        self.db = self.tmp / "api.db"
        data = self.tmp / "rows.jsonl"
        with data.open("w", encoding="utf-8") as fh:
            for i, (text, author) in enumerate(ROWS):
                fh.write(json.dumps({
                    "platform": "unit", "item_id": f"as_1_{i}", "url": f"https://x/{i}",
                    "text": text, "published_at": f"2026-07-{i + 1:02d}", "author": author,
                }, ensure_ascii=False) + "\n")
        store = Store(self.db)
        ingest_file(store, data, "pet_water_fountain")
        self.run = run_category(store, "pet_water_fountain", min_size=2)
        store.close()
        self.client = TestClient(create_app([str(self.db)]))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_health(self) -> None:
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

    def test_runs_list(self) -> None:
        res = self.client.get("/api/runs")
        self.assertEqual(res.status_code, 200)
        runs = res.json()["runs"]
        self.assertGreaterEqual(len(runs), 1)
        self.assertEqual(runs[0]["category"], "pet_water_fountain")
        self.assertEqual(runs[0]["category_name"], "宠物智能设备")

    def test_run_detail_has_opportunities(self) -> None:
        res = self.client.get(f"/api/runs/{self.run.run_id}")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["category"], "pet_water_fountain")
        self.assertTrue(body["opportunities"])
        opp = body["opportunities"][0]
        self.assertIn("members", opp)
        self.assertLessEqual(len(opp["members"]), 12)
        self.assertIn("hotness", opp)
        self.assertIn("inspiration_score", opp)
        self.assertIn("inspiration_tag", opp)
        self.assertIn("ai_fit", opp)
        scores = [o["inspiration_score"] for o in body["opportunities"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_members_pagination(self) -> None:
        detail = self.client.get(f"/api/runs/{self.run.run_id}").json()
        cluster_id = detail["opportunities"][0]["cluster_id"]
        res = self.client.get(
            f"/api/runs/{self.run.run_id}/members",
            params={"cluster_id": cluster_id, "offset": 0, "limit": 1},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertGreaterEqual(body["total"], 1)
        self.assertEqual(len(body["items"]), 1)

    def test_anchors_endpoint(self) -> None:
        res = self.client.get("/api/anchors", params={"category": "pet_water_fountain"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("anchors", res.json())

    def test_index_serves_spa(self) -> None:
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("PainRadar", res.text)
        self.assertIn("/static/app.js", res.text)

    def test_unknown_run_404(self) -> None:
        self.assertEqual(self.client.get("/api/runs/nope").status_code, 404)

    def test_categories_endpoint(self) -> None:
        res = self.client.get("/api/categories")
        self.assertEqual(res.status_code, 200)
        cats = {c["category"]: c for c in res.json()["categories"]}
        self.assertIn("pet_water_fountain", cats)
        self.assertGreaterEqual(cats["pet_water_fountain"]["items"], 6)
        self.assertEqual(cats["pet_water_fountain"]["name"], "宠物智能设备")

    def test_custom_category_requires_confirmed_apps(self) -> None:
        res = self.client.post("/api/categories/custom", json={"name": "咖啡机", "term": "coffee maker"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("apps", res.json()["detail"])

    def test_custom_category_requires_fields(self) -> None:
        res = self.client.post("/api/categories/custom", json={"name": "", "term": ""})
        self.assertEqual(res.status_code, 400)

    def test_register_custom_category(self) -> None:
        import json as _json

        from painradar.config import CATEGORIES, register_custom_category

        path = self.tmp / "custom.json"
        key = register_custom_category("咖啡机", "coffee maker", {"1": "Coffee App"}, path=path)
        self.assertTrue(key.startswith("custom_"))
        self.assertIn(key, CATEGORIES)
        spec = CATEGORIES[key]
        self.assertEqual(spec.name, "咖啡机")
        self.assertIn("coffee", spec.domain_terms)
        self.assertIn("功能与故障", spec.scenes)
        data = _json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data[key]["app_names"]["1"], "Coffee App")
        CATEGORIES.pop(key, None)

    def test_manual_run_rule(self) -> None:
        import time

        before = len(self.client.get("/api/runs").json()["runs"])
        res = self.client.post("/api/run", json={"category": "pet_water_fountain", "extractor": "rule"})
        self.assertEqual(res.status_code, 202)
        job_id = res.json()["job"]["job_id"]
        for _ in range(60):
            job = self.client.get(f"/api/run/{job_id}").json()["job"]
            if job["status"] in ("done", "failed"):
                break
            time.sleep(0.2)
        self.assertEqual(job["status"], "done", job.get("error"))
        self.assertTrue(job["run_id"])
        after = self.client.get("/api/runs").json()["runs"]
        self.assertEqual(len(after), before + 1)

    def test_manual_run_rejects_unknown_category(self) -> None:
        res = self.client.post("/api/run", json={"category": "nope", "extractor": "rule"})
        self.assertEqual(res.status_code, 400)


    def test_solutions_endpoint_returns_snapshot(self) -> None:
        res = self.client.get("/api/solutions")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), dict)

if __name__ == "__main__":
    unittest.main()
