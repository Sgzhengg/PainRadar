"""Tests for the deterministic L0–L4 tree."""

from __future__ import annotations

import unittest

from painradar.levels import LevelInput, classify_workaround, level_from_workaround_type, resolve_level


class TestWorkaroundType(unittest.TestCase):
    def test_substitute(self):
        self.assertEqual(classify_workaround("switched to stainless bowls"), "substitute")

    def test_self_rescue(self):
        self.assertEqual(classify_workaround("reset it twice a day"), "self_rescue")

    def test_escalation(self):
        self.assertEqual(classify_workaround("contacted customer support"), "escalation")

    def test_none(self):
        self.assertEqual(classify_workaround(""), "none")


class TestResolveLevel(unittest.TestCase):
    def test_no_obstacle_is_l0(self):
        self.assertEqual(resolve_level(LevelInput(obstacle="")), "L0")

    def test_obstacle_only_is_l1(self):
        self.assertEqual(resolve_level(LevelInput(obstacle="pump noise")), "L1")

    def test_substitute_is_l2(self):
        self.assertEqual(
            resolve_level(LevelInput(obstacle="pump noise", workaround="switched to bowls")), "L2"
        )

    def test_escalation_stays_l1(self):
        self.assertEqual(
            resolve_level(LevelInput(obstacle="pump noise", workaround="contacted support")), "L1"
        )

    def test_declared_l4_wins(self):
        self.assertEqual(
            resolve_level(LevelInput(obstacle="noise", workaround="bought a silent pump", declared="L4")),
            "L4",
        )

    def test_type_driven(self):
        self.assertEqual(level_from_workaround_type("self_rescue", "L2", True), "L2")
        self.assertEqual(level_from_workaround_type("escalation", "L2", True), "L1")
        self.assertEqual(level_from_workaround_type("none", "L4", True), "L4")
        self.assertEqual(level_from_workaround_type("none", "L1", False), "L0")


if __name__ == "__main__":
    unittest.main()
