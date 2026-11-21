"""Clustering: semantic-first, scene as a fallback label.

The old implementation partitioned by the static scene dictionary *before* any
similarity check. That splits one need across scenes ("夜间噪音" vs "清洗换水")
and forces new categories to hand-maintain a scene list.

Now:

1. atoms link when they share the model's ``canonical_pain`` phrase, or when
   their TF-IDF signature is similar enough — no scene precondition;
2. large components are split with average-linkage so one bucket cannot hide
   two different obstacles;
3. a cluster is labelled by its medoid's canonical phrase (fallback: scene).

The interface is unchanged, so the pipeline, scores and reports keep working.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

from .schema import Cluster, PainAtom
from .textproc import cosine, tfidf_vectors, tokenize

SPLIT_AT = 8  # only try a similarity split when a group has at least this many atoms


@dataclass
class ClusterResult:
    clusters: list[Cluster]
    assignments: dict[str, str]
    noise_rate: float
    threshold: float


def _vectors(atoms: list[PainAtom]) -> list[dict[str, float]]:
    return tfidf_vectors([tokenize(a.signature()) for a in atoms])


def _signature(atom: PainAtom) -> str:
    """Semantic signature: canonical need first, then the structured slots."""
    parts = [atom.canonical_pain or "", atom.scene or "", atom.job or "",
             atom.obstacle or "", atom.workaround or ""]
    return " | ".join(p for p in parts if p)


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
    base = (medoid.canonical_pain or medoid.scene or "未分类").strip()
    persona = medoid.persona
    return f"{base} · {persona}" if persona else base


def _components(atoms: list[PainAtom], threshold: float) -> list[list[int]]:
    """Single-linkage components over canonical phrases and TF-IDF similarity."""
    n = len(atoms)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    vectors = tfidf_vectors([tokenize(_signature(a)) for a in atoms])
    canonical = [(a.canonical_pain or "").strip().lower() for a in atoms]

    for i in range(n):
        for j in range(i + 1, n):
            if canonical[i] and canonical[i] == canonical[j]:
                union(i, j)
                continue
            if cosine(vectors[i], vectors[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def _bucket_key(atom: PainAtom) -> str:
    """Canonical need first; scene only when the extractor could not name it."""
    return (atom.canonical_pain or "").strip().lower() or (atom.scene or "未分类")


def _centroid(group: list[PainAtom]) -> dict[str, float]:
    vectors = tfidf_vectors([tokenize(_signature(a)) for a in group])
    total: dict[str, float] = {}
    for vec in vectors:
        for k, v in vec.items():
            total[k] = total.get(k, 0.0) + v
    norm = sum(v * v for v in total.values()) ** 0.5 or 1.0
    return {k: v / norm for k, v in total.items()}


def cluster_atoms(
    atoms: list[PainAtom],
    threshold: float = 0.32,
    min_size: int = 3,
    merge_threshold: float = 0.62,
) -> ClusterResult:
    """Buckets by canonical need (scene as fallback), then merge semantically.

    The static scene dictionary is no longer a hard partition: two scenes whose
    centroids are similar get merged, and unscene atoms still cluster by text.
    """
    if not atoms:
        return ClusterResult([], {}, 0.0, threshold)

    buckets: dict[str, list[PainAtom]] = defaultdict(list)
    for atom in atoms:
        buckets[_bucket_key(atom)].append(atom)

    # Merge buckets whose semantic centroids are close, regardless of scene.
    groups: list[list[PainAtom]] = list(buckets.values())
    centroids = [_centroid(g) for g in groups]
    merged = True
    while merged and len(groups) > 1:
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if cosine(centroids[i], centroids[j]) >= merge_threshold:
                    groups[i] += groups[j]
                    centroids[i] = _centroid(groups[i])
                    groups.pop(j)
                    centroids.pop(j)
                    merged = True
                    break
            if merged:
                break

    clusters: list[Cluster] = []
    assignments: dict[str, str] = {}
    noise_count = 0

    def emit(group: list[PainAtom]) -> None:
        nonlocal noise_count
        if len(group) < min_size:
            noise_count += len(group)
            for atom in group:
                assignments[atom.atom_id] = "noise"
            return
        vectors = _vectors(group) if len(group) > 1 else [{}]
        medoid_idx = 0
        if len(group) > 1:
            scores = [
                sum(cosine(vectors[i], vectors[j]) for j in range(len(group)) if j != i)
                / (len(group) - 1)
                for i in range(len(group))
            ]
            medoid_idx = max(range(len(group)), key=lambda i: scores[i])
        medoid = group[medoid_idx]
        digest = hashlib.sha256("|".join(sorted(a.atom_id for a in group)).encode()).hexdigest()[:10]
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
        for atom in group:
            assignments[atom.atom_id] = cid

    for group in groups:
        if len(group) < min_size:
            emit(group)
            continue
        unscened = all(not (a.canonical_pain or a.scene) or a.scene == "其他场景" for a in group)
        if len(group) >= SPLIT_AT or (unscened and len(group) >= max(min_size * 2, 4)):
            pieces = _agglomerative(group, threshold=max(threshold, 0.36), min_size=min_size)
            if pieces:
                for piece in pieces:
                    emit(piece)
                continue
        emit(group)

    clusters.sort(key=lambda c: c.size, reverse=True)
    noise_rate = noise_count / len(atoms) if atoms else 0.0
    return ClusterResult(clusters, assignments, noise_rate, threshold)
