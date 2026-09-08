"""SQLite persistence. Items are upserted; user verdicts are never overwritten."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from radar.models import UTC, Item, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    key         TEXT UNIQUE NOT NULL,
    url         TEXT NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT DEFAULT '',
    author      TEXT,
    lang        TEXT,
    topics      TEXT DEFAULT '[]',
    sources     TEXT DEFAULT '[]',
    evidence    TEXT DEFAULT '[]',
    metrics     TEXT DEFAULT '{}',
    readme      TEXT DEFAULT '',
    created_at  TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    score       REAL DEFAULT 0,
    breakdown   TEXT DEFAULT '{}',
    card        TEXT,
    status      TEXT NOT NULL DEFAULT 'new'
);
CREATE INDEX IF NOT EXISTS items_score  ON items(score DESC);
CREATE INDEX IF NOT EXISTS items_status ON items(status);

CREATE TABLE IF NOT EXISTS briefs (
    id         TEXT PRIMARY KEY,
    run_id     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'new'
);
CREATE INDEX IF NOT EXISTS briefs_run ON briefs(run_id DESC);

CREATE TABLE IF NOT EXISTS runs (
    id         TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    stats      TEXT DEFAULT '{}'
);
"""


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).astimezone(UTC)
    except ValueError:
        return None


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    @contextmanager
    def tx(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # -- items -----------------------------------------------------------
    def upsert(self, item: Item) -> str:
        """Insert or refresh. Preserves status, first_seen, and any stored card."""
        ts = now().isoformat()
        row = self.conn.execute(
            "SELECT first_seen FROM items WHERE key = ?", (item.key,)
        ).fetchone()
        first_seen = row["first_seen"] if row else ts
        self.conn.execute(
            """
            INSERT INTO items (id, key, url, title, summary, author, lang, topics,
                               sources, evidence, metrics, readme, created_at,
                               first_seen, last_seen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET
                url=excluded.url,
                title=excluded.title,
                summary=excluded.summary,
                author=COALESCE(excluded.author, items.author),
                lang=COALESCE(excluded.lang, items.lang),
                topics=excluded.topics,
                sources=excluded.sources,
                evidence=excluded.evidence,
                metrics=excluded.metrics,
                readme=CASE WHEN excluded.readme != '' THEN excluded.readme
                            ELSE items.readme END,
                created_at=COALESCE(excluded.created_at, items.created_at),
                last_seen=excluded.last_seen
            """,
            (
                item.id, item.key, item.url, item.title, item.summary, item.author,
                item.lang, json.dumps(item.topics), json.dumps(sorted(item.sources)),
                json.dumps(item.evidence), json.dumps(item.metrics, default=str),
                item.readme,
                item.created_at.isoformat() if item.created_at else None,
                first_seen, ts,
            ),
        )
        return item.id

    def set_score(self, item_id: str, score: float, breakdown: dict) -> None:
        self.conn.execute(
            "UPDATE items SET score = ?, breakdown = ? WHERE id = ?",
            (score, json.dumps(breakdown), item_id),
        )

    def set_readme(self, item_id: str, readme: str) -> None:
        self.conn.execute("UPDATE items SET readme = ? WHERE id = ?", (readme, item_id))
        self.conn.commit()

    def set_card(self, item_id: str, card: dict) -> None:
        self.conn.execute(
            "UPDATE items SET card = ? WHERE id = ?", (json.dumps(card), item_id)
        )
        self.conn.commit()

    def set_status(self, ident: str, status: str) -> int:
        cur = self.conn.execute(
            "UPDATE items SET status = ? WHERE id = ? OR key = ?", (status, ident, ident)
        )
        self.conn.commit()
        return cur.rowcount

    def to_item(self, row: sqlite3.Row) -> Item:
        sources = json.loads(row["sources"] or "[]")
        it = Item(
            key=row["key"], url=row["url"], title=row["title"],
            source=(sources or ["?"])[0],
            summary=row["summary"] or "", author=row["author"], lang=row["lang"],
            topics=json.loads(row["topics"] or "[]"),
            created_at=_dt(row["created_at"]),
            metrics=json.loads(row["metrics"] or "{}"),
            evidence=json.loads(row["evidence"] or "[]"),
            readme=row["readme"] or "",
        )
        it.sources = set(sources)
        return it

    def items(self, *, include_dismissed: bool = False, limit: int | None = None,
              order: str = "score DESC") -> list[sqlite3.Row]:
        sql = "SELECT * FROM items"
        if not include_dismissed:
            sql += " WHERE status != 'dismissed'"
        sql += " ORDER BY " + order
        if limit:
            sql += " LIMIT %d" % int(limit)
        return self.conn.execute(sql).fetchall()

    def get(self, ident: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM items WHERE id = ? OR key = ?", (ident, ident)
        ).fetchone()

    # -- briefs & runs ---------------------------------------------------
    def add_brief(self, brief_id: str, run_id: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO briefs (id, run_id, created_at, payload) "
            "VALUES (?,?,?,?)",
            (brief_id, run_id, now().isoformat(), json.dumps(payload)),
        )
        self.conn.commit()

    def briefs(self, run_id: str | None = None, limit: int = 50) -> list[dict]:
        if run_id:
            rows = self.conn.execute(
                "SELECT * FROM briefs WHERE run_id = ? ORDER BY created_at", (run_id,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM briefs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            payload = json.loads(r["payload"])
            payload["_id"] = r["id"]
            payload["_run"] = r["run_id"]
            out.append(payload)
        return out

    def run_started(self, run_id: str | None) -> str | None:
        """ISO timestamp a run began, for 'what is new since then' queries.

        Falls back to the newest run, so `radar report` on its own still has a
        sensible boundary when no run id is passed.
        """
        if run_id:
            row = self.conn.execute(
                "SELECT started_at FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row:
                return row["started_at"]
        row = self.conn.execute(
            "SELECT started_at FROM runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return row["started_at"] if row else None

    def count_since(self, since: str) -> int:
        """Items first seen at or after `since` (an ISO timestamp)."""
        row = self.conn.execute(
            "SELECT COUNT(*) c FROM items WHERE first_seen >= ? AND status != 'dismissed'",
            (since,),
        ).fetchone()
        return row["c"] if row else 0

    def latest_run(self) -> str | None:
        row = self.conn.execute(
            "SELECT id FROM runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def start_run(self, run_id: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs (id, started_at) VALUES (?, ?)",
            (run_id, now().isoformat()),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, stats: dict) -> None:
        self.conn.execute(
            "UPDATE runs SET stats = ? WHERE id = ?", (json.dumps(stats), run_id)
        )
        self.conn.commit()

    def counts(self) -> dict:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) c FROM items GROUP BY status"
        ).fetchall()
        return {r["status"]: r["c"] for r in rows}
