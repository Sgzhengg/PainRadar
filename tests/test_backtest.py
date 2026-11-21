"""Tests for B-set predictions and outcome collectors (offline)."""

from __future__ import annotations

import json
import unittest

from painradar.net import HttpClient, Response
from painradar.outcomes import appstore_outcome, github_outcome
from painradar.predictions import (
    extract_keywords,
    is_specific,
    make_prediction,
    random_baseline,
    vocabulary,
)
from painradar.schema import PainAtom


def _atom(i: int, quote: str) -> PainAtom:
    return PainAtom(
        atom_id=f"pa_{i}", comment_uid=f"cm_{i}", quote=quote, span_start=0, span_end=10,
        match_score="exact", scene="夜间噪音", trigger="", job="", obstacle="", workaround="",
        cost_type="", cost_estimate="", persona="", intensity=3, expression="complaint",
        level="L2", wtp_level="none", wtp_quote="", domain="宠物", confidence=0.8,
        model_version="t", prompt_version="t", taxonomy_version="t", run_id="r",
    )


ATOMS = [
    _atom(1, "the pump noise is terrible at night and the motor rattles"),
    _atom(2, "pump noise keeps me awake and the motor hum is loud"),
    _atom(3, "pump noise from the motor is unbearable at night"),
]


class TestPredictions(unittest.TestCase):
    def test_keywords_are_phrases_and_exclude_generic_words(self):
        kws = extract_keywords(ATOMS)
        self.assertIn("pump noise", kws)
        self.assertNotIn("app", kws)
        self.assertGreaterEqual(len(kws), 2)

    def test_make_prediction(self):
        pred = make_prediction("run", "pc_1", ATOMS, "2025-11-01", "2026-11-01")
        self.assertIsNotNone(pred)
        self.assertIn("2025-11-01", pred.proposition)
        self.assertGreaterEqual(len(pred.keywords), 2)

    def test_generic_prediction_is_rejected(self):
        generic = _atom(9, "the device stopped working and the app keeps crashing")
        pred = make_prediction("run", "pc_2", [generic], "2025-11-01", "2026-11-01",
                               keywords=["device stopped", "app crashing"])
        self.assertIsNone(pred)

    def test_subscription_is_not_domain_specific_for_sleep(self):
        words = ("sleep", "insomnia", "snore", "alarm")
        self.assertFalse(is_specific(["cancel subscription", "subscription refund"], words))
        self.assertTrue(is_specific(["insomnia tracking", "alarm wake"], words))

    def test_random_baseline_is_deterministic(self):
        import random

        vocab = vocabulary(ATOMS)
        a = random_baseline(vocab, 2, random.Random(7))
        b = random_baseline(vocab, 2, random.Random(7))
        self.assertEqual(a, b)


class Fake:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(url)
        return Response(200, {}, json.dumps(self.payload).encode())


def _client(payload) -> HttpClient:
    return HttpClient(user_agent="t", transport=Fake(payload), sleep=lambda _: None, rate_per_sec=1000)


GH = {
    "items": [
        {"full_name": "a/silent-pump", "html_url": "https://x/1", "stargazers_count": 42,
         "created_at": "2026-02-01", "name": "silent-pump", "description": "quiet pump noise fix"},
        {"full_name": "b/unrelated", "html_url": "https://x/2", "stargazers_count": 99,
         "created_at": "2026-02-01", "name": "todo", "description": "a todo app"},
    ]
}

IOS = {
    "results": [
        {"trackName": "Quiet Pump", "trackViewUrl": "https://a/1", "releaseDate": "2026-03-01T00:00:00Z"},
        {"trackName": "Old Pump", "trackViewUrl": "https://a/2", "releaseDate": "2024-03-01T00:00:00Z"},
    ]
}


class TestOutcomes(unittest.TestCase):
    def test_github_hit_requires_phrase_and_stars(self):
        out = github_outcome(["pump noise"], "2025-11-01", "2026-11-01", client=_client(GH))
        self.assertTrue(out.hit)
        self.assertEqual(len(out.evidence), 1)

    def test_github_miss_on_unrelated(self):
        out = github_outcome(["mold filter"], "2025-11-01", "2026-11-01", client=_client(GH))
        self.assertFalse(out.hit)

    def test_appstore_filters_by_release_date(self):
        out = appstore_outcome(["quiet pump"], "2025-11-01", "2026-11-01", client=_client(IOS))
        self.assertTrue(out.hit)
        self.assertEqual(len(out.evidence), 1)
        self.assertEqual(out.evidence[0]["name"], "Quiet Pump")


class FakeAdjudicator:
    def __init__(self, match: str):
        self.match = match
        self.calls = 0

    def judge(self, proposition, candidates):
        from painradar.adjudicate import Adjudication

        self.calls += 1
        return [Adjudication(i + 1, self.match, "fake", 0.9) for i in range(len(candidates))]


class TestAdjudication(unittest.TestCase):
    def test_no_verdict_rejects_candidate(self):
        adj = FakeAdjudicator("no")
        out = github_outcome(["pump noise"], "2025-11-01", "2026-11-01",
                             client=_client(GH), adjudicator=adj)
        self.assertFalse(out.hit)
        self.assertEqual(out.scanned, 1)
        self.assertEqual(out.rejected, 1)
        self.assertTrue(out.adjudicated)

    def test_yes_verdict_accepts_candidate(self):
        adj = FakeAdjudicator("yes")
        out = appstore_outcome(["quiet pump"], "2025-11-01", "2026-11-01",
                               client=_client(IOS), adjudicator=adj)
        self.assertTrue(out.hit)
        self.assertEqual(out.evidence[0]["match"], "yes")

    def test_llm_adjudicator_parses_response(self):
        from painradar.adjudicate import LLMAdjudicator

        payload = {
            "choices": [{"message": {"content": '{"results":[{"index":1,"match":"yes","reason":"same problem","confidence":0.8}]}'}}]
        }
        adj = LLMAdjudicator(client=_client(payload), model="fake", base_url="http://fake")
        verdicts = adj.judge("proposition", [{"name": "x", "description": "y"}])
        self.assertEqual(verdicts[0].match, "yes")
        self.assertEqual(verdicts[0].reason, "same problem")


if __name__ == "__main__":
    unittest.main()
