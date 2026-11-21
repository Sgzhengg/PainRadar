"""Validation for returned annotation batches."""

from __future__ import annotations

LEVELS = {"L0", "L1", "L2", "L3", "L4"}
WTP = {"strong", "weak", "none", ""}


def validate(batch: list[dict], labels: list[dict], scenes: set[str]) -> list[str]:
    errors: list[str] = []
    batch_ids = [r["comment_uid"] for r in batch]
    label_ids = [r["comment_uid"] for r in labels]

    missing = set(batch_ids) - set(label_ids)
    extra = set(label_ids) - set(batch_ids)
    if missing:
        errors.append(f"缺少 {len(missing)} 条：{', '.join(sorted(missing)[:5])}")
    if extra:
        errors.append(f"多出 {len(extra)} 条（不在批次里）：{', '.join(sorted(extra)[:5])}")

    for row in labels:
        uid = row["comment_uid"]
        valid = (row.get("gold_valid") or "").strip()
        level = (row.get("gold_level") or "").strip()
        scene = (row.get("gold_scene") or "").strip()
        obstacle = (row.get("gold_obstacle") or "").strip()
        wtp = (row.get("gold_wtp") or "").strip()

        if valid not in {"0", "1"}:
            errors.append(f"{uid}: gold_valid 必须是 0 或 1，实际 {valid!r}")
            continue
        if wtp not in WTP:
            errors.append(f"{uid}: gold_wtp 取值非法 {wtp!r}")
        if valid == "0":
            if level or scene or obstacle:
                errors.append(f"{uid}: 标为无效却填了 level/scene/obstacle")
            continue
        if level not in LEVELS:
            errors.append(f"{uid}: gold_level 非法 {level!r}")
        if not obstacle:
            errors.append(f"{uid}: 有效痛点缺少 gold_obstacle")
        if scene not in scenes:
            errors.append(f"{uid}: 未知场景 {scene!r}")
    return errors
