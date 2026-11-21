"""Connector protocol.

A connector is the only place that knows how to reach a platform. Everything
downstream sees :class:`~painradar.schema.RawItem` and nothing else.

The protocol is intentionally tiny (discover / fetch / quota / health) so that
a new platform is a new file plus a registry entry, not a pipeline change —
the one idea worth keeping from MediaCrawler (plan §2.2).
"""

from __future__ import annotations

from typing import Iterable, Protocol

from ..schema import RawItem, Tier


class Connector(Protocol):
    platform: str
    tier: Tier

    def fetch(self) -> Iterable[RawItem]:
        """Yield raw items for this source."""

    def health(self) -> dict[str, object]:
        """Return a small, serialisable health snapshot."""


class ConnectorRegistry:
    """Name -> connector factory, so the CLI can grow without if/else chains."""

    def __init__(self) -> None:
        self._factories: dict[str, object] = {}

    def register(self, name: str, factory: object) -> None:
        self._factories[name] = factory

    def create(self, name: str, **kwargs: object) -> Connector:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise SystemExit(f"unknown connector {name!r}") from exc
        return factory(**kwargs)  # type: ignore[operator]


registry = ConnectorRegistry()
