"""Pipeline orchestration: ingest -> extract -> cluster -> score -> opportunities."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .cluster import cluster_atoms
from .config import CategorySpec, category as get_category
from .connectors.file_connector import FileConnector
from .extract import SpanGate, build_extractor, prepare_text
from .schema import PainAtom, RawItem, Tier
from .scoring import assess_solo_fit, estimate_market, score_clusters
from .store import Store, new_run_id
from .textproc import author_key, detect_lang, minhash, tokenize
from .validity import ValidityFilter

VALIDATION_KIT = [
    {
        "hypothesis": "H1 人群存在且聚集",
        "experiment": "5 个社群观察 + 10 次访谈",
        "threshold": "≥6/10 人能复述同一场景",
        "cost": "7 天 / 2,000 元",
    },
    {
        "hypothesis": "H2 痛感足够强",
        "experiment": "落地页 + 等候名单",
        "threshold": "访问→留资 ≥8%",
        "cost": "7 天 / 1,000 元",
    },
    {
        "hypothesis": "H3 愿意付费",
        "experiment": "预售 / Concierge MVP",
        "threshold": "≥3 单预付，或 ≥2 人付定金",
        "cost": "14 天 / 3,000 元",
    },
]


@dataclass
class IngestResult:
    total: int = 0
    inserted: int = 0
    duplicates: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"total": self.total, "inserted": self.inserted, "duplicates": self.duplicates, "skipped": self.skipped}


@dataclass
class RunResult:
    run_id: str
    category: str
    stats: dict[str, Any] = field(default_factory=dict)
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    report_paths: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ingestion


def ingest_items(store: Store, items: Iterable[RawItem], category_key: str) -> IngestResult:
    """Normalise, scrub, dedupe and persist a stream of raw items."""
    get_category(category_key)  # validate early
    result = IngestResult()
    salt = store.salt()

    for item in items:
        result.total += 1
        text = (item.text or "").strip()
        # Chinese comments are denser than English: 8 characters already carry
        # a concrete complaint. 20 silently dropped most of them.
        if len(text) < 8:
            result.skipped += 1
            continue
        masked, sha = prepare_text(text)
        lang = item.lang or detect_lang(masked) or "unknown"
        sig = minhash(tokenize(masked))
        dup = store.find_duplicate(sha, sig, category=category_key)
        comment_uid = "cm_" + sha[:16]
        ok = store.insert_item(
            {
                "comment_uid": comment_uid,
                "platform": item.platform,
                "item_id": item.item_id,
                "url": item.url,
                "published_at": item.published_at,
                "lang": lang,
                "category": category_key,
                "text_masked": masked,
                "text_sha": sha,
                "author_key": author_key(salt, item.platform, item.author or "anonymous"),
                "rating": item.rating,
                "tier": item.tier.value,
                "tos_basis": item.tos_basis,
                "minhash_json": json.dumps(sig),
                "duplicate_of": dup,
                "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "parent_context": item.parent_context or "",
                "likes": int(item.likes or 0),
                "replies": int(item.replies or 0),
                "post_id": item.post_id or "",
            }
        )
        if ok:
            result.inserted += 1
            if dup:
                result.duplicates += 1
        else:
            result.skipped += 1
    # insert_item does not commit; closing the connection would roll back.
    store._conn.commit()
    return result


def ingest_file(
    store: Store,
    path: Path,
    category_key: str,
    platform: str = "file",
    tos_basis: str = "user_provided",
    tier: str = "A",
) -> IngestResult:
    connector = FileConnector(
        path=path, category=category_key, platform=platform,
        tos_basis=tos_basis, tier=Tier(tier),
    )
    result = ingest_items(store, connector.fetch(), category_key)
    store.audit("cli", "ingest", "file", str(path), f"{category_key}: {result.as_dict()}")
    return result


# ---------------------------------------------------------------------------
# Pipeline


def _app_of(item_id: str) -> str:
    parts = item_id.split("_")
    return parts[1] if len(parts) >= 3 and parts[0] == "as" else "unknown"


def run_category(
    store: Store,
    category_key: str,
    extractor_name: str = "rule",
    threshold: float = 0.32,
    min_size: int = 3,
    llm_model: str | None = None,
    llm_base_url: str | None = None,
    llm_consistency: bool = True,
    mode: str = "b2c",
    validity_filter: bool = True,
    before: str | None = None,
    apps: list[str] | None = None,
) -> RunResult:
    spec: CategorySpec = get_category(category_key)
    items = store.items(category_key)
    if before:
        items = [r for r in items if r["published_at"] < before]
    if apps:
        wanted = set(apps)
        items = [r for r in items if _app_of(str(r["item_id"])) in wanted]
    if spec.excluded_apps:
        excluded = set(spec.excluded_apps)
        items = [r for r in items if _app_of(str(r["item_id"])) not in excluded]
    if not items:
        raise SystemExit(f"no items for category {category_key!r}; ingest first")

    run_id = new_run_id()
    extractor = build_extractor(
        extractor_name,
        spec,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
        llm_consistency=llm_consistency,
        mode=mode,
    )
    gate = SpanGate()

    atoms: list[PainAtom] = []
    dates_by_atom: dict[str, str] = {}
    authors_by_atom: dict[str, str] = {}
    batch: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    vf = ValidityFilter(spec) if validity_filter else None
    filtered = 0

    def _row(a: PainAtom) -> dict[str, Any]:
        return {
            "atom_id": a.atom_id,
            "run_id": a.run_id,
            "comment_uid": a.comment_uid,
            "quote": a.quote,
            "span_start": a.span_start,
            "span_end": a.span_end,
            "match_score": a.match_score,
            "scene": a.scene,
            "trigger": a.trigger,
            "job": a.job,
            "obstacle": a.obstacle,
            "workaround": a.workaround,
            "cost_type": a.cost_type,
            "cost_estimate": a.cost_estimate,
            "persona": a.persona,
            "intensity": a.intensity,
            "expression": a.expression,
            "level": a.level,
            "wtp_level": a.wtp_level,
            "wtp_quote": a.wtp_quote,
            "domain": a.domain,
            "confidence": a.confidence,
            "model_version": a.model_version,
            "prompt_version": a.prompt_version,
            "taxonomy_version": a.taxonomy_version,
            "supersedes": a.supersedes,
            "canonical_pain": a.canonical_pain,
            "buyer_role": a.buyer_role,
            "b2b_score": a.b2b_score,
            "created_at": now,
        }

    for idx, row in enumerate(items, start=1):
        if vf is not None:
            verdict = vf.judge(row["text_masked"], row["rating"])
            if not verdict.valid:
                filtered += 1
                if idx % 20 == 0:
                    print(f"  extracted {len(atoms)}/{len(items)} (item {idx}, filtered {filtered})", flush=True)
                continue
        raw = RawItem(
            platform=row["platform"],
            item_id=row["item_id"],
            url=row["url"],
            text=row["text_masked"],
            published_at=row["published_at"],
            category=row["category"],
            parent_context=(row["parent_context"] if "parent_context" in row.keys() else "") or "",
            likes=(row["likes"] if "likes" in row.keys() else 0),
            replies=(row["replies"] if "replies" in row.keys() else 0),
            post_id=(row["post_id"] if "post_id" in row.keys() else "") or "",
        )
        atom = extractor.extract(raw, row["text_masked"], row["comment_uid"], run_id)
        if atom is not None:
            atoms.append(atom)
            dates_by_atom[atom.atom_id] = row["published_at"]
            authors_by_atom[atom.atom_id] = row["author_key"]
            batch.append(_row(atom))
        # Persist in batches: a long LLM run that dies at item 80 keeps its first
        # 80 atoms instead of losing everything.
        if len(batch) >= 20:
            store.insert_atoms(batch)
            batch = []
        if idx % 20 == 0:
            print(f"  extracted {len(atoms)}/{len(items)} (item {idx})", flush=True)

    if batch:
        store.insert_atoms(batch)

    if not atoms:
        raise SystemExit("no atoms extracted; check the data or the extractor")

    # Clusters
    by_id = {a.atom_id: a for a in atoms}
    result = cluster_atoms(atoms, threshold=threshold, min_size=min_size)
    store.insert_clusters(
        run_id,
        [
            {
                "cluster_id": c.cluster_id,
                "label": c.label,
                "size": c.size,
                "noise": c.noise,
                "medoid_atom_id": c.medoid_atom_id,
                "members": c.members,
            }
            for c in result.clusters
        ],
        result.assignments,
    )

    atoms_by_cluster: dict[str, list[PainAtom]] = {}
    for atom_id, cid in result.assignments.items():
        atoms_by_cluster.setdefault(cid, []).append(by_id[atom_id])

    scores = score_clusters(atoms_by_cluster, authors_by_atom, dates_by_atom, mode=mode)
    store.insert_scores(run_id, [s.as_dict() for s in scores])

    # Opportunities
    total_atoms = len(atoms)
    market = estimate_market(spec.market, spec)
    cluster_labels = {c.cluster_id: c.label for c in result.clusters}
    opps: list[dict[str, Any]] = []

    for score in scores:
        members = atoms_by_cluster.get(score.cluster_id, [])
        if not members:
            continue
        medoid = max(members, key=lambda a: a.confidence)
        personas = [a.persona for a in members if a.persona]
        # No persona evidence is better than a fake one: the report and UI show
        # "待补", which is honest and prompts collection.
        persona = Counter(personas).most_common(1)[0][0] if personas else ""
        share = len(members) / total_atoms
        one_liner = _one_liner(medoid, spec, persona=persona)
        opp = {
            "opportunity_id": f"op_{score.cluster_id[3:]}",
            "cluster_id": score.cluster_id,
            "title": cluster_labels.get(score.cluster_id, medoid.scene),
            "one_liner": one_liner,
            "persona": persona,
            "workaround": medoid.workaround,
            "pain_tier": _pain_tier(score.pain),
            "opportunity_tier": score.tier,
            "market_low": round(market.low * share, 2),
            "market_mid": round(market.mid * share, 2),
            "market_high": round(market.high * share, 2),
            "assumptions": market.assumptions
            + [
                {
                    "name": "声量份额分摊",
                    "key": "share",
                    "low": round(max(0.0, share * 0.7), 3),
                    "mid": round(share, 3),
                    "high": round(min(1.0, share * 1.3), 3),
                    "grade": "C",
                    "grade_label": "C 评论推断",
                    "note": "按簇内原子占比分摊品类 SOM，待用实际人群校准",
                }
            ],
            "sensitivity": [
                {**s, "delta": round(s["delta"] * share, 2)} for s in market.sensitivity
            ],
            "falsifier": market.falsifier,
            "validation": VALIDATION_KIT,
        }
        opp["solo_fit"] = assess_solo_fit(members)
        opps.append(opp)

    # Hardware / ops-heavy ideas stay, but rank below a software idea a solo
    # developer could ship within two weeks.
    opps.sort(
        key=lambda o: (0 if o["solo_fit"]["level"] == "高" else 1, o["market_mid"]),
        reverse=True,
    )
    store.insert_opportunities(run_id, opps)

    levels: dict[str, int] = {}
    for a in atoms:
        levels[a.level] = levels.get(a.level, 0) + 1

    stats = {
        "items": len(items),
        "atoms": len(atoms),
        "clusters": len(result.clusters),
        "noise_rate": round(result.noise_rate, 4),
        "levels": levels,
        "extractor": extractor_name,
        "mode": mode,
        "threshold": threshold,
        "min_size": min_size,
        "platforms": sorted({r["platform"] for r in items}),
        "window": [min(r["published_at"] for r in items), max(r["published_at"] for r in items)],
        "synthetic": all(r["platform"] == "demo" for r in items),
        "validity_filtered": filtered,
    }
    if hasattr(extractor, "stats"):
        stats["extraction"] = extractor.stats.as_dict()  # type: ignore[attr-defined]
    store.save_run(run_id, category_key, stats)

    return RunResult(run_id=run_id, category=category_key, stats=stats, opportunities=opps)


def _pain_tier(pain: float) -> str:
    return "强" if pain >= 70 else ("中" if pain >= 45 else "弱")


def _one_liner(atom: PainAtom, spec: CategorySpec, persona: str = "") -> str:
    """人群 + 场景 + 阻碍 + 代价（场景标签保持中文，阻碍引用原文）。"""
    who = persona or atom.persona or "用户"
    scene = atom.scene or spec.name
    obstacle = (atom.obstacle or "关键环节受阻").strip()
    if len(obstacle) > 60:
        obstacle = obstacle[:60].rstrip() + "…"
    cost = ""
    if atom.cost_estimate and atom.cost_type == "money":
        cost = f"，金额约 {atom.cost_estimate}"
    elif atom.cost_estimate and atom.cost_type == "time":
        cost = f"，多花 {atom.cost_estimate}"
    return f"{who}在「{scene}」中受阻：{obstacle}{cost}。"
