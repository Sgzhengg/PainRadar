"""Unit and integration tests (stdlib unittest, no network)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from painradar.cluster import cluster_atoms
from painradar.config import CATEGORIES, category
from painradar.extract import RuleExtractor, SpanGate, prepare_text
from painradar.pipeline import ingest_file, run_category
from painradar.report import render_markdown
from painradar.schema import PainAtom, RawItem
from painradar.scoring import estimate_market, score_clusters
from painradar.store import Store
from painradar.textproc import (
    detect_lang,
    jaccard_estimate,
    mask_pii,
    minhash,
    normalize_text,
    tokenize,
)


class TestTextProc(unittest.TestCase):
    def test_normalize_collapses_whitespace_and_width(self):
        self.assertEqual(normalize_text("Ｈｅｌｌｏ   world\n"), "Hello world")

    def test_mask_pii_removes_direct_identifiers(self):
        raw = "contact me at a.b@example.com or +86 13800138000, wechat: abc_12345, https://x.co/1"
        masked = mask_pii(raw)
        for token in ("[EMAIL]", "[PHONE]", "[WECHAT]", "[URL]"):
            self.assertIn(token, masked)
        self.assertNotIn("a.b@example.com", masked)
        self.assertNotIn("13800138000", masked)

    def test_detect_lang(self):
        self.assertEqual(detect_lang("这个饮水机太吵了"), "zh")
        self.assertEqual(detect_lang("the pump is too loud"), "en")

    def test_minhash_near_duplicate(self):
        a = tokenize("the pump noise is terrible at night and my cat refuses to drink")
        b = tokenize("the pump noise is terrible at night and my cat refuses to drink water")
        c = tokenize("I bought a new tent for camping last weekend")
        self.assertGreater(jaccard_estimate(minhash(a), minhash(b)), 0.6)
        self.assertLess(jaccard_estimate(minhash(a), minhash(c)), 0.2)


class TestSpanGate(unittest.TestCase):
    def setUp(self):
        self.gate = SpanGate()
        self.text = "The pump is so loud at night. I ended up moving it to the bathroom."

    def test_exact(self):
        loc = self.gate.locate("I ended up moving it to the bathroom", self.text)
        self.assertIsNotNone(loc)
        self.assertEqual(loc[2], "exact")
        self.assertEqual(self.text[loc[0]:loc[1]], "I ended up moving it to the bathroom")

    def test_normalized_handles_fullwidth(self):
        text = "这个饮水机太吵了，我只好搬到卫生间。"
        loc = self.gate.locate("这个饮水机太吵了", text)
        self.assertIsNotNone(loc)
        self.assertEqual(loc[2], "exact")

    def test_reject_when_absent(self):
        self.assertIsNone(self.gate.locate("this sentence does not exist anywhere", self.text))

    def test_reject_short(self):
        self.assertIsNone(self.gate.locate("loud", self.text))


class TestExtractor(unittest.TestCase):
    def setUp(self):
        self.spec = category("pet_water_fountain")
        self.ex = RuleExtractor(self.spec)
        self.gate = SpanGate()

    def _extract(self, text: str) -> PainAtom | None:
        masked, _ = prepare_text(text)
        raw = RawItem("test", "1", "https://x", masked, "2026-07-01", self.spec.key)
        return self.ex.extract(raw, masked, "cm_test", "run_test")

    def test_quote_is_verbatim_substring(self):
        text = "The pump noise is terrible at night. I ended up moving it to the bathroom."
        atom = self._extract(text)
        self.assertIsNotNone(atom)
        masked, _ = prepare_text(text)
        self.assertEqual(masked[atom.span_start:atom.span_end], atom.quote)

    def test_level_l2_requires_workaround(self):
        text = "The pump noise is terrible at night. I ended up moving it to the bathroom."
        atom = self._extract(text)
        self.assertIn(atom.level, {"L2", "L3", "L4"})
        self.assertTrue(atom.workaround)

    def test_l4_when_already_paid(self):
        text = "I bought three of these in two years and the motor keeps dying."
        atom = self._extract(text)
        self.assertIsNotNone(atom)
        self.assertEqual(atom.level, "L4")

    def test_pure_emotion_is_l1_or_dropped(self):
        atom = self._extract("Ugh. So annoying. Whatever.")
        # "annoying" is a complaint signal but carries no obstacle -> L1, never L2.
        if atom is not None:
            self.assertEqual(atom.level, "L1")
            self.assertFalse(atom.workaround)

    def test_no_signal_dropped(self):
        self.assertIsNone(self._extract("Nice product. Looks good on the counter."))


class TestClusteringAndScoring(unittest.TestCase):
    def _atom(self, i: int, scene: str, obstacle: str, workaround: str = "") -> PainAtom:
        return PainAtom(
            atom_id=f"pa_{i}", comment_uid=f"cm_{i}", quote=f"{obstacle}. {workaround}",
            span_start=0, span_end=10, match_score="exact", scene=scene, trigger="",
            job="job", obstacle=obstacle, workaround=workaround, cost_type="", cost_estimate="",
            persona="多猫家庭", intensity=4, expression="complaint", level="L2",
            wtp_level="none", wtp_quote="", domain="宠物", confidence=0.8,
            model_version="t", prompt_version="t", taxonomy_version="t", run_id="r",
        )

    def test_scene_grouping_and_noise(self):
        atoms = [self._atom(i, "夜间噪音", "pump is loud") for i in range(4)]
        atoms += [self._atom(10 + i, "清洗换水", "mold in corner") for i in range(3)]
        atoms.append(self._atom(99, "其他场景", "unrelated one-off"))
        result = cluster_atoms(atoms, min_size=3)
        self.assertEqual(len(result.clusters), 2)
        self.assertGreater(result.noise_rate, 0)

    def test_scores_in_range_and_ordered(self):
        atoms = [self._atom(i, "夜间噪音", "pump is loud", "moved to bathroom") for i in range(5)]
        result = cluster_atoms(atoms, min_size=3)
        by_cluster = {"pc": atoms}
        scores = score_clusters({"pc": atoms}, {a.atom_id: f"author{i}" for i, a in enumerate(atoms)},
                                {a.atom_id: "2026-07-01" for a in atoms})
        self.assertTrue(scores)
        for s in scores:
            self.assertGreaterEqual(s.pain, 0)
            self.assertLessEqual(s.pain, 100)
            self.assertGreaterEqual(s.opportunity, 0)
            self.assertLessEqual(s.opportunity, 100)
            self.assertIn(s.tier, {"强", "中", "弱"})

    def test_market_range_is_ordered(self):
        spec = CATEGORIES["pet_water_fountain"]
        est = estimate_market(spec.market, spec)
        self.assertLess(est.low, est.mid)
        self.assertLess(est.mid, est.high)
        self.assertTrue(est.falsifier)
        self.assertEqual(len(est.sensitivity), 5)


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="painradar-test-"))
        self.db = self.tmp / "test.db"
        self.data = self.tmp / "sample.jsonl"
        rows = [
            ("The pump noise is terrible at night. I ended up moving it to the bathroom.", "夜间噪音", "u1"),
            ("At night the motor noise keeps waking me up. I use a towel under it.", "夜间噪音", "u2"),
            ("Loud pump noise at night, so I switched to bowls in the bedroom.", "夜间噪音", "u3"),
            ("Mold keeps growing in the corners. I scrub it with a toothbrush twice a week.", "清洗换水", "u4"),
            ("The basin is hard to clean and mold builds up. I use a bottle brush now.", "清洗换水", "u5"),
            ("Cleaning takes forever because mold grows under the seal. I soak it in vinegar.", "清洗换水", "u6"),
            ("The cord is too short for my apartment. I had to use an extension cord.", "电源线", "u7"),
            ("Cable does not reach the outlet, so I run an extension across the floor.", "电源线", "u8"),
            ("The power cord is short and the outlet is far. I use an extension cord now.", "电源线", "u9"),
        ]
        with self.data.open("w", encoding="utf-8") as fh:
            for i, (text, _, author) in enumerate(rows):
                fh.write(json.dumps({
                    "platform": "unit", "item_id": str(i), "url": f"https://x/{i}",
                    "text": text, "published_at": f"2026-07-{i + 1:02d}", "author": author,
                }, ensure_ascii=False) + "\n")
        self.store = Store(self.db)

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_end_to_end(self):
        ing = ingest_file(self.store, self.data, "pet_water_fountain")
        self.assertEqual(ing.inserted, 9)
        run = run_category(self.store, "pet_water_fountain", min_size=3)
        self.assertGreaterEqual(run.stats["clusters"], 2)
        self.assertTrue(run.opportunities)
        md = render_markdown(self.store, run.run_id, self.tmp)
        self.assertTrue(md.exists())
        text = md.read_text(encoding="utf-8")
        self.assertIn("数据与分母", text)
        self.assertIn("证伪条件", text)

    def test_app_payload_shape(self):
        ingest_file(self.store, self.data, "pet_water_fountain")
        run = run_category(self.store, "pet_water_fountain", min_size=3)
        from painradar.appdata import build_payload

        payload = build_payload([(self.store, None)])
        self.assertEqual(len(payload["runs"]), 1)
        item = payload["runs"][0]
        self.assertEqual(item["category_name"], "宠物智能设备")
        self.assertTrue(item["opportunities"])
        opp = item["opportunities"][0]
        for key in ("title", "one_liner", "pain", "opportunity", "members", "ladder"):
            self.assertIn(key, opp)
        self.assertLessEqual(len(opp["members"]), 12)

        # every atom must point at a verbatim span
        for atom in self.store.atoms(run.run_id):
            item = self.store.item(atom["comment_uid"])
            self.assertEqual(item["text_masked"][atom["span_start"]:atom["span_end"]], atom["quote"])

    def test_delete_cascades(self):
        ingest_file(self.store, self.data, "pet_water_fountain")
        run = run_category(self.store, "pet_water_fountain", min_size=3)
        uid = self.store.atoms(run.run_id)[0]["comment_uid"]
        n = self.store.soft_delete(uid)
        self.assertEqual(n, 1)
        self.assertIsNone(self.store.item(uid))

    def test_audit_row_written(self):
        self.store.audit("unit", "fetch", "appstore", "pet_water_fountain", '{"items": 1}')
        row = self.store._conn.execute(
            "SELECT actor, action, object_type, object_id FROM audit ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row["actor"], "unit")
        self.assertEqual(row["action"], "fetch")
        self.assertEqual(row["object_type"], "appstore")
        self.assertEqual(row["object_id"], "pet_water_fountain")

    def test_ingest_is_idempotent(self):
        first = ingest_file(self.store, self.data, "pet_water_fountain")
        second = ingest_file(self.store, self.data, "pet_water_fountain")
        self.assertEqual(first.inserted, 9)
        self.assertEqual(second.inserted, 0)


class TestCategoryScope(unittest.TestCase):
    def test_pet_category_excludes_insurance_sources(self):
        spec = category("pet_water_fountain")
        self.assertIn("1278520013", spec.excluded_apps)
        self.assertEqual(spec.name, "宠物智能设备")
        self.assertEqual(spec.app_names["1586120661"], "Petlibro")

    def test_one_liner_does_not_invent_a_persona(self):
        atom = PainAtom(
            atom_id="pa_x", comment_uid="cm_x", quote="leaks", span_start=0, span_end=5,
            match_score="exact", scene="清洗换水", trigger="", job="", obstacle="底部漏水",
            workaround="", cost_type="", cost_estimate="", persona="", intensity=3,
            expression="complaint", level="L2", wtp_level="none", wtp_quote="", domain="宠物",
            confidence=0.8, model_version="t", prompt_version="t", taxonomy_version="t", run_id="r",
        )
        from painradar.pipeline import _one_liner

        text = _one_liner(atom, category("pet_water_fountain"))
        self.assertIn("用户", text)
        self.assertNotIn("该品类用户", text)


if __name__ == "__main__":
    unittest.main()
