"""Semantic adjudication of B-set candidates.

Word matching produced a 90% random-baseline hit rate, so a "hit" meant
nothing. This module asks a model one narrow question per candidate:

    "Does this product specifically address the pain in this prediction?"

It is still a filter, not a judge: accepted evidence must be spot-checked by a
human, and the review export exists for exactly that.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .net import HttpClient, HttpError

SYSTEM = """You are auditing market evidence. Given a pain prediction and a numbered
list of candidate products, decide for EACH candidate whether it specifically
addresses that pain (not merely shares words). Return JSON:
{"results": [{"index": 1, "match": "yes|no|uncertain", "reason": "<12 words max>", "confidence": 0.0-1.0}]}
Rules:
- "yes" only if the product's stated purpose is the same problem, not a generic tool.
- Shared words like water/clean/app are NOT evidence by themselves.
- If the description is too thin to tell, return "uncertain".
Return JSON only."""


@dataclass
class Adjudication:
    index: int
    match: str
    reason: str
    confidence: float


class LLMAdjudicator:
    version = "adjudicate-v0.1"

    def __init__(
        self,
        client: HttpClient | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = (base_url or os.environ.get("PAINRADAR_LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("PAINRADAR_LLM_API_KEY", "")
        self.model = model or os.environ.get("PAINRADAR_LLM_MODEL", "")
        if client is None and not (self.base_url and self.model):
            raise RuntimeError("adjudicator needs PAINRADAR_LLM_BASE_URL and PAINRADAR_LLM_MODEL")
        self.client = client or HttpClient(user_agent="PainRadar/0.1", timeout=60, max_retries=2, rate_per_sec=2)

    def judge(self, proposition: str, candidates: list[dict]) -> list[Adjudication]:
        if not candidates:
            return []
        listing = [
            {
                "index": i + 1,
                "name": c.get("name", ""),
                "description": (c.get("description") or "")[:300],
            }
            for i, c in enumerate(candidates[:15])
        ]
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"prediction": proposition, "candidates": listing}, ensure_ascii=False
                    ),
                },
            ],
        }
        try:
            body = self.client.post_json(
                f"{self.base_url}/chat/completions",
                payload,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
            content = body["choices"][0]["message"]["content"]  # type: ignore[index]
            data = json.loads(content[content.find("{"): content.rfind("}") + 1])
        except (HttpError, OSError, KeyError, ValueError, TypeError):
            return [Adjudication(i + 1, "uncertain", "adjudication failed", 0.0) for i in range(len(listing))]

        out: list[Adjudication] = []
        for row in data.get("results", []):
            try:
                out.append(
                    Adjudication(
                        index=int(row.get("index", 0)),
                        match=str(row.get("match", "uncertain")).lower(),
                        reason=str(row.get("reason", ""))[:80],
                        confidence=float(row.get("confidence", 0.0) or 0.0),
                    )
                )
            except (TypeError, ValueError):
                continue
        known = {a.index for a in out}
        for i in range(1, len(listing) + 1):
            if i not in known:
                out.append(Adjudication(i, "uncertain", "not returned", 0.0))
        return out
