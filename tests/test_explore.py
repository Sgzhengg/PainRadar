import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from painradar import config
from painradar import explore as explore_mod
from painradar.api.app import create_app
from painradar.api.jobs import Job, JobRegistry
from painradar.store import Store


def _atom(i: int, quote: str, level: str = "L3") -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "atom_id": f"pa_{i}", "run_id": "run_explore", "comment_uid": f"cm_{i}",
        "quote": quote, "span_start": 0, "span_end": len(quote),
        "match_score": "exact", "scene": "PDF 合并", "trigger": "", "job": "合并",
        "obstacle": "付费墙", "workaround": "截图", "cost_type": "money",
        "cost_estimate": "30", "persona": "小团队运营", "intensity": 4,
        "expression": "complaint", "level": level, "wtp_level": "strong",
        "wtp_quote": "愿意付费", "domain": "pdf", "confidence": 0.8,
        "model_version": "t", "prompt_version": "t", "taxonomy_version": "t",
        "supersedes": None, "canonical_pain": "合并收费", "created_at": now,
    }


class ExploreApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.db = base / "explore.db"
        store = Store(self.db)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        store.save_run("run_explore", "pet_water_fountain", {"items": 2})
        store.insert_clusters(
            "run_explore",
            [{"cluster_id": "cl_pdf", "label": "PDF 合并收费", "size": 2, "noise": 0,
              "medoid_atom_id": "pa_1", "members": ["pa_1", "pa_2"]}],
            {"pa_1": "cl_pdf", "pa_2": "cl_pdf"},
        )
        for i, quote in enumerate(("合并个 PDF 也要开会员，最后只能截图", "公司每周都要合并报表，付费墙太烦")):
            store.insert_item({
                "comment_uid": f"cm_{i}", "platform": "xhs", "item_id": f"n{i}",
                "url": f"https://example.com/{i}", "published_at": "2026-11-01",
                "lang": "zh", "category": "pet_water_fountain", "text_masked": quote,
                "text_sha": f"s{i}", "author_key": f"a{i}", "rating": None, "tier": "A",
                "tos_basis": "user_provided", "minhash_json": "[]", "duplicate_of": None,
                "ingested_at": now, "parent_context": "", "likes": 100 - i * 10,
                "replies": 0, "post_id": f"n{i}",
            })
        store.insert_atoms([
            _atom(1, "合并个 PDF 也要开会员，最后只能截图"),
            _atom(2, "公司每周都要合并报表，付费墙太烦"),
        ])
        store.close()

        explore_mod.SESSION_DIR = base / "sessions"
        explore_mod.MEMORY_PATH = base / "memory.json"
        self.client = TestClient(create_app([str(self.db)]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_start_returns_evidence_and_directions(self):
        res = self.client.post(
            "/api/explore/sessions", json={"seed": "我想做 PDF 相关的东西"}
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["seed"], "我想做 PDF 相关的东西")
        self.assertTrue(body["evidence"])
        self.assertTrue(body["directions"])
        self.assertTrue(body["directions"][0]["evidence"])
        self.assertIn("question", body)
        self.assertTrue(Path(explore_mod.SESSION_DIR, f"{body['session_id']}.json").exists())

    def test_turn_records_reaction(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        sid = start["session_id"]
        res = self.client.post(
            f"/api/explore/sessions/{sid}/turn",
            json={"message": "第一条有点意思", "reaction": {"title": "PDF 合并收费", "reaction": "like"}},
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(len(body["reactions"]), 1)
        self.assertGreaterEqual(len(body["messages"]), 3)

    def test_converge_returns_brief(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        res = self.client.post(f"/api/explore/sessions/{start['session_id']}/converge")
        self.assertEqual(res.status_code, 200)
        markdown = res.json()["markdown"]
        self.assertIn("评论证据", markdown)
        self.assertIn("下一步验证", markdown)

    def test_unknown_session(self):
        self.assertEqual(self.client.get("/api/explore/sessions/nope").status_code, 404)

    def test_pressure_rounds_progress(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        sid = start["session_id"]
        self.assertEqual(start["probe"]["kind"], "direction")

        first = self.client.post(
            f"/api/explore/sessions/{sid}/turn",
            json={"message": "第一条有点意思", "reaction": {"title": "PDF 合并收费", "reaction": "like"}},
        ).json()
        self.assertEqual(first["probe"]["kind"], "counterfactual")

        second = self.client.post(
            f"/api/explore/sessions/{sid}/turn", json={"message": "他们其实能忍"}
        ).json()
        self.assertEqual(second["probe"]["kind"], "payment")

    def test_converge_has_payment_hypothesis(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        markdown = self.client.post(f"/api/explore/sessions/{start['session_id']}/converge").json()["markdown"]
        self.assertIn("付费假设", markdown)

    def test_validate_without_crawler_config(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        with patch.object(config, "MEDIACRAWLER_API_URL", ""):
            res = self.client.post(
                f"/api/explore/sessions/{start['session_id']}/validate",
                json={"platform": "xhs", "keywords": ["PDF"]},
            )
        self.assertEqual(res.status_code, 400)

    def test_validate_creates_category_and_job(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        fake = Job(job_id="job_test", category="custom_x", extractor="rule")
        with patch.object(config, "MEDIACRAWLER_API_URL", "http://crawler.test"), \
             patch.object(config, "CUSTOM_PATH", Path(self.tmp.name) / "custom.json"), \
             patch.object(JobRegistry, "submit_remote_fetch", return_value=fake):
            res = self.client.post(
                f"/api/explore/sessions/{start['session_id']}/validate",
                json={"platform": "xhs", "keywords": ["PDF 合并"], "max_notes": 20},
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["category"].startswith("custom_"))
        self.assertEqual(body["job"]["job_id"], "job_test")
        self.assertEqual(body["keywords"], ["PDF 合并"])
        stored = self.client.get(f"/api/explore/sessions/{start['session_id']}").json()
        self.assertEqual(stored["validation"]["category"], body["category"])
        self.assertEqual(stored["validation"]["job_id"], "job_test")

    def test_validation_result_reflects_back(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        res = self.client.post(
            f"/api/explore/sessions/{start['session_id']}/validation-result",
            json={"run_id": "run_explore"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn(body["verdict"], ("supports", "weakens", "insufficient"))
        self.assertTrue(body["summary"])
        self.assertEqual(body["metrics"]["atoms"], 2)

        stored = self.client.get(f"/api/explore/sessions/{start['session_id']}").json()
        self.assertEqual(stored["validation_result"]["verdict"], body["verdict"])
        self.assertGreaterEqual(len(stored["messages"]), 3)

    def test_validation_memory_used_by_next_session(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        self.client.post(
            f"/api/explore/sessions/{start['session_id']}/validation-result",
            json={"run_id": "run_explore"},
        )
        self.assertTrue(explore_mod.MEMORY_PATH.exists())

        again = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        self.assertTrue(again["memory"])
        notes = [
            d.get("memory_note")
            for msg in again["messages"]
            for d in (msg.get("directions") or [])
            if d.get("memory_note")
        ]
        self.assertTrue(notes)

    def test_payment_answer_is_remembered(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        sid = start["session_id"]
        self.client.post(f"/api/explore/sessions/{sid}/turn", json={"message": "第一条有点意思"})
        self.client.post(f"/api/explore/sessions/{sid}/turn", json={"message": "他们其实能忍"})
        self.client.post(f"/api/explore/sessions/{sid}/turn", json={"message": "老板会买，走公司报销"})

        again = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        answers = [m.get("answer", "") for m in again["memory"] if m.get("answer")]
        self.assertIn("老板会买，走公司报销", answers)

    def test_memory_endpoints(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        self.client.post(
            f"/api/explore/sessions/{start['session_id']}/validation-result",
            json={"run_id": "run_explore"},
        )
        memory = self.client.get("/api/explore/memory").json()
        self.assertTrue(memory["directions"])

        item = memory["directions"][0]
        res = self.client.post(
            "/api/explore/memory/delete",
            json={"kind": "directions", "seed": item["seed"], "title": item["title"]},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["directions"], [])

        self.assertEqual(self.client.delete("/api/explore/memory").status_code, 200)
        self.assertEqual(self.client.get("/api/explore/memory").json()["directions"], [])

    def test_draft_from_direction(self):
        start = self.client.post("/api/explore/sessions", json={"seed": "PDF"}).json()
        sid = start["session_id"]
        self.client.post(f"/api/explore/sessions/{sid}/validation-result", json={"run_id": "run_explore"})
        res = self.client.post(f"/api/explore/sessions/{sid}/draft")
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["draft"]["title"])
        self.assertGreaterEqual(len(body["draft"]["mvp_scope"]), 3)
        self.assertIn("7 天验证计划", body["markdown"])

        stored = self.client.get(f"/api/explore/sessions/{sid}").json()
        self.assertIn("draft_markdown", stored)


if __name__ == "__main__":
    unittest.main()
