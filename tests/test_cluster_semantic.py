import unittest

from painradar.cluster import cluster_atoms
from painradar.schema import PainAtom


def _atom(i: int, scene: str, canonical: str, obstacle: str) -> PainAtom:
    return PainAtom(
        atom_id=f"pa_{i}",
        comment_uid=f"cm_{i}",
        quote=f"{obstacle}",
        span_start=0,
        span_end=len(obstacle),
        match_score="exact",
        scene=scene,
        trigger="",
        job="job",
        obstacle=obstacle,
        workaround="",
        cost_type="",
        cost_estimate="",
        persona="",
        intensity=3,
        expression="complaint",
        level="L2",
        wtp_level="none",
        wtp_quote="",
        domain="",
        confidence=0.8,
        model_version="t",
        prompt_version="t",
        taxonomy_version="t",
        run_id="r",
        canonical_pain=canonical,
    )


class SemanticClusterTests(unittest.TestCase):
    def test_same_canonical_across_scenes_merge(self):
        atoms = [_atom(i, "订阅", "订阅取消入口难找", "取消入口找不到") for i in range(3)]
        atoms += [_atom(10 + i, "支付", "订阅取消入口难找", "取消按钮藏得深") for i in range(3)]
        result = cluster_atoms(atoms, min_size=3)
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(result.clusters[0].size, 6)

    def test_different_canonical_stay_apart(self):
        atoms = [_atom(i, "订阅", "订阅取消入口难找", "取消入口找不到") for i in range(3)]
        atoms += [_atom(10 + i, "噪音", "水泵夜间噪音大", "pump is loud at night") for i in range(3)]
        result = cluster_atoms(atoms, min_size=3)
        self.assertEqual(len(result.clusters), 2)

    def test_no_scene_no_canonical_still_clusters(self):
        atoms = [_atom(i, "其他场景", "", "导出表格总是失败，需要手动复制") for i in range(5)]
        result = cluster_atoms(atoms, min_size=3)
        self.assertEqual(len(result.clusters), 1)


if __name__ == "__main__":
    unittest.main()
