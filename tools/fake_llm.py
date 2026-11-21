"""A deterministic fake LLM endpoint for local end-to-end tests.

    python tools/fake_llm.py --port 8765
    python run.py --db var/llm.db run --category pet_water_fountain \
        --extractor llm --llm-base-url http://127.0.0.1:8765 --llm-model fake

It answers /chat/completions with a schema-shaped JSON object whose ``quote`` is
always a verbatim prefix of the submitted text, so the span gate can be
exercised without spending tokens.
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _best_sentence(text: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s+", text.strip()) if p.strip()]
    long_parts = [p for p in parts if len(p) >= 30]
    if long_parts:
        return max(long_parts, key=len)[:280]
    return (text.strip()[:280] if text.strip() else "no text")


def _scene(text: str) -> str:
    low = text.lower()
    for keyword, scene in (
        ("wifi", "App 与连接"),
        ("connect", "App 与连接"),
        ("app", "App 与连接"),
        ("update", "固件与更新"),
        ("subscription", "订阅与付费"),
        ("support", "客服与售后"),
        ("noise", "夜间噪音"),
        ("loud", "夜间噪音"),
        ("clean", "清洗换水"),
        ("mold", "清洗换水"),
    ):
        if keyword in low:
            return scene
    return "其他场景"


def _workaround(text: str) -> str:
    low = text.lower()
    for marker in ("ended up", "i use", "i had to", "只能", "只好", "改用"):
        if marker in low:
            idx = low.index(marker)
            return text[idx : idx + 80].strip()
    return ""


def build_response(text: str) -> dict:
    quote = _best_sentence(text)
    workaround = _workaround(text)
    level = "L2" if workaround else "L1"
    return {
        "quote": quote,
        "scene": _scene(text),
        "trigger": "",
        "job": "complete the task without friction",
        "obstacle": quote,
        "workaround": workaround,
        "cost_type": "",
        "cost_estimate": "",
        "persona": "",
        "intensity": 3,
        "expression": "complaint",
        "level": level,
        "wtp_level": "none",
        "wtp_quote": "",
        "confidence": 0.72,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # silence
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        text = ""
        try:
            user = body["messages"][-1]["content"]
            text = json.loads(user).get("text", "")
        except Exception:
            text = ""
        payload = {
            "id": "fake",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": json.dumps(build_response(text), ensure_ascii=False)}}],
        }
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"fake llm on http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
