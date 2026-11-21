"""File / BYOD connector.

Reads JSONL, JSON or CSV exports. This is the only connector enabled in M0-M1:
it covers the "user exports their own data" path, which is both the most
compliant source and the one carrying outcome labels (plan §6.1).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from ..schema import RawItem, Tier
from .base import registry


@dataclass
class FileConnector:
    path: Path
    category: str
    platform: str = "file"
    tos_basis: str = "user_provided"
    tier: Tier = Tier.A

    platform_name = "file"

    def rows(self) -> Iterator[dict]:
        suffix = self.path.suffix.lower()
        if suffix == ".jsonl":
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
        elif suffix == ".json":
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("items", [])
            yield from data
        elif suffix == ".csv":
            with self.path.open("r", encoding="utf-8-sig", newline="") as fh:
                yield from csv.DictReader(fh)
        else:
            raise SystemExit(f"unsupported file type: {self.path.suffix}")

    def fetch(self) -> Iterable[RawItem]:
        for i, row in enumerate(self.rows(), start=1):
            yield RawItem(
                platform=str(row.get("platform") or self.platform),
                item_id=str(row.get("item_id") or row.get("id") or f"{self.path.stem}-{i}"),
                url=str(row.get("url") or ""),
                text=str(row.get("text") or ""),
                published_at=str(row.get("published_at") or row.get("date") or "2026-01-01"),
                category=self.category,
                author=str(row.get("author") or ""),
                lang=str(row.get("lang") or ""),
                rating=row.get("rating"),
                tier=self.tier,
                tos_basis=str(row.get("tos_basis") or self.tos_basis),
            )

    def health(self) -> dict[str, object]:
        return {"platform": self.platform, "path": str(self.path), "exists": self.path.exists()}


registry.register("file", FileConnector)
