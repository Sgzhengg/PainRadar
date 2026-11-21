"""Small HTTP layer: retries, per-host rate limiting, injectable transport.

No third-party dependency. The ``transport`` hook exists so tests can run
completely offline and so a future async client can be swapped in without
touching connectors.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping


@dataclass
class Response:
    status: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> object:
        return json.loads(self.body.decode("utf-8"))


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], Response]


class RateLimiter:
    """Token bucket, one token per ``1/rate`` seconds, with a small burst."""

    def __init__(self, rate_per_sec: float = 1.0, burst: int = 1):
        self.interval = 1.0 / max(rate_per_sec, 0.01)
        self.burst = max(1, burst)
        self._tokens = float(self.burst)
        self._last = time.monotonic()

    def acquire(self) -> None:
        now = time.monotonic()
        self._tokens = min(self.burst, self._tokens + (now - self._last) / self.interval)
        self._last = now
        if self._tokens < 1.0:
            sleep_for = (1.0 - self._tokens) * self.interval
            time.sleep(sleep_for)
            self._tokens = 0.0
            self._last = time.monotonic()
        else:
            self._tokens -= 1.0


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: bytes = b""):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url
        self.body = body


def _urllib_transport(method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float) -> Response:
    req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, dict(resp.headers), resp.read())
    except urllib.error.HTTPError as exc:  # 4xx/5xx still carries a body
        return Response(exc.code, dict(exc.headers or {}), exc.read())


class HttpClient:
    def __init__(
        self,
        user_agent: str,
        timeout: float = 20.0,
        max_retries: int = 3,
        rate_per_sec: float = 1.0,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.limiter = RateLimiter(rate_per_sec)
        self.transport = transport or _urllib_transport
        self.sleep = sleep

    # -- low level ---------------------------------------------------------
    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
    ) -> Response:
        merged = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if headers:
            merged.update(headers)
        last: Response | None = None
        for attempt in range(self.max_retries + 1):
            self.limiter.acquire()
            resp = self.transport(method, url, merged, body, self.timeout)
            if resp.status < 400:
                return resp
            last = resp
            if resp.status not in (429, 500, 502, 503, 504):
                break
            retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
            delay = float(retry_after) if retry_after else min(2 ** attempt, 8)
            self.sleep(delay)
        raise HttpError(last.status if last else 0, url, last.body if last else b"")

    def get_json(self, url: str, params: Mapping[str, object] | None = None, headers: Mapping[str, str] | None = None) -> object:
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        return self.request("GET", url, headers=headers).json()

    def post_form(self, url: str, data: Mapping[str, str], headers: Mapping[str, str] | None = None) -> object:
        body = urllib.parse.urlencode(data).encode("utf-8")
        merged = {"Content-Type": "application/x-www-form-urlencoded"}
        if headers:
            merged.update(headers)
        return self.request("POST", url, headers=merged, body=body).json()

    def post_json(self, url: str, payload: Mapping[str, object], headers: Mapping[str, str] | None = None) -> object:
        body = json.dumps(payload).encode("utf-8")
        merged = {"Content-Type": "application/json"}
        if headers:
            merged.update(headers)
        return self.request("POST", url, headers=merged, body=body).json()
