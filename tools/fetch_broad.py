"""Broad everyday-friction corpus across unrelated life domains.

    python tools/fetch_broad.py --db var/broad.db --pages 2

The point is breadth: a pain that shows up in caregiving, teaching and home
repair at the same time is likely a generic workflow pain, not a domain quirk.
Each domain is its own category so cross-domain co-occurrence is measurable.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.config import register_custom_category  # noqa: E402
from painradar.connectors.reddit_archive import RedditArchiveConnector  # noqa: E402
from painradar.pipeline import ingest_items  # noqa: E402
from painradar.store import Store  # noqa: E402

DOMAINS = [
    ("钱与账单", "money bills", ["personalfinance", "povertyfinance"]),
    ("照护与医疗", "care health", ["CaregiverSupport", "HealthInsurance"]),
    ("家庭与教育", "family education", ["Parenting", "Teachers"]),
    ("房屋与维修", "home repair", ["HomeImprovement", "Plumbing"]),
    ("求职与职业", "career jobs", ["jobs", "resumes"]),
    ("出行与身份", "travel immigration", ["travel", "immigration"]),
    ("神经多样与无障碍", "neuro accessibility", ["ADHD", "disability"]),
    ("手续与合规", "paperwork compliance", ["legaladvice", "tax"]),
]

SCENES = {
    "表格与文书": ["form", "paperwork", "document", "application", "表格", "文书", "材料"],
    "预约与等待": ["appointment", "wait", "queue", "预约", "排队", "等待"],
    "费用与账单": ["bill", "cost", "charge", "fee", "费用", "账单", "收费"],
    "信息找不到": ["confusing", "unclear", "don't know", "找不到", "不清楚", "看不懂"],
    "沟通与跟进": ["call", "email", "follow up", "no response", "电话", "邮件", "没人回"],
    "规则与资格": ["eligible", "requirement", "policy", "rule", "资格", "规定", "政策"],
    "出错与纠错": ["error", "wrong", "mistake", "denied", "出错", "错误", "被拒"],
    "多方协调": ["coordinate", "between", "transfer", "协调", "转接", "对接"],
    "时间与期限": ["deadline", "late", "delay", "期限", "延误", "超时"],
    "线上线下切换": ["online", "in person", "portal", "线上", "线下", "网站"],
    "语言与理解": ["language", "translate", "jargon", "语言", "翻译", "术语"],
    "隐私与安全": ["privacy", "identity", "scam", "隐私", "身份", "诈骗"],
    "系统不可用": ["down", "broken", "offline", "崩", "故障", "打不开"],
    "其他场景": [],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/broad.db")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    store = Store(args.db)
    total = 0
    try:
        keys: dict[str, str] = {}
        for name, term, _subs in DOMAINS:
            keys[name] = register_custom_category(name, term)

        # one shared scene vocabulary across domains so clusters stay comparable
        from painradar.config import CUSTOM_PATH, load_custom_categories

        data = json.loads(CUSTOM_PATH.read_text(encoding="utf-8"))
        for name, _term, _subs in DOMAINS:
            data[keys[name]]["scenes"] = {k: list(v) for k, v in SCENES.items()}
        CUSTOM_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        load_custom_categories()

        for name, _term, subs in DOMAINS:
            key = keys[name]
            for subreddit in subs:
                conn = RedditArchiveConnector(
                    category=key, subreddit=subreddit, pages=args.pages, limit=args.limit
                )
                try:
                    result = ingest_items(store, conn.fetch(), key)
                except Exception:  # noqa: BLE001
                    continue
                total += result.inserted
                print(f"  r/{subreddit:<18} -> {key:<18} +{result.inserted}")
                time.sleep(1)

        print(f"\ninserted {total}")
        for category, platform, n in store._conn.execute(
            "SELECT category, platform, COUNT(rowid) FROM items WHERE deleted_at IS NULL GROUP BY category, platform"
        ).fetchall():
            print(f"  {category:<22} {platform:<10} {n}")
            store.audit("tool", "fetch", platform, category, f'{{"items": {n}}}')
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
