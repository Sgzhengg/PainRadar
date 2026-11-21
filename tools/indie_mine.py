"""Thin wrapper: python tools/indie_mine.py --input ... --keyword ..."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.indie.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
