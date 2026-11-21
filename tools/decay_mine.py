"""Mine value-decay signals for a specific product (why people stop using it).

    python tools/decay_mine.py --product "Apple Watch" \
        --subreddits AppleWatch,AppleWatchFitness \
        --pages 10 --max-texts 200 --out docs/decay-v3/apple-watch.md

Two-stage classification:
  1. gate  — is this a first-person "bought it, then stopped" narrative?
  2. tag   — which decay trigger (12 classes; `unclear` allowed, `other` not)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.connectors.reddit_archive import RedditArchiveConnector  # noqa: E402
from painradar.net import HttpClient  # noqa: E402

GATE_SYSTEM = """你在筛选"价值衰减叙述"：用户买了某个产品，用了一段时间，然后不用了/少用了。

只回答两件事：
- is_decay：true 当且仅当满足前两条：
  (1) 本人拥有或长期使用过该产品；
  (2) 表达了"用得少 / 不用了 / 卖了 / 吃灰 / 觉得不值"中的任意一种。
  理由可以隐含，不要求明说。
- reason：一句话说明为什么是/不是（≤30 字）。

以下都不算：纯夸奖、纯提问、讨论新闻/法律/系统版本、他人设备、求推荐、二手买卖信息本身。
返回 JSON：{"items": [{"i": 0, "is_decay": true, "reason": "..."}, ...]}
条目数与输入一致，i 是输入下标。"""

TAG_SYSTEM = """你在给"价值衰减叙述"分类。每条必须选一个触发，禁止用 other：

value_not_realized  功能没被用起来/期待落空
friction            设置、操作、环境成本太高
redundancy          手机或其他设备已能做
discomfort          佩戴不适、眼疲劳、晕动
charging            充电/续航
notification_fatigue 通知疲劳
price_regret        觉得不值
hardware_failure    电池老化、损坏、故障
ecosystem_lock      被平台/软件/工具锁定
life_change         搬家、换工作、生娃等生活变化
upgrade_seeking     想换新款（不是衰减）
unclear             信息不足，无法判断

同时抽取：
- job：买它是为了完成什么任务
- expected / realized：期待 vs 实际
- substitute：现在用什么替代
- action：sold / shelved / gave_away / still_using / unknown
- quote：最能代表的一句原文（≤60 字）
- reason_stated：挂牌是否明确说了"为什么卖/为什么不用"（true/false）。
  没说原因的，decay_trigger 用 unclear。

