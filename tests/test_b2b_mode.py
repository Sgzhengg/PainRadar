import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from painradar.api.app import create_app
from painradar.extract import b2b_identity
from painradar.schema import PainAtom
from painradar.scoring import score_clusters
from painradar.store import Store


class B2BIdentityTests(unittest.TestCase):
    def test_owner_signals(self):
        role, score = b2b_identity("我是开厂的，厂里人工成本太高，接单报价都靠 Excel")
        self.assertEqual(role, "老板")
        self.assertGreaterEqual(score, 2)

    def test_employee_signals(self):
        role, score = b2b_identity("店里员工排班总是乱，客户投诉")
        self.assertEqual(role, "员工")
        self.assertGreaterEqual(score, 1)

    def test_consumer_has_no_signal(self):
        self.assertEqual(b2b_identity("这个 App 挺好用，界面也好看"), ("", 0))


def _atom(i: int, b2b: int, role: str = "") -> PainAtom:
    return PainAtom(
        atom_id=f"pa_{i}",
        comment_uid=f"cm_{i}",
        quote="厂里人工成本太高，接单报价全靠人工",
        span_start=0,
        span_end=10,
        match_score="exact",
        scene="报价接单",
        trigger="",
        job="报价",
        obstacle="人工成本高",
        workaround="Excel",
        cost_type="labor",
        cost_estimate="2 人",
        persona="小厂老板",
        intensity=4,
        expression="complaint",
        level="L3",
        wtp_level="strong",
        wtp_quote="愿意付费",
        domain="manufacturing",
        confidence=0.8,
        model_version="t",
        prompt_version="t",
        taxonomy_version="t",
        run_id="r",
        canonical_pain="报价效率低",
        buyer_role=role,
        b2b_score=b2b,
    )


class B2BScoringTests(unittest.TestCase):
    def test_buyer_factor_moves_score(self):
        atoms = [_atom(i, 3, "老板") for i in range(4)]
        b2c = score_clusters({"pc": atoms}, {a.atom_id: f"u{i}" for i, a in enumerate(atoms)}, mode="b2c")[0]
        b2b = score_clusters({"pc": atoms}, {a.atom_id: f"u{i}" for i, a in enumerate(atoms)}, mode="b2b")[0]
        self.assertGreater(b2b.factors["buyer"], 0)
        self.assertNotEqual(round(b2c.pain, 1), round(b2b.pain, 1))


class B2BOutreachTests(unittest.TestCase):
    def test_b2b_icebreaker_and_role(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "b2b.db"
            store = Store(db)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            store.save_run("run_b2b", "pet_water_fountain", {"mode": "b2b"})
            store.insert_clusters(
                "run_b2b",
                [{"cluster_id": "cl_1", "label": "报价接单", "size": 1, "noise": 0,
                  "medoid_atom_id": "pa_1", "members": ["pa_1"]}],
                {"pa_1": "cl_1"},
            )
            store.insert_item({
                "comment_uid": "pa_1", "platform": "xhs", "item_id": "n1",
                "url": "https://example.com/n1", "published_at": "2026-11-01",
                "lang": "zh", "category": "pet_water_fountain",
                "text_masked": "厂里人工成本太高，接单报价全靠人工",
                "text_sha": "s1", "author_key": "a1", "rating": None, "tier": "A",
                "tos_basis": "user_provided", "minhash_json": "[]", "duplicate_of": None,
                "ingested_at": now, "parent_context": "", "likes": 99, "replies": 0, "post_id": "n1",
            })
            store.insert_atoms([{
                "atom_id": "pa_1", "run_id": "run_b2b", "comment_uid": "pa_1",
                "quote": "厂里人工成本太高，接单报价全靠人工", "span_start": 0, "span_end": 10,
                "match_score": "exact", "scene": "报价接单", "trigger": "", "job": "报价",
                "obstacle": "人工成本高", "workaround": "Excel", "cost_type": "labor",
                "cost_estimate": "2 人", "persona": "小厂老板", "intensity": 4,
                "expression": "complaint", "level": "L3", "wtp_level": "strong",
                "wtp_quote": "愿意付费", "domain": "manufacturing", "confidence": 0.8,
                "model_version": "t", "prompt_version": "t", "taxonomy_version": "t",
                "supersedes": None, "canonical_pain": "报价效率低",
                "buyer_role": "老板", "b2b_score": 3, "created_at": now,
            }])
            store.close()

            client = TestClient(create_app([str(db)]))
            res = client.get("/api/runs/run_b2b/clusters/cl_1/outreach.csv?mode=b2b")
            self.assertEqual(res.status_code, 200)
            text = res.content.decode("utf-8-sig")
            self.assertIn("buyer_role", text)
            self.assertIn("老板您好", text)
            self.assertIn("Demo", text)
            self.assertNotIn("免费内测", text)


if __name__ == "__main__":
    unittest.main()
