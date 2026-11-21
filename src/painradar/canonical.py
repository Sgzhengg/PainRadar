"""Demand normalization: turn a cluster into a comparable demand statement.

Word similarity cannot bridge "can't cancel subscription" and "charged me for a
year". This step asks a model to write one short Chinese demand statement plus a
type for each cluster, so clusters from different domains can be merged by
*meaning* instead of vocabulary.

The type vocabulary is not fixed: each call sees the types produced so far and
is told to reuse them when possible, so the taxonomy emerges from the data.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .net import HttpClient, HttpError

SYSTEM = """你是需求分析师。给定若干评论簇（每簇有 id 和最多 6 条原文），为每簇输出一条中文需求陈述。

要求：
- demand：不超过 14 字，写成"谁/什么场景 + 卡在哪"，例如"订阅取消流程不透明"。
  不要写"用户希望…"，不要复述原文。
- **优先复用 existing_demands 中语义相同的陈述，并且逐字使用原句**；
  只有确实不同时才新建。
- type：4-10 字，具体到"什么问题"，例如"订阅取消流程""睡眠数据准确性"，不要用"订阅付费"这种大类。优先复用 existing_types。
- buyer：不超过 12 字的人群描述，例如"订阅制 App 用户"。
- workaround：用户现在怎么凑合（没有就空字符串）。
- cost：观察到的代价（时间/金钱/情绪，没有就空字符串）。

