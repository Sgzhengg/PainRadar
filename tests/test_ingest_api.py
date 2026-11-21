import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from painradar.api.app import create_app
from painradar.store import Store

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "indie_demo.json"


class IngestApiTests(unittest.TestCase):
    def test_ingest_mediacrawler_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ui.db"
            client = TestClient(create_app([str(db)]))
            res = client.post(
                "/api/ingest",
                json={
                    "source": "mediacrawler",
                    "file": str(SAMPLE),
                    "category": "pet_water_fountain",
                    "min_len": 6,
                },
            )
            self.assertEqual(res.status_code, 202, res.text)
            body = res.json()
            self.assertGreater(body["ingest"]["inserted"], 0)
            self.assertEqual(body["connector"]["dropped"], 5)

            store = Store(db)
            try:
                rows = store.items("pet_water_fountain")
            finally:
                store.close()
            self.assertTrue(rows)
            self.assertTrue(all(r["parent_context"] for r in rows))
            self.assertGreater(max(r["likes"] for r in rows), 0)

    def test_ingest_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ui.db"
            client = TestClient(create_app([str(db)]))
            res = client.post(
                "/api/ingest",
                json={"file": str(Path(tmp) / "nope.json"), "category": "pet_water_fountain"},
            )
            self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
