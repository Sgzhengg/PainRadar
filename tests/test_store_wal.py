import tempfile
import unittest
from pathlib import Path

from painradar.store import Store


class SQLitePragmaTests(unittest.TestCase):
    def test_wal_and_busy_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "wal.db")
            try:
                journal = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
                sync = store._conn.execute("PRAGMA synchronous").fetchone()[0]
                busy = store._conn.execute("PRAGMA busy_timeout").fetchone()[0]
            finally:
                store.close()
        self.assertEqual(journal.lower(), "wal")
        self.assertEqual(int(sync), 1)  # NORMAL
        self.assertEqual(int(busy), 30000)


if __name__ == "__main__":
    unittest.main()
