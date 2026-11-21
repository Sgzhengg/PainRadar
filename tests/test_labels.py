"""Tests for annotation batch validation."""

from __future__ import annotations

import unittest

from painradar.labels import validate

SCENES = {"夜间噪音", "App 与连接"}


def _row(uid: str, valid="1", level="L2", scene="夜间噪音", obstacle="噪音大", wtp="none"):
    return {
        "comment_uid": uid, "gold_valid": valid, "gold_level": level,
        "gold_scene": scene, "gold_obstacle": obstacle, "gold_wtp": wtp,
    }


class TestValidate(unittest.TestCase):
    def test_clean_batch(self):
        batch = [{"comment_uid": "a"}, {"comment_uid": "b"}]
        labels = [_row("a"), _row("b", valid="0", level="", scene="", obstacle="")]
        self.assertEqual(validate(batch, labels, SCENES), [])

    def test_missing_row(self):
        errors = validate([{"comment_uid": "a"}, {"comment_uid": "b"}], [_row("a")], SCENES)
        self.assertTrue(any("缺少" in e for e in errors))

    def test_invalid_level(self):
        errors = validate([{"comment_uid": "a"}], [_row("a", level="L9")], SCENES)
        self.assertTrue(any("gold_level" in e for e in errors))

    def test_valid_without_obstacle(self):
        errors = validate([{"comment_uid": "a"}], [_row("a", obstacle="")], SCENES)
        self.assertTrue(any("gold_obstacle" in e for e in errors))

    def test_unknown_scene(self):
        errors = validate([{"comment_uid": "a"}], [_row("a", scene="外星场景")], SCENES)
        self.assertTrue(any("未知场景" in e for e in errors))

    def test_invalid_row_with_extra_fields(self):
        errors = validate([{"comment_uid": "a"}], [_row("a", valid="0")], SCENES)
        self.assertTrue(any("无效却填了" in e for e in errors))

    def test_bad_valid_flag(self):
        errors = validate([{"comment_uid": "a"}], [_row("a", valid="yes")], SCENES)
        self.assertTrue(any("gold_valid" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
