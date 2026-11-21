"""Zero-API-key demo of the indie pipeline.

Uses the committed sample + frozen model responses, so it runs offline and
spends 0 tokens:

    python tools/indie_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.indie.cli import main  # noqa: E402

SAMPLE = ROOT / "data" / "samples" / "indie_pdf_demo.json"
CACHE = ROOT / "tests" / "fixtures" / "indie_cache"
OUT = ROOT / "reports" / "indie_demo.md"


def run() -> int:
    print(f"input : {SAMPLE}")
    print(f"cache : {CACHE}")
    print(f"output: {OUT}")
    return main(
        [
            "--input", str(SAMPLE),
            "--keyword", "PDF工具（离线演示）",
            "--cache-dir", str(CACHE),
            "--model", "deepseek-chat",
            "--offline",
            "--workers", "1",
            "--out", str(OUT),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(run())
