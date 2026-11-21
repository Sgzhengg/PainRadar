"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .anchors import ItunesAnchor, import_csv, save_anchors
from .config import CATEGORIES, DB_PATH, PROJECT_ROOT, REPORT_DIR, SAMPLE_DIR, category as get_category
from .connectors.appstore import AppStoreConnector
from .connectors.reddit import RedditConnector
from .extract import LLMNotConfigured
from .net import HttpError
from .schema import Tier
from .pipeline import ingest_file, ingest_items, run_category
from .report import render_docx, render_markdown
from .store import Store

SAMPLE_MAP = {
    "pet_water_fountain": SAMPLE_DIR / "pet_water_fountain.jsonl",
    "home_storage": SAMPLE_DIR / "home_storage.jsonl",
    "camping_gear": SAMPLE_DIR / "camping_gear.jsonl",
}


def _store(args: argparse.Namespace) -> Store:
    return Store(Path(args.db) if getattr(args, "db", None) else DB_PATH)


def cmd_init(args: argparse.Namespace) -> int:
    store = _store(args)
    print(f"initialised {store.path}")
    print(json.dumps(store.stats(), ensure_ascii=False))
    store.close()
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from .pipeline import ingest_items

    store = _store(args)
    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"file not found: {path}")
    if getattr(args, "source", "file") == "mediacrawler":
        from .connectors.mediacrawler import MediaCrawlerConnector

        field_map = json.loads(args.field_map) if getattr(args, "field_map", "") else None
        connector = MediaCrawlerConnector(
            path=path,
            category=args.category,
            field_map=field_map,
            min_len=getattr(args, "min_len", 6),
            tos_basis=args.tos_basis,
            tier=Tier(args.tier),
        )
        result = ingest_items(store, connector.fetch(), args.category)
        print(json.dumps({"ingest": result.as_dict(), "connector": connector.stats}, ensure_ascii=False))
        store.audit("cli", "ingest", "mediacrawler", str(path), f"{args.category}: {result.as_dict()}")
    else:
        result = ingest_file(
            store, path, args.category,
            platform=args.platform, tos_basis=args.tos_basis, tier=args.tier,
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False))
    store.close()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        result = run_category(
            store, args.category,
            extractor_name=args.extractor,
            threshold=args.threshold,
            min_size=args.min_size,
            llm_model=args.llm_model,
            llm_base_url=args.llm_base_url,
            llm_consistency=args.double_run or args.llm_consistency,
            mode=getattr(args, "mode", "b2c"),
            validity_filter=args.validity_filter,
        )
    except LLMNotConfigured as exc:
        print(f"llm extractor not configured: {exc}", file=sys.stderr)
        print("hint: set PAINRADAR_LLM_BASE_URL / PAINRADAR_LLM_API_KEY / PAINRADAR_LLM_MODEL "
              "or pass --llm-model and --llm-base-url", file=sys.stderr)
        store.close()
        return 2
    print(f"run {result.run_id} · {result.category}")
    print(json.dumps(result.stats, ensure_ascii=False, indent=2))
    rows = store.opportunities(result.run_id)
    if rows:
        print("\n机会：")
        for i, o in enumerate(rows, start=1):
            print(f"  {i}. [{o['opportunity_tier']}] {o['title']} — {o['one_liner']}")
    store.close()
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    store = _store(args)
    run_id = args.run
    if not run_id:
        latest = store.latest_run(args.category)
        if not latest:
            raise SystemExit("no runs for this category; run `painradar run` first")
        run_id = latest["run_id"]
    md = render_markdown(store, run_id, Path(args.out) if args.out else REPORT_DIR)
    print(f"markdown: {md}")
    if args.docx:
        docx = render_docx(store, run_id, md)
        if docx:
            print(f"docx: {docx}")
        else:
            print("docx skipped: python-docx not installed")
    store.close()
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    db = Path(args.db) if args.db else DB_PATH
    if args.reset and db.exists():
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(db) + suffix)
            if p.exists():
                p.unlink()
    store = Store(db)
    print(f"demo db: {db}")
    ok = 0
    for key, path in SAMPLE_MAP.items():
        if not path.exists():
            print(f"  ! missing sample: {path}")
            continue
        spec = get_category(key)
        print(f"\n== {spec.name} ({key}) ==")
        ing = ingest_file(store, path, key, platform="demo", tos_basis="user_provided")
        print(f"  ingest: {ing.as_dict()}")
        run = run_category(store, key, extractor_name=args.extractor,
                           threshold=args.threshold, min_size=args.min_size)
        print(f"  atoms={run.stats['atoms']} clusters={run.stats['clusters']} "
              f"noise={run.stats['noise_rate']:.0%}")
        out_dir = REPORT_DIR / "demo"
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in list(out_dir.glob(f"{key}-*.md")) + list(out_dir.glob(f"{key}-*.docx")):
            old.unlink(missing_ok=True)
        md = render_markdown(store, run.run_id, out_dir)
        print(f"  report: {md}")
        if args.docx:
            docx = render_docx(store, run.run_id, md)
            if docx:
                print(f"  docx:   {docx}")
        for i, o in enumerate(run.opportunities[:3], start=1):
            print(f"   {i}. [{o['opportunity_tier']}] {o['title']} — {o['one_liner']}")
        ok += 1
    print(f"\n{ok} categories processed. reports in {REPORT_DIR / 'demo'}")
    store.close()
    return 0 if ok else 1


