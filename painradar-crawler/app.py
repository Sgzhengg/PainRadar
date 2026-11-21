"""PainRadar crawler bridge: HTTP task API around MediaCrawler.

Endpoints (Bearer token when MEDIACRAWLER_API_TOKEN is set):

    POST /api/crawl              {platform, keywords, max_notes, cookies}
    GET  /api/tasks/{task_id}
    GET  /api/tasks/{task_id}/results
    POST /api/profiles/{platform}  upload a zipped Chrome profile
    GET  /api/profiles             list uploaded profiles
    GET  /health

The crawl runs in a background thread, so the caller gets a task_id immediately
and PainRadar polls it without holding a long HTTP connection.
"""

from __future__ import annotations

import hmac
import io
import json
import os
import shutil
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

from runner import CrawlSpec, MediaCrawlerRunner, NeedLoginError, RunnerError
from storage import TaskStore


def _default_data_dir() -> Path:
    """/data on Zeabur; temp dir in CI/dev where /data is not writable."""
    root = Path("/data")
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return root
    except OSError:
        return Path(tempfile.gettempdir()) / "painradar-crawler"


DATA_ROOT = Path(os.environ.get("DATA_DIR", _default_data_dir()))
TASK_DB = os.environ.get("TASK_DB", str(DATA_ROOT / "tasks.db"))
RESULT_DIR = Path(os.environ.get("RESULT_DIR", DATA_ROOT / "results"))
PROFILE_ROOT = Path(os.environ.get("PROFILE_DIR", DATA_ROOT / "browser_data"))
COOKIE_DIR = Path(os.environ.get("COOKIE_DIR", DATA_ROOT / "cookies"))
API_TOKEN = os.environ.get("MEDIACRAWLER_API_TOKEN", "").strip()
MAX_PROFILE_BYTES = int(os.environ.get("MAX_PROFILE_BYTES", str(300 * 1024 * 1024)))
# One Chromium crawl at a time by default: prevents OOM on a small Zeabur plan.
MAX_CONCURRENT_TASKS = max(1, int(os.environ.get("MAX_CONCURRENT_TASKS", "1")))
TASK_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_TASKS)
PLATFORM_ORDER = ("xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu")
PLATFORMS = set(PLATFORM_ORDER)
PLATFORM_LABELS = {
    "xhs": "小红书", "dy": "抖音", "ks": "快手", "bili": "B站",
    "wb": "微博", "tieba": "贴吧", "zhihu": "知乎",
}

app = FastAPI(title="PainRadar Crawler Bridge", version="0.2.0")
store = TaskStore(TASK_DB)
runner = MediaCrawlerRunner()
RESULT_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_ROOT.mkdir(parents=True, exist_ok=True)


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
            error=f"登录态已过期，请在配置中更新平台 Cookie 或重新上传 profile（{exc}）",
        )
    except RunnerError as exc:
        store.update(task_id, status="failed", stage="failed", error=f"远程抓取失败：{exc}")
    except Exception as exc:  # noqa: BLE001
        store.update(task_id, status="failed", stage="failed", error=f"{type(exc).__name__}: {exc}")


def _execute_and_release(task_id: str, spec: CrawlSpec) -> None:
    try:
        _execute(task_id, spec)
    finally:
        TASK_SLOTS.release()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "painradar-crawler",
        "home": str(runner.home),
        "profiles": str(PROFILE_ROOT),
        "max_concurrent_tasks": MAX_CONCURRENT_TASKS,
    }


@app.post("/api/crawl", status_code=202)
def start_crawl(req: CrawlRequest, _: None = Depends(require_token)) -> dict[str, Any]:
    platform = req.platform.strip().lower()
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"platform must be {'|'.join(PLATFORM_ORDER)}")
    keywords = [k.strip() for k in req.keywords if k.strip()]
    if not keywords:
        raise HTTPException(status_code=400, detail="keywords is required")

    if not TASK_SLOTS.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail=f"crawler busy: max {MAX_CONCURRENT_TASKS} concurrent task(s); retry later",
        )

    try:
        task_id = uuid.uuid4().hex[:16]
        store.create(task_id, platform, keywords)
        spec = CrawlSpec(
            platform=platform,
            keywords=keywords,
            max_notes=max(1, min(req.max_notes, 1000)),
            cookies=req.cookies,
        )
        threading.Thread(
            target=_execute_and_release, args=(task_id, spec), daemon=True
        ).start()
    except Exception:
        TASK_SLOTS.release()
        raise
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


