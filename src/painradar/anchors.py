"""External anchors: the non-comment evidence that keeps market numbers honest.

An anchor is one observation of an outside fact — a rating count, a price, a
BSR, an ad count. The report prints them next to the market range so a reader
can see whether the sample is 0.1% or 80% of the observable population.

Sources implemented:

* ``itunes``  — public iTunes lookup API (rating count / average rating).
* ``file``    — CSV import for Keepa / Ad Library / manual research exports.

Every anchor carries a grade (A/B/C/D) and an ``as_of`` date.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .net import HttpClient, HttpError
from .store import Store


@dataclass
class AnchorObs:
    category: str
    source: str
    metric: str
    value: float
    as_of: str
    url: str = ""
    grade: str = "C"
    note: str = ""

    def anchor_id(self) -> str:
        raw = f"{self.category}|{self.source}|{self.metric}|{self.as_of}|{self.value}"
        return "an_" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    def as_row(self) -> dict[str, object]:
        return {
            "anchor_id": self.anchor_id(),
            "category": self.category,
            "source": self.source,
            "metric": self.metric,
            "value": self.value,
            "as_of": self.as_of,
            "url": self.url,
            "grade": self.grade,
            "note": self.note,
        }


def save_anchors(store: Store, anchors: Iterable[AnchorObs]) -> int:
    n = 0
    for a in anchors:
        store.insert_anchor(a.as_row())  # type: ignore[arg-type]
        n += 1
    return n


def import_csv(store: Store, path: Path, category: str) -> int:
    """CSV columns: metric,value[,source,as_of,url,grade,note]."""
    n = 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            metric = (row.get("metric") or "").strip()
            raw_value = (row.get("value") or "").strip()
            if not metric or not raw_value:
                continue
            obs = AnchorObs(
                category=category,
                source=(row.get("source") or "manual").strip(),
                metric=metric,
                value=float(raw_value),
                as_of=(row.get("as_of") or date.today().isoformat()).strip(),
                url=(row.get("url") or "").strip(),
                grade=((row.get("grade") or "C").strip().upper() or "C")[:1],
                note=(row.get("note") or "").strip(),
            )
            store.insert_anchor(obs.as_row())  # type: ignore[arg-type]
            n += 1
    return n


@dataclass
class ItunesAnchor:
    """Pull rating count and average rating for an App Store app."""

    category: str
    app_id: str
    country: str = "us"
    client: HttpClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = HttpClient(user_agent="PainRadar/0.1 (research)", rate_per_sec=0.5)

    def fetch(self) -> list[AnchorObs]:
        url = f"https://itunes.apple.com/lookup?id={self.app_id}&country={self.country}"
        try:
            data = self.client.get_json(url)  # type: ignore[union-attr]
        except HttpError:
            return []
        if not isinstance(data, dict) or not data.get("results"):
            return []
        app = data["results"][0]
        as_of = date.today().isoformat()
        out: list[AnchorObs] = []
        if isinstance(app.get("userRatingCount"), (int, float)):
            out.append(
                AnchorObs(
                    category=self.category,
                    source="itunes",
                    metric="rating_count",
                    value=float(app["userRatingCount"]),
                    as_of=as_of,
                    url=str(app.get("trackViewUrl", "")),
                    grade="A",
                    note=f"App Store {self.country} · {app.get('trackName', '')}",
                )
            )
        if isinstance(app.get("averageUserRating"), (int, float)):
            out.append(
                AnchorObs(
                    category=self.category,
                    source="itunes",
                    metric="avg_rating",
                    value=float(app["averageUserRating"]),
                    as_of=as_of,
                    url=str(app.get("trackViewUrl", "")),
                    grade="A",
                    note=f"App Store {self.country} · {app.get('trackName', '')}",
                )
            )
        return out


def sample_coverage(store: Store, category: str, run_id: str) -> dict[str, float] | None:
    """Sample size as a share of the observable review population, if known."""
    rows = store.anchors(category)
    counts = [r["value"] for r in rows if r["metric"] == "rating_count"]
    if not counts:
        return None
    population = max(counts)
    if population <= 0:
        return None
    sample = store._conn.execute(
        "SELECT COUNT(*) AS n FROM items WHERE category=? AND deleted_at IS NULL", (category,)
    ).fetchone()["n"]
    return {
        "sample": float(sample),
        "population": population,
        "coverage": sample / population,
    }
