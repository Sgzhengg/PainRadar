"""B-set predictions: turn a cluster into a falsifiable, time-boxed claim.

A prediction is deliberately boring:

    (cluster, T0) -> "within the next 12 months, at least one *paid* product or
    app appears that sells against these keywords"

The keywords come from the atoms' quotes, not from the Chinese scene labels, so
that GitHub / App Store search works in English.
"""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from dataclasses import dataclass

from .schema import PainAtom
from .textproc import tokenize

#: Words that appear in almost every review and therefore have no discrimination.
STOPWORDS = {
    "app", "apps", "device", "devices", "fountain", "fountains", "feeder", "feeders",
    "product", "products", "pet", "pets", "cat", "cats", "dog", "dogs", "water",
    "use", "used", "uses", "using", "really", "just", "like", "get", "gets", "got",
    "one", "two", "also", "can", "cant", "cannot", "will", "would", "work", "works",
    "working", "time", "times", "day", "days", "now", "still", "even", "much",
    "many", "make", "makes", "made", "need", "needs", "want", "wants", "buy",
    "bought", "amazon", "review", "reviews", "good", "great", "bad", "nice",
    "thing", "things", "way", "ways", "lot", "bit", "little", "better", "best",
    "after", "before", "when", "then", "than", "with", "without", "from", "have",
    "has", "had", "was", "were", "are", "been", "being", "this", "that", "these",
    "those", "there", "their", "they", "them", "its", "our", "your", "you",
    "the", "and", "for", "but", "not", "all", "any", "out", "off", "too", "very",
    "does", "did", "doing", "over", "into", "about", "again", "still", "only",
}


@dataclass
class Prediction:
    prediction_id: str
    cluster_id: str
    keywords: list[str]
    t0: str
    window_end: str
    proposition: str


def _words(quote: str) -> list[str]:
    return [
        t.lower()
        for t in tokenize(quote)
        if t.isalpha() and len(t) >= 3 and t.lower() not in STOPWORDS
    ]


def extract_keywords(atoms: list[PainAtom], k: int = 3, min_docs: int | None = None) -> list[str]:
    """Frequent bigrams ("pump noise", "wifi connect") beat single words.

    Single frequent words ("issue", "clean") match half of GitHub and produce
    meaningless hits, as the first backtest showed.
    """
    if min_docs is None:
        min_docs = 2 if len(atoms) >= 6 else 1
    counts: Counter[str] = Counter()
    for atom in atoms:
        words = _words(atom.quote)
        grams = {f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)}
        counts.update(grams)
    ranked = [g for g, c in counts.most_common(40) if c >= min_docs]
    return ranked[:k]


#: A prediction must mention something specific to the category; otherwise a
#: generic cluster ("device not working") matches every repair app on earth.
DOMAIN_TERMS = {
    "fountain", "feeder", "litter", "pump", "filter", "nozzle", "bowl", "collar",
    "camera", "sensor", "wifi", "subscription", "refill", "mold", "noise",
    "battery", "cord", "spout", "motor", "clog", "leak", "dry", "wet",
}


def is_specific(keywords: list[str], domain_terms: tuple[str, ...] | None = None) -> bool:
    terms = domain_terms or DOMAIN_TERMS
    return any(term in phrase.lower() for phrase in keywords for term in terms)


def make_prediction(
    run_id: str,
    cluster_id: str,
    atoms: list[PainAtom],
    t0: str,
    window_end: str,
    keywords: list[str] | None = None,
    require_domain: bool = True,
    domain_terms: tuple[str, ...] | None = None,
) -> Prediction | None:
    keywords = keywords or extract_keywords(atoms)
    if len(keywords) < 1:
        return None
    if require_domain and not is_specific(keywords, domain_terms):
        return None
    digest = hashlib.sha256(f"{run_id}|{cluster_id}".encode()).hexdigest()[:12]
    proposition = (
        f"在 {t0} 起 12 个月内，出现至少一个以「{' / '.join(keywords)}」为卖点的付费产品"
        f"（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。"
    )
    return Prediction(
        prediction_id=f"pred_{digest}",
        cluster_id=cluster_id,
        keywords=keywords,
        t0=t0,
        window_end=window_end,
        proposition=proposition,
    )


def random_baseline(vocabulary: list[str], k: int, rng: random.Random) -> list[str]:
    return rng.sample(vocabulary, min(k, len(vocabulary)))


def vocabulary(atoms: list[PainAtom]) -> list[str]:
    """All bigrams seen in the corpus, for a same-specificity random baseline."""
    grams: set[str] = set()
    for atom in atoms:
        words = _words(atom.quote)
        for i in range(len(words) - 1):
            grams.add(f"{words[i]} {words[i + 1]}")
    return sorted(grams)


def llm_queries(label: str, quotes: list[str], n: int = 3) -> list[str]:
    """Ask the LLM for 3 short English search phrases for a cluster.

    Bigram frequency produces phrases like "says already"; a model that sees
    the quotes can produce "quiet fountain pump" instead. Returns [] when no
    endpoint is configured, so the caller can fall back to bigrams.
    """
    import json
    import os

    from .net import HttpClient, HttpError

    base = os.environ.get("PAINRADAR_LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("PAINRADAR_LLM_API_KEY", "")
    model = os.environ.get("PAINRADAR_LLM_MODEL", "")
    if not (base and model):
        return []
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write search queries for product discovery. Given a pain cluster "
                    "and sample quotes, return JSON {\"queries\": [..]} with 3 short English "
                    "queries of 2-4 words each, as a user would search GitHub or an app store. "
                    "Avoid generic words like app, device, product. No explanations."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"cluster": label, "quotes": quotes[:5]}, ensure_ascii=False),
            },
        ],
    }
    client = HttpClient(user_agent="PainRadar/0.1", timeout=45, max_retries=1, rate_per_sec=2)
    try:
        body = client.post_json(
            f"{base}/chat/completions", payload,
            headers={"Authorization": f"Bearer {key}"} if key else {},
        )
        content = body["choices"][0]["message"]["content"]  # type: ignore[index]
        data = json.loads(content[content.find("{"): content.rfind("}") + 1])
        queries = [str(q).strip() for q in data.get("queries", []) if str(q).strip()]
        return queries[:n]
    except (HttpError, OSError, KeyError, ValueError, TypeError):
        return []
