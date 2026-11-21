"""Text utilities: normalisation, PII scrubbing, language ID, shingling, TF-IDF.

No third-party dependencies. Everything here is deterministic so that the same
input always produces the same ledger rows and the same report.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import re
import unicodedata
from collections import Counter
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# Normalisation


_CHAR_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u00a0": " ", "\u3000": " ",
}


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """NFKC-normalise and collapse whitespace, keeping a map back to ``text``.

    Curly quotes/dashes are folded first so that model output ("it’s") matches
    human text ("it's") without weakening the anchor check.
    """
    out: list[str] = []
    idx_map: list[int] = []
    prev_space = False
    for i, ch in enumerate(text):
        ch = _CHAR_MAP.get(ch, ch)
        for c in unicodedata.normalize("NFKC", ch):
            if c.isspace():
                if prev_space:
                    continue
                out.append(" ")
                idx_map.append(i)
                prev_space = True
            else:
                out.append(c)
                idx_map.append(i)
                prev_space = False
    return "".join(out), idx_map


def normalize_text(text: str) -> str:
    return normalize_with_map(text)[0].strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def author_key(salt: str, platform: str, author: str) -> str:
    """Stable, irreversible pseudonym. Never store the raw author string."""
    msg = f"{platform}\x1f{author}".encode("utf-8")
    return "hmac:" + hmac.new(salt.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


# ---------------------------------------------------------------------------
# PII scrubbing

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("URL", re.compile(r"https?://[^\s)>\]]+", re.I)),
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("WECHAT", re.compile(r"(?:微信|wechat|weixin|vx|wx)\s*[:：]?\s*[A-Za-z0-9_\-]{4,}", re.I)),
    ("HANDLE", re.compile(r"(?<![\w.])@[A-Za-z0-9_]{2,30}")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")),
    ("PHONE", re.compile(r"(?<!\d)\+?\d[\d\s\-()]{7,}\d(?!\d)")),
    ("ID", re.compile(r"(?<!\d)\d{6,}(?!\d)")),
    ("ADDR", re.compile(r"[\u4e00-\u9fa5]{2,}(?:省|市|区|县|镇|路|街|号|栋|室)")),
]


def mask_pii(text: str) -> str:
    """Replace direct identifiers with typed tokens.

    Deliberately aggressive: a missed identifier is a compliance incident, a
    false positive is a slightly less readable quote.
    """
    out = text
    for label, pattern in _PATTERNS:
        out = pattern.sub(f"[{label}]", out)
    return out


# ---------------------------------------------------------------------------
# Language identification

_CJK = re.compile(r"[\u4e00-\u9fff]")


def detect_lang(text: str) -> str:
    cjk = len(_CJK.findall(text))
    letters = sum(1 for c in text if c.isalpha())
    if letters == 0:
        return "unknown"
    return "zh" if cjk / letters > 0.25 else "en"


# ---------------------------------------------------------------------------
# Sentences

_SENT_SPLIT = re.compile(r"(?<=[.!?。！？；;])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    return [s for _, _, s in split_sentences_with_offsets(text)]


def split_sentences_with_offsets(text: str) -> list[tuple[int, int, str]]:
    """Split into sentences and keep their character offsets in ``text``."""
    out: list[tuple[int, int, str]] = []
    start = 0
    for m in re.finditer(r"[.!?。！？；;]+|\n+", text):
        end = m.end()
        seg = text[start:end]
        stripped = seg.strip()
        if len(stripped) >= 8:
            s = start + (len(seg) - len(seg.lstrip()))
            e = start + len(seg.rstrip())
            out.append((s, e, text[s:e]))
        start = end
    if start < len(text):
        seg = text[start:]
        if len(seg.strip()) >= 8:
            out.append((start, len(text), seg.strip()))
    return out


# ---------------------------------------------------------------------------
# Shingling / MinHash

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "have", "has", "had", "but",
    "you", "your", "are", "was", "were", "not", "can", "cant", "will", "would",
    "just", "really", "very", "too", "its", "it's", "they", "them", "their",
    "from", "about", "into", "when", "what", "which", "been", "being", "than",
}


def tokenize(text: str) -> list[str]:
    """Word tokens for English, character bigrams for Chinese."""
    cjk = len(_CJK.findall(text))
    if cjk and cjk / max(1, len(text)) > 0.2:
        cleaned = re.sub(r"[\s\W_]+", "", text)
        return [cleaned[i : i + 2] for i in range(len(cleaned) - 1)]
    words = re.findall(r"[a-z0-9']+", text.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


def shingles(tokens: Sequence[str], k: int = 3) -> set[str]:
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


_NUM_HASHES = 64


def _h(seed: int, value: str) -> int:
    data = f"{seed}:{value}".encode("utf-8")
    return int.from_bytes(hashlib.blake2b(data, digest_size=4).digest(), "big")


def minhash(tokens: Sequence[str], num_hashes: int = _NUM_HASHES) -> list[int]:
    sh = shingles(tokens)
    if not sh:
        return [0] * num_hashes
    sig = []
    for seed in range(num_hashes):
        sig.append(min(_h(seed, s) for s in sh))
    return sig


def jaccard_estimate(a: Sequence[int], b: Sequence[int]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    same = sum(1 for x, y in zip(a, b) if x == y)
    return same / len(a)


# ---------------------------------------------------------------------------
# TF-IDF


def tfidf_vectors(docs: Sequence[Sequence[str]]) -> list[dict[str, float]]:
    n = len(docs)
    df: Counter[str] = Counter()
    for doc in docs:
        df.update(set(doc))
    idf = {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}
    vectors: list[dict[str, float]] = []
    for doc in docs:
        tf = Counter(doc)
        length = max(1, len(doc))
        vec = {term: (count / length) * idf[term] for term, count in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append({k: v / norm for k, v in vec.items()})
    return vectors


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


# ---------------------------------------------------------------------------
# Misc


def money_amounts(text: str) -> list[float]:
    """Best-effort monetary values, used for cost signals only."""
    values: list[float] = []
    for m in re.finditer(r"[$￥¥]\s?(\d+(?:\.\d+)?)", text):
        values.append(float(m.group(1)))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s?(?:dollars?|usd|元|块|美元)", text, re.I):
        values.append(float(m.group(1)))
    return values


def hours_amounts(text: str) -> list[float]:
    values: list[float] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s?(?:hours?|hrs?|分钟|小时)", text, re.I):
        raw = float(m.group(1))
        values.append(raw / 60.0 if "分钟" in m.group(0) else raw)
    return values


def unique_preserving_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
