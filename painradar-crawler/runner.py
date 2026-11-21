"""MediaCrawler adapter for the PainRadar bridge service.

MediaCrawler versions differ in CLI flags and output layout, so this adapter
keeps every version-specific choice in environment variables:

- ``MEDIACRAWLER_HOME``   crawler checkout (default ``/app/MediaCrawler``)
- ``CRAWLER_CMD_TEMPLATE`` command template, placeholders ``{platform}`` and
  ``{keywords}`` (default uses the common ``main.py --lt cookie --type search``)
- ``CRAWLER_TIMEOUT``     seconds per crawl (default 1200)
- ``CRAWLER_DATA_DIR``    output root (default ``<home>/data``)
- ``COOKIE_DIR``          persistent cookie directory (default ``/data/cookies``)

Cookies are passed through MediaCrawler's real CLI option ``--cookies`` (the
version pinned here supports it). For xhs only ``web_session`` is required by
its login implementation; other platforms apply the whole cookie string.

The bridge never invents data: it only normalizes what MediaCrawler wrote.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

DOMAINS = {
    "xhs": ".xiaohongshu.com",
    "dy": ".douyin.com",
    "ks": ".kuaishou.com",
    "bili": ".bilibili.com",
    "wb": ".weibo.com",
    "tieba": ".tieba.baidu.com",
    "zhihu": ".zhihu.com",
}

NEED_LOGIN_RE = re.compile(
    r"(需要登录|请先登录|扫码登录|登录已过期|登录失效|cookie.*(过期|失效|invalid|expired)|login required)",
    re.IGNORECASE,
)

NOTE_ID_KEYS = ("note_id", "aweme_id", "bvid", "aid", "question_id", "video_id", "mblog_id", "mid", "tid", "post_id", "id")
COMMENT_ID_KEYS = ("comment_id", "cid", "reply_id", "id")
CONTENT_KEYS = ("content", "text", "comment_content", "text_raw")
LIKE_KEYS = ("like_count", "liked_count", "digg_count", "like_num", "likes", "attitudes_count")


class RunnerError(RuntimeError):
    pass


class NeedLoginError(RunnerError):
    pass


@dataclass
class CrawlSpec:
    platform: str
    keywords: list[str]
    max_notes: int = 50
    cookies: Any = None


def parse_cookies(raw: Any, platform: str) -> list[dict[str, Any]] | None:
    """Accept a cookie list, ``{cookies: [...]}`` or a ``k=v; k2=v2`` string."""
    if not raw:
        return None
    if isinstance(raw, dict):
        raw = raw.get("cookies", raw)
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, dict)]
    if isinstance(raw, str):
        out = []
        for part in raw.split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            if name.strip():
                out.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": DOMAINS.get(platform, ""),
                    "path": "/",
                })
        return out or None
    return None


def cookie_string(cookies: list[dict[str, Any]]) -> str:
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name"))


def _first(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if record.get(key) not in (None, ""):
            return record[key]
    return None


def _comments_of(record: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("comments", "comment_list", "sub_comments", "replies"):
        value = record.get(key)
        if isinstance(value, list):
            return [c for c in value if isinstance(c, dict)]
    return []


def _normalize_comment(raw: dict[str, Any], index: int) -> dict[str, Any]:
    cid = _first(raw, COMMENT_ID_KEYS)
    content = _first(raw, CONTENT_KEYS) or ""
    subs = _comments_of(raw)
    return {
        "comment_id": str(cid or f"c{index}"),
        "content": str(content),
        "like_count": int(_first(raw, LIKE_KEYS) or 0),
        "sub_comments": [_normalize_comment(s, j) for j, s in enumerate(subs)],
    }


def _normalize_note(raw: dict[str, Any], nid: str) -> dict[str, Any]:
    comments = [_normalize_comment(c, i) for i, c in enumerate(_comments_of(raw))]
    return {
        "note_id": nid,
        "title": str(_first(raw, ("title", "note_title", "desc")) or ""),
        "desc": str(_first(raw, ("desc", "description", "content", "text")) or ""),
        "url": str(_first(raw, ("url", "note_url", "share_url", "web_url")) or ""),
        "liked_count": int(_first(raw, LIKE_KEYS) or 0),
        "comments": comments,
    }


def _iter_records(payload: Any):
    if isinstance(payload, list):
        yield from (x for x in payload if isinstance(x, dict))
    elif isinstance(payload, dict):
        for key in ("data", "items", "results", "notes"):
            value = payload.get(key)
            if isinstance(value, list):
                yield from (x for x in value if isinstance(x, dict))
                return
        yield payload


class MediaCrawlerRunner:
    def __init__(self, home: str | None = None) -> None:
        self.home = Path(home or os.environ.get("MEDIACRAWLER_HOME", "/app/MediaCrawler"))
        self.data_dir = Path(os.environ.get("CRAWLER_DATA_DIR", self.home / "data"))
        self.cookie_dir = Path(os.environ.get("COOKIE_DIR", "/data/cookies"))
        self.timeout = int(os.environ.get("CRAWLER_TIMEOUT", "1200"))
        self.template = os.environ.get(
            "CRAWLER_CMD_TEMPLATE",
            "python main.py --platform {platform} --lt cookie --type search --keywords {keywords}",
        )

    # -- cookies ---------------------------------------------------------
    def resolve_cookies(self, spec: CrawlSpec) -> str:
        """Request cookie > PLATFORM_COOKIES_* env > persisted file."""
        persisted = self.cookie_dir / f"{spec.platform}.txt"

        cookies = parse_cookies(spec.cookies, spec.platform)
        if not cookies:
            env_raw = os.environ.get(f"PLATFORM_COOKIES_{spec.platform.upper()}", "")
            cookies = parse_cookies(env_raw, spec.platform)
        if cookies:
            value = cookie_string(cookies)
            try:
                self.cookie_dir.mkdir(parents=True, exist_ok=True)
                persisted.write_text(value, encoding="utf-8")
            except OSError:
                # Read-only /data or no volume: keep the cookie in-memory only.
                pass
            return value
        if persisted.exists():
            try:
                return persisted.read_text(encoding="utf-8").strip()
            except OSError:
                return ""
        return ""

    WRAPPER = (
        'import config, runpy, sys;'
        'config.ENABLE_CDP_MODE=False;'
        'config.HEADLESS=True;'
        'config.SAVE_LOGIN_STATE=True;'
        'runpy.run_path("main.py", run_name="__main__")'
    )

    def build_command(self, spec: CrawlSpec, cookies: str = "") -> list[str]:
        keywords = ",".join(spec.keywords)
        rendered = self.template.format(platform=spec.platform, keywords=keywords)
        args = shlex.split(rendered)

        # MediaCrawler's config is plain Python and ignores env vars, so force
        # headless/CDP-off inside a wrapper instead of editing the checkout.
        force = os.environ.get("CRAWLER_FORCE_HEADLESS", "1") == "1"
        if force and any(a.endswith("main.py") for a in args):
            idx = next(i for i, a in enumerate(args) if a.endswith("main.py"))
            args = [sys.executable, "-c", self.WRAPPER, *args[idx + 1:]]

        if cookies and "--cookies" not in args:
            args.extend(["--cookies", cookies])
        return args

    # -- run -------------------------------------------------------------
    def _spawn(self, args: list[str]) -> subprocess.Popen:
        kwargs: dict[str, Any] = {
            "cwd": str(self.home),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "env": {**os.environ, "PYTHONUNBUFFERED": "1"},
        }
        if os.name == "posix":
            # New session so a timeout can kill Chromium children together.
            kwargs["start_new_session"] = True
        else:
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return subprocess.Popen(args, **kwargs)

    def _terminate_tree(self, proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        if os.name == "posix":
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:  # noqa: BLE001
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:  # noqa: BLE001
                    pass
        else:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )

    def run(
        self,
        spec: CrawlSpec,
        on_progress: Callable[[str, int, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.home.exists():
            raise RunnerError(f"MediaCrawler checkout not found at {self.home}")
        cookies = self.resolve_cookies(spec)
        started = time.time()
        if on_progress:
            on_progress("crawling", 20, f"启动 MediaCrawler: {spec.platform}")

        proc = self._spawn(self.build_command(spec, cookies))
        try:
            stdout, stderr = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            self._terminate_tree(proc)
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            raise RunnerError(f"crawler timed out after {self.timeout}s") from exc

        def decode(value: bytes | str | None) -> str:
            if not isinstance(value, bytes):
                return value or ""
            for encoding in ("utf-8", "gbk"):
                try:
                    return value.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return value.decode("utf-8", errors="replace")

        output = f"{decode(stdout)}\n{decode(stderr)}"
        if NEED_LOGIN_RE.search(output):
            raise NeedLoginError("登录态已过期，请在配置中更新平台 Cookie")
        if proc.returncode != 0:
            tail = output.strip().splitlines()[-6:]
            raise RunnerError(f"crawler exited {proc.returncode}: {' | '.join(tail)}")

        if on_progress:
            on_progress("converting", 75, "读取抓取结果并清洗")
        notes = self.collect(started, spec.max_notes)
        if on_progress:
            on_progress("completed", 100, f"抓取 {len(notes)} 条")
        return notes

    # -- result collection ----------------------------------------------
    def collect(self, started: float, max_notes: int) -> list[dict[str, Any]]:
        if not self.data_dir.exists():
            return []
        cutoff = started - 120
        files = [
            p for p in self.data_dir.rglob("*.json")
            if p.is_file() and p.stat().st_mtime >= cutoff
        ]
        files.sort(key=lambda p: p.stat().st_mtime)

        notes: dict[str, dict[str, Any]] = {}
        pending_comments: list[tuple[str, dict[str, Any]]] = []

        for path in files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for record in _iter_records(payload):
                nid = _first(record, NOTE_ID_KEYS)
                content = _first(record, CONTENT_KEYS)
                is_comment = bool(_first(record, COMMENT_ID_KEYS)) and content is not None
                if is_comment:
                    parent = str(_first(record, ("note_id", "aweme_id", "bvid", "aid", "question_id")) or "")
                    pending_comments.append((parent, record))
                elif nid is not None:
                    notes.setdefault(str(nid), _normalize_note(record, str(nid)))

        for parent, record in pending_comments:
            if parent and parent in notes:
                notes[parent]["comments"].append(_normalize_comment(record, len(notes[parent]["comments"])))
            elif parent:
                stub = notes.setdefault(parent, {
                    "note_id": parent, "title": "", "desc": "",
                    "url": "", "liked_count": 0, "comments": [],
                })
                stub["comments"].append(_normalize_comment(record, len(stub["comments"])))

        result = []
        for note in notes.values():
            if not note["comments"]:
                continue
            note["comments"] = note["comments"][:200]
            result.append(note)
        result.sort(key=lambda n: n.get("liked_count", 0), reverse=True)
        return result[: max(1, max_notes)]
