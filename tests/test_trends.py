"""Offline tests for the Google Trends series summary math."""

from __future__ import annotations

import unittest

from painradar.trends import TrendSeries


class TestTrendSeries(unittest.TestCase):
    def test_summary_computes_change(self) -> None:
        s = TrendSeries("t", "", "today 12-m", [("d1", 10), ("d2", 20), ("d3", 30), ("d4", 40)])
        out = s.summary()
        self.assertEqual(out["points"], 4)
        self.assertEqual(out["head_avg"], 10.0)
        self.assertEqual(out["tail_avg"], 40.0)
        self.assertEqual(out["change_pct"], 300.0)
        self.assertEqual(out["peak_value"], 40)

    def test_flat_series(self) -> None:
        s = TrendSeries("t", "", "x", [("a", 5), ("b", 5), ("c", 5), ("d", 5)])
        self.assertEqual(s.summary()["change_pct"], 0.0)

    def test_empty_series(self) -> None:
        self.assertEqual(TrendSeries("t", "", "x").summary(), {"points": 0})

    def test_yoy_uses_two_52_week_windows(self) -> None:
        points = [(f"w{i}", 10) for i in range(156)] + [(f"w{i}", 15) for i in range(156, 208)]
        out = TrendSeries("t", "", "today 5-y", points).summary()
        self.assertEqual(out["yoy_pct"], 50.0)

    def test_yoy_missing_for_short_series(self) -> None:
        out = TrendSeries("t", "", "today 12-m", [("a", 5)] * 52).summary()
        self.assertIsNone(out["yoy_pct"])


if __name__ == "__main__":
    unittest.main()
