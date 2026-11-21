"""LLM client: JSON schema checks, disk cache, token accounting, rate limiting."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx


class LLMError(RuntimeError):
    pass


@dataclass
class TokenAccount:
    prompt: int = 0
    completion: int = 0
    calls: int = 0
    cached: int = 0
    failed: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, prompt: int, completion: int) -> None:
        with self.lock:
            self.prompt += prompt
            self.completion += completion
            self.calls += 1

    def hit_cache(self) -> None:
        with self.lock:
            self.cached += 1

    def fail(self) -> None:
        with self.lock:
            self.failed += 1

    def as_dict(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt,
            "completion_tokens": self.completion,
            "total_tokens": self.prompt + self.completion,
            "cache_hits": self.cached,
            "failures": self.failed,
        }


class LLM:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        cache_dir: str | Path = "var/indie_cache",
        min_interval: float = 0.4,
        timeout: float = 180.0,
        temperature: float = 0.0,
        offline: bool = False,
    ) -> None:
        self.model = model or os.environ.get("PAINRADAR_LLM_MODEL", "deepseek-chat")
        self.base_url = (base_url or os.environ.get("PAINRADAR_LLM_BASE_URL", "https://api.deepseek.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("PAINRADAR_LLM_API_KEY", "")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.timeout = timeout
        self.temperature = temperature
        self.offline = offline or os.environ.get("PAINRADAR_LLM_OFFLINE") == "1"
        self.tokens = TokenAccount()
        self._last_call = 0.0
        self._rate_lock = threading.Lock()
        self.client = httpx.Client(timeout=timeout)

    # -- cache ---------------------------------------------------------
    def _key(self, system: str, user: str) -> str:
        blob = f"{self.model}|{system}|{user}".encode()
        return hashlib.sha256(blob).hexdigest()[:24]

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _cache_get(self, key: str) -> dict | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None
        return data.get("result")

    def _cache_put(self, key: str, result: dict) -> None:
        tmp = self._cache_path(key).with_suffix(".tmp")
        tmp.write_text(json.dumps({"result": result}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._cache_path(key))

    # -- call ----------------------------------------------------------
    def _throttle(self) -> None:
        with self._rate_lock:
            wait = self.min_interval - (time.time() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()

    def chat_json(
        self,
        system: str,
        user: str,
        required: tuple[str, ...] = (),
        max_retries: int = 3,
    ) -> dict:
        key = self._key(system, user)
        cached = self._cache_get(key)
        if cached is not None:
            self.tokens.hit_cache()
            return cached
        if self.offline:
            raise LLMError(f"offline cache miss for {key}")

        last_error: Exception | None = None
        for attempt in range(max_retries):
            self._throttle()
            try:
                resp = self.client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "temperature": self.temperature,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                    timeout=self.timeout,
                )
                if resp.status_code == 429:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage") or {}
                self.tokens.add(int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)))
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content[content.find("{") : content.rfind("}") + 1])
                missing = [k for k in required if k not in parsed]
                if missing:
                    raise LLMError(f"missing keys: {missing}")
                self._cache_put(key, parsed)
                return parsed
            except (httpx.HTTPError, KeyError, ValueError, LLMError) as exc:
                last_error = exc
                time.sleep(1.0 * (attempt + 1))
        self.tokens.fail()
        raise LLMError(f"llm failed after {max_retries} tries: {last_error}")

    def close(self) -> None:
        self.client.close()


def run_parallel(items: list[Any], fn: Callable[[Any], Any], workers: int = 3) -> list[Any]:
    """Run fn over items with a small thread pool; preserves order."""
    if workers <= 1:
        return [fn(x) for x in items]
    results: list[Any] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, item): i for i, item in enumerate(items)}
        for future, i in futures.items():
            results[i] = future.result()
    return results
