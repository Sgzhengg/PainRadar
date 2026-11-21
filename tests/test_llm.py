"""LLM extractor tests: parsing, span gate, dual-pass consistency, fallback."""

from __future__ import annotations

import json
import unittest

from painradar.config import category
from painradar.extract import (
    LLMExtractor,
    LLMNotConfigured,
    RuleExtractor,
    SpanGate,
    _parse_json_object,
)
from painradar.net import HttpClient, Response
from painradar.schema import RawItem

TEXT = "The pump noise is terrible at night. I ended up moving it to the bathroom."

GOOD = {
    "quote": "The pump noise is terrible at night.",
    "scene": "夜间噪音",
    "trigger": "at night",
    "job": "sleep through the night",
    "obstacle": "the pump noise is terrible",
    "workaround": "moved it to the bathroom",
    "cost_type": "",
    "cost_estimate": "",
    "persona": "",
    "intensity": 4,
    "expression": "complaint",
    "level": "L2",
    "wtp_level": "none",
    "wtp_quote": "",
    "confidence": 0.8,
}


class FakeLLM:
    """Returns successive message contents; repeats the last one."""

    def __init__(self, contents: list[str]):
        self.contents = contents
        self.calls = 0

    def __call__(self, method, url, headers, body, timeout):
        content = self.contents[min(self.calls, len(self.contents) - 1)]
        self.calls += 1
        payload = {"choices": [{"message": {"content": content}}]}
        return Response(200, {}, json.dumps(payload).encode())


def _client(fake: FakeLLM) -> HttpClient:
    return HttpClient(user_agent="t", transport=fake, sleep=lambda _: None, rate_per_sec=1000)


def _extractor(contents: list[str], consistency: bool = True, fallback=None) -> LLMExtractor:
    return LLMExtractor(
        category("pet_water_fountain"),
        client=_client(FakeLLM(contents)),
        model="fake-model",
        base_url="http://fake",
        consistency=consistency,
        fallback=fallback,
    )


def _item() -> RawItem:
    return RawItem("test", "1", "https://x", TEXT, "2026-07-01", "pet_water_fountain")


class TestParse(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(_parse_json_object('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(_parse_json_object('```json\n{"a": 2}\n```'), {"a": 2})

    def test_json_in_prose(self):
        self.assertEqual(_parse_json_object('Here you go: {"a": 3} thanks'), {"a": 3})

    def test_invalid(self):
        self.assertIsNone(_parse_json_object("not json"))


class TestLLMExtractor(unittest.TestCase):
    def test_agreeing_passes(self):
        ex = _extractor([json.dumps(GOOD), json.dumps(GOOD)])
        atom = ex.extract(_item(), TEXT, "cm_x", "run_x")
        self.assertIsNotNone(atom)
        self.assertEqual(atom.level, "L2")
        self.assertEqual(atom.quote, GOOD["quote"])
        self.assertIn("agree", atom.model_version)
        self.assertEqual(ex.stats.extracted, 1)
        self.assertEqual(ex.stats.fallback, 0)

    def test_span_is_verbatim(self):
        ex = _extractor([json.dumps(GOOD), json.dumps(GOOD)])
        atom = ex.extract(_item(), TEXT, "cm_x", "run_x")
        self.assertEqual(TEXT[atom.span_start:atom.span_end], atom.quote)

    def test_missing_span_falls_back_to_rules(self):
        bad = dict(GOOD, quote="a sentence that is not in the text at all", obstacle="", wtp_quote="")
        ex = _extractor([json.dumps(bad), json.dumps(bad)], fallback=RuleExtractor(category("pet_water_fountain")))
        atom = ex.extract(_item(), TEXT, "cm_x", "run_x")
        self.assertIsNotNone(atom)
        self.assertIn("fallback-no_span", atom.model_version)
        self.assertEqual(ex.stats.fallback, 1)

    def test_quote_failure_can_recover_from_obstacle(self):
        # If the model's quote is unusable but its obstacle is verbatim, use it.
        partial = dict(GOOD, quote="not in the text", obstacle="the pump noise is terrible")
        ex = _extractor([json.dumps(partial), json.dumps(partial)])
        atom = ex.extract(_item(), TEXT, "cm_x", "run_x")
        self.assertIsNotNone(atom)
        self.assertEqual(atom.quote.lower(), "the pump noise is terrible")

    def test_disagreement_downgrades_without_fallback(self):
        second = dict(GOOD, level="L4", scene="清洗换水", obstacle="mold everywhere")
        ex = _extractor([json.dumps(GOOD), json.dumps(second)], fallback=None)
        atom = ex.extract(_item(), TEXT, "cm_x", "run_x")
        self.assertIsNotNone(atom)
        self.assertIn("disagree", atom.model_version)
        self.assertLess(atom.confidence, 0.8)
        self.assertEqual(ex.stats.disagree, 1)

    def test_disagreement_prefers_rule_fallback(self):
        second = dict(GOOD, level="L4", scene="清洗换水", obstacle="mold everywhere")
        rule = RuleExtractor(category("pet_water_fountain"))
        ex = _extractor([json.dumps(GOOD), json.dumps(second)], fallback=rule)
        atom = ex.extract(_item(), TEXT, "cm_x", "run_x")
        self.assertIn("fallback-disagree", atom.model_version)

    def test_invalid_level_is_inferred(self):
        bad_level = dict(GOOD, level="definitely-high")
        ex = _extractor([json.dumps(bad_level), json.dumps(bad_level)])
        atom = ex.extract(_item(), TEXT, "cm_x", "run_x")
        self.assertIn(atom.level, {"L1", "L2", "L3", "L4"})

    def test_no_json_falls_back(self):
        rule = RuleExtractor(category("pet_water_fountain"))
        ex = _extractor(["not json at all"], fallback=rule)
        atom = ex.extract(_item(), TEXT, "cm_x", "run_x")
        self.assertIsNotNone(atom)
        self.assertIn("fallback-no_json", atom.model_version)

    def test_unconfigured_without_client(self):
        with self.assertRaises(LLMNotConfigured):
            LLMExtractor(category("pet_water_fountain"), client=None, model=None, base_url=None, api_key=None)

    def test_l0_is_dropped(self):
        l0 = dict(GOOD, level="L0", obstacle="")
        ex = _extractor([json.dumps(l0), json.dumps(l0)])
        self.assertIsNone(ex.extract(_item(), TEXT, "cm_x", "run_x"))
        self.assertEqual(ex.stats.dropped_l0, 1)


if __name__ == "__main__":
    unittest.main()
