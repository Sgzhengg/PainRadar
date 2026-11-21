"""PainRadar — turn public comments into evidence-backed product opportunities.

The package is deliberately dependency-free: the offline demo must run on a
stock CPython 3.11+ interpreter with no network access and no API keys.

Layers (see docs/methodology.md):

    ingest -> normalise/scrub/dedup -> extract (span-gated) -> cluster
           -> score -> market estimate -> opportunity card -> report
"""

__version__ = "0.1.0"

from .schema import Level, MatchScore, PainAtom, RawItem, Tier

__all__ = ["__version__", "Level", "MatchScore", "PainAtom", "RawItem", "Tier"]
