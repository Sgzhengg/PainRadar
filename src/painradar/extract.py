"""Extraction: the span gate and the rule-based pain-atom extractor.

Two extractors share one contract:

* :class:`RuleExtractor` — deterministic, offline, no API key. It is the
  baseline used by the demo and by the tests, and the fallback when no LLM is
  configured.
* :class:`LLMExtractor` — calls an OpenAI-compatible endpoint when
  ``PAINRADAR_LLM_BASE_URL`` / ``PAINRADAR_LLM_API_KEY`` / ``PAINRADAR_LLM_MODEL``
  are set. It is wired but *not* enabled by default.

Both must pass every atom through :class:`SpanGate`. An atom whose quote cannot
be located verbatim in the scrubbed text is dropped — never repaired.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Iterable

from .lexicon import PAIN_TERMS
from .levels import LevelInput, level_from_workaround_type, resolve_level
from .taxonomy import classify_scene
from .config import MODEL_VERSION, PROMPT_VERSION, TAXONOMY_VERSION, CategorySpec
from .net import HttpClient, HttpError
from .schema import PainAtom, RawItem
from .textproc import (
    detect_lang,
    hours_amounts,
    mask_pii,
    money_amounts,
    normalize_with_map,
    split_sentences_with_offsets,
)

# ---------------------------------------------------------------------------
# Span gate


def _locate(quote: str, text: str) -> tuple[int, int, str] | None:
    """Return (start, end, match_score) for a verbatim quote, or None.

    Order: exact -> NFKC/whitespace-normalised -> case-insensitive -> fuzzy
    (Levenshtein-style ratio >= 0.90). The caller re-slices the text so the
    stored quote is always a true substring.
    """
    q = quote.strip()
    if len(q) < 8:
        return None

    pos = text.find(q)
    if pos >= 0:
        return pos, pos + len(q), "exact"

    ntext, imap = normalize_with_map(text)
    nq = normalize_with_map(q)[0].strip()
    pos = ntext.find(nq)
    if pos >= 0:
        return imap[pos], imap[pos + len(nq) - 1] + 1, "normalized"

    low_text, low_q = ntext.lower(), nq.lower()
    pos = low_text.find(low_q)
    if pos >= 0:
        return imap[pos], imap[pos + len(low_q) - 1] + 1, "normalized"

    # Fuzzy: anchor on the first token, then compare fixed-size windows.
    if len(q) >= 20:
        anchor = nq[:6].lower()
        best: tuple[float, int, int] | None = None
        scanned = 0
        start = 0
        width = len(nq)
        while scanned < 200:
            i = low_text.find(anchor, start)
            if i < 0:
                break
            for delta in (-8, -4, 0, 4, 8):
                s = max(0, i + delta)
                e = min(len(ntext), s + width + (8 if delta else 0))
                window = ntext[s:e]
                ratio = difflib.SequenceMatcher(None, window.lower(), low_q).ratio()
                if ratio >= 0.90 and (best is None or ratio > best[0]):
                    best = (ratio, s, e)
            start = i + 1
            scanned += 1
        if best:
            _, s, e = best
            return imap[s], imap[e - 1] + 1, "fuzzy"
    return None


class SpanGate:
    """Locate and validate quotes against the scrubbed source text."""

    def locate(self, quote: str, text: str) -> tuple[int, int, str] | None:
        return _locate(quote, text)


# ---------------------------------------------------------------------------
# Rule extractor signals

_PAIN = PAIN_TERMS
_WORKAROUND = [
    "i use", "i just", "i had to", "switched to", "ended up", "resorted",
    "taped", "zip tie", "wedge", "bypass", "workaround", "diy", "manually",
    "with a towel", "piece of foam", "extension cord", "foil", "backup",
    "只能", "只好", "改用", "拿", "凑合", "自己", "手动", "临时", "用胶带",
    "垫", "绑", "粘", "堆在", "塞在", "放在", "搬到", "换成", "买了",
]
_TRIGGER = [
    "when ", "whenever", "every time", "at night", "in the rain", "in wind",
    "每次", "一到", "只要", "半夜", "晚上", "换季", "下雨", "做饭",
]
_WTP = [
    "would pay", "i'd pay", "worth paying", "worth every", "shut up and take",
    "take my money", "愿意付", "愿意花钱", "花钱也", "多少钱", "贵点也行",
]
_ASK = ["any recommendations", "recommend", "looking for", "suggestions", "求推荐", "有没有", "求", "推荐"]
_BUY = ["i bought", "i paid", "purchased", "already paid", "买了", "下单", "付了"]
_INTENS = ["really", "so ", "extremely", "super", "completely", "totally", "太", "特别", "非常", "完全", "简直"]
_HOPE = ["i wish", "hope", "would be great", "希望", "要是", "如果能"]


def _find_any(text: str, needles: Iterable[str]) -> str | None:
    low = text.lower()
    for n in needles:
        if n in low:
            return n
    return None


_LEAD = (
    "and ", "but ", "so ", "then ", "which ", "that ", "because ", "where ",
    "结果", "但是", "不过", "所以", "然后", "而且", "而且", "但",
)


def _clean(fragment: str) -> str:
    s = fragment.strip(" ,.，。;；:：!！?？")
    low = s.lower()
    for lead in _LEAD:
        if low.startswith(lead):
            s = s[len(lead):]
            break
    return s.strip(" ,.，。;；:：").strip()


def _clause(sentence: str, pos: int, before: int = 60, after: int = 110) -> str:
    """Expand around ``pos`` to the nearest clause boundary."""
    start = max(0, pos - before)
    end = min(len(sentence), pos + after)
    left = max(sentence.rfind("，", 0, pos), sentence.rfind(",", 0, pos), sentence.rfind(";", 0, pos))
    if left > start:
        start = left + 1
    right_candidates = [i for i in (sentence.find("，", pos), sentence.find(",", pos), sentence.find("。", pos)) if i > 0]
    if right_candidates and min(right_candidates) < end:
        end = min(right_candidates)
    return _clean(sentence[start:end])


def _sentence_features(sentence: str) -> dict[str, bool]:
    low = sentence.lower()
    return {
        "pain": any(m in low for m in _PAIN),
        "work": any(m in low for m in _WORKAROUND),
        "cost": bool(money_amounts(sentence) or hours_amounts(sentence)),
        "wtp": any(m in low for m in _WTP),
        "trigger": any(m in low for m in _TRIGGER),
        "ask": any(m in low for m in _ASK),
    }


def _score_sentence(sentence: str) -> int:
    f = _sentence_features(sentence)
    score = 3 * f["pain"] + 3 * f["work"] + 2 * f["cost"] + 3 * f["wtp"] + f["trigger"] + f["ask"]
    if f["pain"] and f["work"]:
        score += 3  # the sentence we most want: obstacle + workaround
    return int(score)


@dataclass
class ExtractionStats:
    seen: int = 0
    extracted: int = 0
    dropped_l0: int = 0
    dropped_no_span: int = 0
    dropped_short: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "seen": self.seen,
            "extracted": self.extracted,
            "dropped_l0": self.dropped_l0,
            "dropped_no_span": self.dropped_no_span,
            "dropped_short": self.dropped_short,
        }


class RuleExtractor:
    """Deterministic baseline extractor (no network, no API key)."""

    version = MODEL_VERSION

    def __init__(self, category: CategorySpec, gate: SpanGate | None = None):
        self.category = category
        self.gate = gate or SpanGate()
        self.stats = ExtractionStats()

    # -- public ------------------------------------------------------------
    def extract(self, item: RawItem, text_masked: str, comment_uid: str, run_id: str) -> PainAtom | None:
        self.stats.seen += 1
        sentences = split_sentences_with_offsets(text_masked)
        if not sentences:
            self.stats.dropped_short += 1
            return None

        scored = []
        for s, e, sentence in sentences:
            f = _sentence_features(sentence)
            scored.append((_score_sentence(sentence), f, s, e, sentence))

        best = max(scored, key=lambda row: row[0])
        if best[0] <= 0:
            hopeful = next((row for row in scored if _find_any(row[4], _HOPE)), None)
            if not hopeful:
                self.stats.dropped_l0 += 1
                return None
            best = hopeful

        # Prefer a span that covers both the obstacle sentence and the
        # workaround sentence, so the evidence supports the whole atom.
        pain_rows = [row for row in scored if row[1]["pain"]]
        work_rows = [row for row in scored if row[1]["work"]]
        pain_hint, work_hint = "", ""
        if pain_rows and work_rows:
            p = max(pain_rows, key=lambda row: row[0])
            w = max(work_rows, key=lambda row: row[0])
            start, end = min(p[2], w[2]), max(p[3], w[3])
            if end - start <= 320:
                best = (p[0] + w[0], p[1], start, end, text_masked[start:end])
                pain_hint, work_hint = p[4], w[4]
        if not pain_hint and pain_rows:
            pain_hint = max(pain_rows, key=lambda row: row[0])[4]

        _, _, start, end, quote = best
        located = self.gate.locate(quote, text_masked)
        if not located:
            self.stats.dropped_no_span += 1
            return None
        start, end, match = located
        quote = text_masked[start:end]

        atom = self._build(
            item, comment_uid, run_id, quote, start, end, match, text_masked,
            pain_hint=pain_hint, work_hint=work_hint,
        )
        if atom is None:
            self.stats.dropped_l0 += 1
            return None
        self.stats.extracted += 1
        return atom

    # -- internals ---------------------------------------------------------
    def _build(
        self,
        item: RawItem,
        comment_uid: str,
        run_id: str,
        quote: str,
        start: int,
        end: int,
        match: str,
        full_text: str,
        pain_hint: str = "",
        work_hint: str = "",
    ) -> PainAtom | None:
        low = quote.lower()

        workaround = _clean(work_hint)[:140] if work_hint else ""
        if not workaround:
            for m in _WORKAROUND:
                if m in low:
                    workaround = _clause(quote, low.index(m))
                    break

        obstacle = _clean(pain_hint)[:160] if pain_hint else ""
        if not obstacle:
            for m in _PAIN:
                if m in low:
                    obstacle = _clause(quote, low.index(m))
                    break
        if not obstacle:
            for m in (" but ", " so ", " because ", "但是", "不过", "所以", "结果"):
                if m in low:
                    obstacle = _clause(quote, low.index(m) + len(m), before=0, after=80)
                    break
        if len(obstacle) < 12:
            obstacle = _clean(quote[:140])

        trigger = ""
        for m in _TRIGGER:
            if m in low:
                trigger = _clause(quote, low.index(m), before=30, after=80)
                break

        cost_type, cost_estimate = "", ""
        money = money_amounts(quote)
        hours = hours_amounts(quote)
        if money:
            cost_type, cost_estimate = "money", f"{money[0]:g}"
        elif hours:
            cost_type, cost_estimate = "time", f"{hours[0]:g}h"

        wtp_level, wtp_quote = "none", ""
        for m in _WTP:
            if m in low:
                wtp_level, wtp_quote = "strong", _clause(quote, low.index(m))
                break
        if wtp_level == "none" and _find_any(quote, _ASK):
            wtp_level = "weak"

        declared = ""
        if _find_any(quote, _BUY):
            declared = "L4"
        elif wtp_level == "strong" or (cost_type and _find_any(quote, _ASK)):
            declared = "L3"

        level = resolve_level(
            LevelInput(
                obstacle=obstacle,
                workaround=workaround,
                cost_type=cost_type,
                cost_estimate=cost_estimate,
                declared=declared,
                text=quote,
            )
        )

        if level == "L0":
            return None

        scene = classify_scene(full_text, self.category) if full_text else "其他场景"
        if scene == "其他场景":
            scene = classify_scene(quote, self.category)
        persona = (
            self._match(self.category.personas, quote)
            or self._match(self.category.personas, full_text)
            or ""
        )
        job = self._job(scene)
        intensity = self._intensity(quote)

        if _find_any(quote, _ASK):
            expression = "help_seek"
        elif _find_any(quote, ["recommend", "求推荐", "推荐"]):
            expression = "recommendation_request"
        elif _find_any(quote, ["switched to", "改用", "换成"]):
            expression = "escape"
        else:
            expression = "complaint"

        filled = sum(
            1
            for v in (scene, trigger, job, obstacle, workaround, cost_type, persona, wtp_quote)
            if v
        )
        confidence = min(0.95, 0.43 + 0.06 * filled)
        if len(quote) < 40:
            confidence = max(0.3, confidence - 0.08)

        atom_id = hashlib.sha256(
            f"{comment_uid}|{start}|{end}|{self.version}".encode("utf-8")
        ).hexdigest()[:16]

        return PainAtom(
            atom_id=f"pa_{atom_id}",
            comment_uid=comment_uid,
            quote=quote,
            span_start=start,
            span_end=end,
            match_score=match,
            scene=scene,
            trigger=trigger,
            job=job,
            obstacle=obstacle,
            workaround=workaround,
            cost_type=cost_type,
            cost_estimate=cost_estimate,
            persona=persona,
            intensity=intensity,
            expression=expression,
            level=level,
            wtp_level=wtp_level,
            wtp_quote=wtp_quote,
            domain="/".join(self.category.domain_path),
            confidence=round(confidence, 3),
            model_version=self.version,
            prompt_version=PROMPT_VERSION,
            taxonomy_version=TAXONOMY_VERSION,
            run_id=run_id,
        )

    def _match(self, mapping: dict[str, tuple[str, ...]], text: str) -> str:
        low = text.lower()
        for label, needles in mapping.items():
            for n in needles:
                needle = n.lower()
                if re.search(r"[a-z]", needle):
                    if re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", low):
                        return label
                elif needle in low:
                    return label
        return ""

    def _job(self, scene: str) -> str:
        if detect_lang(scene) == "zh":
            return f"{scene}时不被打断" if scene else "完成当前任务"
        return f"handle {scene} without friction" if scene else "complete the task at hand"

    @staticmethod
    def _intensity(quote: str) -> int:
        low = quote.lower()
        score = 2
        score += sum(1 for m in _INTENS if m in low)
        if "!" in quote or "！" in quote:
            score += 1
        if _find_any(quote, ["崩溃", "hate", "furious", "ridiculous", "受不了"]):
            score += 1
        return max(1, min(5, score))


# ---------------------------------------------------------------------------
# LLM extractor (optional)


SYSTEM_PROMPT = """You are a strict information extractor. You receive ONE review and
return ONE JSON object with the fields below. Rules:
- quote MUST be an exact substring of the input text (copy it verbatim, no edits).
- If a field is not supported by the text, return an empty string. Never invent.
- scene MUST be exactly one of the provided `scenes`, or "其他场景" when none fits.
  Do not invent new scene names.