返回 JSON：{"records": [{"i": 0, "decay_trigger": "...", "job": "...", "expected": "...",
"realized": "...", "substitute": "...", "action": "...", "quote": "..."}, ...]}"""


def call(client: HttpClient, base_url: str, api_key: str, model: str, system: str, payload: dict) -> dict:
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    try:
        resp = client.post_json(
            f"{base_url}/chat/completions",
            body,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )
        content = resp["choices"][0]["message"]["content"]
        return json.loads(content[content.find("{"): content.rfind("}") + 1])
    except Exception as exc:  # noqa: BLE001
        print("  llm failed:", type(exc).__name__, str(exc)[:80], file=sys.stderr)
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--subreddits", default="")
    ap.add_argument("--keywords", default="")
    ap.add_argument("--signal-regex", default=r"(stopped|quit|dust|drawer|barely|rarely|regret|sold|returned|unused|never use|waste|forgot|gave up|not using)")
    ap.add_argument("--pages", type=int, default=10)
    ap.add_argument("--max-texts", type=int, default=200)
    ap.add_argument("--texts-file", default="", help="JSONL with {text} — skip Reddit fetch")
    ap.add_argument("--listing-mode", action="store_true", help="second-hand listings: skip gate, reason may be silent")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=os.environ.get("PAINRADAR_LLM_MODEL", "deepseek-chat"))
    ap.add_argument("--base-url", default=os.environ.get("PAINRADAR_LLM_BASE_URL", "https://api.deepseek.com/v1"))
    ap.add_argument("--api-key", default=os.environ.get("PAINRADAR_LLM_API_KEY", ""))
    args = ap.parse_args()

    signal = re.compile(args.signal_regex, re.I)
    texts: list[str] = []
    if args.texts_file:
        for line in Path(args.texts_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                text = json.loads(line).get("text", "")
            except ValueError:
                continue
            if text:
                texts.append(text)
        print(f"  loaded {len(texts)} texts from {args.texts_file}")
    else:
        for sub in [s.strip() for s in args.subreddits.split(",") if s.strip()]:
            conn = RedditArchiveConnector(category="decay", subreddit=sub, keywords=(), pages=args.pages, limit=100)
            try:
                for item in conn.fetch():
                    if signal.search(item.text):
                        texts.append(item.text)
            except Exception as exc:  # noqa: BLE001
                print(f"  r/{sub} failed: {exc}", file=sys.stderr)
            print(f"  r/{sub}: {len(texts)} candidates")

    seen, unique = set(), []
    for t in texts:
        key = t[:120]
        if key in seen:
            continue
        seen.add(key)
        unique.append(t)
    unique = unique[: args.max_texts]
    if not unique:
        print("no texts", file=sys.stderr)
        return 2

    client = HttpClient(user_agent="PainRadar/0.1", timeout=120, max_retries=1, rate_per_sec=0.5)
    gated: list[tuple[int, str]] = []
    if args.listing_mode:
        gated = list(enumerate(unique))
        print(f"  listing mode: all {len(gated)} listings treated as sold")
    for start in range(0, len(unique), 20) if not args.listing_mode else []:
        batch = unique[start : start + 20]
        res = call(client, args.base_url, args.api_key, args.model, GATE_SYSTEM,
                   {"texts": [{"i": i, "text": t} for i, t in enumerate(batch)]})
        for item in res.get("items", []):
            if str(item.get("is_decay")).strip().lower() in ("true", "yes", "1"):
                idx = int(item.get("i", -1))
                if 0 <= idx < len(batch):
                    gated.append((start + idx, batch[idx]))
        print(f"  gate {min(start + 20, len(unique))}/{len(unique)} -> kept {len(gated)}")

    records: list[dict] = []
    for start in range(0, len(gated), 20):
        batch = gated[start : start + 20]
        res = call(client, args.base_url, args.api_key, args.model, TAG_SYSTEM,
                   {"texts": [{"i": i, "text": t} for i, (_idx, t) in enumerate(batch)]})
        for item in res.get("records", []):
            idx = int(item.get("i", -1))
            if 0 <= idx < len(batch):
                item["_text"] = batch[idx][1]
                records.append(item)
        print(f"  tag {min(start + 20, len(gated))}/{len(gated)}")

    stated = sum(1 for r in records if r.get("reason_stated") is True)
    triggers = Counter(r.get("decay_trigger", "unclear") for r in records if r.get("reason_stated") is True)
    actions = Counter(r.get("action", "unknown") for r in records)
    jobs = Counter((r.get("job") or "")[:40] for r in records if r.get("job"))

    lines = [
        f"# 价值衰减地图：{args.product}",
        "",
        f"> 候选 {len(unique)} 条 → 判定为衰减叙述 {len(gated)} 条 → 完成分类 {len(records)} 条"
        + (f"；其中 {stated} 条说明了原因" if args.listing_mode else ""),
        "",
        "## 衰减触发（为什么不用了）",
        "",
        "| 触发 | 条数 | 占比 |",
        "|---|---|---|",
    ]
    for k, v in triggers.most_common():
        lines.append(f"| {k} | {v} | {v / max(1, len(records)) * 100:.0f}% |")

    lines += ["", "## 处置动作", "", "| 动作 | 条数 |", "|---|---|"]
    for k, v in actions.most_common():
        lines.append(f"| {k} | {v} |")

    lines += ["", "## 购买任务", ""]
    for k, v in jobs.most_common(8):
        lines.append(f"- {k}（{v}）")

    lines += ["", "## 典型叙述", ""]
    shown = 0
    for r in records:
        if shown >= 10 or not r.get("quote"):
            continue
        shown += 1
        lines += [
            f"### {shown}. {r.get('job') or '—'}",
            "",
            f"> {r.get('quote')}",
            "",
            f"- 期待：{r.get('expected') or '—'}",
            f"- 实际：{r.get('realized') or '—'}",
            f"- 触发：`{r.get('decay_trigger')}`　替代：{r.get('substitute') or '—'}　处置：`{r.get('action')}`",
            "",
        ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
