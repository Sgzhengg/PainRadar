"""Outcome collectors for the B set.

Two public, key-free sources:

* GitHub repository search — new repos inside the window.
* iTunes search — apps released inside the window.

Evidence passes two stages: a cheap lexical prefilter (shared core terms), then
an optional semantic adjudicator that asks whether the product actually solves
the pain. Without the adjudicator the strict lexical rule is used, and the
report says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from .net import HttpClient, HttpError

GITHUB_SEARCH = "https://api.github.com/search/repositories"
ITUNES_SEARCH = "https://itunes.apple.com/search"

#: Words too generic to evidence a match on their own.
GENERIC = {
    "app", "apps", "device", "devices", "fix", "issue", "issues", "problem",
    "problems", "error", "errors", "not", "working", "work", "broken", "update",
    "updates", "help", "support", "best", "good", "new",
}


@dataclass
class Outcome:
    source: str
    query: str
    hit: bool
    evidence: list[dict]
    error: str = ""
    scanned: int = 0
    rejected: int = 0
    adjudicated: bool = False


def _core_terms(keywords: list[str]) -> set[str]:
    terms: set[str] = set()
    for phrase in keywords:
        for w in phrase.lower().replace("-", " ").split():
            if len(w) >= 3 and w not in GENERIC:
                terms.add(w)
    return terms


def _loose(text: str, keywords: list[str], core: set[str]) -> bool:
    low = text.lower()
    if any(k.lower() in low for k in keywords):
        return True
    return any(w in low for w in core)


def _strict(text: str, keywords: list[str], core: set[str]) -> bool:
    low = text.lower()
    if any(k.lower() in low for k in keywords):
        return True
    return len([w for w in core if w in low]) >= 2


def _client() -> HttpClient:
    return HttpClient(
        user_agent="PainRadar/0.1 (research)",
        timeout=25,
        max_retries=2,
        rate_per_sec=0.7,
    )


def github_candidates(
    keywords: list[str],
    t0: str,
    t1: str,
    client: HttpClient | None = None,
    min_stars: int = 5,
    limit: int = 15,
) -> tuple[list[dict], str, str]:
    client = client or _client()
    query = f"{' '.join(keywords)} created:{t0}..{t1}"
    try:
        data = client.get_json(
            GITHUB_SEARCH,
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 30},
            headers={"Accept": "application/vnd.github+json"},
        )
    except (HttpError, OSError) as exc:
        return [], query, str(exc)
    core = _core_terms(keywords)
    items = data.get("items", []) if isinstance(data, dict) else []
    out = []
    for item in items:
        text = f"{item.get('name', '')} {item.get('description') or ''}"
        if item.get("stargazers_count", 0) < min_stars:
            continue
        if not _loose(text, keywords, core):
            continue
        out.append(
            {
                "name": item.get("full_name"),
                "description": item.get("description") or "",
                "url": item.get("html_url"),
                "stars": item.get("stargazers_count"),
                "created_at": item.get("created_at"),
            }
        )
        if len(out) >= limit:
            break
    return out, query, ""


def appstore_candidates(
    keywords: list[str],
    t0: str,
    t1: str,
    client: HttpClient | None = None,
    country: str = "us",
    limit: int = 15,
) -> tuple[list[dict], str, str]:
    client = client or _client()
    term = " ".join(keywords)
    try:
        data = client.get_json(
            ITUNES_SEARCH,
            params={"term": term, "country": country, "entity": "software", "limit": 50},
        )
    except (HttpError, OSError) as exc:
        return [], term, str(exc)
    core = _core_terms(keywords)
    out = []
    for app in data.get("results", []) if isinstance(data, dict) else []:
        released = str(app.get("releaseDate", ""))[:10]
        if not released or not (t0 <= released <= t1):
            continue
        text = f"{app.get('trackName', '')} {app.get('description', '')}"
        if not _loose(text, keywords, core):
            continue
        out.append(
            {
                "name": app.get("trackName"),
                "description": app.get("description") or "",
                "url": app.get("trackViewUrl"),
                "released": released,
            }
        )
        if len(out) >= limit:
            break
    return out, term, ""


def _finish(
    source: str,
    query: str,
    candidates: list[dict],
    keywords: list[str],
    proposition: str,
    adjudicator,
    error: str,
) -> Outcome:
    if not candidates:
        return Outcome(source, query, False, [], error, 0, 0, adjudicator is not None)

    core = _core_terms(keywords)
    if adjudicator is not None:
        verdicts = adjudicator.judge(proposition or " / ".join(keywords), candidates)
        by_index = {v.index: v for v in verdicts}
        accepted = []
        for i, cand in enumerate(candidates, start=1):
            v = by_index.get(i)
            cand = dict(cand)
            cand["match"] = v.match if v else "uncertain"
            cand["reason"] = v.reason if v else ""
            cand["confidence"] = v.confidence if v else 0.0
            if cand["match"] == "yes":
                accepted.append(cand)
        return Outcome(
            source, query, bool(accepted), accepted[:3], error,
            scanned=len(candidates), rejected=len(candidates) - len(accepted), adjudicated=True,
        )

    strict = [c for c in candidates if _strict(f"{c.get('name')} {c.get('description')}", keywords, core)]
    return Outcome(
        source, query, bool(strict), strict[:3], error,
        scanned=len(candidates), rejected=len(candidates) - len(strict), adjudicated=False,
    )


def github_outcome(
    keywords: list[str],
    t0: str,
    t1: str,
    client: HttpClient | None = None,
    min_stars: int = 5,
    proposition: str = "",
    adjudicator=None,
) -> Outcome:
    candidates, query, error = github_candidates(keywords, t0, t1, client=client, min_stars=min_stars)
    return _finish("github", query, candidates, keywords, proposition, adjudicator, error)


def appstore_outcome(
    keywords: list[str],
    t0: str,
    t1: str,
    client: HttpClient | None = None,
    country: str = "us",
    proposition: str = "",
    adjudicator=None,
) -> Outcome:
    candidates, query, error = appstore_candidates(keywords, t0, t1, client=client, country=country)
    return _finish("appstore", query, candidates, keywords, proposition, adjudicator, error)


def collect(
    keywords: list[str],
    t0: str,
    t1: str,
    proposition: str = "",
    adjudicator=None,
    client: HttpClient | None = None,
) -> list[Outcome]:
    return [
        github_outcome(keywords, t0, t1, client=client, proposition=proposition, adjudicator=adjudicator),
        appstore_outcome(keywords, t0, t1, client=client, proposition=proposition, adjudicator=adjudicator),
    ]
