"""Offline tests for the tool-fit matcher."""

from __future__ import annotations

import unittest

from painradar.tool_fit import WEIGHTS, _parse, _total

GOOD = {
    "scores": {k: 5 for k in WEIGHTS},
    "reasons": {k: "r" for k in WEIGHTS},
    "verdict": "full",
    "gap": "",
}


class TestToolFit(unittest.TestCase):
    def test_all_fives_is_100(self) -> None:
        self.assertEqual(_total({k: 5 for k in WEIGHTS}), 100)

    def test_parse_accepts_full(self) -> None:
        res = _parse(GOOD)
        assert res is not None
        self.assertEqual(res.verdict, "full")
        self.assertEqual(res.total, 100)

    def test_parse_rejects_missing_dimension(self) -> None:
        self.assertIsNone(_parse({"scores": {"capability_match": 5}}))

    def test_unknown_verdict_falls_back_to_no(self) -> None:
        bad = dict(GOOD, verdict="maybe")
        res = _parse(bad)
        assert res is not None
        self.assertEqual(res.verdict, "no")


if __name__ == "__main__":
    unittest.main()