返回 JSON：{"results": [{"id": "...", "demand": "...", "type": "...", "buyer": "...", "workaround": "...", "cost": "..."}]}
只返回 JSON。"""


TAXONOMY_SYSTEM = """你是需求分析师。下面是若干评论簇的摘要（id、品类、簇标签、少量原文）。
请归纳出 8-12 个**跨簇共享**的需求，每个需求满足：
- demand：不超过 14 字，写成"谁/什么场景 + 卡在哪"，例如"订阅取消流程不透明"；
- definition：一句话说明边界（哪些属于它、哪些不属于）；
- buyer：不超过 12 字的人群。
要求：不同品类的同类问题必须归到同一个需求；不要为每个簇单独造一个需求。
返回 JSON：{"demands": [{"id": "D1", "demand": "...", "definition": "...", "buyer": "..."}]}"""

ASSIGN_SYSTEM = """你是需求分析师。给定一份需求表（id、demand、definition）和若干评论簇，
把每个簇归入最贴近的一个需求；如果没有任何一条真正贴合，demand_id 用 "D0"。宁可用 D0，也不要硬塞。
返回 JSON：{"assignments": [{"cluster_id": "...", "demand_id": "D1"}]}"""


@dataclass
class Canonical:
    key: str
    demand: str
    type: str
    buyer: str = ""
    workaround: str = ""
    cost: str = ""


def _key(category: str, label: str) -> str:
    return hashlib.sha256(f"v4|{category}|{label}".encode()).hexdigest()[:16]


def _load_cache(path: Path | None) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def _save_cache(path: Path | None, data: dict) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class LLMNormalizer:
    def __init__(
        self,
        client: HttpClient | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = (base_url or os.environ.get("PAINRADAR_LLM_BASE_URL", "")).rstrip("/")
        self.model = model or os.environ.get("PAINRADAR_LLM_MODEL", "")
        self.api_key = api_key or os.environ.get("PAINRADAR_LLM_API_KEY", "")
        if client is None and not (self.base_url and self.model):
            raise RuntimeError("normalizer needs PAINRADAR_LLM_BASE_URL and PAINRADAR_LLM_MODEL")
        self.client = client or HttpClient(user_agent="PainRadar/0.1", timeout=90, max_retries=2, rate_per_sec=2)

    def _raw_call(self, system: str, payload: dict) -> dict:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        try:
            resp = self.client.post_json(
                f"{self.base_url}/chat/completions",
                body,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
            content = resp["choices"][0]["message"]["content"]  # type: ignore[index]
            return json.loads(content[content.find("{"): content.rfind("}") + 1])
        except (HttpError, OSError, KeyError, ValueError, TypeError):
            return {}

    def taxonomy(self, clusters: list, target: int = 10) -> list[dict]:
        payload = {
            "target": target,
            "clusters": [
                {
                    "id": _key(c.category, c.label),
                    "category": c.category,
                    "label": c.label,
                    "quotes": [a.get("quote", "")[:140] for a in c.atoms[:3]],
                }
                for c in clusters
            ],
        }
        data = self._raw_call(TAXONOMY_SYSTEM, payload)
        out = []
        for i, d in enumerate(data.get("demands", []), start=1):
            demand = str(d.get("demand", "")).strip()
            if not demand:
                continue
            out.append(
                {
                    "id": f"D{i}",
                    "demand": demand[:20],
                    "definition": str(d.get("definition", ""))[:80],
                    "buyer": str(d.get("buyer", ""))[:16],
                }
            )
        return out

    def assign(self, clusters: list, taxonomy: list[dict]) -> dict[str, str]:
        payload = {
            "taxonomy": taxonomy,
            "clusters": [
                {
                    "id": _key(c.category, c.label),
                    "category": c.category,
                    "label": c.label,
                    "quotes": [a.get("quote", "")[:120] for a in c.atoms[:2]],
                }
                for c in clusters
            ],
        }
        data = self._raw_call(ASSIGN_SYSTEM, payload)
        out: dict[str, str] = {}
        for row in data.get("assignments", []):
            try:
                out[str(row["cluster_id"])] = str(row["demand_id"])
            except (KeyError, TypeError):
                continue
        return out

    def _call(self, payload_clusters: list[dict], existing: list[str], demands: list[str]) -> list[dict]:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "existing_types": existing,
                            "existing_demands": demands[-40:],
                            "clusters": payload_clusters,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        try:
            resp = self.client.post_json(
                f"{self.base_url}/chat/completions",
                body,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
            content = resp["choices"][0]["message"]["content"]  # type: ignore[index]
            data = json.loads(content[content.find("{"): content.rfind("}") + 1])
            return list(data.get("results", []))
        except (HttpError, OSError, KeyError, ValueError, TypeError):
            return []

    def canonicalize(self, clusters: list, batch_size: int = 40, cache_path: Path | None = None) -> dict[str, Canonical]:
        cache = _load_cache(cache_path)
        out: dict[str, Canonical] = {}
        todo = []
        for c in clusters:
            key = _key(c.category, c.label)
            if key in cache:
                out[key] = Canonical(**cache[key])
            else:
                todo.append(c)

        types: list[str] = [v.get("type", "") for v in cache.values() if v.get("type")]
        demands: list[str] = [v.get("demand", "") for v in cache.values() if v.get("demand")]
        for start in range(0, len(todo), batch_size):
            chunk = todo[start : start + batch_size]
            payload = [
                {
                    "id": _key(c.category, c.label),
                    "category": c.category,
                    "label": c.label,
                    "quotes": [a.get("quote", "")[:160] for a in c.atoms[:6]],
                }
                for c in chunk
            ]
            results = self._call(payload, sorted(set(types))[:12], demands)
            for item in results:
                try:
                    canon = Canonical(
                        key=str(item["id"]),
                        demand=str(item.get("demand", "")).strip()[:20],
                        type=str(item.get("type", "")).strip()[:8],
                        buyer=str(item.get("buyer", "")).strip()[:16],
                        workaround=str(item.get("workaround", "")).strip()[:40],
                        cost=str(item.get("cost", "")).strip()[:40],
                    )
                except (KeyError, TypeError):
                    continue
                if not canon.demand:
                    continue
                out[canon.key] = canon
                cache[canon.key] = asdict(canon)
                if canon.type and canon.type not in types:
                    types.append(canon.type)
                if canon.demand and canon.demand not in demands:
                    demands.append(canon.demand)
            _save_cache(cache_path, cache)
        return out
