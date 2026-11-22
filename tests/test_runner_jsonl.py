import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "painradar-crawler"))

from runner import MediaCrawlerRunner  # noqa: E402


class JSONLCollectTests(unittest.TestCase):
    def test_collects_notes_and_comments_from_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            path = data_dir / "xhs" / "search.jsonl"
            path.parent.mkdir()
            rows = [
                {"note_id": "n1", "title": "t", "desc": "d", "liked_count": 10},
                {"comment_id": "c1", "note_id": "n1", "content": "太难用了", "like_count": 5},
            ]
            path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                encoding="utf-8",
            )

            runner = MediaCrawlerRunner(home=tmp)
            runner.data_dir = data_dir
            notes = runner.collect(started=time.time() - 1, max_notes=5)

        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["note_id"], "n1")
        self.assertEqual(notes[0]["comments"][0]["content"], "太难用了")


if __name__ == "__main__":
    unittest.main()
