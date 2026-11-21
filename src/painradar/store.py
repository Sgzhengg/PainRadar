"""SQLite evidence ledger.

Design rules (plan §5.3):

* append-only: derived rows are never updated, a correction is a new row that
  ``supersedes`` the old one;
* every derived row carries ``run_id`` + model/prompt/taxonomy versions;
* deletion is a soft delete on the comment plus a cascade that marks dependent
  atoms deleted, so a 72-hour deletion request is executable and auditable.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL,
    stats_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    comment_uid TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    item_id TEXT NOT NULL,
    url TEXT NOT NULL,
    published_at TEXT NOT NULL,
    lang TEXT NOT NULL,
    category TEXT NOT NULL,
    text_masked TEXT NOT NULL,
    text_sha TEXT NOT NULL,
    author_key TEXT NOT NULL,
    rating REAL,
    tier TEXT NOT NULL,
    tos_basis TEXT NOT NULL,
    minhash_json TEXT NOT NULL,
    duplicate_of TEXT,
    ingested_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category, deleted_at);
CREATE INDEX IF NOT EXISTS idx_items_sha ON items(text_sha);

CREATE TABLE IF NOT EXISTS atoms (
    atom_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    comment_uid TEXT NOT NULL,
    quote TEXT NOT NULL,
    span_start INTEGER NOT NULL,
    span_end INTEGER NOT NULL,
    match_score TEXT NOT NULL,
    scene TEXT NOT NULL DEFAULT '',
    trigger TEXT NOT NULL DEFAULT '',
    job TEXT NOT NULL DEFAULT '',
    obstacle TEXT NOT NULL DEFAULT '',
    workaround TEXT NOT NULL DEFAULT '',
    cost_type TEXT NOT NULL DEFAULT '',
    cost_estimate TEXT NOT NULL DEFAULT '',
    persona TEXT NOT NULL DEFAULT '',
    intensity INTEGER NOT NULL DEFAULT 0,
    expression TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL DEFAULT 'L0',
    wtp_level TEXT NOT NULL DEFAULT 'none',
    wtp_quote TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    model_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    taxonomy_version TEXT NOT NULL,
    supersedes TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_atoms_run ON atoms(run_id);
CREATE INDEX IF NOT EXISTS idx_atoms_comment ON atoms(comment_uid);

CREATE TABLE IF NOT EXISTS clusters (
    cluster_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    label TEXT NOT NULL,
    size INTEGER NOT NULL,
    noise INTEGER NOT NULL,
    medoid_atom_id TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (cluster_id, run_id)
);

CREATE TABLE IF NOT EXISTS atom_cluster (
    run_id TEXT NOT NULL,
    atom_id TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    PRIMARY KEY (run_id, atom_id)
);

CREATE TABLE IF NOT EXISTS scores (
    run_id TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    pain REAL NOT NULL,
    opportunity REAL NOT NULL,
    tier TEXT NOT NULL,
    factors_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, cluster_id)
);

CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    title TEXT NOT NULL,
    one_liner TEXT NOT NULL,
    persona TEXT NOT NULL,
    workaround TEXT NOT NULL,
    pain_tier TEXT NOT NULL,
    opportunity_tier TEXT NOT NULL,
    market_low REAL NOT NULL,
    market_mid REAL NOT NULL,
    market_high REAL NOT NULL,
    assumptions_json TEXT NOT NULL,
    sensitivity_json TEXT NOT NULL,
    falsifier TEXT NOT NULL,
    validation_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (opportunity_id, run_id)
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS anchors (
    anchor_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    as_of TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    grade TEXT NOT NULL DEFAULT 'C',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchors_category ON anchors(category);

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    category TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    t0 TEXT NOT NULL,
    window_end TEXT NOT NULL,
    keywords_json TEXT NOT NULL,
    proposition TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
    prediction_id TEXT NOT NULL,
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    hit INTEGER NOT NULL,
    evidence_json TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (prediction_id, source)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """Additive migrations for databases created by older versions."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(predictions)")}
        if "mode" not in cols:
            self._conn.execute(
                "ALTER TABLE predictions ADD COLUMN mode TEXT NOT NULL DEFAULT 'backtest'"
            )
            self._conn.commit()

        item_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(items)")}
        for name, ddl in (
            ("parent_context", "ALTER TABLE items ADD COLUMN parent_context TEXT NOT NULL DEFAULT ''"),
            ("likes", "ALTER TABLE items ADD COLUMN likes INTEGER NOT NULL DEFAULT 0"),
            ("replies", "ALTER TABLE items ADD COLUMN replies INTEGER NOT NULL DEFAULT 0"),
            ("post_id", "ALTER TABLE items ADD COLUMN post_id TEXT NOT NULL DEFAULT ''"),
        ):
            if name not in item_cols:
                self._conn.execute(ddl)

        atom_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(atoms)")}
        if "canonical_pain" not in atom_cols:
            self._conn.execute(
                "ALTER TABLE atoms ADD COLUMN canonical_pain TEXT NOT NULL DEFAULT ''"
            )

        opp_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(opportunities)")}
        if "solo_fit_json" not in opp_cols:
            self._conn.execute(
                "ALTER TABLE opportunities ADD COLUMN solo_fit_json TEXT NOT NULL DEFAULT '{}'"
            )
        self._conn.commit()

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # -- meta --------------------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self._conn.commit()

    def salt(self) -> str:
        salt = self.get_meta("author_salt")
        if salt is None:
            salt = uuid.uuid4().hex
            self.set_meta("author_salt", salt)
        return salt

    def audit(self, actor: str, action: str, object_type: str, object_id: str, detail: str = "") -> None:
        self._conn.execute(
            "INSERT INTO audit(ts, actor, action, object_type, object_id, detail) VALUES(?,?,?,?,?,?)",
            (_now(), actor, action, object_type, object_id, detail),
        )
        self._conn.commit()

    # -- items -------------------------------------------------------------
    def find_duplicate(self, text_sha: str, signature: Sequence[int], category: str | None = None) -> str | None:
        row = self._conn.execute(
            "SELECT comment_uid FROM items WHERE text_sha=? AND deleted_at IS NULL LIMIT 1",
            (text_sha,),
        ).fetchone()
        if row:
            return row["comment_uid"]
        # Near-duplicate check is bounded to the most recent 500 rows (and to the
        # same category when provided) so ingest stays O(1) per item.
        if category:
            rows = self._conn.execute(
                "SELECT comment_uid, minhash_json FROM items WHERE deleted_at IS NULL AND category=?"
                " ORDER BY ingested_at DESC LIMIT 500",
                (category,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT comment_uid, minhash_json FROM items WHERE deleted_at IS NULL ORDER BY ingested_at DESC LIMIT 500"
            ).fetchall()
        from .textproc import jaccard_estimate

        for r in rows:
            if jaccard_estimate(json.loads(r["minhash_json"]), list(signature)) >= 0.85:
                return r["comment_uid"]
        return None

    def insert_item(self, row: dict[str, Any]) -> bool:
        payload = {
            "comment_uid": row["comment_uid"],
            "platform": row["platform"],
            "item_id": row["item_id"],
            "url": row["url"],
            "published_at": row["published_at"],
            "lang": row["lang"],
            "category": row["category"],
            "text_masked": row["text_masked"],
            "text_sha": row["text_sha"],
            "author_key": row["author_key"],
            "rating": row.get("rating"),
            "tier": row["tier"],
            "tos_basis": row["tos_basis"],
            "minhash_json": row["minhash_json"],
            "duplicate_of": row.get("duplicate_of"),
            "ingested_at": row["ingested_at"],
            "parent_context": row.get("parent_context", ""),
            "likes": int(row.get("likes", 0) or 0),
            "replies": int(row.get("replies", 0) or 0),
            "post_id": row.get("post_id", ""),
        }
        try:
            self._conn.execute(
                """INSERT INTO items(comment_uid, platform, item_id, url, published_at, lang,
                       category, text_masked, text_sha, author_key, rating, tier, tos_basis,
                       minhash_json, duplicate_of, ingested_at, parent_context, likes, replies, post_id)
                   VALUES(:comment_uid,:platform,:item_id,:url,:published_at,:lang,
                       :category,:text_masked,:text_sha,:author_key,:rating,:tier,:tos_basis,
                       :minhash_json,:duplicate_of,:ingested_at,:parent_context,:likes,:replies,:post_id)""",
                payload,
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def items(self, category: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM items WHERE category=? AND deleted_at IS NULL AND duplicate_of IS NULL ORDER BY published_at",
            (category,),
        ).fetchall()

    def item(self, comment_uid: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM items WHERE comment_uid=? AND deleted_at IS NULL", (comment_uid,)
        ).fetchone()

    def soft_delete(self, comment_uid: str) -> int:
        """Cascade a deletion request: comment + derived atoms."""
        now = _now()
        cur = self._conn.execute(
            "UPDATE items SET deleted_at=? WHERE comment_uid=?", (now, comment_uid)
        )
        self._conn.execute("DELETE FROM atoms WHERE comment_uid=?", (comment_uid,))
        self._conn.commit()
        self.audit("system", "delete", "item", comment_uid, "72h cascade")
        return cur.rowcount

    def soft_delete_apps(self, category: str, app_ids: Sequence[str]) -> int:
        """Remove every item from the given app ids (off-topic source cleanup)."""
        total = 0
        for app in app_ids:
            rows = self._conn.execute(
                "SELECT comment_uid FROM items WHERE category=? AND item_id LIKE ? AND deleted_at IS NULL",
                (category, f"as_{app}_%"),
            ).fetchall()
            for row in rows:
                total += self.soft_delete(row["comment_uid"])
        return total

    # -- atoms -------------------------------------------------------------
    def insert_atoms(self, atoms: Iterable[dict[str, Any]]) -> int:
        n = 0
        with self.tx() as conn:
            for a in atoms:
                conn.execute(
                    """INSERT OR REPLACE INTO atoms(atom_id, run_id, comment_uid, quote, span_start,
                        span_end, match_score, scene, trigger, job, obstacle, workaround, cost_type,
                        cost_estimate, persona, intensity, expression, level, wtp_level, wtp_quote,
                        domain, confidence, model_version, prompt_version, taxonomy_version,
                        supersedes, created_at)
                       VALUES(:atom_id,:run_id,:comment_uid,:quote,:span_start,:span_end,:match_score,
                        :scene,:trigger,:job,:obstacle,:workaround,:cost_type,:cost_estimate,:persona,
                        :intensity,:expression,:level,:wtp_level,:wtp_quote,:domain,:confidence,
                        :model_version,:prompt_version,:taxonomy_version,:supersedes,:created_at)""",
                    a,
                )
                n += 1
        return n

    def atoms(self, run_id: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM atoms WHERE run_id=? ORDER BY atom_id", (run_id,)
        ).fetchall()

    # -- clusters ----------------------------------------------------------
    def insert_clusters(self, run_id: str, clusters: Sequence[dict[str, Any]], assignments: dict[str, str]) -> None:
        now = _now()
        with self.tx() as conn:
            for c in clusters:
                conn.execute(
                    "INSERT OR REPLACE INTO clusters(cluster_id, run_id, label, size, noise, medoid_atom_id, created_at)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (c["cluster_id"], run_id, c["label"], c["size"], int(c["noise"]), c["medoid_atom_id"], now),
                )
                for atom_id in c["members"]:
                    conn.execute(
                        "INSERT OR REPLACE INTO atom_cluster(run_id, atom_id, cluster_id) VALUES(?,?,?)",
                        (run_id, atom_id, c["cluster_id"]),
                    )

    def clusters(self, run_id: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM clusters WHERE run_id=? ORDER BY size DESC", (run_id,)
        ).fetchall()

    def cluster_members(self, run_id: str, cluster_id: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            """SELECT a.*, c.label, i.platform, i.url, i.published_at, i.item_id,
                      i.likes AS likes, i.replies AS replies
               FROM atoms a
               JOIN atom_cluster ac ON ac.atom_id=a.atom_id AND ac.run_id=a.run_id
               JOIN clusters c ON c.cluster_id=ac.cluster_id AND c.run_id=ac.run_id
               JOIN items i ON i.comment_uid=a.comment_uid
               WHERE a.run_id=? AND ac.cluster_id=?
               ORDER BY i.likes DESC, a.confidence DESC""",
            (run_id, cluster_id),
        ).fetchall()

    # -- scores / opportunities -------------------------------------------
    def insert_scores(self, run_id: str, scores: Sequence[dict[str, Any]]) -> None:
        now = _now()
        with self.tx() as conn:
            for s in scores:
                conn.execute(
                    "INSERT OR REPLACE INTO scores(run_id, cluster_id, pain, opportunity, tier, factors_json, created_at)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (run_id, s["cluster_id"], s["pain"], s["opportunity"], s["tier"],
                     json.dumps(s["factors"], ensure_ascii=False), now),
                )

    def insert_opportunities(self, run_id: str, opps: Sequence[dict[str, Any]]) -> None:
        now = _now()
        with self.tx() as conn:
            for o in opps:
                conn.execute(
                    """INSERT OR REPLACE INTO opportunities(opportunity_id, run_id, cluster_id, title,
                        one_liner, persona, workaround, pain_tier, opportunity_tier, market_low,
                        market_mid, market_high, assumptions_json, sensitivity_json, falsifier,
                        validation_json, created_at, solo_fit_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (o["opportunity_id"], run_id, o["cluster_id"], o["title"], o["one_liner"],
                     o["persona"], o["workaround"], o["pain_tier"], o["opportunity_tier"],
                     o["market_low"], o["market_mid"], o["market_high"],
                     json.dumps(o["assumptions"], ensure_ascii=False),
                     json.dumps(o["sensitivity"], ensure_ascii=False),
                     o["falsifier"], json.dumps(o["validation"], ensure_ascii=False), now,
                     json.dumps(o.get("solo_fit") or {}, ensure_ascii=False)),
                )

    def opportunities(self, run_id: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM opportunities WHERE run_id=? ORDER BY opportunity_tier DESC, market_mid DESC",
            (run_id,),
        ).fetchall()

    # -- runs --------------------------------------------------------------
    def save_run(self, run_id: str, category: str, stats: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO runs(run_id, category, created_at, stats_json) VALUES(?,?,?,?)",
            (run_id, category, _now(), json.dumps(stats, ensure_ascii=False)),
        )
        self._conn.commit()

    def latest_run(self, category: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM runs WHERE category=? ORDER BY created_at DESC LIMIT 1", (category,)
        ).fetchone()

    def stats(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for table in ("items", "atoms", "clusters", "scores", "opportunities", "runs", "anchors"):
            out[table] = self._conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        return out

    # -- external anchors --------------------------------------------------
    def insert_anchor(self, row: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO anchors(anchor_id, category, source, metric, value, as_of,
                   url, grade, note, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                row["anchor_id"], row["category"], row["source"], row["metric"], row["value"],
                row["as_of"], row["url"], row["grade"], row["note"], _now(),
            ),
        )
        self._conn.commit()

    def anchors(self, category: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM anchors WHERE category=? ORDER BY metric, as_of DESC", (category,)
        ).fetchall()

    # -- predictions / outcomes (B set) -----------------------------------
    def insert_predictions(self, rows: Sequence[dict[str, Any]]) -> None:
        now = _now()
        with self.tx() as conn:
            for r in rows:
                conn.execute(
                    """INSERT OR REPLACE INTO predictions(prediction_id, run_id, category, cluster_id,
                           t0, window_end, keywords_json, proposition, created_at, mode)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (r["prediction_id"], r["run_id"], r["category"], r["cluster_id"],
                     r["t0"], r["window_end"], json.dumps(r["keywords"], ensure_ascii=False),
                     r["proposition"], now, r.get("mode", "backtest")),
                )

    def predictions(self, run_id: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM predictions WHERE run_id=? ORDER BY prediction_id", (run_id,)
        ).fetchall()

    def insert_outcome(self, row: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO outcomes(prediction_id, source, query, hit, evidence_json, collected_at, error)
               VALUES(?,?,?,?,?,?,?)""",
            (row["prediction_id"], row["source"], row["query"], int(row["hit"]),
             json.dumps(row["evidence"], ensure_ascii=False), _now(), row.get("error", "")),
        )
        self._conn.commit()

    def outcomes(self, prediction_id: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM outcomes WHERE prediction_id=?", (prediction_id,)
        ).fetchall()
