"""Conversational deep dive: clarify a request, then mine one product/platform.

Flow:
  plan(message)      -> structured spec + 3 clarifying questions
  execute(spec)      -> fetch evidence, analyze, return a markdown report
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .connectors.reddit_archive import RedditArchiveConnector
from .net import HttpClient

SPEC_SYSTEM = """从用户的一句话里提取"专项挖掘"需求，返回 JSON：
{
 "product": "要研究的产品/服务",
 "platform": "平台或渠道（如 App Store、Reddit、二手平台、官网）",
 "system": "系统/生态（如 iOS、Android、Windows、Web、硬件设备）",
 "focus": "decay | pain",
 "subreddits": ["2-4 个最相关的 Reddit 板块，不带 r/"],
 "keywords": ["3-6 个英文关键词，用于筛评论"],
 "goal": "一句话说明用户想得到什么结论"
}

focus 判断：
- decay：用户关心"买了为什么不用/吃灰/卖了"
- pain：用户关心"用起来哪里受阻/功能痛点"
不确定时用 pain。
只返回 JSON。"""

QUESTIONS_SYSTEM = """用大白话问 3 个问题，帮普通人确定研究范围。
不要用专业术语（口径、样本、归一化、聚类、板块、语料）。
每个问题不超过 20 字，答案要能直接选。
返回 JSON：{"questions": ["...", "...", "..."]}"""

GATE_SYSTEM = """判断这条文本是否属于"目标产品的价值衰减叙述"：
本人拥有/长期使用过，并且表达了用得少、不用了、卖了、吃灰或觉得不值。
返回 JSON：{"items":[{"i":0,"is_decay":true,"reason":"..."}]}，条目数与输入一致。"""

TAG_SYSTEM = """给价值衰减叙述分类，必须从以下选一个：
value_not_realized / friction / redundancy / discomfort / charging /
notification_fatigue / price_regret / hardware_failure / ecosystem_lock /
life_change / upgrade_seeking / unclear
同时抽取 job（购买任务）、expected（期待）、realized（实际）、
substitute（替代品）、action（sold/shelved/gave_away/still_using/unknown）、
quote（≤60 字原文）、reason_stated（是否说明原因）。
返回 JSON：{"records":[{"i":0,...}]}，条目数与输入一致。"""

PAIN_SYSTEM = """从这些用户自述里抽取产品痛点。每条返回：
{"i":0,"pain":"不超过 20 字的痛点","trigger":"触发场景","severity":1-5,
 "quote":"≤60 字原文","product_area":"功能模块"}
