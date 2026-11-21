"""Clustering: taxonomy-first, similarity-second.

M1 groups atoms by their controlled ``scene`` label first, because a business
user reads "夜间噪音 / 清洗换水 / 水泵故障" and immediately understands the cut.
Within a large scene we still split by average-linkage similarity so that two
distinct obstacles do not hide inside one bucket.

This is deliberately simpler than HDBSCAN and, more importantly, explainable:
the report can say exactly which scene a cluster came from. The interface is
the one HDBSCAN will implement later.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

from .schema import Cluster, PainAtom
from .textproc import cosine, tfidf_vectors, tokenize

SPLIT_AT = 8  # only try a similarity split when a scene has at least this many atoms


@dataclass
class ClusterResult:
    clusters: list[Cluster]
    assignments: dict[str, str]
    noise_rate: float
    threshold: float


def _vectors(atoms: list[PainAtom]) -> list[dict[str, float]]:
    return tfidf_vectors([tokenize(a.signature()) for a in atoms])


def _agglomerative(atoms: list[PainAtom], threshold: float, min_size: int) -> list[list[PainAtom]]:
    """Average-linkage merge; returns groups of at least ``min_size``."""
    if len(atoms) < min_size:
        return []
    vectors = _vectors(atoms)
    groups: list[list[int]] = [[i] for i in range(len(atoms))]

    def avg_sim(g1: list[int], g2: list[int]) -> float:
        return sum(cosine(vectors[i], vectors[j]) for i in g1 for j in g2) / (len(g1) * len(g2))

    while len(groups) > 1:
        best: tuple[float, int, int] | None = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                s = avg_sim(groups[i], groups[j])
                if best is None or s > best[0]:
                    best = (s, i, j)
        if best is None or best[0] < threshold:
            break
        _, i, j = best
        groups[i] += groups[j]
        groups.pop(j)

    return [[atoms[i] for i in g] for g in groups if len(g) >= min_size]


def _label(members: list[PainAtom], medoid: PainAtom) -> str:
    scene = medoid.scene or "未分类"
    persona = medoid.persona
    return f"{scene} · {persona}" if persona else scene


def cluster_atoms(
    atoms: list[PainAtom],
    threshold: float = 0.32,
    min_size: int = 3,
) -> ClusterResult:
    if not atoms:
        return ClusterResult([], {}, 0.0, threshold)

    scenes: dict[str, list[PainAtom]] = defaultdict(list)
    for a in atoms:
        scenes[a.scene or "未分类"].append(a)

    clusters: list[Cluster] = []
    assignments: dict[str, str] = {}
    noise_count = 0

    for scene, members in scenes.items():
        groups: list[list[PainAtom]]
        if scene == "其他场景":
            # If we could not name the scene, do not invent a bucket: split by
            # similarity and keep only stable pieces, otherwise treat as noise.
            groups = _agglomerative(members, threshold=max(threshold, 0.36), min_size=min_size)
            if not groups:
                noise_count += len(members)
                for a in members:
                    assignments[a.atom_id] = "noise"
                continue
        elif len(members) >= SPLIT_AT:
            split = _agglomerative(members, threshold=threshold, min_size=min_size)
            # Only accept the split if it is clean: every piece >= min_size and
            # it actually produced more than one piece.
            groups = split if len(split) > 1 else [members]
        else:
            groups = [members]

        for group in groups:
            if len(group) < min_size:
                noise_count += len(group)
                for a in group:
                    assignments[a.atom_id] = "noise"
                continue
            vectors = _vectors(group)
            medoid_idx = 0
            if len(group) > 1:
                scores = [
                    sum(cosine(vectors[i], vectors[j]) for j in range(len(group)) if j != i) / (len(group) - 1)
                    for i in range(len(group))
                ]
                medoid_idx = max(range(len(group)), key=lambda i: scores[i])
            medoid = group[medoid_idx]
            digest = hashlib.sha256(
                "|".join(sorted(a.atom_id for a in group)).encode()
            ).hexdigest()[:10]
            cid = f"pc_{digest}"
            clusters.append(
                Cluster(
                    cluster_id=cid,
                    label=_label(group, medoid),
                    members=[a.atom_id for a in group],
                    medoid_atom_id=medoid.atom_id,
                    size=len(group),
                    noise=False,
                )
            )
            for a in group:
                assignments[a.atom_id] = cid

    clusters.sort(key=lambda c: c.size, reverse=True)
    noise_rate = noise_count / len(atoms) if atoms else 0.0
    return ClusterResult(clusters, assignments, noise_rate, threshold)
