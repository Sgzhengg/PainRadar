"""CLI: MediaCrawler export -> cleaned contexts -> signals -> report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .llm import LLM
from .loader import build_contexts, load_threads
from .map_stage import run_map
from .reduce_stage import run_reduce
from .report import render_report, write_report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Indie opportunity mining pipeline")
    ap.add_argument("--input", required=True, help="MediaCrawler JSON/JSONL export")
    ap.add_argument("--keyword", required=True, help="report keyword, also used in filename")
    ap.add_argument("--out", default="", help="output markdown path")
    ap.add_argument("--min-len", type=int, default=6, help="drop comments shorter than this")
    ap.add_argument("--top-comments", type=int, default=4, help="comments kept per thread")
    ap.add_argument("--batch-size", type=int, default=4, help="contexts per map call")
    ap.add_argument("--workers", type=int, default=3, help="parallel LLM calls")
    ap.add_argument("--max-threads", type=int, default=0, help="0 = all")
    ap.add_argument("--mapping", default="", help="JSON file with custom field names")
    ap.add_argument("--filter", default="", help="comma-separated domain terms; threads without them are dropped")
    ap.add_argument("--model", default="", help="override LLM model")
    ap.add_argument("--cache-dir", default="var/indie_cache", help="LLM response cache directory")
    ap.add_argument("--offline", action="store_true", help="replay cached responses only (no network)")
    args = ap.parse_args(argv)

    mapping = None
    if args.mapping:
        mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8"))

    threads = load_threads(args.input, mapping=mapping)
    if args.max_threads:
        threads = threads[: args.max_threads]
    if not threads:
        print("no threads loaded; check --input and --mapping", file=sys.stderr)
        return 1

    domain_terms = [x.strip() for x in args.filter.split(",") if x.strip()]
    blocks, input_stats = build_contexts(
        threads,
        top_comments=args.top_comments,
        min_comment_len=args.min_len,
        domain_terms=domain_terms,
    )
    input_stats["threads"] = len(threads)
    print(f"threads={len(threads)} contexts={len(blocks)} " + " ".join(f"{k}={v}" for k, v in input_stats.items()))

    llm = LLM(model=args.model or None, cache_dir=args.cache_dir, offline=args.offline)
    try:
        signals, map_stats = run_map(
            llm, blocks, batch_size=args.batch_size, workers=args.workers
        )
        print(f"signals={len(signals)} " + " ".join(f"{k}={v}" for k, v in map_stats.items()))
        clusters = run_reduce(llm, signals)
    finally:
        llm.close()

    out = Path(args.out) if args.out else Path("reports") / f"report_{args.keyword}_{__import__('datetime').date.today().isoformat()}.md"
    markdown = render_report(
        keyword=args.keyword,
        clusters=clusters,
        signals=signals,
        input_stats=input_stats,
        token_stats=llm.tokens.as_dict(),
        source=str(args.input),
    )
    path = write_report(out, markdown)
    print(f"report -> {path}")
    print("tokens: " + json.dumps(llm.tokens.as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
