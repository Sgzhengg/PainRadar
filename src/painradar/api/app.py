"""PainRadar HTTP API (FastAPI).

Run with:
    python run.py serve --db var/gold200.db --db var/gold.db
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..appdata import _app_label, build_run
from ..config import PROJECT_ROOT, category as get_category
from ..store import Store
from .jobs import JobRegistry

STATIC = Path(__file__).parent / "static"


class RunRequest(BaseModel):
    category: str
    extractor: str = "rule"
    mode: str = "b2c"


class FetchRequest(BaseModel):
    platform: str
    category: str
    mode: str = "b2c"
    keywords: list[str] = []
    max_notes: int = 50
    cookie: str = ""
    extractor: str = "rule"


class IngestRequest(BaseModel):
    source: str = "mediacrawler"
    file: str
    category: str
    platform: str = ""
    min_len: int = 6
    field_map: dict = {}


class AppChoice(BaseModel):
    app_id: str
    name: str = ""


class CustomCategoryRequest(BaseModel):
    name: str
    term: str
    pages: int = 3
    apps: list[AppChoice] = []


def _registry(paths: list[str]) -> list[str]:
    return paths


def _latest_runs(store: Store) -> list[dict]:
    rows = store._conn.execute(
        "SELECT run_id, category, created_at, stats_json FROM runs ORDER BY created_at DESC"
    ).fetchall()
    out: list[dict] = []
    seen: dict[str, int] = {}
    for row in rows:
        stats = json.loads(row["stats_json"])
        spec = get_category(row["category"])
        bucket = seen.get(row["category"], 0)
        seen[row["category"]] = bucket + 1
        out.append(
            {
                "run_id": row["run_id"],
                "category": row["category"],
                "category_name": spec.name,
                "created_at": row["created_at"],
                "extractor": stats.get("extractor", ""),
                "items": stats.get("items", 0),
                "atoms": stats.get("atoms", 0),
                "clusters": stats.get("clusters", 0),
                "noise_rate": stats.get("noise_rate", 0),
                "latest_for_category": bucket == 0,
            }
        )
    return out


def _find_run(paths: list[str], run_id: str) -> tuple[Store, dict]:
    for path in paths:
        store = Store(path)
        row = store._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is not None:
            return store, dict(row)
        store.close()
    raise HTTPException(status_code=404, detail=f"run not found: {run_id}")


def create_app(db_paths: list[str]) -> FastAPI:
    from ..config import STORE_BACKEND

    if STORE_BACKEND == "d1":
        # Cloud/edge mode: a single logical D1 database replaces local files.
        db_paths = ["d1:main"]
    if not db_paths:
        raise ValueError("at least one database path is required")

    app = FastAPI(title="PainRadar API", version="0.2.0")
    registry = JobRegistry(db_paths)

    @app.middleware("http")
    async def no_store_assets(request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "databases": len(db_paths)}

    @app.get("/api/runs")
    def list_runs() -> dict:
        runs: list[dict] = []
        seen: set[str] = set()
        for path in db_paths:
            store = Store(path)
            try:
                for item in _latest_runs(store):
                    if item["run_id"] in seen:
                        continue
                    seen.add(item["run_id"])
                    runs.append(item)
            finally:
                store.close()

        latest: dict[str, str] = {}
        for r in runs:
            current = latest.get(r["category"])
            if current is None or r["created_at"] > current:
                latest[r["category"]] = r["created_at"]
        for r in runs:
            r["latest_for_category"] = latest[r["category"]] == r["created_at"]
        # newest first inside a category, categories alphabetical
        runs.sort(key=lambda r: r["created_at"], reverse=True)
        runs.sort(key=lambda r: r["category_name"])
        return {"runs": runs}

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str, max_members: int = Query(12, ge=0, le=100)) -> dict:
        store, _ = _find_run(db_paths, run_id)
        try:
            return build_run(store, run_id, max_members=max_members)
        finally:
            store.close()

    @app.get("/api/runs/{run_id}/clusters/{cluster_id}/outreach.csv")
    def outreach_csv(run_id: str, cluster_id: str, mode: str = Query("")) -> Response:
        import json as _json

        store, row = _find_run(db_paths, run_id)
        try:
            members = store.cluster_members(run_id, cluster_id)
        finally:
            store.close()
        try:
            run_mode = _json.loads(row["stats_json"] or "{}").get("mode", "b2c")
        except Exception:  # noqa: BLE001
            run_mode = "b2c"
        b2b = (mode or run_mode) == "b2b"

        # Only people who described an obstacle / paid / compared: L0-L1 are
        # emotions and make poor outreach targets.
        rows = [m for m in members if m["level"] in ("L2", "L3", "L4")]
        rows.sort(key=lambda m: (m["likes"] if "likes" in m.keys() else 0), reverse=True)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["url", "quote", "likes", "level", "scene", "buyer_role", "icebreaker"])
        for m in rows:
            scene = m["scene"] or ""
            quote = (m["quote"] or "").replace("\n", " ")[:60]
            role = m["buyer_role"] if "buyer_role" in m.keys() else ""
            if b2b:
                greeting = f"{role}您好" if role in ("老板", "管理者") else "您好"
                icebreaker = (
                    f"{greeting}，看到您在「{scene}」提到「{quote}」。"
                    f"我们正在为传统行业做一套 AI 提效方案，可免费为贵司做一次流程诊断 + Demo 试用；"
                    f"如果方便，想约 15 分钟交流一下，可以吗？"
                )
            else:
                icebreaker = (
                    f"看到你在「{scene}」里提到「{quote}」，"
                    f"我正在做一个只解决这件事的小工具，想邀请你免费内测，愿意聊聊吗？"
                )
            writer.writerow([
                m["url"],
                m["quote"],
                m["likes"] if "likes" in m.keys() else 0,
                m["level"],
                scene,
                role,
                icebreaker,
            ])
        suffix = "_b2b" if b2b else ""
        filename = f"outreach{suffix}_{cluster_id}.csv"
        return Response(
            content=buf.getvalue().encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/runs/{run_id}/members")
    def cluster_members(
        run_id: str,
        cluster_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict:
        store, row = _find_run(db_paths, run_id)
        try:
            spec = get_category(row["category"])
            members = store.cluster_members(run_id, cluster_id)
            page = members[offset : offset + limit]
            return {
                "total": len(members),
                "offset": offset,
                "items": [
                    {
                        "quote": m["quote"],
                        "platform": m["platform"],
                        "app": _app_label(m["item_id"], spec),
                        "published_at": m["published_at"],
                        "url": m["url"],
                        "confidence": round(m["confidence"], 2),
                        "level": m["level"],
                        "scene": m["scene"],
                    }
                    for m in page
                ],
            }
        finally:
            store.close()

    @app.post("/api/ingest", status_code=202)
    def ingest_mediacrawler(req: IngestRequest) -> dict:
        """Import a local MediaCrawler export into the evidence ledger."""
        from ..connectors.mediacrawler import MediaCrawlerConnector
        from ..pipeline import ingest_items

        path = Path(req.file)
        if not path.exists():
            raise HTTPException(status_code=400, detail=f"file not found: {req.file}")
        if req.source != "mediacrawler":
            raise HTTPException(status_code=400, detail="only source=mediacrawler is supported here")
        connector = MediaCrawlerConnector(
            path=path,
            category=req.category,
            field_map=req.field_map or None,
            min_len=max(1, min(req.min_len, 40)),
        )
        last_store = Store(db_paths[0])
        try:
            result = ingest_items(last_store, connector.fetch(), req.category)
            last_store.audit(
                "api", "ingest", "mediacrawler", str(path), f"{req.category}: {result.as_dict()}"
            )
        finally:
            last_store.close()
        return {"ingest": result.as_dict(), "connector": connector.stats}

    @app.get("/api/categories")
    def list_categories() -> dict:
        from ..config import CATEGORIES

        out = []
        for key, spec in CATEGORIES.items():
            uids: set[str] = set()
            for path in db_paths:
                store = Store(path)
                try:
                    rows = store._conn.execute(
                        "SELECT comment_uid FROM items WHERE category=? AND deleted_at IS NULL",
                        (key,),
                    ).fetchall()
                    uids.update(r["comment_uid"] for r in rows)
                finally:
                    store.close()
            out.append({"category": key, "name": spec.name, "items": len(uids)})
        return {"categories": out}

    @app.get("/api/apps/search")
    def app_search(term: str, limit: int = Query(8, ge=1, le=10)) -> dict:
        from ..connectors.appstore import search_apps

        term = term.strip()
        if not term:
            raise HTTPException(status_code=400, detail="term is required")
        try:
            return {"apps": search_apps(term, limit=limit)}
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"App Store search failed: {exc}")

    @app.post("/api/categories/custom", status_code=202)
    def create_custom_category(req: CustomCategoryRequest) -> dict:
        from ..config import register_custom_category

        name = req.name.strip()
        term = req.term.strip()
        if not name or not term:
            raise HTTPException(status_code=400, detail="name and term are required")
        if not req.apps:
            raise HTTPException(
                status_code=400,
                detail="apps must be confirmed first: call /api/apps/search and pass the chosen apps",
            )
        chosen = req.apps[:5]
        app_ids = [a.app_id for a in chosen]
        names = {a.app_id: (a.name or a.app_id) for a in chosen}
        key = register_custom_category(name, term, app_names=names)
        try:
            job = registry.submit_fetch(key, app_ids, pages=max(1, min(req.pages, 10)))
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {
            "category": key,
            "name": name,
            "apps": [{"app_id": a.app_id, "name": names[a.app_id]} for a in chosen],
            "job": job.as_dict(),
        }

    CORPORA = {
        "main": {"db": "var/llm_full.db", "label": "全品类（795 评论）", "frozen": None},
        "topcharts": {"db": "var/topcharts_llm.db", "label": "Top Charts 40 应用", "frozen": None},
        "hardware": {"db": "var/hardware.db", "label": "硬件设备（12 类）", "frozen": None},
        "pdf": {"db": "var/pdf.db", "label": "PDF 工具", "frozen": "var/demand_taxonomy_pdf.json"},
        "devtools": {"db": "var/devtools.db", "label": "开发者工具", "frozen": "var/demand_taxonomy_dev.json"},
        "smb": {"db": "var/smb.db", "label": "中小企业 SaaS", "frozen": "var/demand_taxonomy_smb.json"},
        "download": {"db": "var/download.db", "label": "下载/媒体工具", "frozen": "var/demand_taxonomy_download.json"},
        "broad": {"db": "var/broad_llm.db", "label": "日常工作生活", "frozen": "var/demand_taxonomy_broad.json"},
        "reddit": {"db": "var/reddit.db", "label": "Reddit 社区", "frozen": None},
        "community": {"db": "var/community.db", "label": "社区讨论", "frozen": None},
    }
    _disc_jobs: dict = {}

    def _snapshot_path(corpus: str) -> Path:
        if corpus == "main":
            return PROJECT_ROOT / "var" / "discovery.json"
        return PROJECT_ROOT / "var" / f"discovery_{corpus}.json"

    @app.get("/api/discovery/corpora")
    def discovery_corpora() -> dict:
        return {
            "corpora": [
                {
                    "name": name,
                    "label": cfg["label"],
                    "ready": _snapshot_path(name).exists(),
                }
                for name, cfg in CORPORA.items()
            ]
        }

    @app.get("/api/discovery")
    def discovery_snapshot(corpus: str = "main") -> dict:
        import json as _json

        if corpus not in CORPORA:
            raise HTTPException(status_code=400, detail=f"unknown corpus: {corpus}")
        path = _snapshot_path(corpus)
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"corpus '{corpus}' 还没有快照；点“生成快照”或运行 run.py discover --db {CORPORA[corpus]['db']}",
            )
        data = _json.loads(path.read_text(encoding="utf-8"))
        data["corpus"] = corpus
        return data

    @app.post("/api/discovery/build")
    def discovery_build(payload: dict) -> dict:
        import threading
        import uuid

        corpus = str(payload.get("corpus") or "").strip()
        if corpus not in CORPORA:
            raise HTTPException(status_code=400, detail=f"unknown corpus: {corpus}")
        job_id = uuid.uuid4().hex[:12]
        _disc_jobs[job_id] = {"status": "running", "corpus": corpus, "error": None}

        def _work() -> None:
            import json as _json
            from datetime import datetime, timezone

            from ..discover import discover_canonical

            try:
                cfg = CORPORA[corpus]
                db = PROJECT_ROOT / cfg["db"]
                frozen = PROJECT_ROOT / cfg["frozen"] if cfg["frozen"] else PROJECT_ROOT / "var" / "demand_taxonomy_frozen.json"
                demands, stats = discover_canonical(
                    [str(db)],
                    top=30,
                    min_size=8,
                    cache_path=PROJECT_ROOT / "var" / "demand_cache.json",
                    statement_threshold=0.3,
                    taxonomy_cache=PROJECT_ROOT / "var" / "demand_taxonomy.json",
                    refresh_taxonomy=False,
                    frozen_path=frozen,
                    assignment_cache=PROJECT_ROOT / "var" / f"assignment_cache_{corpus}.json",
                    freeze=False,
                    rebuild=False,
                )
                snapshot = {
                    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                    "source": cfg["db"],
                    "taxonomy_version": stats.get("taxonomy_version"),
                    "coverage": stats.get("coverage"),
                    "unassigned": stats.get("unassigned"),
                    "demands": [d.as_dict() for d in demands],
                }
                _snapshot_path(corpus).write_text(
                    _json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                _disc_jobs[job_id] = {"status": "done", "corpus": corpus, "error": None,
                                      "demands": len(demands), "coverage": stats.get("coverage")}
            except Exception as exc:  # noqa: BLE001
                _disc_jobs[job_id] = {"status": "failed", "corpus": corpus, "error": str(exc)}

        threading.Thread(target=_work, daemon=True).start()
        return {"job_id": job_id}

    @app.get("/api/discovery/build/{job_id}")
    def discovery_build_status(job_id: str) -> dict:
        job = _disc_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="unknown build job")
        return job

    @app.get("/api/solutions")
    def solutions_snapshot() -> dict:
        path = PROJECT_ROOT / "var" / "solutions.json"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail="no solutions; run: python run.py solve --snapshot var/discovery.json",
            )
        import json as _json

        return _json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/anchors")
    def anchors(category: str) -> dict:
        for path in db_paths:
            store = Store(path)
            try:
                rows = store.anchors(category)
                if rows:
                    return {
                        "category": category,
                        "anchors": [
                            {
                                "metric": r["metric"],
                                "value": r["value"],
                                "source": r["source"],
                                "grade": r["grade"],
                                "as_of": r["as_of"],
                            }
                            for r in rows
                        ],
                    }
            finally:
                store.close()
        return {"category": category, "anchors": []}

    @app.post("/api/fetch", status_code=202)
    def start_remote_fetch(req: FetchRequest) -> dict:
        from ..config import MEDIACRAWLER_API_URL

        if not MEDIACRAWLER_API_URL:
            raise HTTPException(
                status_code=400,
                detail="MEDIACRAWLER_API_URL 未配置：请先按 docs/deploy-zeabur.md 部署采集服务",
            )
        allowed = {"xhs", "dy", "bili", "zhihu", "appstore"}
        platform = req.platform.strip().lower()
        if platform not in allowed:
            raise HTTPException(status_code=400, detail=f"platform must be one of {sorted(allowed)}")
        try:
            get_category(req.category)
        except SystemExit:
            raise HTTPException(status_code=400, detail=f"unknown category: {req.category}")
        cookies: dict[str, str] = {}
        for part in (req.cookie or "").split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                if k.strip():
                    cookies[k.strip()] = v.strip()
        try:
            job = registry.submit_remote_fetch(
                category=req.category,
                platform=platform,
                keywords=[k.strip() for k in req.keywords if k.strip()],
                max_notes=max(1, min(req.max_notes, 1000)),
                cookies=cookies or None,
                extractor=req.extractor if req.extractor in ("rule", "llm") else "rule",
                mode=req.mode if req.mode in ("b2c", "b2b") else "b2c",
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"job": job.as_dict()}

    @app.post("/api/run", status_code=202)
    def start_run(req: RunRequest) -> dict:
        if req.extractor not in ("rule", "llm"):
            raise HTTPException(status_code=400, detail="extractor must be rule or llm")
        try:
            get_category(req.category)
        except SystemExit:
            raise HTTPException(status_code=400, detail=f"unknown category: {req.category}")
        try:
            job = registry.submit(req.category, req.extractor, mode=req.mode if req.mode in ("b2c", "b2b") else "b2c")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"job": job.as_dict()}

    @app.get("/api/run/active")
    def active_run() -> dict:
        job = registry.active()
        return {"job": job.as_dict() if job else None}

    @app.get("/api/run/latest")
    def latest_job(category: str | None = None) -> dict:
        job = registry.latest(category)
        return {"job": job.as_dict() if job else None}

    @app.get("/api/run/{job_id}")
    def run_status(job_id: str) -> dict:
        job = registry.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
        return {"job": job.as_dict()}

    _dd_sessions: dict = {}
    _dd_jobs: dict = {}

    @app.post("/api/deepdive/plan")
    def deepdive_plan(payload: dict) -> dict:
        import uuid

        from ..deepdive import DeepDive

        message = str(payload.get("message") or "").strip()
        if not message:
            raise HTTPException(status_code=400, detail="message is required")
        plan = DeepDive().plan(message)
        sid = uuid.uuid4().hex[:12]
        _dd_sessions[sid] = {"message": message, "spec": plan["spec"], "questions": plan["questions"]}
        return {"session_id": sid, **plan}

    @app.post("/api/deepdive/preview")
    def deepdive_preview(payload: dict) -> dict:
        from ..deepdive import DeepDive

        sid = str(payload.get("session_id") or "")
        session = _dd_sessions.get(sid)
        if not session:
            raise HTTPException(status_code=404, detail="unknown session")
        spec = dict(session["spec"])
        override = payload.get("spec") or {}
        for key in ("product", "platform", "system", "focus"):
            if isinstance(override.get(key), str) and override[key].strip():
                spec[key] = override[key].strip()
        for key in ("subreddits", "keywords", "domain_terms"):
            if isinstance(override.get(key), list) and override[key]:
                spec[key] = override[key]
        if isinstance(override.get("app_store"), bool):
            spec["app_store"] = override["app_store"]
        if isinstance(override.get("fetch_runs"), int):
            spec["fetch_runs"] = max(1, min(int(override["fetch_runs"]), 4))
        if isinstance(override.get("app_query"), str) and override["app_query"].strip():
            spec["app_query"] = override["app_query"].strip()
        if isinstance(override.get("pain_taxonomy"), str) and override["pain_taxonomy"].strip():
            spec["pain_taxonomy"] = override["pain_taxonomy"].strip()
        session["spec"] = spec
        return DeepDive().preview(spec)

    @app.post("/api/deepdive/run")
    def deepdive_run(payload: dict) -> dict:
        import threading
        import uuid

        from ..deepdive import DeepDive

        sid = str(payload.get("session_id") or "")
        session = _dd_sessions.get(sid)
        if not session:
            raise HTTPException(status_code=404, detail="unknown session; call /api/deepdive/plan first")
        answers = [str(a) for a in (payload.get("answers") or []) if str(a).strip()]
        override = payload.get("spec") or {}
        for key in ("product", "platform", "system", "focus"):
            if isinstance(override.get(key), str) and override[key].strip():
                session["spec"][key] = override[key].strip()
        for key in ("subreddits", "keywords", "domain_terms"):
            if isinstance(override.get(key), list) and override[key]:
                session["spec"][key] = override[key]
        if isinstance(override.get("app_store"), bool):
            session["spec"]["app_store"] = override["app_store"]
        if isinstance(override.get("fetch_runs"), int):
            session["spec"]["fetch_runs"] = max(1, min(int(override["fetch_runs"]), 4))
        if isinstance(override.get("app_query"), str) and override["app_query"].strip():
            session["spec"]["app_query"] = override["app_query"].strip()
        if isinstance(override.get("pain_taxonomy"), str) and override["pain_taxonomy"].strip():
            session["spec"]["pain_taxonomy"] = override["pain_taxonomy"].strip()
        from ..deepdive import product_is_concrete

        spec_now = session["spec"]
        if not product_is_concrete(spec_now):
            raise HTTPException(
                status_code=400,
                detail="还缺具体产品名：请在澄清问题里补充（例如 Apple Watch），再点“补充后重新理解”。",
            )
        if not (spec_now.get("subreddits") or []) and not spec_now.get("app_store"):
            raise HTTPException(
                status_code=400,
                detail="还缺数据源：请填写至少一个 Reddit 板块，或勾选 App Store。",
            )

        job_id = uuid.uuid4().hex[:12]
        _dd_jobs[job_id] = {"status": "running", "report": None}

        def _work() -> None:
            try:
                result = DeepDive().execute(session["spec"], answers, force=bool(payload.get("force")))
                _dd_jobs[job_id] = {"status": "done", "report": result}
            except Exception as exc:  # noqa: BLE001
                _dd_jobs[job_id] = {"status": "failed", "error": str(exc)}

        threading.Thread(target=_work, daemon=True).start()
        return {"job_id": job_id}

    @app.post("/api/deepdive/compare")
    def deepdive_compare(payload: dict) -> dict:
        import threading
        import uuid

        from ..deepdive import DeepDive

        raw_products = payload.get("products") or []
        products = []
        for item in raw_products:
            if isinstance(item, dict):
                if str(item.get("product") or "").strip():
                    products.append(item)
            elif str(item).strip():
                products.append(str(item).strip())
        if len(products) < 2:
            raise HTTPException(status_code=400, detail="至少需要两个产品才能对比")
        template = {
            "platform": payload.get("platform") or "Reddit",
            "system": payload.get("system") or "",
            "focus": payload.get("focus") or "decay",
            "subreddits": payload.get("subreddits") or [],
            "keywords": payload.get("keywords") or [],
            "app_store": bool(payload.get("app_store")),
        }
        force = bool(payload.get("force"))
        job_id = uuid.uuid4().hex[:12]
        _dd_jobs[job_id] = {"status": "running", "report": None}

        def _work() -> None:
            try:
                result = DeepDive().compare(products, template, force=force)
                _dd_jobs[job_id] = {"status": "done", "report": result}
            except Exception as exc:  # noqa: BLE001
                _dd_jobs[job_id] = {"status": "failed", "error": str(exc)}

        threading.Thread(target=_work, daemon=True).start()
        return {"job_id": job_id}

    @app.get("/api/deepdive/{job_id}")
    def deepdive_status(job_id: str) -> dict:
        job = _dd_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="unknown job")
        return job

    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/runs/{run_id}")
    def run_page(run_id: str) -> FileResponse:  # deep link falls back to the SPA
        return FileResponse(STATIC / "index.html")

    return app