只抽取明确表达受阻/不满的条目；没有痛点的返回空数组。
返回 JSON：{"records":[...]}"""


def _chat(client: HttpClient, base_url: str, key: str, model: str, system: str, payload: dict) -> dict:
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
            headers={"Authorization": f"Bearer {key}"} if key else {},
        )
        content = resp["choices"][0]["message"]["content"]
        return json.loads(content[content.find("{"): content.rfind("}") + 1])
    except Exception as exc:  # noqa: BLE001
        print("llm failed", type(exc).__name__, str(exc)[:80], file=sys.stderr)
        return {}


CACHE_PATH = Path(__file__).resolve().parents[2] / "var" / "deepdive_cache.json"
CACHE_TTL_SECONDS = 24 * 3600


def _cache_key(spec: dict, answers: list[str] | None) -> str:
    import hashlib

    blob = json.dumps(
        {
            "spec": {
                k: spec.get(k)
                for k in ("product", "platform", "system", "focus", "subreddits", "keywords",
                          "app_store", "app_query")
            },
            "answers": answers or [],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")



HISTORY_PATH = Path(__file__).resolve().parents[2] / "var" / "deepdive_history.json"
HISTORY_MAX = 300


def _load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _save_history(history: dict) -> None:
    if len(history) > HISTORY_MAX:
        ordered = sorted(history.items(), key=lambda kv: kv[1].get("created_at", ""))
        history = dict(ordered[-HISTORY_MAX:])
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _with_history(key: str, spec: dict, counts: dict, result: dict) -> dict:
    import datetime as _dt

    if not key or not counts:
        return result
    history = _load_history()
    entry = history.get(key) or {}
    series = list(entry.get("series") or [])
    if not series and entry.get("counts"):
        series = [{"date": str(entry.get("created_at", ""))[:10], "counts": entry["counts"]}]

    if series:
        prev_counts = series[-1].get("counts", {})
        prev_date = series[-1].get("date", "")
        rows = []
        for name in sorted(set(prev_counts) | set(counts), key=lambda x: -counts.get(x, 0)):
            before = int(prev_counts.get(name, 0))
            after = int(counts.get(name, 0))
            rows.append(f"| {name} | {before} | {after} | {after - before:+d} |")
        section = "\n".join(
            ["", f"## 与上次对比（{prev_date}）", "", "| 触发 | 上次 | 本次 | 变化 |", "|---|---|---|---|", *rows]
        )
        result["markdown"] = result["markdown"].replace("\n## 局限", section + "\n\n## 局限", 1)
        result["delta_base"] = prev_date

    today = _dt.date.today().isoformat()
    series.append({"date": today, "counts": counts})
    series = series[-12:]
    history[key] = {
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "product": spec.get("product"),
        "counts": counts,
        "series": series,
    }
    _save_history(history)
    result["series"] = series
    return result



THEME_SYSTEM = """把这些用户痛点归并为不超过 8 个主题，主题名用 4-10 个字的中文短语。
必须覆盖全部输入；语义相近的合并。返回 JSON：
{"themes": [{"name": "主题名", "pains": ["原痛点1", "原痛点2"]}]}"""


TAXONOMY_ASSIGN_SYSTEM = """把每条痛点归入给定的固定主题表之一。只能使用列表里的主题名，
不得新造。若确实无法归类，用"其他"。返回 JSON：
{"assignments": [{"pain": "原痛点", "theme": "主题名"}]}"""



THEME_HINTS = {
    "付费与订阅": ("订阅", "收费", "价格", "付费", "退款", "贵", "定价", "免费"),
    "弹窗与广告": ("广告", "弹窗", "推广", "推销"),
    "格式转换与 OCR": ("OCR", "ocr", "转换", "识别", "扫描", "翻译"),
    "性能与稳定性": ("崩溃", "卡顿", "闪退", "慢", "性能", "内存", "发热", "bug"),
    "配置与使用门槛": ("配置", "设置", "安装", "门槛", "上手", "学习", "教程"),
    "PDF 编辑与表单": ("表单", "编辑", "注释", "签名", "合并", "拆分", "页面"),
    "界面与易用性": ("界面", "UI", "难用", "复杂", "布局"),
    "隐私与 AI 开关": ("隐私", "AI", "禁用", "数据"),
    "文件管理": ("文件", "管理", "整理", "存储", "目录"),
}


def _heuristic_theme(pain: str, themes: list[str]) -> str:
    for theme, words in THEME_HINTS.items():
        if theme not in themes:
            continue
        if any(word.lower() in pain.lower() for word in words):
            return theme
    return "其他"

GENERIC_PRODUCT_WORDS = ("问题", "需求", "东西", "事情", "产品", "用户", "体验", "场景", "未知", "不清楚")


def product_is_concrete(spec: dict) -> bool:
    product = str(spec.get("product") or "").strip()
    if len(product) < 2:
        return False
    return not any(word in product for word in GENERIC_PRODUCT_WORDS)


@dataclass
class DeepDive:
    model: str = os.environ.get("PAINRADAR_LLM_MODEL", "deepseek-chat")
    base_url: str = os.environ.get("PAINRADAR_LLM_BASE_URL", "https://api.deepseek.com/v1")
    api_key: str = os.environ.get("PAINRADAR_LLM_API_KEY", "")
    timeout: int = 120

    def __post_init__(self) -> None:
        self.client = HttpClient(user_agent="PainRadar/0.1", timeout=self.timeout, max_retries=1, rate_per_sec=0.5)

    def plan(self, message: str, history: list[str] | None = None) -> dict:
        text = message if not history else message + "\n补充：" + "；".join(history)
        spec = _chat(self.client, self.base_url, self.api_key, self.model, SPEC_SYSTEM, {"message": text})
        questions = _chat(
            self.client, self.base_url, self.api_key, self.model, QUESTIONS_SYSTEM, {"spec": spec}
        ).get("questions") or []
        missing: list[str] = []
        if not product_is_concrete(spec):
            missing.append("product")
            questions = ["请补充具体产品 / 服务名称（例如 Apple Watch、Kindle）"] + questions
        if not (spec.get("subreddits") or spec.get("app_store")):
            missing.append("subreddits")
            questions = questions + ["你能提供 1–2 个相关的 Reddit 板块吗？没有就勾选 App Store。"]
        if len(questions) < 3:
            questions = (questions + [
                "看多久？",
                "主要看谁？",
                "最想知道什么？",
            ])[:3]
        return {"spec": spec, "questions": questions[:3], "missing": missing}



    def _load_taxonomy(self, spec: dict) -> list[str]:
        name = str(spec.get("pain_taxonomy") or "").strip()
        if not name:
            return []
        path = Path(__file__).resolve().parents[2] / "var" / f"pain_taxonomy_{name}.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return []
        themes = [str(x).strip() for x in (data.get("themes") or []) if str(x).strip()]
        return themes

    def _normalize_pains(self, pains: list[str], themes: list[str] | None = None) -> dict[str, str]:
        if not pains:
            return {}
        mapping: dict[str, str] = {}
        if themes:
            allowed = set(themes)
            for start in range(0, len(pains), 25):
                batch = pains[start : start + 25]
                result = _chat(
                    self.client, self.base_url, self.api_key, self.model,
                    TAXONOMY_ASSIGN_SYSTEM,
                    {"themes": themes, "pains": batch},
                )
                for item in result.get("assignments") or []:
                    pain = str(item.get("pain") or "").strip()
                    theme = str(item.get("theme") or "").strip()
                    if pain and theme in allowed:
                        mapping[pain] = theme
            for pain in pains:
                if pain in mapping:
                    continue
                mapping[pain] = _heuristic_theme(pain, themes)
            return mapping

        result = _chat(
            self.client, self.base_url, self.api_key, self.model,
            THEME_SYSTEM, {"pains": pains[:60]},
        )
        for theme in result.get("themes") or []:
            name = str(theme.get("name") or "").strip()
            if not name:
                continue
            for pain in theme.get("pains") or []:
                mapping[str(pain).strip()] = name
        return mapping

    def compare(self, products: list, template: dict, force: bool = False) -> dict:
        """Run execute() per product; each product may carry its own sources."""
        rows = []
        counts_by_product: dict[str, dict] = {}
        names: list[str] = []
        for item in products[:3]:
            if isinstance(item, dict):
                name = str(item.get("product") or "").strip()
                spec = dict(template)
                for key in ("subreddits", "keywords"):
                    value = item.get(key)
                    if isinstance(value, list) and value:
                        spec[key] = value
                if isinstance(item.get("app_store"), bool):
                    spec["app_store"] = item["app_store"]
            else:
                name = str(item).strip()
                spec = dict(template)
            if not name:
                continue
            names.append(name)
            spec["product"] = name
            result = self.execute(spec, force=force)
            counts = {}
            series = result.get("series") or []
            if series:
                counts = dict(series[-1].get("counts") or {})
            counts_by_product[name] = counts
            top = max(counts, key=counts.get) if counts else "—"
            rows.append(
                {
                    "product": name,
                    "count": result.get("count", 0),
                    "top": top,
                    "total": sum(counts.values()),
                }
            )

        lines = [f"# 多产品对比：{' vs '.join(names)}", ""]
        lines.append("| 产品 | 有效证据 | 首要触发 | 触发总数 |")
        lines.append("|---|---|---|---|")
        for row in rows:
            lines.append(f"| {row['product']} | {row['count']} | {row['top']} | {row['total']} |")

        all_triggers = sorted({k for c in counts_by_product.values() for k in c})
        if all_triggers:
            lines += ["", "## 触发分布（占各自总数比例）", ""]
            lines.append("| 触发 | " + " | ".join(names) + " |")
            lines.append("|---" * (len(names) + 1) + "|")
            for trigger in all_triggers:
                cells = []
                for name in names:
                    counts = counts_by_product[name]
                    total = sum(counts.values()) or 1
                    cells.append(f"{(counts.get(trigger, 0) / total * 100):.0f}%")
                lines.append(f"| {trigger} | " + " | ".join(cells) + " |")

        lines += ["", "## 说明", "", "- 同一套板块与关键词，仅产品名不同；", "- 百分比按各产品自身触发总数归一化。"]
        return {"spec": {"product": " vs ".join(names)}, "markdown": "\n".join(lines), "count": sum(r["count"] for r in rows), "cached": False, "series": []}

    # -- evidence ---------------------------------------------------------
    def _fetch(self, spec: dict, pages: int = 8, key: str = "") -> list[str]:
        runs = int(spec.get("fetch_runs") or 1)
        runs = max(1, min(runs, 4))
        domain = [str(x).strip().lower() for x in (spec.get("domain_terms") or []) if str(x).strip()]
        if not domain:
            domain = [
                w for w in re.split(r"[^a-z0-9]+", str(spec.get("product") or "").lower()) if len(w) >= 3
            ]
        seen: set[str] = set()
        union: list[str] = []
        store = None
        if key:
            corpus_dir = Path(__file__).resolve().parents[2] / "var" / "deepdive_corpus"
            corpus_dir.mkdir(parents=True, exist_ok=True)
            store = corpus_dir / f"{key}.jsonl"
            if store.exists():
                keywords_all = [k.lower() for k in (spec.get("keywords") or []) if k]
                for line in store.read_text(encoding="utf-8").splitlines():
                    text = line.strip()
                    if not text:
                        continue
                    low = text.lower()
                    if keywords_all and not any(k in low for k in keywords_all):
                        continue
                    if domain and not any(term in low for term in domain):
                        continue
                    if text[:100] not in seen:
                        seen.add(text[:100])
                        union.append(text)
        for _ in range(runs):
            for text in self._fetch_once(spec, pages):
                digest = text[:100]
                if digest in seen:
                    continue
                seen.add(digest)
                union.append(text)
        if store is not None:
            store.write_text("\n".join(union[-2000:]) + "\n", encoding="utf-8")
        return union[-2000:]

    def _fetch_once(self, spec: dict, pages: int = 8) -> list[str]:
        subs = [s.strip().lstrip("r/") for s in (spec.get("subreddits") or []) if str(s).strip()]
        if not subs:
            subs = ["AppleWatch"]
        keywords = tuple(k.lower() for k in (spec.get("keywords") or []) if k)
        domain = [str(x).strip().lower() for x in (spec.get("domain_terms") or []) if str(x).strip()]
        if not domain:
            domain = [
                w for w in re.split(r"[^a-z0-9]+", str(spec.get("product") or "").lower()) if len(w) >= 3
            ]
        texts: list[str] = []
        for sub in subs[:4]:
            collected: list[str] = []
            for attempt in range(3):
                conn = RedditArchiveConnector(
                    category="deepdive", subreddit=sub, keywords=(),
                    pages=pages if attempt == 0 else max(3, pages // 2), limit=100,
                )
                try:
                    for item in conn.fetch():
                        low = item.text.lower()
                        if keywords and not any(k in low for k in keywords):
                            continue
                        if domain and not any(term in low for term in domain):
                            continue
                        collected.append(item.text)
                except Exception as exc:  # noqa: BLE001
                    print(f"r/{sub} attempt {attempt + 1} failed: {exc}", file=sys.stderr)
                if collected:
                    break
                time.sleep(1.5)
            texts.extend(collected)
        seen, unique = set(), []
        for t in texts:
            if t[:100] in seen:
                continue
            seen.add(t[:100])
            unique.append(t)
        return unique[:240]



    def _appstore(self, spec: dict, pages: int) -> tuple[list[dict], list[str]]:
        from .connectors.appstore import AppStoreConnector, search_apps

        query = str(spec.get("app_query") or spec.get("product") or "").strip()
        if not query:
            return [], []
        try:
            apps = search_apps(query, limit=5)
        except Exception:  # noqa: BLE001
            return [], []
        tokens = [w for w in re.split(r"[^a-z0-9]+", query.lower()) if len(w) > 2]
        if tokens:
            matched_apps = [a for a in apps if any(tok in str(a.get("name", "")).lower() for tok in tokens)]
            apps = matched_apps[:1] or apps[:1]
        else:
            apps = apps[:1]
        texts: list[str] = []
        for app in apps:
            conn = AppStoreConnector(category="deepdive", app_id=str(app["app_id"]), pages=pages)
            try:
                texts.extend(item.text for item in conn.fetch())
            except Exception:  # noqa: BLE001
                continue
        return apps, texts

    def preview(self, spec: dict) -> dict:
        """Light probe: one page per subreddit, count keyword matches."""
        subs = [str(s).strip().lstrip("r/") for s in (spec.get("subreddits") or []) if str(s).strip()]
        keywords = [k.lower() for k in (spec.get("keywords") or []) if k]
        rows = []
        for sub in subs[:4]:
            conn = RedditArchiveConnector(category="deepdive", subreddit=sub, keywords=(), pages=1, limit=100)
            try:
                texts = [item.text for item in conn.fetch()]
            except Exception:  # noqa: BLE001
                texts = []
            matched = sum(1 for t in texts if not keywords or any(k in t.lower() for k in keywords))
            rows.append({"subreddit": sub, "scanned": len(texts), "matched": matched})
        app_rows = []
        if spec.get("app_store"):
            apps, app_texts = self._appstore(spec, pages=1)
            for app in apps:
                app_rows.append({"app": app["name"], "app_id": str(app["app_id"]),
                                 "rating_count": app.get("rating_count", 0)})
            rows.append({"subreddit": "AppStore", "scanned": len(app_texts), "matched": len(app_texts)})

        reddit_rows = [r for r in rows if r["subreddit"] != "AppStore"]
        total = sum(r["scanned"] for r in reddit_rows)
        matched_total = sum(r["matched"] for r in reddit_rows)
        hit_rate = round(matched_total / total, 3) if total else 0.0

        suggested: list[str] = []
        if total and hit_rate < 0.05:
            # keep single-token keywords, add generic abandonment signals
            kept = [k for k in keywords if " " not in k]
            base = ["stopped", "quit", "dust", "drawer", "barely", "rarely",
                    "regret", "sold", "unused", "gave up", "waste", "not using"]
            for item in kept + base:
                if item and item not in suggested:
                    suggested.append(item)
            suggested = suggested[:8]

        return {
            "subreddits": subs,
            "keywords": keywords,
            "rows": rows,
            "scanned": total,
            "matched": matched_total,
            "app_scanned": sum(r["scanned"] for r in rows if r["subreddit"] == "AppStore"),
            "hit_rate": hit_rate,
            "suggested_keywords": suggested,
            "app_store": app_rows,
            "advice": (
                "命中率偏低，已生成更宽的关键词建议"
                if suggested
                else ("样本量可用" if not total or hit_rate >= 0.05 else "命中率偏低")
            ),
        }

    def execute(self, spec: dict, answers: list[str] | None = None, force: bool = False) -> dict:
        cache_key = ""
        if answers:
            refined = _chat(
                self.client, self.base_url, self.api_key, self.model,
                "根据补充回答修正 spec。只返回 JSON，且必须保留原有全部字段"
                "（product/platform/system/focus/subreddits/keywords/goal）。",
                {"spec": spec, "answers": answers},
            )
            if refined:
                merged = dict(spec)
                for key in ("product", "platform", "system", "focus", "goal"):
                    value = refined.get(key)
                    if isinstance(value, str) and value.strip():
                        merged[key] = value.strip()
                for key in ("subreddits", "keywords"):
                    value = refined.get(key)
                    if isinstance(value, list) and value:
                        merged[key] = value
                spec = merged

        cache_key = _cache_key(spec, answers)
        if not force:
            cache = _load_cache()
            entry = cache.get(cache_key)
            if entry and time.time() - entry.get("created_at", 0) < CACHE_TTL_SECONDS:
                result = dict(entry["result"])
                result["cached"] = True
                return result

        texts = self._fetch(spec, key=cache_key)
        app_texts: list[str] = []
        if spec.get("app_store"):
            _, app_texts = self._appstore(spec, pages=2)
            texts = texts + app_texts
        focus = spec.get("focus", "pain")
        counts: dict = {}
        report = [f"# 专项挖掘：{spec.get('product') or '未命名'}", ""]
        report.append(
            f"> 平台：{spec.get('platform') or '—'} ｜ 系统：{spec.get('system') or '—'} ｜ "
            f"口径：{'价值衰减' if focus == 'decay' else '使用痛点'} ｜ 样本：{len(texts)} 条"
        )
        report.append("")
        if not texts:
            report.append("没有抓到匹配的样本，建议放宽关键词或换板块。")
            return {"spec": spec, "markdown": "\n".join(report), "count": 0}

        if focus == "decay":
            kept = []
            for start in range(0, len(texts), 20):
                batch = texts[start : start + 20]
                res = _chat(self.client, self.base_url, self.api_key, self.model, GATE_SYSTEM,
                            {"texts": [{"i": i, "text": t} for i, t in enumerate(batch)]})
                for it in res.get("items", []):
                    if str(it.get("is_decay")).lower() in ("true", "yes", "1"):
                        idx = int(it.get("i", -1))
                        if 0 <= idx < len(batch):
                            kept.append((start + idx, batch[idx]))
            records = []
            for start in range(0, len(kept), 20):
                batch = kept[start : start + 20]
                res = _chat(self.client, self.base_url, self.api_key, self.model, TAG_SYSTEM,
                            {"texts": [{"i": i, "text": t} for i, (_, t) in enumerate(batch)]})
                for it in res.get("records", []):
                    idx = int(it.get("i", -1))
                    if 0 <= idx < len(batch):
                        it["_text"] = batch[idx][1]
                        records.append(it)
            triggers = Counter(r.get("decay_trigger", "unclear") for r in records)
            counts = dict(triggers)
            actions = Counter(r.get("action", "unknown") for r in records)
            report += ["## 衰减触发", "", "| 触发 | 条数 | 占比 |", "|---|---|---|"]
            for k, v in triggers.most_common():
                report.append(f"| {k} | {v} | {v / max(1, len(records)) * 100:.0f}% |")
            report += ["", "## 处置动作", ""]
            for k, v in actions.most_common():
                report.append(f"- {k}：{v}")
            report += ["", "## 典型叙述", ""]
            for r in [x for x in records if x.get("quote")][:8]:
                report += [
                    f"**{r.get('job') or '—'}**",
                    "",
                    f"> {r.get('quote')}",
                    "",
                    f"- 触发：`{r.get('decay_trigger') or 'unclear'}`　处置：`{r.get('action') or 'unknown'}`　替代：{r.get('substitute') or '—'}",
                    "",
                ]
            result_count = len(records)
        else:
            records = []
            for start in range(0, len(texts), 20):
                batch = texts[start : start + 20]
                res = _chat(self.client, self.base_url, self.api_key, self.model, PAIN_SYSTEM,
                            {"texts": [{"i": i, "text": t} for i, t in enumerate(batch)]})
                for it in res.get("records", []):
                    idx = int(it.get("i", -1))
                    if 0 <= idx < len(batch):
                        it["_text"] = batch[idx][1]
                        records.append(it)
            raw_pains = sorted({str(r.get("pain") or "").strip() for r in records if r.get("pain")})
            themes = self._load_taxonomy(spec)
            theme_map = self._normalize_pains(raw_pains, themes) if raw_pains else {}
            theme_severities: dict[str, list[int]] = {}
            for r in records:
                raw = str(r.get("pain") or "").strip()
                if not raw:
                    continue
                theme = theme_map.get(raw, raw)
                theme_severities.setdefault(theme, []).append(int(r.get("severity") or 0))
            pains = Counter({k: len(v) for k, v in theme_severities.items()})
            counts = dict(pains)
            try:
                dump_rows = []
                for r in records:
                    raw = str(r.get("pain") or "").strip()
                    if not raw:
                        continue
                    dump_rows.append(
                        {
                            "pain": raw,
                            "theme": theme_map.get(raw, raw),
                            "quote": str(r.get("quote") or "")[:300],
                            "product_area": r.get("product_area") or "",
                            "severity": int(r.get("severity") or 0),
                        }
                    )
                dump_path = Path(__file__).resolve().parents[2] / "var" / "deepdive_last_records.json"
                dump_path.write_text(json.dumps(dump_rows, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
            report += ["## 主要痛点", "", "| 痛点 | 次数 | 强度均值 |", "|---|---|---|"]
            for pain, n in pains.most_common(12):
                severities = theme_severities.get(pain, [])
                avg = sum(severities) / max(1, len(severities))
                report.append(f"| {pain} | {n} | {avg:.1f} |")
            report += ["", "## 原文证据", ""]
            for r in [x for x in records if x.get("quote")][:10]:
                report.append(f"> {r.get('quote')}  \n> — {r.get('product_area') or ''} · 强度 {r.get('severity')}")
                report.append("")
            result_count = len(records)

        report += ["", "## 局限", "", "- 样本来自公开社区，存在人群偏差；", "- 分类由模型判断，需人工抽检。"]
        result = {"spec": spec, "markdown": "\n".join(report), "count": result_count, "cached": False}
        result = _with_history(cache_key, spec, counts, result)
        if cache_key:
            cache = _load_cache()
            cache[cache_key] = {"created_at": time.time(), "result": {k: v for k, v in result.items() if k != "cached"}}
            _save_cache(cache)
        return result