def _safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    infos = archive.infolist()
    if len(infos) > 20000:
        raise HTTPException(status_code=400, detail="archive has too many entries")
    for info in infos:
        name = Path(info.filename)
        if name.is_absolute() or ".." in name.parts:
            raise HTTPException(status_code=400, detail="archive contains unsafe path")
    archive.extractall(target)


@app.get("/api/platforms")
def list_platforms(_: None = Depends(require_token)) -> dict[str, Any]:
    items = []
    for platform in PLATFORM_ORDER:
        profile = PROFILE_ROOT / f"{platform}_user_data_dir"
        files = 0
        cookie_db = False
        if profile.is_dir():
            files = sum(1 for _ in profile.rglob("*") if _.is_file())
            cookie_db = any(
                (profile / rel).exists()
                for rel in ("Default/Cookies", "Default/Network/Cookies")
            )
        cookie_file = COOKIE_DIR / f"{platform}.txt"
        env_cookie = bool(os.environ.get(f"PLATFORM_COOKIES_{platform.upper()}"))
        ready = bool(env_cookie or cookie_file.exists() or cookie_db)
        items.append({
            "platform": platform,
            "label": PLATFORM_LABELS[platform],
            "ready": ready,
            "profile": str(profile),
            "profile_files": files,
            "profile_cookies": cookie_db,
            "cookie_file": cookie_file.exists(),
            "env_cookie": env_cookie,
            "cookie_source": (
                "env" if env_cookie
                else "file" if cookie_file.exists()
                else "profile" if cookie_db
                else "none"
            ),
        })
    return {
        "platforms": items,
        "cookie_dir": str(COOKIE_DIR),
        "profile_dir": str(PROFILE_ROOT),
    }


@app.post("/api/profiles/{platform}")
async def upload_profile(
    platform: str,
    file: UploadFile = File(...),
    _: None = Depends(require_token),
) -> dict[str, Any]:
    platform = platform.strip().lower()
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"platform must be {'|'.join(PLATFORM_ORDER)}")

    payload = await file.read()
    if len(payload) > MAX_PROFILE_BYTES:
        raise HTTPException(status_code=413, detail="profile archive is too large")
    if not payload:
        raise HTTPException(status_code=400, detail="empty upload")

    PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"profile-{platform}-", dir=str(PROFILE_ROOT)))
    try:
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                _safe_extract(archive, staging)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="upload must be a .zip") from exc

        preferred = staging / f"{platform}_user_data_dir"
        entries = [p for p in staging.iterdir()]
        if preferred.is_dir():
            source = preferred
        elif len(entries) == 1 and entries[0].is_dir():
            source = entries[0]
        else:
            source = staging

        destination = PROFILE_ROOT / f"{platform}_user_data_dir"
        incoming = PROFILE_ROOT / f".{platform}-incoming"
        shutil.rmtree(incoming, ignore_errors=True)
        shutil.copytree(source, incoming)
        shutil.rmtree(destination, ignore_errors=True)
        incoming.replace(destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        "ok": True,
        "platform": platform,
        "path": str(destination),
        "files": sum(1 for _ in destination.rglob("*") if _.is_file()),
    }


@app.get("/api/profiles")
def list_profiles(_: None = Depends(require_token)) -> dict[str, Any]:
    items = []
    for path in sorted(PROFILE_ROOT.glob("*_user_data_dir")):
        if not path.is_dir():
            continue
        items.append({
            "platform": path.name.removesuffix("_user_data_dir"),
            "path": str(path),
            "files": sum(1 for _ in path.rglob("*") if _.is_file()),
        })
    return {"profiles": items}
