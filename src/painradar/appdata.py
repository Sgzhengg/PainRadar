"""Assemble run data for the interactive UI (single-file, no server)."""

from __future__ import annotations

import json
from typing import Any

from .config import category as get_category
from .store import Store


def _app_label(item_id: object, spec) -> str:
    parts = str(item_id or "").split("_")
    app = parts[1] if len(parts) >= 3 and parts[0] == "as" else ""
    return spec.app_names.get(app, app)


def build_run(store: Store, run_id: str, max_members: int = 12) -> dict[str, Any]:
    run = store._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise SystemExit(f"run not found: {run_id}")
    spec = get_category(run["category"])
    stats = json.loads(run["stats_json"])
    scores = {
        r["cluster_id"]: r
        for r in store._conn.execute("SELECT * FROM scores WHERE run_id=?", (run_id,)).fetchall()
    }

    opps: list[dict[str, Any]] = []
    for o in store.opportunities(run_id):
        score = scores.get(o["cluster_id"])
        factors = json.loads(score["factors_json"]) if score else {}
        members = store.cluster_members(run_id, o["cluster_id"])
        ladder: dict[str, int] = {}
        for m in members:
            ladder[m["level"]] = ladder.get(m["level"], 0) + 1
        opps.append(
            {
                "cluster_id": o["cluster_id"],
                "title": o["title"],
                "one_liner": o["one_liner"],
                "persona": o["persona"],
                "workaround": o["workaround"],
                "pain": round(score["pain"], 1) if score else None,
                "opportunity": round(score["opportunity"], 1) if score else None,
                "pain_tier": o["pain_tier"],
                "opportunity_tier": o["opportunity_tier"],
                "market_low": o["market_low"],
                "market_mid": o["market_mid"],
                "market_high": o["market_high"],
                "falsifier": o["falsifier"],
                "factors": factors,
                "ladder": ladder,
                "member_count": len(members),
                "members": [
                    {
                        "quote": m["quote"],
                        "platform": m["platform"],
                        "app": _app_label(m["item_id"], spec),
                        "published_at": m["published_at"],
                        "url": m["url"],
                        "confidence": round(m["confidence"], 2),
                        "level": m["level"],
                        "scene": m["scene"],
                    }
                    for m in members[:max_members]
                ],
            }
        )

    anchors = [
        {"metric": a["metric"], "value": a["value"], "source": a["source"], "grade": a["grade"]}
        for a in store.anchors(spec.key)
    ]
    levels = stats.get("levels", {})
    total = sum(levels.values()) or 1
    return {
        "run_id": run_id,
        "category": spec.key,
        "category_name": spec.name,
        "created_at": run["created_at"],
        "stats": {
            "items": stats.get("items", 0),
            "atoms": stats.get("atoms", 0),
            "clusters": stats.get("clusters", 0),
            "noise_rate": stats.get("noise_rate", 0),
            "extractor": stats.get("extractor", ""),
            "l2_share": sum(levels.get(k, 0) for k in ("L2", "L3", "L4")) / total,
            "levels": levels,
        },
        "opportunities": opps[:20],
        "anchors": anchors,
    }


def build_payload(sources: list[tuple[Store, str | None]]) -> dict[str, Any]:
    """One payload from several databases, latest run per category.

    Earlier sources win when a category appears twice, so pass the preferred
    (e.g. LLM) database first.
    """
    runs: list[dict[str, Any]] = []
    seen_categories: set[str] = set()
    for store, run_id in sources:
        if run_id is None:
            rows = store._conn.execute(
                "SELECT run_id, category FROM runs ORDER BY created_at DESC"
            ).fetchall()
            seen_here: set[str] = set()
            for row in rows:
                cat = row["category"]
                if cat in seen_here or cat in seen_categories:
                    continue
                seen_here.add(cat)
                runs.append(build_run(store, row["run_id"]))
            seen_categories |= seen_here
        else:
            run = build_run(store, run_id)
            if run["category"] in seen_categories:
                continue
            seen_categories.add(run["category"])
            runs.append(run)
    runs.sort(key=lambda r: r["category_name"])
    return {"runs": runs}
