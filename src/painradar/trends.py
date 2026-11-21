"""Google Trends client (no official API; uses the public web endpoints).

Google exposes no public API. The website calls two endpoints
(``/trends/api/explore`` and ``/trends/api/widgetdata/multiline``) that work
without login but return 429 unless a cookie jar has visited the homepage first.
This client bootstraps a cookie (NID), then fetches one term at a time.

Values are relative (0-100) *within one request*: a single-term series is
normalised to its own peak, so slope is meaningful but absolute level is not
comparable across terms.
"""

from __future__ import annotations

import http.cookiejar
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
BASE = "https://trends.google.com"


@dataclass
class TrendSeries:
    term: str
    geo: str
    timeframe: str
    points: list[tuple[str, int]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        vals = [v for _, v in self.points]
        if not vals:
            return {"points": 0}
        n = len(vals)
        head = vals[: max(1, n // 4)]
        tail = vals[-max(1, n // 4):]
        head_avg = sum(head) / len(head)
        tail_avg = sum(tail) / len(tail)
        peak_idx = max(range(n), key=lambda i: vals[i])
        # least-squares slope, expressed as % of the mean over the whole window
        mx = (n - 1) / 2
        my = sum(vals) / n
        denom = sum((i - mx) ** 2 for i in range(n))
        slope = sum((i - mx) * (v - my) for i, v in enumerate(vals)) / denom if denom else 0.0
        trend_pct = round(slope * (n - 1) / my * 100, 1) if my else None
        yoy_pct = None
        if n >= 104:
            last12 = vals[-52:]
            prev12 = vals[-104:-52]
            a = sum(prev12) / len(prev12)
            b = sum(last12) / len(last12)
            yoy_pct = round((b - a) / a * 100, 1) if a else None
        return {
            "points": n,
            "mean": round(sum(vals) / n, 1),
            "head_avg": round(head_avg, 1),
            "tail_avg": round(tail_avg, 1),
            "trend_pct": trend_pct,
            "yoy_pct": yoy_pct,
            "change_pct": round((tail_avg - head_avg) / head_avg * 100, 1) if head_avg else None,
            "peak_date": self.points[peak_idx][0],
            "peak_value": vals[peak_idx],
            "latest": vals[-1],
        }


class GoogleTrends:
    def __init__(self, hl: str = "en-US", tz: int = 0, sleep: float = 4.0) -> None:
        self.hl = hl
        self.tz = tz
        self.sleep = sleep
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.opener.addheaders = [
            ("User-Agent", UA),
            ("Accept-Language", "en-US,en;q=0.9"),
        ]
        self._bootstrapped = False

    def bootstrap(self) -> None:
        if self._bootstrapped:
            return
        self.opener.open(f"{BASE}/trends/?geo=US", timeout=25).read()
        self._bootstrapped = True
        time.sleep(1.0)

    def _get_json(self, url: str) -> Any:
        raw = self.opener.open(url, timeout=30).read().decode("utf-8", "ignore")
        if raw.startswith(")]}'"):
            raw = raw.split("\n", 1)[1]
        return json.loads(raw)

    def interest(
        self, term: str, geo: str = "", timeframe: str = "today 12-m"
    ) -> TrendSeries:
        self.bootstrap()
        req = {
            "comparisonItem": [{"keyword": term, "geo": geo, "time": timeframe}],
            "category": 0,
            "property": "",
        }
        explore = self._get_json(
            f"{BASE}/trends/api/explore?hl={self.hl}&tz={self.tz}&req="
            + urllib.parse.quote(json.dumps(req))
        )
        token = None
        widget_req = None
        for w in explore.get("widgets", []):
            if w.get("id") == "TIMESERIES":
                token = w.get("token")
                widget_req = json.dumps(w.get("request"))
                break
        if not token:
            raise RuntimeError(f"no TIMESERIES widget for {term!r}")

        time.sleep(self.sleep)
        data = self._get_json(
            f"{BASE}/trends/api/widgetdata/multiline?hl={self.hl}&tz={self.tz}"
            f"&req={urllib.parse.quote(widget_req)}&token={urllib.parse.quote(token)}"
        )
        series = TrendSeries(term=term, geo=geo, timeframe=timeframe)
        for point in (data.get("default") or {}).get("timelineData", []):
            value = (point.get("value") or [0])[0]
            series.points.append((point.get("formattedTime", ""), int(value)))
        return series
