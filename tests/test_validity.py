"""Validity pre-filter tests."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from painradar.config import category
from painradar.pipeline import ingest_file, run_category
from painradar.store import Store
from painradar.validity import ValidityFilter


class TestValidityFilter(unittest.TestCase):
    def setUp(self):
        self.vf = ValidityFilter(category("pet_water_fountain"))

    def test_praise_is_rejected(self):
        v = self.vf.judge("Best litter box I've ever seen. And for 2 cats it works great", 5)
        self.assertFalse(v.valid, v.reasons)

    def test_short_praise_is_rejected(self):
        v = self.vf.judge("Amazing. I should have bought this years ago.", 5)
        self.assertFalse(v.valid, v.reasons)

    def test_complaint_is_accepted(self):
        v = self.vf.judge("The pump noise is terrible at night. I ended up moving it to the bathroom.", 2)
        self.assertTrue(v.valid, v.reasons)

    def test_negated_praise_still_counts_as_pain(self):
        v = self.vf.judge("It's not great. The app keeps disconnecting every day.", 2)
        self.assertTrue(v.valid, v.reasons)

    def test_off_topic_is_rejected(self):
        v = self.vf.judge("The insurance claim was denied and there is no way to cancel the policy.", 1)
        self.assertFalse(v.valid, v.reasons)

    def test_neutral_text_is_conservative(self):
        # No praise, no pain: score 0, not > 0 -> rejected, but extraction is cheap anyway.
        v = self.vf.judge("The box arrived on Tuesday. It is grey.", 3)
        self.assertFalse(v.valid)


class TestPipelineFilter(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="painradar-valid-"))
        self.data = self.tmp / "items.jsonl"
        rows = [
            ("The pump noise is terrible at night. I ended up moving it to the bathroom.", 2),
            ("App keeps disconnecting after the update. I have to restart it twice a day.", 1),
            ("Best fountain I have ever bought. Works great for my two cats.", 5),
            ("The insurance claim was denied and the policy cannot be cancelled.", 1),
        ]
        with self.data.open("w", encoding="utf-8") as fh:
            for i, (text, rating) in enumerate(rows):
                fh.write(json.dumps({
                    "platform": "unit", "item_id": str(i), "url": f"https://x/{i}",
                    "text": text, "published_at": "2026-07-01", "author": f"u{i}", "rating": rating,
                }, ensure_ascii=False) + "\n")
        self.store = Store(self.tmp / "v.db")

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_filter_drops_praise_and_off_topic(self):
        ingest_file(self.store, self.data, "pet_water_fountain")
        run = run_category(self.store, "pet_water_fountain", min_size=1)
        self.assertGreaterEqual(run.stats["validity_filtered"], 2)
        self.assertLessEqual(run.stats["atoms"], 2)

    def test_filter_can_be_disabled(self):
        ingest_file(self.store, self.data, "pet_water_fountain")
        run = run_category(self.store, "pet_water_fountain", min_size=1, validity_filter=False)
        self.assertEqual(run.stats["validity_filtered"], 0)


if __name__ == "__main__":
    unittest.main()