def cmd_fetch(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        if args.source == "reddit":
            if not args.subreddits:
                raise SystemExit("--subreddits is required for reddit (comma separated)")
            connector = RedditConnector(
                category=args.category,
                query=args.query,
                subreddits=[s.strip() for s in args.subreddits.split(",") if s.strip()],
                limit=args.limit,
                include_comments=not args.no_comments,
            )
        elif args.source == "github":
            from .connectors.github_issues import GitHubIssueConnector

            if not args.query:
                raise SystemExit("--query is required for github")
            connector = GitHubIssueConnector(
                category=args.category, query=args.query, limit=max(1, args.limit)
            )
        elif args.source == "hn":
            from .connectors.hn import HNConnector

            if not args.query:
                raise SystemExit("--query is required for hn")
            connector = HNConnector(
                category=args.category, query=args.query, limit=max(1, args.limit)
            )
        elif args.source == "appstore":
            app_id = args.app_id
            if not app_id and args.search:
                from .connectors.appstore import search_apps

                matches = search_apps(args.search, country=args.country, limit=5)
                if not matches:
                    raise SystemExit(f"no App Store app found for {args.search!r}")
                print("matches:")
                for m in matches:
                    print(f"  {m['app_id']}  {m['name']}  ({m['rating_count']:,} ratings)")
                app_id = matches[0]["app_id"]
                print(f"using {app_id}")
            if not app_id:
                raise SystemExit("--app-id or --search is required for appstore")
            connector = AppStoreConnector(
                category=args.category, app_id=app_id, country=args.country, pages=args.pages
            )
        else:  # pragma: no cover - argparse restricts
            raise SystemExit(f"unknown source {args.source}")

        print(f"health: {connector.health()}")
        result = ingest_items(store, connector.fetch(), args.category)
        print(json.dumps(result.as_dict(), ensure_ascii=False))
        store.audit("cli", "fetch", args.source, args.category, str(result.as_dict()))
        return 0
    except (HttpError, OSError) as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        if args.source == "reddit":
            print(
                "hint: Reddit blocks most unauthenticated JSON requests. Set "
                "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USERNAME / REDDIT_PASSWORD "
                "to use the OAuth API.",
                file=sys.stderr,
            )
        return 2
    finally:
        store.close()


def cmd_anchor(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.source == "itunes":
        if not args.app_id:
            raise SystemExit("--app-id is required for itunes")
        obs = ItunesAnchor(category=args.category, app_id=args.app_id, country=args.country).fetch()
        n = save_anchors(store, obs)
        print(f"saved {n} anchor(s)")
        for o in obs:
            print(f"  {o.metric}={o.value} ({o.grade}) {o.note}")
    else:
        if not args.file:
            raise SystemExit("--file is required for file anchors")
        n = import_csv(store, Path(args.file), args.category)
        print(f"imported {n} anchor(s)")
    store.audit("cli", "anchor", args.source, args.category, "")
    store.close()
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    store = _store(args)
    print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
    for row in store._conn.execute(
        "SELECT category, run_id, created_at FROM runs ORDER BY created_at DESC LIMIT 10"
    ).fetchall():
        print(f"  {row['created_at']}  {row['category']:<20} {row['run_id']}")
    store.close()
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    store = _store(args)
    n = store.soft_delete(args.uid)
    print(f"deleted {n} item(s) and their derived atoms: {args.uid}")
    store.close()
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    print(f"painradar {__version__}")
    print(f"project root : {PROJECT_ROOT}")
    print(f"python       : {sys.version.split()[0]}")
    print(f"db           : {DB_PATH} (exists={DB_PATH.exists()})")
    print(f"samples      : {SAMPLE_DIR} (exists={SAMPLE_DIR.exists()})")
    missing = [str(p) for p in SAMPLE_MAP.values() if not p.exists()]
    print(f"missing samples: {missing or 'none'}")
    try:
        import docx  # noqa: F401
        print("python-docx   : available")
    except ImportError:
        print("python-docx   : not installed (docx export disabled)")
    print(f"categories   : {', '.join(CATEGORIES)}")
    import os
    print(f"reddit oauth : {'configured' if os.environ.get('REDDIT_CLIENT_ID') else 'not configured (public JSON fallback)'}")
    print(f"llm extractor: {'configured' if os.environ.get('PAINRADAR_LLM_BASE_URL') else 'not configured (rule extractor)'}")
    # -- cloud mode checks -------------------------------------------------
    from .config import (
        MEDIACRAWLER_API_TOKEN, MEDIACRAWLER_API_URL, STORE_BACKEND,
        CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_D1_DATABASE_ID,
    )

    mode = "cloud (D1)" if STORE_BACKEND == "d1" else "local (SQLite)"
    print(f"store mode   : {mode}")
    data_dir = Path(os.environ.get("PAINRADAR_DATA_DIR", PROJECT_ROOT / "var"))
    writable = False
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".doctor-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable = True
    except Exception:  # noqa: BLE001
        writable = False
    print(f"data dir     : {data_dir} (writable={writable})")
    print(f"admin lock   : {'enabled' if os.environ.get('PAINRADAR_ADMIN_PASSWORD') else 'disabled (no password set)'}")
    if STORE_BACKEND == "d1":
        ready = all([CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_D1_DATABASE_ID, CLOUDFLARE_API_TOKEN])
        print(f"d1 config    : {'configured' if ready else 'MISSING account/database/token'}")
        if ready:
            try:
                from .store import CloudflareD1Store
                s = CloudflareD1Store()
                row = s._conn.execute("SELECT COUNT(*) AS n FROM items").fetchone()
                print(f"d1 reachable : yes (items={row['n'] if row else 0})")
                s.close()
            except Exception as exc:  # noqa: BLE001
                print(f"d1 reachable : no ({type(exc).__name__}: {exc})")
    print(f"crawler url  : {MEDIACRAWLER_API_URL or 'not configured (local import only)'}")
    print(f"crawler token: {'configured' if MEDIACRAWLER_API_TOKEN else 'not configured'}")
    if MEDIACRAWLER_API_URL:
        try:
            from .connectors.remote_mediacrawler import RemoteMediaCrawler
            health = RemoteMediaCrawler().health()
            print(f"crawler ping : {'ok' if health.get('ok') else 'failed: ' + str(health.get('reason'))}")
        except Exception as exc:  # noqa: BLE001
            print(f"crawler ping : failed ({type(exc).__name__}: {exc})")
    return 0 if not missing else 1


def cmd_serve(args: argparse.Namespace) -> int:
    dbs = getattr(args, "db", None) or [str(DB_PATH)]
    if isinstance(dbs, str):
        dbs = [dbs]
    try:
        import uvicorn

        from .api.app import create_app
    except ImportError as exc:  # pragma: no cover - optional extra
        print(f"serve needs fastapi + uvicorn: {exc}", file=sys.stderr)
        print("install with: pip install -r requirements.txt", file=sys.stderr)
        return 1
    app = create_app(dbs)
    print(f"serving {len(dbs)} database(s) on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload, log_level="info")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    from .discover import discover, discover_canonical, save

    dbs = getattr(args, "db", None) or [str(DB_PATH)]
    if isinstance(dbs, str):
        dbs = [dbs]
    if args.canonical:
        demands, stats = discover_canonical(
            dbs, top=args.top, min_size=args.min_size,
            cache_path=PROJECT_ROOT / "var" / "demand_cache.json",
            statement_threshold=args.statement_threshold,
            taxonomy_cache=PROJECT_ROOT / "var" / "demand_taxonomy.json",
            refresh_taxonomy=args.refresh_taxonomy,
            frozen_path=Path(args.frozen) if args.frozen else PROJECT_ROOT / "var" / "demand_taxonomy_frozen.json",
            assignment_cache=Path(args.assignment_cache)
            if args.assignment_cache
            else PROJECT_ROOT / "var" / "assignment_cache.json",
            freeze=args.freeze,
            rebuild=args.rebuild,
        )
        print(f"clusters={stats.get('clusters')} taxonomy={stats.get('taxonomy')} "
              f"source={stats.get('taxonomy_source')} v={stats.get('taxonomy_version')} "
              f"assigned={stats.get('assigned')} unassigned={stats.get('unassigned')} "
              f"cross_domain={stats.get('cross_domain')}")
    else:
        demands = discover(dbs, min_size=args.min_size, threshold=args.threshold, top=args.top)
    if not demands:
        print("没有可用的痛点原子；先运行 run --category", file=sys.stderr)
        return 1
    print(f"{'#':>2}  {'分数':>5}  {'证据':>4}  {'域':>2}  需求")
    for i, d in enumerate(demands, start=1):
        print(f"{i:>2}  {d.score:>5.0f}  {d.size:>4}  {len(d.domains):>2}  {d.label}"
              + (f"  [{d.type}]" if d.type else ""))
    md, js = save(demands, Path(args.out_dir), source=", ".join(dbs))
    snapshot = PROJECT_ROOT / "var" / "discovery.json"
    from datetime import datetime, timezone

    snapshot.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "source": ", ".join(dbs),
                "taxonomy_version": stats.get("taxonomy_version") if args.canonical else None,
                "coverage": stats.get("coverage") if args.canonical else None,
                "unassigned": stats.get("unassigned") if args.canonical else None,
                "demands": [d.as_dict() for d in demands],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"written {md}")
    print(f"written {js}")
    print(f"written {snapshot}")
    return 0


def cmd_trends(args: argparse.Namespace) -> int:
    import time as _time

    from .trends import GoogleTrends

    terms: list[str] = [x.strip() for x in (args.terms or "").split(",") if x.strip()]
    if args.demands:
        snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        mapping = json.loads(Path(args.terms_file).read_text(encoding="utf-8"))
        for d in snap.get("demands", [])[: args.demands]:
            for term in mapping.get(d["label"], []):
                terms.append(term)
    seen, unique = set(), []
    for term in terms:
        if term.lower() not in seen:
            seen.add(term.lower())
            unique.append(term)
    if not unique:
        print("no terms; pass --terms or --demands with a mapping file", file=sys.stderr)
        return 2

    cache_path = Path(args.cache)
    cache: dict = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}

    client = GoogleTrends(sleep=args.sleep)
    out: dict = {}
    ttl = args.cache_days * 86400
    for term in unique:
        key = f"{term}|{args.geo}|{args.timeframe}"
        entry = cache.get(key)
        fresh = entry and (_time.time() - entry.get("fetched_at", 0)) < ttl
        if not fresh:
            try:
                series = client.interest(term, geo=args.geo, timeframe=args.timeframe)
            except Exception as exc:  # noqa: BLE001 - rate limits are expected
                print(f"{term:<32} FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            entry = {
                "term": term,
                "geo": args.geo,
                "timeframe": args.timeframe,
                "fetched_at": _time.time(),
                "points": series.points,
                "summary": series.summary(),
            }
            cache[key] = entry
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            _time.sleep(args.sleep)
        out[term] = entry

    payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "geo": args.geo,
        "timeframe": args.timeframe,
        "series": out,
    }
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'term':<32}{'mean':>6}{'yoy':>9}{'change':>9}{'peak':>10}  latest")
    for term, entry in out.items():
        s = entry.get("summary") or {}
        yoy = s.get("yoy_pct")
        change = s.get("change_pct")
        print(
            f"{term:<32}{s.get('mean', 0):>6}{yoy if yoy is not None else '-':>9}"
            f"{change if change is not None else '-':>9}"
            f"{s.get('peak_date', '-'):>10}  {s.get('latest', '-')}"
        )
    print(f"written {dest}")
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    import re

    from .solutions import SolutionGenerator, render_markdown

    snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    demands = snap.get("demands", [])[: args.top]
    if not demands:
        print("snapshot has no demands; run discover first", file=sys.stderr)
        return 2

    gen = SolutionGenerator(
        model=args.model,
        base_url=args.base_url,
        cache_path=Path(args.cache),
        currency=args.currency,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict = {}

    for i, demand in enumerate(demands, 1):
        solutions = gen.for_demand(demand)
        if not solutions:
            print(f"[{i}] {demand.get('label')}: no valid solutions returned", file=sys.stderr)
            continue
        recommended = gen.rank(demand, solutions)
        name = re.sub(r"[\\/:*?\"<>|\s]+", "-", str(demand.get("label")))[:40]
        md_path = out_dir / f"{i:02d}-{name}.md"
        md_path.write_text(render_markdown(demand, solutions, recommended), encoding="utf-8")
        payload[demand.get("label")] = {
            "demand_id": demand.get("demand_id"),
            "score": demand.get("score"),
            "size": demand.get("size"),
            "domains": demand.get("domains"),
            "solutions": [s.__dict__ for s in solutions],
            "recommended": recommended,
        }
        print(f"[{i}] {demand.get('label')} -> {len(solutions)} solutions -> {md_path}")
        for s in solutions:
            mark = " ← 建议先做" if s.name == recommended.get("name") else ""
            print(f"    - {s.name} | {s.buyer} | {s.pricing} | 可行性 {s.feasibility}/5{mark}")
        print(f"    理由：{recommended.get('reason', '')}")

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written {dest}")
    return 0


def cmd_solo_fit(args: argparse.Namespace) -> int:
    from .solo_fit import SoloFitScorer

    snap_path = Path(args.snapshot)
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    if isinstance(snap, list):
        snap = {"demands": snap}
    demands = snap.get("demands", [])
    if not demands:
        print("snapshot has no demands", file=sys.stderr)
        return 2

    scorer = SoloFitScorer(
        model=args.model,
        base_url=args.base_url,
        cache_path=Path(args.cache),
        profile=args.profile,
    )
    out: dict = {}
    rows = []
    for d in demands:
        fit = scorer.score(d)
        out[d["label"]] = fit.as_dict()
        d["solo_fit"] = fit.as_dict()
        rows.append((fit.total, d["label"], fit))

    rows.sort(reverse=True)
    print(f"{'score':>6}  {'demand':<22}  结论")
    for total, label, fit in rows:
        print(f"{total:>6}  {label:<22}  {fit.summary}")
        weak = [k for k, v in fit.scores.items() if v <= 2]
        if weak:
            print(f"        短板：{', '.join(weak)}")

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written {dest}")
    if args.attach:
        snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"attached solo_fit -> {snap_path}")
    return 0


