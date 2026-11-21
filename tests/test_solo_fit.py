"""Offline tests for the solo-fit rubric."""

from __future__ import annotations

import unittest

from painradar.solo_fit import WEIGHTS, SoloFitScorer, _parse, _total

GOOD = {
    "scores": {
        "third_party_actionable": 5,
        "leverage": 4,
        "competition_gap": 4,
        "software_only": 5,
        "zero_onboarding": 5,
        "no_docs": 5,
        "low_ops": 5,
        "frequency": 3,
        "self_serve_pay": 4,
    },
    "reasons": {k: "r" for k in WEIGHTS},
    "summary": "可以做",
}


class TestSoloFit(unittest.TestCase):
    def test_all_fives_is_100(self) -> None:
        self.assertEqual(_total({k: 5 for k in WEIGHTS}), 100)

    def test_all_ones_is_zero(self) -> None:
        self.assertEqual(_total({k: 1 for k in WEIGHTS}), 0)

    def test_parse_clamps_and_scores(self) -> None:
        fit = _parse(GOOD)
        assert fit is not None
        self.assertEqual(fit.total, _total(GOOD["scores"]))
        self.assertGreater(fit.total, 60)

    def test_parse_rejects_missing_dimension(self) -> None:
        bad = {"scores": {"software_only": 5}}
        self.assertIsNone(_parse(bad))

    def test_scorer_falls_back_on_bad_payload(self) -> None:
        import json as _json

        from painradar.net import HttpClient, Response

        class Fake:
            def __call__(self, method, url, headers, body, timeout):
                return Response(200, {}, _json.dumps({"choices": [{"message": {"content": "nope"}}]}).encode())

        scorer = SoloFitScorer(api_key="x")
        scorer.client = HttpClient(user_agent="t", transport=Fake(), sleep=lambda _: None, rate_per_sec=1000)
        fit = scorer.score({"label": "x", "definition": "y", "size": 1, "score": 1})
        self.assertEqual(fit.total, 0)


if __name__ == "__main__":
    unittest.main()
