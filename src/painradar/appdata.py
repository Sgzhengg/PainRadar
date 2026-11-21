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
        try:
            solo_fit = json.loads(o["solo_fit_json"] or "{}")
        except (KeyError, ValueError):
            solo_fit = {}
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
                "solo_fit": solo_fit,
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
                        "likes": (m["likes"] if "likes" in m.keys() else 0),
                        "replies": (m["replies"] if "replies" in m.keys() else 0),
                        "canonical_pain": (m["canonical_pain"] if "canonical_pain" in m.keys() else ""),
                        "manual_bottleneck": (m["manual_bottleneck"] if "manual_bottleneck" in m.keys() else ""),
                        "cost_type": (m["cost_type"] if "cost_type" in m.keys() else ""),
                        "wtp_level": (m["wtp_level"] if "wtp_level" in m.keys() else ""),
                    }
                    for m in members[:max_members]
                ],
            }
        )

        likes = [int(m["likes"] or 0) for m in members]
        max_likes = max(likes, default=0)
        total_likes = sum(likes)
        text = " ".join(
            f"{m['quote']} {m['scene']} {m['workaround']} "
            f"{(m['manual_bottleneck'] if 'manual_bottleneck' in m.keys() else '')}"
            for m in members
        ).lower()
        manual = any(
            (m["manual_bottleneck"] if "manual_bottleneck" in m.keys() else "")
            for m in members
        ) or any(w in text for w in (
            "excel", "手工", "人工", "微信", "表格", "粘贴", "复制",
            "对账", "核对", "排产", "录入", "台账",
        ))
        money = any(
            (m["cost_type"] if "cost_type" in m.keys() else "") == "money"
            or (m["wtp_level"] if "wtp_level" in m.keys() else "") == "strong"
            for m in members
        ) or any(w in text for w in ("订阅", "会员", "付费", "太贵", "价格", "收费", "买断"))
        if manual:
            tag = "纯人工太繁琐"
        elif money:
            tag = "现有软件难用/太贵"
        else:
            tag = "流程低效"
        ai_fit = manual or any(w in text for w in (
            "自动", "批量", "识别", "整理", "生成", "excel", "表格", "录入", "对账",
        ))
        ease = {"低": 1.0, "中": 0.55, "高": 0.10}.get(solo_fit.get("level"), 0.40)
        hot = min(1.0, max_likes / 200.0 * 0.6 + total_likes / 2000.0 * 0.4)
        l3_l4 = ladder.get("L3", 0) + ladder.get("L4", 0)
        wtp_share = l3_l4 / max(1, len(members))
        opps[-1].update({
            "hotness": {
                "total_likes": total_likes,
                "max_likes": max_likes,
                "top_quotes": [
                    {"quote": m["quote"], "likes": int(m["likes"] or 0), "level": m["level"]}
                    for m in members
                    if m["quote"]
                ][:2],
            },
            "inspiration_tag": tag,
            "ai_fit": ai_fit,
            "inspiration_score": round(100.0 * (0.55 * hot + 0.35 * ease + 0.10 * wtp_share), 1),
        })

    opps.sort(key=lambda x: x.get("inspiration_score", 0.0), reverse=True)

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
