"""Tests for demand normalization (cache + parsing), no network."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from painradar.canonical import Canonical, LLMNormalizer


class TestCanonical(unittest.TestCase):
    def test_cache_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            data = {"k1": {"key": "k1", "demand": "订阅取消难", "type": "订阅付费",
                           "buyer": "App 用户", "workaround": "联系客服", "cost": "金钱"}}
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            canon = Canonical(**loaded["k1"])
            self.assertEqual(canon.demand, "订阅取消难")
            self.assertEqual(canon.type, "订阅付费")

    def test_normalizer_requires_config(self) -> None:
        import os

        keep = {k: os.environ.pop(k, None) for k in ("PAINRADAR_LLM_BASE_URL", "PAINRADAR_LLM_MODEL")}
        try:
            with self.assertRaises(RuntimeError):
                LLMNormalizer()
        finally:
            for k, v in keep.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
