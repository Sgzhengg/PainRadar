"""Screen consumer utility categories for subscription resentment.

    python tools/screen_utilities.py --pages 2 --per-term 2

For each category we pull recent App Store reviews and measure how often they
mention subscriptions/paywalls versus lifetime/one-time purchases. A category
with a high subscription share and a one-shot job is a candidate for a
one-time-purchase utility.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.connectors.appstore import AppStoreConnector, search_apps  # noqa: E402

TERMS = {
    "pdf_tools": "pdf editor",
    "photo_editor": "photo editor",
    "video_editor": "video editor",
    "scanner": "document scanner",
    "file_transfer": "file transfer",
    "cleaner": "phone cleaner",
    "translate": "translate camera",
}

SUB_RE = re.compile(r"subscri|paywall|free trial|in-app purchase|upgrade to", re.I)
LIFE_RE = re.compile(r"lifetime|one[- ]time|buy once|no subscription", re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--per-term", type=int, default=2)
    ap.add_argument("--out", default="var/utility_screen.json")
    args = ap.parse_args()

    rows = []
    for key, term in TERMS.items():
        try:
            apps = search_apps(term, limit=args.per_term)
        except Exception as exc:  # noqa: BLE001
            print(f"{key}: search failed {exc}")
            continue
        texts: list[str] = []
        names = []
        for app in apps:
            conn = AppStoreConnector(category=key, app_id=str(app["app_id"]), pages=args.pages)
            try:
                items = list(conn.fetch())
            except Exception:  # noqa: BLE001
                continue
            names.append(app["name"])
            texts.extend(i.text for i in items)
            time.sleep(0.4)
        if not texts:
            continue
        sub = sum(1 for t in texts if SUB_RE.search(t))
        life = sum(1 for t in texts if LIFE_RE.search(t))
        rows.append(
            {
                "category": key,
                "term": term,
                "apps": names,
                "reviews": len(texts),
                "subscription_share": round(sub / len(texts), 3),
                "lifetime_share": round(life / len(texts), 3),
            }
        )
        print(f"{key:<14} reviews={len(texts):>4} sub={sub/len(texts):.1%} lifetime={life/len(texts):.1%}")

    rows.sort(key=lambda r: r["subscription_share"], reverse=True)
    Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwritten {args.out}")
    for r in rows:
        print(f"  {r['category']:<14} sub={r['subscription_share']:.1%} life={r['lifetime_share']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
