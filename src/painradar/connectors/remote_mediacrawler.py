"""Client for a remote MediaCrawler service (e.g. deployed on Zeabur).

The edge/Web process never drives a browser itself:

1. ``start_crawl`` POSTs a job and returns a ``task_id`` immediately;
2. the caller polls ``get_task`` (non-blocking, safe behind Cloudflare timeouts);
3. ``poll_and_ingest`` fetches the result JSON, cleans it with the existing
   ``MediaCrawlerConnector`` and writes into the evidence ledger.

Auth is a Bearer token so the crawler endpoint cannot be abused.
"""

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

from .mediacrawler import MediaCrawlerConnector
from ..pipeline import ingest_items


class RemoteCrawlerError(RuntimeError):
    def __init__(self, message: str, status: int = 0, payload: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


class NeedLoginError(RemoteCrawlerError):
    """Raised when the remote platform session (cookie) has expired."""


@dataclass
class CrawlTask:
    task_id: str
    status: str = "queued"
    progress: int = 0
    message: str = ""
    need_login: bool = False
    error: str = ""
    result_url: str = ""

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "CrawlTask":
        raw = data.get("task") if isinstance(data.get("task"), dict) else data
        return cls(
            task_id=str(raw.get("task_id") or raw.get("id") or ""),
            status=str(raw.get("status") or "queued").lower(),
            progress=int(raw.get("progress") or 0),
            message=str(raw.get("message") or ""),
            need_login=bool(raw.get("need_login") or data.get("need_login")),
            error=str(raw.get("error") or ""),
            result_url=str(raw.get("result_url") or ""),
        )


class RemoteMediaCrawler:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        client: httpx.Client | None = None,
        timeout: float = 60.0,
    ) -> None:
        from ..config import MEDIACRAWLER_API_TOKEN, MEDIACRAWLER_API_URL

        self.base_url = (base_url if base_url is not None else MEDIACRAWLER_API_URL).rstrip("/")
        self.token = token if token is not None else MEDIACRAWLER_API_TOKEN
        self.client = client or httpx.Client(timeout=timeout)

    def configured(self) -> bool:
        return bool(self.base_url)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.base_url:
            raise RemoteCrawlerError("MEDIACRAWLER_API_URL is not configured")
        url = f"{self.base_url}{path}"
        resp = self.client.request(method, url, headers=self._headers(), **kwargs)
        try:
            data = resp.json()
        except ValueError:
            data = None
        if resp.status_code == 401 or resp.status_code == 403:
            raise NeedLoginError(
                "登录态已过期或 token 无效，请在配置中更新平台 Cookie / MEDIACRAWLER_API_TOKEN",
                resp.status_code,
                data,
            )
        if resp.status_code >= 400:
            raise RemoteCrawlerError(
                f"crawler {method} {path} failed: {resp.status_code}", resp.status_code, data
            )
        return data

    # -- async task API -------------------------------------------------
    def start_crawl(
        self,
        platform: str,
        keywords: list[str] | str,
        max_notes: int = 50,
        cookies_override: dict[str, str] | None = None,
        category: str = "",
    ) -> CrawlTask:
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        payload = {
            "platform": platform,
            "keywords": keywords,
            "max_notes": max(1, min(int(max_notes), 1000)),
            "category": category,
        }
        if cookies_override:
            payload["cookies"] = cookies_override
        data = self._request("POST", "/api/crawl", json=payload)
        task = CrawlTask.from_payload(data or {})
        if task.need_login:
            raise NeedLoginError("登录态已过期，请在配置中更新平台 Cookie", 200, data)
        if not task.task_id:
            raise RemoteCrawlerError(f"crawler did not return task_id: {data}", 200, data)
        return task

    def get_task(self, task_id: str) -> CrawlTask:
        data = self._request("GET", f"/api/tasks/{task_id}")
        task = CrawlTask.from_payload(data or {})
        if not task.task_id:
            task.task_id = task_id
        return task

    def fetch_results(self, task_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/api/tasks/{task_id}/results")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            for key in ("data", "items", "results", "notes"):
                value = data.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
        raise RemoteCrawlerError(f"unexpected results payload: {type(data).__name__}", 200, data)

    # -- polling / ingest ----------------------------------------------
    def poll_and_ingest(
        self,
        task_id: str,
        category: str,
        store: Any,
        interval: float = 3.0,
        timeout: float = 900.0,
        on_stage: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout

        def stage(name: str, **extra: Any) -> None:
            if on_stage:
                on_stage(name, extra)

        while True:
            task = self.get_task(task_id)
            if task.need_login:
                raise NeedLoginError(
                    "登录态已过期，请在配置中更新平台 Cookie", 200, task.__dict__
                )
            if task.status in ("completed", "done", "success"):
                break
            if task.status in ("failed", "error", "cancelled"):
                raise RemoteCrawlerError(task.error or f"crawl {task.status}", 200, task.__dict__)
            if time.time() > deadline:
                raise RemoteCrawlerError(f"crawl timed out after {timeout:.0f}s", 0, task.__dict__)
            stage(
                "crawling",
                task_id=task_id,
                progress=task.progress,
                message=task.message or task.status,
            )
            time.sleep(interval)

        stage("ingesting", task_id=task_id)
        rows = self.fetch_results(task_id)
        tmp = Path(tempfile.mkdtemp(prefix="painradar-crawl-")) / "results.json"
        tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        connector = MediaCrawlerConnector(path=tmp, category=category)
        result = ingest_items(store, connector.fetch(), category)
        return {
            "task_id": task_id,
            "rows": len(rows),
            "inserted": result.inserted,
            "duplicates": result.duplicates,
            "skipped": result.skipped,
            "connector": connector.stats,
        }

    def set_platform_cookie(self, platform: str, cookie: str) -> dict[str, Any]:
        data = self._request(
            "POST",
            f"/api/platforms/{platform}/cookie",
            json={"cookie": cookie},
        )
        return data if isinstance(data, dict) else {}

    def platforms(self) -> list[dict[str, Any]]:
        if not self.base_url:
            return []
        data = self._request("GET", "/api/platforms")
        if isinstance(data, dict) and isinstance(data.get("platforms"), list):
            return [x for x in data["platforms"] if isinstance(x, dict)]
        return []

    def health(self) -> dict[str, Any]:
        if not self.base_url:
            return {"ok": False, "reason": "MEDIACRAWLER_API_URL not set"}
        try:
            data = self._request("GET", "/health")
            return {"ok": True, "base_url": self.base_url, "detail": data}
        except RemoteCrawlerError as exc:
            return {"ok": False, "base_url": self.base_url, "reason": str(exc), "status": exc.status}
