"""Real velocity from per-run snapshots."""
import json
from datetime import timedelta

from radar import rank, report
from radar.models import now
from tests.conftest import repo


def snap(store, key, run, days_ago, stars):
    store.conn.execute("INSERT OR REPLACE INTO snapshots (key, run, at, stars) VALUES (?,?,?,?)",
                       (key, run, (now() - timedelta(days=days_ago)).isoformat(), stars))
    store.conn.commit()


def test_upsert_records_one_snapshot_per_run(store):
    s = store.begin_fetch()
    store.upsert(repo("x/y", stars=100), s)
    store.upsert(repo("x/y", stars=101), s)        # same run: replaced, not added
    rows = store.snapshot_history()["gh:x/y"]
    assert len(rows) == 1 and rows[0]["stars"] == 101
    store.upsert(repo("x/y", stars=50))            # no run given (a backfill): not recorded
    assert len(store.snapshot_history()["gh:x/y"]) == 1


def test_recent_rate_needs_readings_a_day_apart():
    class R(dict):
        pass
    t = lambda d: (now() - timedelta(days=d)).isoformat()
    assert rank.recent_rate([{"at": t(0), "stars": 10}]) is None
    assert rank.recent_rate([{"at": t(0.2), "stars": 10}, {"at": t(0), "stars": 20}]) is None
    snaps = [{"at": t(10), "stars": 0}, {"at": t(4), "stars": 100}, {"at": t(0), "stars": 300}]
    assert rank.recent_rate(snaps) == 50.0        # the nearest reading >= 1 day old


def test_an_old_repo_that_just_took_off_outranks_its_lifetime_average(store, cfg):
    # A two-year-old repo: 3,650 stars is a lifetime 5/day, but it gained
    # 1,000 in the last 4 days.
    old = repo("old/breakout", stars=3650, stars_per_day=5.0, age_days=730)
    peer = [repo(f"p/{i}", stars=100 * i, stars_per_day=float(10 + i)) for i in range(10)]
    with store.tx():
        for it in [old, *peer]:
            store.upsert(it)
    snap(store, "gh:old/breakout", 1, 4, 2650)
    snap(store, "gh:old/breakout", 2, 0, 3650)
    rank.rank_all(store, cfg)
    bd = json.loads(store.get("gh:old/breakout")["breakdown"])
    assert bd["signals"] == {"stars_per_day_recent": 250.0, "accel": 50.0}
    assert bd["components"]["velocity"] > 0.9       # was bottom of the peer group at 5/day
    lanes = {l["key"]: l for l in report._highlights(store, cfg, since=None)}
    assert [i["title"] for i in lanes["breakout"]["items"]] == ["old/breakout"]
    assert "50.0x its usual pace" in lanes["breakout"]["items"][0]["reason"]["en"]


def test_a_repo_that_stalled_loses_its_velocity(store, cfg):
    faded = repo("was/hot", stars=20000, stars_per_day=200.0)
    peer = [repo(f"p/{i}", stars=100 * i, stars_per_day=float(10 + i)) for i in range(10)]
    with store.tx():
        for it in [faded, *peer]:
            store.upsert(it)
    snap(store, "gh:was/hot", 1, 7, 19990)
    snap(store, "gh:was/hot", 2, 0, 20000)          # 10 stars in a week
    rank.rank_all(store, cfg)
    bd = json.loads(store.get("gh:was/hot")["breakdown"])
    assert bd["signals"]["stars_per_day_recent"] < 2
    assert bd["components"]["velocity"] < 0.2
