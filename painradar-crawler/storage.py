"""SQLite task ledger for the crawler bridge (survives restarts)."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    keywords TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT '',
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    need_login INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    result_path TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
)
"""


class TaskStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._session() as conn:
            conn.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _session(self):
        conn = self._conn()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create(self, task_id: str, platform: str, keywords: list[str]) -> None:
        now = time.time()
        with self._session() as conn:
            conn.execute(
                "INSERT INTO tasks(task_id, platform, keywords, status, stage, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (task_id, platform, json.dumps(keywords, ensure_ascii=False), "queued", "starting", now, now),
            )

    def update(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._session() as conn:
            conn.execute(
                f"UPDATE tasks SET {cols} WHERE task_id=?",
                (*fields.values(), task_id),
            )

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._session() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        try:
            data["keywords"] = json.loads(data["keywords"])
        except ValueError:
            data["keywords"] = []
        return data

    def as_public(self, task: dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": task["task_id"],
            "platform": task["platform"],
            "keywords": task["keywords"],
            "status": task["status"],
            "stage": task["stage"],
            "progress": task["progress"],
            "message": task["message"],
            "need_login": bool(task["need_login"]),
            "error": task["error"],
            "result_url": f"/api/tasks/{task['task_id']}/results"
            if task["status"] == "completed" else "",
        }
