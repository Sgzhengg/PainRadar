"""Category-free demand discovery.

The regular pipeline starts from a category and finds pains inside it. This
module does the opposite: it takes the clusters that were already built inside
each category, drops the category label, merges similar clusters across domains,
and ranks the resulting *demands*.

Category is an output here (which domains a demand appears in), not an input.

Why cluster-level rather than atom-level: with ~1,500 short reviews a centroid
becomes generic and swallows everything. There are only a few dozen clusters,
each already coherent, so merging them is both cheaper and more stable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .store import Store
from .textproc import cosine, tfidf_vectors, tokenize


@dataclass
class Demand:
    demand_id: str
    label: str
    size: int
    type: str = ""
    definition: str = ""
    buyer: str = ""
    buyer_by_domain: dict[str, str] = field(default_factory=dict)
    workaround: str = ""
    cost: str = ""
    domains: dict[str, int] = field(default_factory=dict)
    apps: list[str] = field(default_factory=list)
    l2_share: float = 0.0
    intensity: float = 0.0
    cost_share: float = 0.0
    wtp_share: float = 0.0
    score: float = 0.0
    quote: str = ""
    variants: int = 1
    examples: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _app_of(item_id: str) -> str:
    parts = str(item_id or "").split("_")
    return parts[1] if len(parts) >= 3 and parts[0] == "as" else ""


@dataclass
class SourceCluster:
    run_id: str
    cluster_id: str
    label: str
    category: str
    atoms: list[dict]


def load_clusters(dbs: list[str]) -> list[SourceCluster]:
    """Every cluster from every run, deduped by (category, cluster signature)."""
    out: list[SourceCluster] = []
    seen: set[tuple[str, str]] = set()
    for path in dbs:
        store = Store(path)
        try:
            runs = store._conn.execute("SELECT run_id, category FROM runs").fetchall()
            for run in runs:
                rows = store._conn.execute(
                    "SELECT * FROM clusters WHERE run_id=? ORDER BY cluster_id", (run["run_id"],)
                ).fetchall()
                for c in rows:
                    members = store.cluster_members(run["run_id"], c["cluster_id"])
                    if not members:
                        continue
                    sig = (run["category"], c["label"], hashlib.sha256("|".join(sorted(m["comment_uid"] for m in members[:5])).encode()).hexdigest()[:8])
                    if sig in seen:
                        continue
                    seen.add(sig)
                    out.append(
                        SourceCluster(
                            run_id=run["run_id"],
                            cluster_id=c["cluster_id"],
                            label=c["label"],
                            category=run["category"],
                            atoms=[dict(m) for m in members],
                        )
                    )
        finally:
            store.close()
    return out


def _cluster_doc(cluster: SourceCluster) -> list[str]:
    """Use quotes, not Chinese labels: the vector space is English reviews."""
    text = " ".join((a.get("quote") or "") for a in cluster.atoms[:12])
    return tokenize(text)


def merge_clusters(clusters: list[SourceCluster], threshold: float = 0.22) -> list[list[SourceCluster]]:
    """Average-linkage agglomeration over the (few) existing clusters.

    Incremental centroid matching collapses into one blob; with only a few dozen
    clusters, average linkage is cheap and resists that.
    """
    vectors = tfidf_vectors([_cluster_doc(c) for c in clusters])
    n = len(clusters)
    sim = [[cosine(vectors[i], vectors[j]) for j in range(n)] for i in range(n)]
    groups: list[list[int]] = [[i] for i in range(n)]
    while len(groups) > 1:
        best_i = best_j = -1
        best_s = 0.0
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                total = sum(sim[a][b] for a in groups[i] for b in groups[j])
                s = total / (len(groups[i]) * len(groups[j]))
                if s > best_s:
                    best_i, best_j, best_s = i, j, s
        if best_s < threshold:
            break
        groups[best_i] = groups[best_i] + groups[best_j]
        del groups[best_j]
    return [[clusters[i] for i in g] for g in groups]


def _score(atoms: list[dict], domains: dict[str, int], apps: set[str], max_size: int, max_apps: int) -> tuple[float, float, float, float, float]:
    size = len(atoms)
    l2 = sum(1 for a in atoms if a["level"] in ("L2", "L3", "L4")) / size
    intensity = sum(int(a["intensity"]) for a in atoms) / size / 5
    cost = sum(1 for a in atoms if a.get("cost_type") in ("money", "time")) / size
    wtp = sum(1 for a in atoms if a.get("wtp_level") == "strong") / size
    freq = size / max(1, max_size)
    breadth = len(apps) / max(1, max_apps)
    # Cross-domain recurrence is the point of discovery, so it gets its own term.
    span = min(1.0, len(domains) / 3)
    score = 100 * (
        0.25 * freq + 0.15 * breadth + 0.15 * intensity + 0.10 * cost
        + 0.10 * wtp + 0.10 * l2 + 0.15 * span
    )
    return round(score, 1), round(l2, 3), round(intensity, 3), round(cost, 3), round(wtp, 3)


def discover(
    dbs: list[str],
    min_size: int = 8,
    threshold: float = 0.18,
    top: int = 15,
) -> list[Demand]:
    clusters = load_clusters(dbs)
    if not clusters:
        return []
    groups = [g for g in merge_clusters(clusters, threshold) if sum(len(c.atoms) for c in g) >= min_size]
    if not groups:
        return []
    max_size = max(sum(len(c.atoms) for c in g) for g in groups)
    max_apps = max(
        len({_app_of(a.get("item_id", "")) for c in g for a in c.atoms} - {""}) for g in groups
    )

    out: list[Demand] = []
    for group in groups:
        atoms = [a for c in group for a in c.atoms]
        atoms.sort(key=lambda a: a["confidence"], reverse=True)
        medoid = atoms[0]
        domains: dict[str, int] = {}
        for c in group:
            domains[c.category] = domains.get(c.category, 0) + len(c.atoms)
        apps = {_app_of(a.get("item_id", "")) for a in atoms} - {""}

        from .config import category as get_category

        buyer_by_domain: dict[str, str] = {}
        for domain in domains:
            dom_atoms = [a for a in atoms if domain_of.get(id(a)) == domain]
            personas = [a.get("persona") for a in dom_atoms if a.get("persona")]
            if personas:
                counts: dict[str, int] = {}
                for p in personas:
                    counts[p] = counts.get(p, 0) + 1
                # deterministic tie-break: count desc, then label asc
                buyer_by_domain[domain] = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            else:
                buyer_by_domain[domain] = f"{get_category(domain).name}用户"

        score, l2, intensity, cost, wtp = _score(atoms, domains, apps, max_size, max_apps)
        # Label by the most common source-cluster label: it is already Chinese,
        # human-readable, and survives the cross-domain merge.
        labels: dict[str, int] = {}
        for c in group:
            base = c.label.split(" · ")[0]
            labels[base] = labels.get(base, 0) + len(c.atoms)
        label = max(labels.items(), key=lambda kv: kv[1])[0]
        if label == "其他场景":
            label = (medoid.get("obstacle") or "").strip()[:42] or label
        digest = hashlib.sha256("|".join(sorted(c.cluster_id for c in group)).encode()).hexdigest()[:10]
        out.append(
            Demand(
                demand_id=f"dm_{digest}",
                label=label,
                size=len(atoms),
                domains=dict(sorted(domains.items(), key=lambda kv: kv[1], reverse=True)),
                apps=sorted(apps)[:6],
                l2_share=l2,
                intensity=intensity,
                cost_share=cost,
                wtp_share=wtp,
                score=score,
                quote=medoid["quote"],
                examples=[
                    {
                        "quote": a["quote"],
                        "domain": next(c.category for c in group if a in c.atoms),
                        "level": a["level"],
                        "persona": a.get("persona") or "",
                        "app": _app_of(a.get("item_id", "")),
                    }
                    for a in atoms[:3]
                ],
            )
        )
    out.sort(key=lambda d: d.score, reverse=True)
    return out[:top]


def _char_grams(text: str) -> set[str]:
    t = (text or "").strip()
    return {t[i : i + 2] for i in range(len(t) - 1)} if len(t) >= 2 else {t}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _group_statements(canons: list, threshold: float = 0.34) -> list[list[int]]:
    """Split a demand type into sub-demands by statement similarity.

    Type-level merging is too coarse: "data accuracy" legitimately covers sleep
    tracking, plant identification and expense categorization. Statements inside
    a type are clustered by character bigrams so those stay apart.
    """
    grams = [_char_grams(c.demand) for c in canons]
    groups: list[list[int]] = [[i] for i in range(len(canons))]
    while len(groups) > 1:
        best_i = best_j = -1
        best = 0.0
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                total = sum(_jaccard(grams[a], grams[b]) for a in groups[i] for b in groups[j])
                s = total / (len(groups[i]) * len(groups[j]))
                if s > best:
                    best_i, best_j, best = i, j, s
        if best < threshold:
            break
        groups[best_i] += groups[best_j]
        del groups[best_j]
    return groups


def _corpus_hash(clusters: list[SourceCluster]) -> str:
    keys = sorted(f"{c.category}|{c.label}" for c in clusters)
    return hashlib.sha256("|".join(keys).encode()).hexdigest()[:16]


def load_taxonomy_cache(path: Path | None, corpus_hash: str) -> dict | None:
    if not path or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("corpus_hash") != corpus_hash:
        return None
    if not data.get("taxonomy") or not data.get("assignment"):
        return None
    return data


def save_taxonomy_cache(
    path: Path | None, corpus_hash: str, taxonomy: list[dict], assignment: dict[str, str]
) -> int:
    version = 1
    if path and path.exists():
        try:
            version = int(json.loads(path.read_text(encoding="utf-8")).get("version", 0)) + 1
        except (OSError, ValueError, TypeError):
            version = 1
    if not path:
        return version
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": version,
                "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                "corpus_hash": corpus_hash,
                "taxonomy": taxonomy,
                "assignment": assignment,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return version


def load_frozen_taxonomy(path: Path | None) -> dict | None:
    if not path or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not data.get("demands"):
        return None
    return data


def save_frozen_taxonomy(path: Path | None, taxonomy: list[dict]) -> int:
    if not path:
        return 0
    previous = load_frozen_taxonomy(path)
    version = int(previous.get("version", 2)) + 1 if previous else 2
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": version,
                "frozen_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                "demands": taxonomy,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return version


def load_assignment_cache(path: Path | None, corpus_hash: str, version: int) -> dict[str, str] | None:
    if not path or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("corpus_hash") != corpus_hash or int(data.get("taxonomy_version", -1)) != version:
        return None
    return data.get("assignment") or None


def save_assignment_cache(
    path: Path | None, corpus_hash: str, version: int, assignment: dict[str, str]
) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "corpus_hash": corpus_hash,
                "taxonomy_version": version,
                "assignment": assignment,
                "saved_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def discover_canonical(
    dbs: list[str],
    top: int = 15,
    min_size: int = 6,
    cache_path: Path | None = None,
    statement_threshold: float = 0.30,
    taxonomy_cache: Path | None = None,
    refresh_taxonomy: bool = False,
    frozen_path: Path | None = None,
    freeze: bool = False,
    rebuild: bool = False,
    assignment_cache: Path | None = None,
) -> tuple[list[Demand], dict]:
    """Two-stage normalization: build a shared demand taxonomy, then assign clusters.

    One-shot per-cluster statements either over-merge (by coarse type) or never
    align (each cluster gets its own phrasing). Asking for a global taxonomy first
    makes cross-domain alignment explicit and auditable.
    """
    from .canonical import LLMNormalizer, _key

    clusters = load_clusters(dbs)
    if not clusters:
        return [], {}
    normalizer = LLMNormalizer()

    corpus_hash = _corpus_hash(clusters)
    frozen = None if rebuild else load_frozen_taxonomy(frozen_path)
    if frozen:
        taxonomy = frozen["demands"]
        version = int(frozen.get("version", 1))
        cached_assignment = load_assignment_cache(assignment_cache, corpus_hash, version)
        if cached_assignment:
            assignment = cached_assignment
        else:
            assignment = normalizer.assign(clusters, taxonomy)
            save_assignment_cache(assignment_cache, corpus_hash, version, assignment)
        source = "frozen"
    else:
        cached = None if refresh_taxonomy else load_taxonomy_cache(taxonomy_cache, corpus_hash)
        if cached:
            taxonomy = cached["taxonomy"]
            assignment = cached["assignment"]
            version = int(cached.get("version", 1))
        else:
            taxonomy = normalizer.taxonomy(clusters, target=10)
            if not taxonomy:
                return [], {"error": "taxonomy empty"}
            assignment = normalizer.assign(clusters, taxonomy)
            version = save_taxonomy_cache(taxonomy_cache, corpus_hash, taxonomy, assignment)
        source = "built"
        if freeze:
            version = save_frozen_taxonomy(frozen_path, taxonomy)
            source = "frozen"
    by_id = {d["id"]: d for d in taxonomy}

    groups: dict[str, list[SourceCluster]] = {}
    missing = 0
    missing_labels: list[str] = []
    for c in clusters:
        did = assignment.get(_key(c.category, c.label))
        if did not in by_id:
            missing += 1
            missing_labels.append(f"{c.category}/{c.label}")
            continue
        groups.setdefault(did, []).append(c)

    all_atoms = [a for c in clusters for a in c.atoms]
    max_size = max(1, len(all_atoms))
    max_apps = max(1, len({_app_of(a.get("item_id", "")) for a in all_atoms} - {""}))

    demands: list[Demand] = []
    for did, group in groups.items():
        meta = by_id[did]
        atoms = sorted([a for c in group for a in c.atoms], key=lambda a: a["confidence"], reverse=True)
        if len(atoms) < min_size:
            continue
        domain_of: dict[int, str] = {}
        for c in group:
            for a in c.atoms:
                domain_of[id(a)] = c.category
        domains: dict[str, int] = {}
        for c in group:
            domains[c.category] = domains.get(c.category, 0) + len(c.atoms)
        apps = {_app_of(a.get("item_id", "")) for a in atoms} - {""}

        from .config import category as get_category

        buyer_by_domain: dict[str, str] = {}
        for domain in domains:
            dom_atoms = [a for a in atoms if domain_of.get(id(a)) == domain]
            personas = [a.get("persona") for a in dom_atoms if a.get("persona")]
            if personas:
                counts: dict[str, int] = {}
                for p in personas:
                    counts[p] = counts.get(p, 0) + 1
                # deterministic tie-break: count desc, then label asc
                buyer_by_domain[domain] = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            else:
                buyer_by_domain[domain] = f"{get_category(domain).name}用户"

        score, l2, intensity, cost, wtp = _score(atoms, domains, apps, max_size, max_apps)
        span_bonus = 12 * max(0, len(domains) - 1)
        digest = hashlib.sha256(did.encode()).hexdigest()[:10]
        demands.append(
            Demand(
                demand_id=f"dm_{digest}",
                label=meta["demand"],
                size=len(atoms),
                type=meta["demand"],
                definition=meta.get("definition", ""),
                buyer=meta.get("buyer", ""),
                buyer_by_domain=buyer_by_domain,
                domains=dict(sorted(domains.items(), key=lambda kv: kv[1], reverse=True)),
                apps=sorted(apps)[:6],
                l2_share=l2,
                intensity=intensity,
                cost_share=cost,
                wtp_share=wtp,
                score=round(score + span_bonus, 1),
                quote=atoms[0]["quote"],
                variants=len({c.label.split(" · ")[0] for c in group}),
                examples=[
                    {"quote": a["quote"], "domain": domain_of.get(id(a), ""), "level": a["level"],
                     "app": _app_of(a.get("item_id", ""))}
                    for a in atoms[:3]
                ],
            )
        )
    demands.sort(key=lambda d: d.score, reverse=True)
    stats = {
        "clusters": len(clusters),
        "taxonomy": len(taxonomy),
        "taxonomy_version": version,
        "taxonomy_source": source,
        "assigned": sum(len(v) for v in groups.values()),
        "unassigned": missing,
        "coverage": round(sum(len(v) for v in groups.values()) / max(1, len(clusters)), 3),
        "unassigned_labels": sorted(missing_labels)[:20],
        "cross_domain": sum(1 for d in demands if len(d.domains) > 1),
    }
    return demands[:top], stats


def render_markdown(demands: list[Demand], source: str = "") -> str:
    lines = [
        "# 无品类需求发现",
        "",
        f"> 语料：{source} ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）",
        "",
        "| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, d in enumerate(demands, start=1):
        domains = "、".join(list(d.domains)[:3])
        lines.append(
            f"| {i} | {d.label} | {d.type or '—'} | {d.score:.0f} | {d.size} | {len(d.domains)} | "
            f"{len(d.apps)} | {domains} |"
        )
    lines += ["", "## 逐个需求", ""]
    for i, d in enumerate(demands, start=1):
        lines.append(f"### {i}. {d.label}（{d.score:.0f} 分，{d.size} 条证据，跨 {len(d.domains)} 个域）")
        lines.append("")
        lines.append(f"- 来源域：{'、'.join(f'{k}({v})' for k, v in list(d.domains.items())[:6])}")
        if d.type:
            lines.append(f"- 需求类型：{d.type}　变体：{d.variants} 种说法")
        if d.buyer:
            lines.append(f"- 买家：{d.buyer}")
        for domain, count in list(d.domains.items())[:6]:
            who = d.buyer_by_domain.get(domain, "买家待补")
            lines.append(f"- {domain}: {who}（{count} 条）")
        if d.workaround:
            lines.append(f"- 现有凑合：{d.workaround}")
        if d.cost:
            lines.append(f"- 观察到的代价：{d.cost}")
        lines.append(f"- 覆盖 App：{', '.join(d.apps) or '—'}")
        lines.append(
            f"- 强度：{d.intensity:.2f}　L2+：{d.l2_share:.0%}　代价信号：{d.cost_share:.0%}　付费信号：{d.wtp_share:.0%}"
        )
        lines.append("")
        lines.append(f"> {d.quote}")
        lines.append("")
    return "\n".join(lines)


def save(demands: list[Demand], out_dir: Path, source: str = "") -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "discovery.md"
    js = out_dir / "discovery.json"
    md.write_text(render_markdown(demands, source), encoding="utf-8")
    js.write_text(json.dumps([d.as_dict() for d in demands], ensure_ascii=False, indent=2), encoding="utf-8")
    return md, js
