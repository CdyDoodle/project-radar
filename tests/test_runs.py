"""Time in the corpus is counted in runs, because runs are manual and occasional."""
import json
import sqlite3
from datetime import timedelta

import pytest

from radar import rank
from radar.models import now
from radar.store import SCHEMA, Store, open_store
from tests.conftest import repo


def advance(store: Store, hours: float = 24) -> int:
    """Pretend the last run started `hours` ago, then start a new one."""
    at = (now() - timedelta(hours=hours)).isoformat()
    store.conn.execute("INSERT OR REPLACE INTO meta VALUES ('fetch_at', ?)", (at,))
    return store.begin_fetch()


# -- run numbering -----------------------------------------------------------
def test_reruns_within_the_gap_share_a_run(store):
    first = store.begin_fetch()
    assert store.begin_fetch() == first            # a rerun minutes later
    assert advance(store, hours=7) == first + 1    # a real new run


def test_runs_seen_counts_runs_not_upserts(store):
    s1 = store.begin_fetch()
    store.upsert(repo("x/y"), s1)
    store.upsert(repo("x/y"), s1)                  # same run, seen twice
    assert store.get("gh:x/y")["runs_seen"] == 1
    s2 = advance(store)
    store.upsert(repo("x/y"), s2)
    row = store.get("gh:x/y")
    assert row["runs_seen"] == 2 and row["last_fetch"] == s2


# -- forgetting ----------------------------------------------------------------
def test_items_are_forgotten_after_n_runs_regardless_of_calendar_time(cfg):
    store = open_store(cfg)                        # forget_after_runs = 3
    s = store.begin_fetch()
    store.upsert(repo("old/one"), s)
    store.upsert(repo("keep/saved"), s)
    store.set_status("gh:keep/saved", "saved")
    for _ in range(2):
        s = advance(store, hours=24 * 60)          # two months between runs
        store.upsert(repo("fresh/one"), s)
    keys = {r["key"] for r in store.items()}
    assert "gh:old/one" in keys                    # missed 2 runs: still here
    s = advance(store)
    store.upsert(repo("fresh/one"), s)
    keys = {r["key"] for r in store.items()}
    assert "gh:old/one" not in keys                # missed 3 runs: forgotten
    assert "gh:keep/saved" in keys                 # saved items never go
    assert [r["key"] for r in store.forgotten()] == ["gh:old/one"]


def test_prune_keeps_saved_and_dismissed(cfg):
    store = open_store(cfg)
    s = store.begin_fetch()
    for name in ("a/new", "b/saved", "c/dismissed"):
        store.upsert(repo(name), s)
    store.set_status("gh:b/saved", "saved")
    store.set_status("gh:c/dismissed", "dismissed")
    for _ in range(3):
        advance(store)
    assert store.prune() == 1
    assert store.get("gh:a/new") is None
    assert store.get("gh:b/saved") and store.get("gh:c/dismissed")


def test_forgotten_items_leave_the_velocity_distribution(cfg):
    store = open_store(cfg)
    s = store.begin_fetch()
    for i in range(10):                            # a frozen, very fast cohort
        store.upsert(repo(f"old/{i}", stars_per_day=1000), s)
    for _ in range(3):
        s = advance(store)
    for i in range(10):
        store.upsert(repo(f"new/{i}", stars_per_day=10 + i), s)
    rank.rank_all(store, cfg)
    top = json.loads(store.get("gh:new/9")["breakdown"])["components"]["velocity"]
    assert top == pytest.approx(0.9)               # top of the live cohort, not 0.45


# -- seen_before decay ---------------------------------------------------------
def test_seen_before_grows_with_runs(store, cfg):
    s = store.begin_fetch()
    store.upsert(repo("x/y"), s)

    def pen():
        _, bd = rank.score_item(store.to_item(store.get("gh:x/y")), cfg, store.get("gh:x/y"))
        return -bd["penalties"].get("seen_before", 0)

    assert pen() == 0                               # first run: no penalty
    s = advance(store); store.upsert(repo("x/y"), s)
    assert pen() == pytest.approx(0.3 * 1 / 5)      # second run: a little
    for _ in range(5):
        s = advance(store); store.upsert(repo("x/y"), s)
    assert pen() == pytest.approx(0.3)              # capped at the full weight


# -- backfill without counting as a sighting -------------------------------------
def test_refresh_does_not_touch_sighting_fields(store):
    s = store.begin_fetch()
    store.upsert(repo("x/y", source="github_trending"), s)
    before = store.get("gh:x/y")
    richer = repo("x/y", "now with a description", source="github_trending", stars=900)
    assert store.refresh(richer)
    after = store.get("gh:x/y")
    assert json.loads(after["metrics"])["stars"] == 900
    for col in ("last_seen", "runs_seen", "last_fetch", "first_seen"):
        assert after[col] == before[col]


# -- migration -----------------------------------------------------------------
def test_migration_backfills_runs_from_history(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)                     # a version-0 database
    t0 = now() - timedelta(days=30)
    runs = [t0, t0 + timedelta(hours=1), t0 + timedelta(days=10), t0 + timedelta(days=20)]
    for i, t in enumerate(runs):
        conn.execute("INSERT INTO runs (id, started_at) VALUES (?, ?)", (f"r{i}", t.isoformat()))

    def item(key, first, last):
        conn.execute(
            "INSERT INTO items (id, key, url, title, first_seen, last_seen) VALUES (?,?,?,?,?,?)",
            (key, key, "u", key, first.isoformat(), last.isoformat()))

    item("everywhere", t0 + timedelta(minutes=5), t0 + timedelta(days=20, minutes=5))
    item("early", t0 + timedelta(minutes=5), t0 + timedelta(hours=1, minutes=5))
    conn.commit(); conn.close()

    store = Store(path)
    assert store.schema_version == 1
    assert store.current_fetch() == 3              # 4 runs, two within 6 hours
    every, early = store.get("everywhere"), store.get("early")
    assert (every["last_fetch"], every["runs_seen"]) == (3, 3)
    assert (early["last_fetch"], early["runs_seen"]) == (1, 1)
    Store(path)                                    # reopening is a no-op
    assert Store(path).schema_version == 1


def test_starting_an_existing_run_keeps_its_start_and_stats(store):
    # `radar brief --run <id>` calls start_run on a run that already exists.
    store.start_run("r1")
    first = store.conn.execute("SELECT started_at FROM runs WHERE id='r1'").fetchone()[0]
    store.finish_run("r1", {"_merged": 10})
    store.start_run("r1")
    row = store.conn.execute("SELECT started_at, stats FROM runs WHERE id='r1'").fetchone()
    assert row[0] == first and json.loads(row[1]) == {"_merged": 10}
