"""Run a pinned deep-dive spec and persist the corpus across runs.

    python tools/deepdive_run.py --product "PDF 工具" --focus pain \
        --subreddits pdf,software,macapps \
        --keywords subscription,cancel,refund,expensive,price,adobe \
        --taxonomy pdf --domain-terms pdf,acrobat,ocr,document \
        --app-store --runs 2 --out docs/deepdive-reports/pdf-tools.md

Every run unions its fetched texts with the persisted corpus for the same
(pinned) spec, so sample size only grows.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.deepdive import DeepDive  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--focus", default="pain", choices=["pain", "decay"])
    ap.add_argument("--subreddits", default="")
    ap.add_argument("--keywords", default="")
    ap.add_argument("--domain-terms", default="")
    ap.add_argument("--taxonomy", default="")
    ap.add_argument("--app-store", action="store_true")
    ap.add_argument("--runs", type=int, default=1, help="fetch rounds per run")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec = {
        "product": args.product,
        "platform": "Reddit",
        "system": "",
        "focus": args.focus,
        "subreddits": [s.strip() for s in args.subreddits.split(",") if s.strip()],
        "keywords": [s.strip() for s in args.keywords.split(",") if s.strip()],
        "domain_terms": [s.strip() for s in args.domain_terms.split(",") if s.strip()],
        "app_store": args.app_store,
        "fetch_runs": max(1, min(args.runs, 4)),
    }
    if args.taxonomy:
        spec["pain_taxonomy"] = args.taxonomy

    dive = DeepDive(
        model=os.environ.get("PAINRADAR_LLM_MODEL", "deepseek-chat"),
        base_url=os.environ.get("PAINRADAR_LLM_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=os.environ.get("PAINRADAR_LLM_API_KEY", ""),
    )
    result = dive.execute(spec, force=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result["markdown"], encoding="utf-8")
    print(f"count={result['count']} cached={result.get('cached')} saved={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
