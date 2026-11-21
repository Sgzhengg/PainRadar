"""PainRadar crawler bridge: HTTP task API around MediaCrawler.

Endpoints (Bearer token when MEDIACRAWLER_API_TOKEN is set):

    POST /api/crawl              {platform, keywords, max_notes, cookies}
    GET  /api/tasks/{task_id}
    GET  /api/tasks/{task_id}/results
    GET  /health

The crawl runs in a background thread, so the caller gets a task_id immediately
and PainRadar polls it without holding a long HTTP connection.
"""

from __future__ import annotations

import hmac
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from runner import CrawlSpec, MediaCrawlerRunner, NeedLoginError, RunnerError
from storage import TaskStore

TASK_DB = os.environ.get("TASK_DB", "/data/tasks.db")
RESULT_DIR = Path(os.environ.get("RESULT_DIR", "/data/results"))
API_TOKEN = os.environ.get("MEDIACRAWLER_API_TOKEN", "").strip()

app = FastAPI(title="PainRadar Crawler Bridge", version="0.1.0")
store = TaskStore(TASK_DB)
runner = MediaCrawlerRunner()
RESULT_DIR.mkdir(parents=True, exist_ok=True)


class CrawlRequest(BaseModel):
    platform: str
    keywords: list[str] = []
    max_notes: int = 50
    cookies: Any = None


def require_token(authorization: str = Header("")) -> None:
    if not API_TOKEN:
        return
    expected = f"Bearer {API_TOKEN}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="invalid crawler token")


def _execute(task_id: str, spec: CrawlSpec) -> None:
    try:
        store.update(task_id, status="running", stage="crawling", progress=10)

        def on_progress(stage: str, progress: int, message: str) -> None:
            store.update(task_id, stage=stage, progress=progress, message=message)

        notes = runner.run(spec, on_progress=on_progress)
        result_path = RESULT_DIR / f"{task_id}.json"
        tmp = result_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
        tmp.replace(result_path)
        store.update(
            task_id,
            status="completed",
            stage="completed",
            progress=100,
            message=f"抓取 {len(notes)} 条",
            result_path=str(result_path),
        )
    except NeedLoginError as exc:
        store.update(
            task_id,
            status="failed",
            stage="need_login",
            need_login=1,
            error=f"登录态已过期，请在配置中更新平台 Cookie（{exc}）",
        )
    except RunnerError as exc:
        store.update(task_id, status="failed", stage="failed", error=f"远程抓取失败：{exc}")
    except Exception as exc:  # noqa: BLE001
        store.update(task_id, status="failed", stage="failed", error=f"{type(exc).__name__}: {exc}")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "painradar-crawler", "home": str(runner.home)}


@app.post("/api/crawl", status_code=202)
def start_crawl(req: CrawlRequest, _: None = Depends(require_token)) -> dict[str, Any]:
    platform = req.platform.strip().lower()
    if platform not in {"xhs", "dy", "bili", "zhihu"}:
        raise HTTPException(status_code=400, detail="platform must be xhs|dy|bili|zhihu")
    keywords = [k.strip() for k in req.keywords if k.strip()]
    if not keywords:
        raise HTTPException(status_code=400, detail="keywords is required")

    task_id = uuid.uuid4().hex[:16]
    store.create(task_id, platform, keywords)
    spec = CrawlSpec(
        platform=platform,
        keywords=keywords,
        max_notes=max(1, min(req.max_notes, 1000)),
        cookies=req.cookies,
    )
    threading.Thread(target=_execute, args=(task_id, spec), daemon=True).start()
    return {"task_id": task_id, "status": "queued"}


@app.get("/api/tasks/{task_id}")
def task_status(task_id: str, _: None = Depends(require_token)) -> dict[str, Any]:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return store.as_public(task)


@app.get("/api/tasks/{task_id}/results")
def task_results(task_id: str, _: None = Depends(require_token)) -> list[dict[str, Any]]:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task["need_login"]:
        raise HTTPException(status_code=409, detail=task["error"] or "need login")
    if task["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"task is {task['status']}")
    path = Path(task["result_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="result file missing")
    return json.loads(path.read_text(encoding="utf-8"))