- Write `scene`, `obstacle`, `job`, `persona`, `workaround` in Simplified Chinese,
  even when the review is in English. Keep `quote` and `wtp_quote` verbatim.
- level: L0 pure emotion, L1 complaint only, L2 obstacle + workaround,
  L3 priced/compared/tried a *solution* to this pain, L4 already paid for a
  *solution* to this pain. Having bought the reviewed product does NOT by
  itself make the comment L4.
- cost_type: only "money" or "time" when the quote explicitly contains an amount
  or a duration. Never infer emotion or risk as a cost. If no explicit amount or
  duration, return "" and an empty cost_estimate.
- workaround_type: MUST be one of none / substitute / self_rescue / escalation.
  substitute = the user switched to another product or method; self_rescue = the
  user reset, cleaned, taped, moved or manually worked around it; escalation =
  the only action was contacting support / asking for a refund / leaving a
  review. Contacting support alone is NOT a workaround.
- level is derived from workaround_type: L2 only for substitute/self_rescue,
  L1 for none/escalation; keep L3/L4 when the text shows pricing or payment.
- Return JSON only, no markdown fences."""

FIELD_SPEC = {
    "quote": "string, verbatim substring",
    "scene": "short noun phrase",
    "trigger": "short phrase or empty",
    "job": "what the person is trying to achieve",
    "obstacle": "what blocks them",
    "workaround": "current substitute or empty",
    "workaround_type": "none|substitute|self_rescue|escalation",
    "cost_type": "money|time|emotion|risk|''",
    "cost_estimate": "string or empty",
    "persona": "who they are or empty",
    "intensity": "1-5 integer",
    "expression": "complaint|help_seek|recommendation_request|comparison|escape",
    "level": "L0|L1|L2|L3|L4",
    "wtp_level": "none|weak|strong",
    "wtp_quote": "verbatim substring or empty",
    "confidence": "0-1 float",
}


class LLMNotConfigured(RuntimeError):
    """Raised when no endpoint is configured and no HTTP client was injected."""


_LEVELS = {"L0", "L1", "L2", "L3", "L4"}
_EXPRESSIONS = {"complaint", "help_seek", "recommendation_request", "comparison", "escape"}
_WTP_LEVELS = {"none", "weak", "strong"}
_COST_TYPES = {"money", "time", "emotion", "risk", ""}


def _parse_json_object(content: str) -> dict | None:
    """Accept raw JSON, fenced JSON, or JSON embedded in prose."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _as_str(value: object, limit: int = 400) -> str:
    return str(value or "").strip()[:limit]


