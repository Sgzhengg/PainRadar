"""Tests for category-free discovery."""

from __future__ import annotations

import unittest

from painradar.discover import SourceCluster, _app_of, merge_clusters, render_markdown


def _cluster(label: str, category: str, quotes: list[str], level: str = "L2") -> SourceCluster:
    atoms = [
        {
            "quote": q, "level": level, "intensity": 3, "confidence": 0.9,
            "obstacle": "", "item_id": f"as_1_{i}", "category": category,
            "persona": "", "cost_type": "", "wtp_level": "none",
        }
        for i, q in enumerate(quotes)
    ]
    return SourceCluster(run_id="r", cluster_id=f"pc_{label}", label=label, category=category, atoms=atoms)


class TestDiscover(unittest.TestCase):
    def test_app_of(self) -> None:
        self.assertEqual(_app_of("as_123_456"), "123")
        self.assertEqual(_app_of("file-1"), "")

    def test_merge_similar_clusters(self) -> None:
        a = _cluster("订阅", "sleep_tech", ["cannot cancel my subscription", "charged after cancel"])
        b = _cluster("订阅", "budgeting", ["cannot cancel subscription here", "cancel subscription problem"])
        c = _cluster("浇水", "plant_care", ["watering reminder keeps failing", "reminder never fires"])
        groups = merge_clusters([a, b, c], threshold=0.15)
        sizes = sorted(len(g) for g in groups)
        self.assertIn(2, sizes)  # a and b merge
        self.assertGreaterEqual(len(groups), 2)

    def test_taxonomy_cache_roundtrip(self) -> None:
        import tempfile
        from pathlib import Path

        from painradar.discover import load_taxonomy_cache, save_taxonomy_cache

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tax.json"
            taxonomy = [{"id": "D1", "demand": "订阅取消难", "definition": "x", "buyer": "用户"}]
            assignment = {"k1": "D1"}
            version = save_taxonomy_cache(path, "hash1", taxonomy, assignment)
            self.assertEqual(version, 1)
            cached = load_taxonomy_cache(path, "hash1")
            self.assertIsNotNone(cached)
            self.assertEqual(cached["taxonomy"], taxonomy)
            self.assertIsNone(load_taxonomy_cache(path, "other-hash"))
            self.assertEqual(save_taxonomy_cache(path, "hash1", taxonomy, assignment), 2)

    def test_frozen_taxonomy_roundtrip(self) -> None:
        import tempfile
        from pathlib import Path

        from painradar.discover import load_frozen_taxonomy, save_frozen_taxonomy

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frozen.json"
            taxonomy = [{"id": "D1", "demand": "订阅取消难", "definition": "x", "buyer": "用户"}]
            self.assertEqual(save_frozen_taxonomy(path, taxonomy), 2)
            loaded = load_frozen_taxonomy(path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["version"], 2)
            self.assertEqual(loaded["demands"], taxonomy)
            self.assertEqual(save_frozen_taxonomy(path, taxonomy), 3)

    def test_render_markdown_has_table(self) -> None:
        a = _cluster("订阅", "sleep_tech", ["cannot cancel"])
        groups = merge_clusters([a], threshold=0.2)
        self.assertEqual(len(groups), 1)
        text = render_markdown([])
        self.assertIn("无品类需求发现", text)


if __name__ == "__main__":
    unittest.main()
