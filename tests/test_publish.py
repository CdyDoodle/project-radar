"""`radar publish` against a local bare repository. Nothing touches GitHub."""
import sqlite3
import subprocess

import pytest

from radar import publish as pub
from radar import report
from tests.test_report import seed


@pytest.fixture(autouse=True)
def git_identity(monkeypatch):
    for var, val in [("GIT_AUTHOR_NAME", "t"), ("GIT_AUTHOR_EMAIL", "t@t"),
                     ("GIT_COMMITTER_NAME", "t"), ("GIT_COMMITTER_EMAIL", "t@t")]:
        monkeypatch.setenv(var, val)


@pytest.fixture
def remote(tmp_path):
    path = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--quiet", "--bare", str(path)], check=True)
    return str(path)


def git(remote, *args):
    return subprocess.run(["git", "--git-dir", remote, *args], capture_output=True,
                          text=True, check=True).stdout


def branch_files(remote):
    return set(git(remote, "ls-tree", "-r", "--name-only", "gh-pages").split())


def built(store, cfg):
    seed(store, cfg)
    report.build(cfg, store, run_id="r1")


def test_first_publish_creates_the_site(store, cfg, remote):
    built(store, cfg)
    plan = pub.publish(cfg, store, remote=remote)
    assert plan.pushed and plan.archived_as is None
    assert branch_files(remote) == {".nojekyll", "archive/index.html", "digest.md",
                                    "index.html", "radar.db"}


def test_republish_archives_the_old_page_and_keeps_one_commit(store, cfg, remote):
    built(store, cfg)
    pub.publish(cfg, store, remote=remote)
    plan = pub.publish(cfg, store, remote=remote)
    assert plan.archived_as and plan.archived_as in branch_files(remote)
    assert plan.snapshots == 1
    # The guard opened the old published db; none of its side files may ship.
    assert not {"radar.db-wal", "radar.db-shm"} & branch_files(remote)
    # History never grows: one parentless commit, every time.
    assert git(remote, "rev-list", "--count", "gh-pages").strip() == "1"


def test_published_db_is_a_consistent_copy(store, cfg, remote, tmp_path):
    built(store, cfg)
    pub.publish(cfg, store, remote=remote)
    out = tmp_path / "copy.db"
    out.write_bytes(subprocess.run(["git", "--git-dir", remote, "show", "gh-pages:radar.db"],
                                   capture_output=True, check=True).stdout)
    conn = sqlite3.connect(out)
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 6
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_refuses_to_discard_runs_it_does_not_have(store, cfg, remote):
    built(store, cfg)
    pub.publish(cfg, store, remote=remote)
    store.conn.execute("DELETE FROM runs WHERE id = 'r1'")   # published has r1, local not
    store.conn.commit()
    with pytest.raises(pub.PublishConflict, match="1 run"):
        pub.publish(cfg, store, remote=remote)
    assert pub.publish(cfg, store, remote=remote, force=True).pushed


def test_unreachable_remote_publishes_nothing(store, cfg, remote, monkeypatch):
    built(store, cfg)
    pub.publish(cfg, store, remote=remote)
    tip = git(remote, "rev-parse", "gh-pages")
    real = pub._git

    def flaky(*args, **kw):
        if args[0] == "ls-remote":                 # e.g. a network or credential failure
            class P: returncode = 128
            return P()
        return real(*args, **kw)

    monkeypatch.setattr(pub, "_git", flaky)
    with pytest.raises(pub.PublishError, match="nothing was published"):
        pub.publish(cfg, store, remote=remote)
    assert git(remote, "rev-parse", "gh-pages") == tip   # the live site is untouched


def test_missing_branch_is_created(store, cfg, remote):
    built(store, cfg)
    assert not pub.branch_exists(remote)
    pub.publish(cfg, store, remote=remote)
    assert pub.branch_exists(remote)


def test_dry_run_pushes_nothing(store, cfg, remote):
    built(store, cfg)
    plan = pub.publish(cfg, store, remote=remote, dry_run=True)
    assert not plan.pushed and "index.html" in plan.files
    assert git(remote, "branch", "--list").strip() == ""


def test_nothing_to_publish_is_an_error(store, cfg, remote):
    with pytest.raises(pub.PublishError, match="radar report"):
        pub.publish(cfg, store, remote=remote)


@pytest.mark.parametrize("remote,url", [
    ("https://github.com/CdyDoodle/project-radar.git", "https://cdydoodle.github.io/project-radar/"),
    ("git@github.com:CdyDoodle/project-radar.git", "https://cdydoodle.github.io/project-radar/"),
    ("https://github.com/me/me.github.io", "https://me.github.io/"),
    ("/tmp/origin.git", None),
])
def test_pages_url(remote, url):
    assert pub.pages_url(remote) == url


def test_archive_is_thinned_to_one_page_a_week_after_keep_days(tmp_path):
    from datetime import datetime, timedelta, timezone
    from radar import archive
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    names = []
    for days_ago in range(0, 70, 2):                       # a page every other day
        when = now - timedelta(days=days_ago)
        name = when.strftime("%Y-%m-%d-%H%M") + ".html"
        (tmp_path / name).write_text("x"); names.append((days_ago, name))
    (tmp_path / "index.html").write_text("index")
    removed = archive.prune(tmp_path, keep_days=30, now=now)
    kept = {p.name for p in tmp_path.glob("*.html")}
    recent = [n for d, n in names if d <= 30]
    assert all(n in kept for n in recent)                  # nothing recent touched
    older = [n for d, n in names if d > 30]
    assert 0 < len([n for n in older if n in kept]) < len(older)
    weeks = {datetime.strptime(n[:10], "%Y-%m-%d").isocalendar()[:2]
             for n in older if n in kept}
    assert len(weeks) == len([n for n in older if n in kept])   # one per week
    assert "index.html" in kept and removed and archive.prune(tmp_path, 30, now) == []