def _infer_level(data: dict) -> str:
    if _as_str(data.get("wtp_level")) == "strong":
        return "L4"
    if _as_str(data.get("cost_type")):
        return "L3"
    if _as_str(data.get("workaround")):
        return "L2"
    if _as_str(data.get("obstacle")):
        return "L1"
    return "L0"


_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]{2}")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class LLMExtractor:
    """OpenAI-compatible extractor with span gating and a dual-pass consistency check.

    A single call is never trusted on its own:

    1. ``quote`` must be locatable in the scrubbed text (same gate as rules);
    2. a second pass at a higher temperature must agree on level / scene /
       wtp / obstacle, otherwise the result is downgraded or handed to the
       rule extractor;
    3. any failure falls back to :class:`RuleExtractor` rather than inventing.
    """

    version = "extract-llm-v0.2"

    def __init__(
        self,
        category: CategorySpec,
        gate: SpanGate | None = None,
        client: HttpClient | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        consistency: bool = True,
        fallback: "RuleExtractor | None" = None,
    ):
        self.category = category
        self.gate = gate or SpanGate()
        self.base_url = (base_url or os.environ.get("PAINRADAR_LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("PAINRADAR_LLM_API_KEY", "")
        self.model = model or os.environ.get("PAINRADAR_LLM_MODEL", "")
        self.temperature = temperature
        self.consistency = consistency
        self.fallback = fallback
        if client is not None:
            self.client = client
        else:
            if not (self.base_url and self.model):
                raise LLMNotConfigured(
                    "set PAINRADAR_LLM_BASE_URL and PAINRADAR_LLM_MODEL "
                    "(PAINRADAR_LLM_API_KEY is optional for local endpoints), "
                    "or pass --llm-base-url/--llm-model"
                )
            self.client = HttpClient(
                user_agent="PainRadar/0.1", timeout=60, max_retries=2, rate_per_sec=4
            )
        self.stats = LLMStats()

    # -- API ---------------------------------------------------------------
    def _chat(self, text: str, temperature: float) -> dict | None:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "category": self.category.name_en,
                            "scenes": list(self.category.scenes.keys()),
                            "text": text,
                            "fields": FIELD_SPEC,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        try:
            body = self.client.post_json(
                f"{self.base_url}/chat/completions" if self.base_url else "http://llm.local/chat/completions",
                payload,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
        except HttpError as exc:
            self.stats.errors[f"http_{exc.status}"] = self.stats.errors.get(f"http_{exc.status}", 0) + 1
            return None
        except (OSError, ValueError) as exc:
            name = type(exc).__name__
            self.stats.errors[name] = self.stats.errors.get(name, 0) + 1
            return None
        self.stats.calls += 1
        if isinstance(body, dict):
            usage = body.get("usage") or {}
            try:
                self.stats.tokens_in += int(usage.get("prompt_tokens", 0) or 0)
                self.stats.tokens_out += int(usage.get("completion_tokens", 0) or 0)
            except (TypeError, ValueError):
                pass
        try:
            content = body["choices"][0]["message"]["content"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return None
        return _parse_json_object(str(content))

    # -- extraction --------------------------------------------------------
    def extract(self, item: RawItem, text_masked: str, comment_uid: str, run_id: str) -> PainAtom | None:
        self.stats.seen += 1
        first = self._chat(text_masked, self.temperature)
        if not first:
            return self._fallback(item, text_masked, comment_uid, run_id, "no_json")

        located = self._locate_quote(first, text_masked)
        if not located:
            return self._fallback(item, text_masked, comment_uid, run_id, "no_span")

        agree = "agree"
        if self.consistency:
            second = self._chat(text_masked, min(1.0, self.temperature + 0.3))
            agree = self._agreement(first, second) if second else "disagree"
            if agree == "disagree":
                self.stats.disagree += 1
            elif agree == "soft":
                self.stats.soft_disagree += 1

        if agree == "disagree" and self.fallback is not None:
            return self._fallback(item, text_masked, comment_uid, run_id, "disagree")

        start, end, match, quote = located
        atom = self._build(first, item, comment_uid, run_id, quote, start, end, match, agree)
        if atom.level == "L0":
            # L0 is "pure emotion, no obstacle": the ladder says drop it, not
            # persist it as a low-value card.
            self.stats.dropped_l0 += 1
            return None
        self.stats.extracted += 1
        return atom

    def _locate_quote(self, data: dict, text: str) -> tuple[int, int, str, str] | None:
        min_len = 12 if detect_lang(text) == "zh" else 20
        for key in ("quote", "obstacle", "wtp_quote"):
            candidate = _as_str(data.get(key))
            if len(candidate) < min_len:
                continue
            located = self.gate.locate(candidate, text)
            if located:
                start, end, match = located
                if end - start < min_len:
                    continue
                return start, end, match, text[start:end]
        return None

    def _normalise_scene(self, value: object, text: str) -> str:
        scene = _as_str(value)
        if scene in self.category.scenes:
            return scene
        if scene in ("", "其他场景"):
            return classify_scene(text, self.category)
        return classify_scene(f"{scene} {text}", self.category)

    def _agreement(self, a: dict, b: dict) -> str:
        """agree / soft (same structure, different wording) / disagree."""
        if _as_str(a.get("level")) != _as_str(b.get("level")):
            return "disagree"
        if self._normalise_scene(a.get("scene"), "") != self._normalise_scene(b.get("scene"), ""):
            return "disagree"
        oa, ob = _as_str(a.get("obstacle")), _as_str(b.get("obstacle"))
        if not oa or not ob:
            return "agree" if oa == ob else "disagree"
        return "agree" if _overlap(oa, ob) >= 0.35 else "soft"

    def _build(
        self,
        data: dict,
        item: RawItem,
        comment_uid: str,
        run_id: str,
        quote: str,
        start: int,
        end: int,
        match: str,
        agree: str,
    ) -> PainAtom:
        declared = _as_str(data.get("level")).upper()
        if declared not in _LEVELS:
            declared = _infer_level(data)
        obstacle = _as_str(data.get("obstacle"))
        workaround = _as_str(data.get("workaround"))
        wtype = _as_str(data.get("workaround_type")).lower()
        if wtype not in ("none", "substitute", "self_rescue", "escalation"):
            wtype = ""
        if wtype:
            level = level_from_workaround_type(wtype, declared, bool(obstacle))
        else:
            level = resolve_level(
                LevelInput(obstacle=obstacle, workaround=workaround, declared=declared, text=quote)
            )
        wtp_level = _as_str(data.get("wtp_level")).lower()
        if wtp_level not in _WTP_LEVELS:
            wtp_level = "none"
        expression = _as_str(data.get("expression")).lower()
        if expression not in _EXPRESSIONS:
            expression = "complaint"
        cost_type = _as_str(data.get("cost_type")).lower()
        if cost_type not in _COST_TYPES:
            cost_type = ""
        cost_estimate = _as_str(data.get("cost_estimate"), 80)
        # A cost claim must be backed by an explicit amount/duration in the quote;
        # otherwise it is an inference, and inferences do not belong in a factor
        # called "cost clarity".
        if cost_type in ("money", "time") and not (money_amounts(quote) or hours_amounts(quote)):
            cost_type, cost_estimate = "", ""
        try:
            intensity = int(data.get("intensity", 0) or 0)
        except (TypeError, ValueError):
            intensity = 0
        intensity = max(1, min(5, intensity))
        try:
            confidence = float(data.get("confidence", 0.6) or 0.6)
        except (TypeError, ValueError):
            confidence = 0.6
        confidence = max(0.05, min(0.99, confidence))
        if agree == "soft":
            confidence = round(confidence * 0.8, 3)
        elif agree == "disagree":
            confidence = round(confidence * 0.6, 3)

        atom_id = hashlib.sha256(
            f"{comment_uid}|{start}|{end}|{self.version}".encode("utf-8")
        ).hexdigest()[:16]
        return PainAtom(
            atom_id=f"pa_{atom_id}",
            comment_uid=comment_uid,
            quote=quote,
            span_start=start,
            span_end=end,
            match_score=match,
            scene=self._normalise_scene(data.get("scene"), quote),
            trigger=_as_str(data.get("trigger")),
            job=_as_str(data.get("job")),
            obstacle=obstacle,
            workaround=workaround,
            cost_type=cost_type,
            cost_estimate=cost_estimate,
            persona=_as_str(data.get("persona")),
            intensity=intensity,
            expression=expression,
            level=level,
            wtp_level=wtp_level,
            wtp_quote=_as_str(data.get("wtp_quote")),
            domain="/".join(self.category.domain_path),
            confidence=confidence,
            model_version=f"{self.version}|{agree}",
            prompt_version="p02",
            taxonomy_version=TAXONOMY_VERSION,
            run_id=run_id,
        )

    def _fallback(
        self, item: RawItem, text: str, comment_uid: str, run_id: str, reason: str
    ) -> PainAtom | None:
        self.stats.fallback += 1
        self.stats.reasons[reason] = self.stats.reasons.get(reason, 0) + 1
        if self.fallback is None:
            self.stats.dropped += 1
            return None
        atom = self.fallback.extract(item, text, comment_uid, run_id)
        if atom is not None:
            atom.model_version = f"{self.version}|fallback-{reason}"
            atom.confidence = round(atom.confidence * 0.8, 3)
        return atom


class LLMStats:
    def __init__(self) -> None:
        self.seen = 0
        self.extracted = 0
        self.fallback = 0
        self.disagree = 0
        self.soft_disagree = 0
        self.dropped = 0
        self.dropped_l0 = 0
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.reasons: dict[str, int] = {}
        self.errors: dict[str, int] = {}

    def as_dict(self) -> dict[str, object]:
        return {
            "seen": self.seen,
            "extracted": self.extracted,
            "fallback": self.fallback,
            "disagree": self.disagree,
            "soft_disagree": self.soft_disagree,
            "dropped": self.dropped,
            "dropped_l0": self.dropped_l0,
            "calls": self.calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "reasons": dict(self.reasons),
            "errors": dict(self.errors),
        }


def build_extractor(
    name: str,
    category: CategorySpec,
    llm_model: str | None = None,
    llm_base_url: str | None = None,
    llm_consistency: bool = True,
):
    if name == "rule":
        return RuleExtractor(category)
    if name == "llm":
        return LLMExtractor(
            category,
            model=llm_model,
            base_url=llm_base_url,
            consistency=llm_consistency,
            fallback=RuleExtractor(category),
        )
    raise SystemExit(f"unknown extractor {name!r}; use 'rule' or 'llm'")


def prepare_text(raw: str) -> tuple[str, str]:
    """Return (masked text, sha of the original)."""
    return mask_pii(raw), hashlib.sha256(raw.encode("utf-8")).hexdigest()
