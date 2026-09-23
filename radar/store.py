"""SQLite persistence. Items are upserted; user verdicts are never overwritten."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
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


# Fetches closer together than this count as one run. Runs are manual and
# occasional, so a rerun an hour later is the same look at the world, not a
# second sighting -- it must not advance anything's "seen in N runs" count.
DEFAULT_RUN_GAP_HOURS = 6.0


def _migrate_1(conn: sqlite3.Connection) -> None:
    """Track sightings by run rather than by wall clock.

    `last_fetch` is the run number an item was last seen in and `runs_seen`
    counts the runs that saw it. Existing rows are backfilled from the runs
    table: the run an item was last seen in is the newest run that started
    before its last_seen, and runs_seen counts runs between first and last
    sighting -- an upper bound, since a source may have skipped a run.
    """
    conn.execute("ALTER TABLE items ADD COLUMN runs_seen INTEGER NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE items ADD COLUMN last_fetch INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")

    starts = [r[0] for r in conn.execute("SELECT started_at FROM runs ORDER BY started_at")]
    seqs: list[tuple[str, int]] = []      # (started_at, run number)
    seq, prev = 0, None
    for s in starts:
        when = _dt(s)
        if when is None:
            continue
        if prev is None or (when - prev).total_seconds() >= DEFAULT_RUN_GAP_HOURS * 3600:
            seq += 1
            prev = when
        seqs.append((when.isoformat(), seq))

    rows = conn.execute("SELECT id, first_seen, last_seen FROM items").fetchall()
    for item_id, first, last in rows:
        first_dt, last_dt = _dt(first), _dt(last)
        last_run = 0
        seen = set()
        for started, n in seqs:
            started_dt = _dt(started)
            if last_dt and started_dt <= last_dt:
                last_run = n
                if first_dt and started_dt >= first_dt - timedelta(hours=DEFAULT_RUN_GAP_HOURS):
                    seen.add(n)
        conn.execute("UPDATE items SET last_fetch = ?, runs_seen = ? WHERE id = ?",
                     (last_run, max(len(seen), 1), item_id))
    if seqs:
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('fetch_seq', ?)", (str(seq),))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('fetch_at', ?)", (seqs[-1][0],))


# Each entry upgrades the database by one version (PRAGMA user_version).
MIGRATIONS = [_migrate_1]


class Store:
    def __init__(self, path: Path, *, forget_after_runs: int | None = None,
                 run_gap_hours: float = DEFAULT_RUN_GAP_HOURS):
        """`forget_after_runs`: hide items no run has seen in that many runs.

        None (the default) hides nothing, which is what tests and one-off
        scripts want. The CLI passes `rank.forget_after_runs` from config.
        """
        self.path = path
        self.forget_after_runs = forget_after_runs
        self.run_gap_hours = run_gap_hours
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for n, step in enumerate(MIGRATIONS[version:], start=version + 1):
            with self.tx():
                step(self.conn)
                self.conn.execute(f"PRAGMA user_version = {n}")

    @property
    def schema_version(self) -> int:
        return self.conn.execute("PRAGMA user_version").fetchone()[0]

    # -- runs as the unit of time ------------------------------------------
    def _meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def current_fetch(self) -> int:
        return int(self._meta("fetch_seq") or 0)

    def begin_fetch(self) -> int:
        """The run number for a fetch starting now.

        A fetch within `run_gap_hours` of the run's first fetch reuses that
        run's number, so reruns and a quick `fetch` after `run` count once.
        """
        seq = self.current_fetch()
        started = _dt(self._meta("fetch_at"))
        if seq and started and (now() - started).total_seconds() < self.run_gap_hours * 3600:
            return seq
        seq += 1
        with self.tx():
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES ('fetch_seq', ?)", (str(seq),))
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES ('fetch_at', ?)",
                              (now().isoformat(),))
        return seq

    def _active_clause(self) -> tuple[str, tuple]:
        """SQL keeping items seen in the last `forget_after_runs` runs, plus saved ones."""
        if not self.forget_after_runs:
            return "", ()
        return ("(last_fetch > ? OR status = 'saved')",
                (self.current_fetch() - int(self.forget_after_runs),))

    def is_active(self, row) -> bool:
        if not self.forget_after_runs or row["status"] == "saved":
            return True
        return row["last_fetch"] > self.current_fetch() - int(self.forget_after_runs)

    def forgotten(self) -> list[sqlite3.Row]:
        """Items no recent run has seen. Dismissed ones are never listed."""
        clause, params = self._active_clause()
        if not clause:
            return []
        return self.conn.execute(
            f"SELECT * FROM items WHERE status = 'new' AND NOT {clause}", params
        ).fetchall()

    def prune(self) -> int:
        """Delete forgotten items. Saved and dismissed items are always kept:
        a deleted dismissal would bring the item back as new next time."""
        ids = [r["id"] for r in self.forgotten()]
        with self.tx():
            self.conn.executemany("DELETE FROM items WHERE id = ?", [(i,) for i in ids])
        if ids:
            # Deleted rows leave the file the same size until it is rebuilt.
            self.conn.execute("VACUUM")
        return len(ids)

    @contextmanager
    def tx(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # -- items -----------------------------------------------------------
    def upsert(self, item: Item, fetch_seq: int | None = None) -> str:
        """Insert or refresh. Preserves status, first_seen, and any stored card.

        A refresh folds the stored copy into the fresh sighting first, so
        sources, watchers and evidence seen in earlier runs are kept. Without
        this, cross-source corroboration only counted when two sources
        happened to land in the same fetch.

        `fetch_seq` is the run doing the sighting (see begin_fetch);
        `runs_seen` goes up once per run, however many times it is upserted.
        """
        ts = now().isoformat()
        seq = self.current_fetch() if fetch_seq is None else fetch_seq
        row = self.conn.execute(
            "SELECT * FROM items WHERE key = ?", (item.key,)
        ).fetchone()
        first_seen = row["first_seen"] if row else ts
        if row:
            item.carry_forward(self.to_item(row))
        self.conn.execute(
            """
            INSERT INTO items (id, key, url, title, summary, author, lang, topics,
                               sources, evidence, metrics, readme, created_at,
                               first_seen, last_seen, runs_seen, last_fetch)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)
            ON CONFLICT(key) DO UPDATE SET
                runs_seen=items.runs_seen
                    + (CASE WHEN items.last_fetch = excluded.last_fetch THEN 0 ELSE 1 END),
                last_fetch=MAX(items.last_fetch, excluded.last_fetch),
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
                first_seen, ts, seq,
            ),
        )
        return item.id

    def refresh(self, item: Item) -> bool:
        """Update an item's metadata without counting it as a sighting.

        For backfills: last_seen, runs_seen and last_fetch stay as they were,
        so looking a repo up does not make it look recently seen.
        """
        row = self.conn.execute("SELECT * FROM items WHERE key = ?", (item.key,)).fetchone()
        if not row:
            return False
        item.carry_forward(self.to_item(row))
        self.conn.execute(
            """UPDATE items SET title=?, summary=?, author=COALESCE(?, author),
                   lang=COALESCE(?, lang), topics=?, sources=?, evidence=?, metrics=?,
                   created_at=COALESCE(?, created_at)
               WHERE key = ?""",
            (item.title, item.summary, item.author, item.lang, json.dumps(item.topics),
             json.dumps(sorted(item.sources)), json.dumps(item.evidence),
             json.dumps(item.metrics, default=str),
             item.created_at.isoformat() if item.created_at else None, item.key),
        )
        return True

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

    def items(self, *, include_dismissed: bool = False, include_forgotten: bool = False,
              limit: int | None = None, order: str = "score DESC") -> list[sqlite3.Row]:
        where, params = [], ()
        if not include_dismissed:
            where.append("status != 'dismissed'")
        if not include_forgotten:
            clause, params = self._active_clause()
            if clause:
                where.append(clause)
        sql = "SELECT * FROM items"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY " + order
        if limit:
            sql += " LIMIT %d" % int(limit)
        return self.conn.execute(sql, params).fetchall()

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
            "INSERT OR IGNORE INTO runs (id, started_at) VALUES (?, ?)",
            (run_id, now().isoformat()),
        )
        self.conn.commit()

    def last_stats(self) -> dict | None:
        """Per-source counts of the newest run that recorded any."""
        row = self.conn.execute(
            "SELECT stats FROM runs WHERE stats != '{}' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return json.loads(row["stats"]) if row else None

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


def open_store(cfg) -> Store:
    """A Store configured from config.toml: forgetting on, run gap as set."""
    return Store(
        cfg.db_path,
        forget_after_runs=int(cfg.get("rank.forget_after_runs", 3)) or None,
        run_gap_hours=float(cfg.get("rank.run_gap_hours", DEFAULT_RUN_GAP_HOURS)),
    )