def cmd_match_tool(args: argparse.Namespace) -> int:
    from .tool_fit import ToolMatcher

    tool = json.loads(Path(args.tool).read_text(encoding="utf-8"))
    snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    if isinstance(snap, list):
        snap = {"demands": snap}
    demands = snap.get("demands", [])
    if not demands:
        print("snapshot has no demands", file=sys.stderr)
        return 2

    matcher = ToolMatcher(
        tool,
        model=args.model,
        base_url=args.base_url,
        cache_path=Path(args.cache),
    )
    rows = []
    out: dict = {}
    for d in demands:
        res = matcher.match(d)
        d["tool_match"] = res.as_dict()
        rows.append((res.total, d.get("label"), res))
        out[d.get("label")] = {"demand_id": d.get("demand_id"), **res.as_dict()}

    rows.sort(reverse=True)
    print(f"{'score':>6}  {'verdict':<8}{'demand':<22} gap")
    for total, label, res in rows:
        print(f"{total:>6}  {res.verdict:<8}{str(label):<22} {res.gap[:40]}")

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written {dest}")
    if args.attach:
        Path(args.snapshot).write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"attached tool_match -> {args.snapshot}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="painradar", description="PainRadar CLI")
    p.add_argument("--db", help="path to the SQLite ledger")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="create the ledger")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("ingest", help="ingest a JSONL/JSON/CSV file")
    sp.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    sp.add_argument("--file", required=True)
    sp.add_argument("--platform", default="file")
    sp.add_argument("--source", default="file", choices=["file", "mediacrawler"])
    sp.add_argument("--field-map", default="", help="JSON override for MediaCrawler field names")
    sp.add_argument("--min-len", type=int, default=6, help="drop comments shorter than this")
    sp.add_argument("--tos-basis", default="user_provided")
    sp.add_argument("--tier", default="A", choices=["A", "B", "C"])
    sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("run", help="extract, cluster, score and build opportunities")
    sp.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    sp.add_argument("--extractor", default="rule", choices=["rule", "llm"])
    sp.add_argument("--threshold", type=float, default=0.32)
    sp.add_argument("--min-size", type=int, default=3)
    sp.add_argument("--llm-model", default=None)
    sp.add_argument("--llm-base-url", default=None)
    sp.add_argument("--llm-consistency", action=argparse.BooleanOptionalAction, default=False)
    sp.add_argument("--double-run", action="store_true", help="enable the second consistency pass (2x tokens)")
    sp.add_argument("--validity-filter", action=argparse.BooleanOptionalAction, default=True)
    sp.add_argument("--mode", default="b2c", choices=["b2c", "b2b"],
                    help="b2b: traditional-industry / high-ticket mode")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("report", help="render a report for a run")
    sp.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    sp.add_argument("--run", default=None)
    sp.add_argument("--out", default=None)
    sp.add_argument("--docx", action="store_true")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("demo", help="run the bundled demo end to end")
    sp.add_argument("--reset", action="store_true")
    sp.add_argument("--extractor", default="rule", choices=["rule", "llm"])
    sp.add_argument("--threshold", type=float, default=0.32)
    sp.add_argument("--min-size", type=int, default=3)
    sp.add_argument("--docx", action="store_true")
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("match-tool", help="match a concrete tool against discovered demands")
    sp.add_argument("--tool", required=True, help="tool profile JSON")
    sp.add_argument("--snapshot", default="var/discovery.json")
    sp.add_argument("--cache", default="var/tool_match_cache.json")
    sp.add_argument("--out", default="var/tool_match.json")
    sp.add_argument("--attach", action="store_true")
    sp.add_argument("--model", default=None)
    sp.add_argument("--base-url", default=None)
    sp.set_defaults(func=cmd_match_tool)

    sp = sub.add_parser("solo-fit", help="score demands for a solo developer")
    sp.add_argument("--snapshot", default="var/discovery.json")
    sp.add_argument("--cache", default="var/solo_fit_cache.json")
    sp.add_argument("--out", default="var/solo_fit.json")
    sp.add_argument("--attach", action="store_true", help="write scores back into the snapshot")
    sp.add_argument("--profile", default="consumer", choices=["consumer", "b2b", "ai_saas"])
    sp.add_argument("--model", default=None)
    sp.add_argument("--base-url", default=None)
    sp.set_defaults(func=cmd_solo_fit)

    sp = sub.add_parser("solve", help="generate solution concepts for top demands")
    sp.add_argument("--snapshot", default="var/discovery.json")
    sp.add_argument("--top", type=int, default=3)
    sp.add_argument("--out-dir", default="docs/solutions")
    sp.add_argument("--out", default="var/solutions.json")
    sp.add_argument("--cache", default="var/solutions_cache.json")
    sp.add_argument("--currency", default="USD", help="USD for overseas buyers, CNY for domestic")
    sp.add_argument("--model", default=None)
    sp.add_argument("--base-url", default=None)
    sp.set_defaults(func=cmd_solve)

    sp = sub.add_parser("trends", help="fetch Google Trends series for demand terms")
    sp.add_argument("--terms", default="", help="comma-separated search terms")
    sp.add_argument("--demands", type=int, default=0, help="take top N demand terms from the snapshot")
    sp.add_argument("--snapshot", default="var/discovery.json")
    sp.add_argument("--terms-file", default="var/demand_terms.json")
    sp.add_argument("--geo", default="", help="country code; empty means worldwide")
    sp.add_argument("--timeframe", default="today 12-m")
    sp.add_argument("--sleep", type=float, default=4.0)
    sp.add_argument("--cache", default="var/trends_cache.json")
    sp.add_argument("--cache-days", type=float, default=7.0)
    sp.add_argument("--out", default="var/trends.json")
    sp.set_defaults(func=cmd_trends)

    sp = sub.add_parser("fetch", help="fetch comments from a live source")
    sp.add_argument("--source", required=True, choices=["reddit", "appstore", "github", "hn"])
    sp.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    sp.add_argument("--query", default="")
    sp.add_argument("--subreddits", default="")
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--no-comments", action="store_true")
    sp.add_argument("--app-id", default="")
    sp.add_argument("--country", default="us")
    sp.add_argument("--pages", type=int, default=3)
    sp.add_argument("--search", default="", help="App Store search term (resolves app id)")
    sp.set_defaults(func=cmd_fetch)

    sp = sub.add_parser("anchor", help="ingest external anchors (ratings, prices, BSR)")
    sp.add_argument("--source", required=True, choices=["itunes", "file"])
    sp.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    sp.add_argument("--app-id", default="")
    sp.add_argument("--country", default="us")
    sp.add_argument("--file", default="")
    sp.set_defaults(func=cmd_anchor)

    sp = sub.add_parser("stats", help="ledger statistics")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("delete", help="cascade-delete one comment (GDPR/PIPL)")
    sp.add_argument("--uid", required=True)
    sp.set_defaults(func=cmd_delete)

    sp = sub.add_parser("doctor", help="environment check")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("discover", help="category-free demand discovery")
    sp.add_argument("--db", action="append", default=argparse.SUPPRESS)
    sp.add_argument("--min-size", type=int, default=8)
    sp.add_argument("--threshold", type=float, default=0.30)
    sp.add_argument("--top", type=int, default=15)
    sp.add_argument("--canonical", action="store_true", help="normalize clusters into demand statements first")
    sp.add_argument("--refresh-taxonomy", action="store_true", help="ignore the cached demand taxonomy")
    sp.add_argument("--frozen", default=None, help="alternate frozen taxonomy path (one per corpus profile)")
    sp.add_argument("--assignment-cache", default=None, help="alternate assignment cache path")
    sp.add_argument("--freeze", action="store_true", help="freeze the current taxonomy as vN for future runs")
    sp.add_argument("--rebuild", action="store_true", help="ignore the frozen taxonomy and rebuild")
    sp.add_argument("--statement-threshold", type=float, default=0.30,
                    help="similarity needed to keep two demand statements together")
    sp.add_argument("--out-dir", default="docs/discovery")
    sp.set_defaults(func=cmd_discover)

    sp = sub.add_parser("serve", help="start the HTTP API + web UI")
    sp.add_argument("--db", action="append", default=argparse.SUPPRESS,
                    help="database path; repeat to merge several (defaults to the global --db or var/painradar.db)")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8770)
    sp.add_argument("--reload", action="store_true")
    sp.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit as exc:
        if exc.code and isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    raise SystemExit(main())
