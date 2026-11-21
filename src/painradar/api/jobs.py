"""In-process job runner for manual pipeline runs triggered from the UI.

One job at a time, executed in a background thread. State lives in memory; the
result is the run_id written to SQLite, which the UI then loads as usual.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from ..pipeline import ingest_items, run_category
from ..store import Store


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class Job:
    job_id: str
    category: str
    extractor: str
    kind: str = "run"  # run | fetch
    status: str = "queued"  # queued | running | done | failed
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None
    run_id: str | None = None
    stats: dict | None = None
    error: str | None = None
    stage: str | None = None
    progress: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


class JobRegistry:
    def __init__(self, db_paths: list[str], min_size: int = 3) -> None:
        self.db_paths = db_paths
        self.min_size = min_size
        self._jobs: dict[str, Job] = {}
        self._active: str | None = None
        self._lock = threading.Lock()

    # -- queries ----------------------------------------------------------
    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def latest(self, category: str | None = None) -> Job | None:
        jobs = [j for j in self._jobs.values() if category is None or j.category == category]
        return max(jobs, key=lambda j: j.started_at) if jobs else None

    def active(self) -> Job | None:
        if self._active is None:
            return None
        return self._jobs.get(self._active)

    # -- submission -------------------------------------------------------
    def _main_db(self) -> str:
        """The database with the most items: new categories land there."""
        best, best_n = self.db_paths[0], -1
        for path in self.db_paths:
            store = Store(path)
            try:
                n = store._conn.execute(
                    "SELECT COUNT(rowid) FROM items WHERE deleted_at IS NULL"
                ).fetchone()[0]
            finally:
                store.close()
            if n > best_n:
                best, best_n = path, n
        return best

    def _db_for(self, category: str) -> str:
        for path in self.db_paths:
            store = Store(path)
            try:
                n = store._conn.execute(
                    "SELECT COUNT(rowid) FROM items WHERE category=? AND deleted_at IS NULL",
                    (category,),
                ).fetchone()[0]
                if n:
                    return path
            finally:
                store.close()
        raise ValueError(f"no items for category {category!r} in any database")

    def submit(self, category: str, extractor: str = "rule") -> Job:
        with self._lock:
            current = self.active()
            if current is not None and current.status in ("queued", "running"):
                raise RuntimeError(f"job {current.job_id} is still {current.status}")
            db_path = self._db_for(category)
            job = Job(job_id=f"job_{uuid.uuid4().hex[:10]}", category=category, extractor=extractor)
            self._jobs[job.job_id] = job
            self._active = job.job_id
        threading.Thread(target=self._run, args=(job, db_path), daemon=True).start()
        return job

    def submit_fetch(self, category: str, apps: list[str], pages: int = 3) -> Job:
        """Fetch App Store reviews into the category, then stop (run separately)."""
        with self._lock:
            current = self.active()
            if current is not None and current.status in ("queued", "running"):
                raise RuntimeError(f"job {current.job_id} is still {current.status}")
            job = Job(
                job_id=f"job_{uuid.uuid4().hex[:10]}",
                category=category,
                extractor="fetch",
                kind="fetch",
            )
            self._jobs[job.job_id] = job
            self._active = job.job_id
        threading.Thread(target=self._run_fetch, args=(job, apps, pages), daemon=True).start()
        return job

    def _store(self) -> Store:
        from ..config import STORE_BACKEND

        return Store() if STORE_BACKEND == "d1" else Store(self._main_db())

    def submit_remote_fetch(
        self,
        category: str,
        platform: str,
        keywords: list[str],
        max_notes: int,
        cookies: dict[str, str] | None = None,
        extractor: str = "rule",
    ) -> Job:
        """Start a Zeabur crawl job and ingest/analyze it asynchronously."""
        with self._lock:
            current = self.active()
            if current is not None and current.status in ("queued", "running"):
                raise RuntimeError(f"job {current.job_id} is still {current.status}")
            job = Job(
                job_id=f"job_{uuid.uuid4().hex[:10]}",
                category=category,
                extractor=extractor,
                kind="fetch_remote",
                stage="starting",
            )
            self._jobs[job.job_id] = job
            self._active = job.job_id
        threading.Thread(
            target=self._run_remote_fetch,
            args=(job, platform, keywords, max_notes, cookies),
            daemon=True,
        ).start()
        return job

    def _run_remote_fetch(
        self,
        job: Job,
        platform: str,
        keywords: list[str],
        max_notes: int,
        cookies: dict[str, str] | None,
    ) -> None:
        from ..connectors.remote_mediacrawler import (
            NeedLoginError,
            RemoteCrawlerError,
            RemoteMediaCrawler,
        )

        job.status = "running"
        store = None
        try:
            crawler = RemoteMediaCrawler()
            task = crawler.start_crawl(
                platform=platform,
                keywords=keywords,
                max_notes=max_notes,
                cookies_override=cookies,
                category=job.category,
            )
            job.stats = {"task_id": task.task_id, "platform": platform}

            def on_stage(name: str, extra: dict) -> None:
                job.stage = name
                job.progress = int(extra.get("progress") or 0)
                if extra:
                    job.stats = {**(job.stats or {}), **extra}

            store = self._store()
            ingest = crawler.poll_and_ingest(
                task.task_id,
                job.category,
                store,
                on_stage=on_stage,
            )
            job.stats = {**(job.stats or {}), **ingest}

            job.stage = "analyzing"
            if ingest.get("inserted", 0) > 0:
                result = run_category(
                    store, job.category, extractor_name=job.extractor, min_size=self.min_size
                )
                job.run_id = result.run_id
                job.stats = {**job.stats, "extraction": result.stats}
            job.stage = "done"
            job.status = "done"
        except NeedLoginError as exc:
            job.error = f"登录态已过期，请在配置中更新平台 Cookie（{exc}）"
            job.status = "failed"
            job.stage = "need_login"
        except RemoteCrawlerError as exc:
            job.error = f"远程抓取失败：{exc}"
            job.status = "failed"
        except Exception as exc:  # noqa: BLE001
            job.error = f"{type(exc).__name__}: {exc}"
            job.status = "failed"
            traceback.print_exc()
        finally:
            if store is not None:
                store.close()
            job.finished_at = _now()
            with self._lock:
                if self._active == job.job_id:
                    self._active = None

    def _run_fetch(self, job: Job, apps: list[str], pages: int) -> None:
        from ..connectors.appstore import AppStoreConnector

        job.status = "running"
        store = None
        db_path = self._main_db()
        try:
            store = Store(db_path)
            inserted = 0
            for app in apps:
                connector = AppStoreConnector(category=job.category, app_id=app, pages=pages)
                result = ingest_items(store, list(connector.fetch()), job.category)
                inserted += result.inserted
            store._conn.commit()
            rows = store._conn.execute(
                "SELECT COUNT(rowid) FROM items WHERE category=? AND deleted_at IS NULL",
                (job.category,),
            ).fetchone()[0]
            job.stats = {
                "inserted": inserted,
                "rows": rows,
                "apps": len(apps),
                "pages": pages,
                "db": db_path,
            }
            job.status = "done"
        except Exception as exc:  # noqa: BLE001
            job.error = f"{type(exc).__name__}: {exc}"
            job.status = "failed"
            traceback.print_exc()
        finally:
            if store is not None:
                store.close()
            job.finished_at = _now()
            with self._lock:
                if self._active == job.job_id:
                    self._active = None

    def _run(self, job: Job, db_path: str) -> None:
        job.status = "running"
        store = None
        try:
            store = Store(db_path)
            result = run_category(
                store, job.category, extractor_name=job.extractor, min_size=self.min_size
            )
            job.run_id = result.run_id
            job.stats = result.stats
            job.status = "done"
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            job.error = f"{type(exc).__name__}: {exc}"
            job.status = "failed"
            traceback.print_exc()
        finally:
            if store is not None:
                store.close()
            job.finished_at = _now()
            with self._lock:
                if self._active == job.job_id:
                    self._active = None
