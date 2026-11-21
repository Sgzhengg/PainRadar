import inspect
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from painradar.api.app import create_app
from painradar.extract import FIELD_SPEC, SYSTEM_PROMPT, LLMExtractor
from painradar.pipeline import ingest_items  # noqa: F401  (ensures store wiring)
from painradar.schema import PainAtom, RawItem
from painradar.scoring import assess_solo_fit
from painradar.store import Store


def _atom(atom_id: str, text: str, level: str = "L2") -> PainAtom:
    return PainAtom(
        atom_id=atom_id,
        comment_uid="cm_" + atom_id,
        quote=text,
        span_start=0,
        span_end=len(text),
        match_score="exact",
        scene="订阅取消",
        trigger="",
        job="取消订阅",
        obstacle=text,
        workaround="发邮件",
        cost_type="",
        cost_estimate="",
        persona="",
        intensity=4,
        expression="complaint",
        level=level,
        wtp_level="weak",
        wtp_quote="",
        domain="",
        confidence=0.8,
        model_version="test",
        prompt_version="test",
        taxonomy_version="test",
        run_id="run1",
        canonical_pain="订阅取消入口难找",
    )


class SoloFitTests(unittest.TestCase):
    def test_software_is_low(self):
        fit = assess_solo_fit([_atom("a1", "网页插件导出总是失败，只能手动复制")])
        self.assertEqual(fit["level"], "低")
        self.assertEqual(fit["form"], "浏览器插件")

    def test_hardware_is_high(self):
        fit = assess_solo_fit([_atom("a2", "门锁电池没电就进不了门，还要上门安装")])
        self.assertEqual(fit["level"], "高")
        self.assertLess(fit["score"], 0.5)


class SingleRunTests(unittest.TestCase):
    def test_default_single_run(self):
        sig = inspect.signature(LLMExtractor.__init__)
        self.assertFalse(sig.parameters["consistency"].default)

    def test_cot_fields_present(self):
        self.assertIn("reasoning", FIELD_SPEC)
        self.assertIn("canonical_pain", FIELD_SPEC)
        self.assertIn("reasoning", SYSTEM_PROMPT)


class OutreachCsvTests(unittest.TestCase):
    def test_csv_sorted_and_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            store = Store(db)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            store.save_run("run1", "pet_water_fountain", {"levels": {"L1": 1, "L2": 2}})
            store.insert_clusters(
                "run1",
                [{"cluster_id": "cl_1", "label": "订阅取消", "size": 3, "noise": 0,
                  "medoid_atom_id": "pa_1", "members": ["pa_1", "pa_2", "pa_3"]}],
                {"pa_1": "cl_1", "pa_2": "cl_1", "pa_3": "cl_1"},
            )
            for i, (cid, likes) in enumerate((("pa_1", 10), ("pa_2", 286), ("pa_3", 1))):
                store.insert_item({
                    "comment_uid": cid,
                    "platform": "xiaohongshu",
                    "item_id": f"n1_{cid}",
                    "url": f"https://example.com/{cid}",
                    "published_at": "2026-11-01",
                    "lang": "zh",
                    "category": "pet_water_fountain",
                    "text_masked": "取消订阅的入口根本找不到",
                    "text_sha": f"sha{i}",
                    "author_key": f"au{i}",
                    "rating": None,
                    "tier": "A",
                    "tos_basis": "user_provided",
                    "minhash_json": "[]",
                    "duplicate_of": None,
                    "ingested_at": now,
                    "parent_context": "原帖",
                    "likes": likes,
                    "replies": 0,
                    "post_id": "n1",
                })
            store.insert_atoms([
                {
                    "atom_id": "pa_1", "run_id": "run1", "comment_uid": "pa_1",
                    "quote": "取消订阅的入口根本找不到", "span_start": 0, "span_end": 12,
                    "match_score": "exact", "scene": "订阅取消", "trigger": "", "job": "取消",
                    "obstacle": "入口难找", "workaround": "发邮件", "cost_type": "",
                    "cost_estimate": "", "persona": "", "intensity": 4, "expression": "complaint",
                    "level": "L2", "wtp_level": "weak", "wtp_quote": "", "domain": "",
                    "confidence": 0.8, "model_version": "t", "prompt_version": "t",
                    "taxonomy_version": "t", "supersedes": None, "canonical_pain": "订阅取消",
                    "created_at": now,
                },
                {
                    "atom_id": "pa_2", "run_id": "run1", "comment_uid": "pa_2",
                    "quote": "取消订阅的入口根本找不到", "span_start": 0, "span_end": 12,
                    "match_score": "exact", "scene": "订阅取消", "trigger": "", "job": "取消",
                    "obstacle": "入口难找", "workaround": "发邮件", "cost_type": "",
                    "cost_estimate": "", "persona": "", "intensity": 4, "expression": "complaint",
                    "level": "L3", "wtp_level": "weak", "wtp_quote": "", "domain": "",
                    "confidence": 0.8, "model_version": "t", "prompt_version": "t",
                    "taxonomy_version": "t", "supersedes": None, "canonical_pain": "订阅取消",
                    "created_at": now,
                },
                {
                    "atom_id": "pa_3", "run_id": "run1", "comment_uid": "pa_3",
                    "quote": "太烦了", "span_start": 0, "span_end": 3,
                    "match_score": "exact", "scene": "订阅取消", "trigger": "", "job": "",
                    "obstacle": "", "workaround": "", "cost_type": "",
                    "cost_estimate": "", "persona": "", "intensity": 2, "expression": "complaint",
                    "level": "L1", "wtp_level": "none", "wtp_quote": "", "domain": "",
                    "confidence": 0.6, "model_version": "t", "prompt_version": "t",
                    "taxonomy_version": "t", "supersedes": None, "canonical_pain": "",
                    "created_at": now,
                },
            ])
            store.close()

            client = TestClient(create_app([str(db)]))
            res = client.get("/api/runs/run1/clusters/cl_1/outreach.csv")
            self.assertEqual(res.status_code, 200)
            text = res.content.decode("utf-8-sig")
            lines = text.strip().splitlines()
            self.assertEqual(lines[0].split(",")[0], "url")
            # L1 excluded; highest likes first
            self.assertEqual(len(lines), 3)
            self.assertIn("286", lines[1])
            self.assertIn("icebreaker", lines[0])


if __name__ == "__main__":
    unittest.main()
