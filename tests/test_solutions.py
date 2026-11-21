"""Offline tests for the solution schema and rendering."""

from __future__ import annotations

import unittest

from painradar.solutions import Solution, _parse, render_markdown

VALID = {
    "name": "更新回滚",
    "pitch": "一键回到上个版本",
    "mechanism": "对应证据0的更新后崩溃",
    "buyer": "长期用户",
    "mvp": ["保存版本", "一键回滚"],
    "pricing": "一次性 ¥30",
    "price_band": "低",
    "why_now": "",
    "risks": ["商店审核"],
    "validation": {"hypothesis": "h", "experiment": "e", "threshold": "t", "duration": "7 天"},
    "feasibility": 4,
    "evidence_index": 0,
}


class TestSolutions(unittest.TestCase):
    def test_parse_accepts_grounded_solution(self) -> None:
        sols = _parse({"solutions": [VALID]}, quote_count=1)
        self.assertEqual(len(sols), 1)
        self.assertEqual(sols[0].name, "更新回滚")

    def test_parse_rejects_out_of_range_evidence(self) -> None:
        bad = dict(VALID, evidence_index=5)
        self.assertEqual(_parse({"solutions": [bad]}, quote_count=1), [])

    def test_parse_rejects_missing_validation(self) -> None:
        bad = dict(VALID, validation={"hypothesis": "h"})
        self.assertEqual(_parse({"solutions": [bad]}, quote_count=1), [])

    def test_render_includes_quote(self) -> None:
        demand = {
            "label": "更新后功能异常",
            "definition": "x",
            "score": 80,
            "size": 10,
            "domains": {"a": 1},
            "examples": [{"quote": "it broke after the update"}],
        }
        md = render_markdown(demand, [Solution(**{k: v for k, v in VALID.items()})])
        self.assertIn("对应证据：it broke after the update", md)
        self.assertIn("7 天验证", md)

class TestRankingFallback(unittest.TestCase):
    def test_rank_falls_back_to_feasibility_when_llm_fails(self) -> None:
        import json as _json

        from painradar.net import HttpClient, Response
        from painradar.solutions import Solution, SolutionGenerator

        class Fake:
            def __call__(self, method, url, headers, body, timeout):
                payload = {"choices": [{"message": {"content": "not json"}}]}
                return Response(200, {}, _json.dumps(payload).encode())

        gen = SolutionGenerator(api_key="x")
        gen.client = HttpClient(user_agent="t", transport=Fake(), sleep=lambda _: None, rate_per_sec=1000)
        sols = [
            Solution(name="A", pitch="p", mechanism="m", buyer="b", mvp=["1"], pricing="$1",
                     validation={"hypothesis": "h", "experiment": "e", "threshold": "t"}, feasibility=2),
            Solution(name="B", pitch="p", mechanism="m", buyer="b", mvp=["1"], pricing="$1",
                     validation={"hypothesis": "h", "experiment": "e", "threshold": "t"}, feasibility=5),
        ]
        rec = gen.rank({"label": "x"}, sols)
        self.assertEqual(rec["name"], "B")
        self.assertIn("回退", rec["reason"])



if __name__ == "__main__":
    unittest.main()
