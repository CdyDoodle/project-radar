"""Publish the local dashboard, digest and corpus to GitHub Pages.

Your machine is the source of truth: briefs can only be generated here
(they need a Claude Code login), so the site is published from here too.

What lands on the `gh-pages` branch:

    index.html          the dashboard just built
    digest.md           the newest markdown digest
    radar.db            the corpus, so it can be inspected or restored
    archive/<stamp>.html  the page this publish replaced
    archive/index.html    a dated list of every archived page
    .nojekyll

The branch is one parentless commit, force-pushed every time. The dashboard
and database are a few MB rewritten per publish; history would add that much
each time, forever. The archive files in the tree are the history worth
keeping.
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from radar import archive
from radar.config import Config
from radar.store import Store

BRANCH = "gh-pages"


class PublishError(RuntimeError):
    pass


class PublishConflict(PublishError):
    """The published corpus has runs the local one has never seen."""


@dataclass
class Plan:
    remote: str
    site_url: str | None
    files: dict[str, int] = field(default_factory=dict)   # path -> bytes
    archived_as: str | None = None
    snapshots: int = 0
    remote_runs: int = 0
    pushed: bool = False


# -- git ---------------------------------------------------------------------
def _git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        # Never echo a URL that might carry a token.
        err = re.sub(r"https://[^@\s]+@", "https://***@", proc.stderr.strip())
        raise PublishError(f"git {args[0]} failed: {err[:400]}")
    return proc


def origin_url(home: Path) -> str:
    return _git("remote", "get-url", "origin", cwd=home).stdout.strip()


def pages_url(remote: str) -> str | None:
    """https://owner.github.io/repo/ for a GitHub remote, else None."""
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", remote)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    if repo.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner.lower()}.github.io/"
    return f"https://{owner.lower()}.github.io/{repo}/"


def _rmtree(path: Path) -> None:
    # git marks pack files read-only, which rmtree cannot delete on Windows.
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerror)


# -- the corpus guard ----------------------------------------------------------
def _run_ids(path: Path) -> set[str]:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return {r[0] for r in conn.execute("SELECT id FROM runs")}
        finally:
            conn.close()
    except sqlite3.Error:
        return set()


def check_corpus(local: Store, published_db: Path) -> int:
    """Refuse to overwrite a published corpus holding runs we don't have.

    Returns how many runs the published copy has. Raises PublishConflict if
    some of them are missing locally -- publishing would silently discard
    them (a CI run, or a publish from another machine).
    """
    remote = _run_ids(published_db)
    mine = {r[0] for r in local.conn.execute("SELECT id FROM runs")}
    missing = sorted(remote - mine)
    if missing:
        raise PublishConflict(
            f"the published corpus has {len(missing)} run(s) your local database "
            f"doesn't (newest: {missing[-1]}). Publishing would discard them. "
            "Rerun with --force to publish anyway.")
    return len(remote)


# -- publish -----------------------------------------------------------------
def publish(cfg: Config, store: Store, *, remote: str | None = None,
            dry_run: bool = False, force: bool = False) -> Plan:
    out = cfg.out_dir
    page = out / "index.html"
    digests = sorted(out.glob("digest-*.md"), key=lambda p: p.stat().st_mtime)
    if not page.exists() or not digests:
        raise PublishError(f"nothing to publish in {out}; run `radar report` first")

    remote = remote or origin_url(cfg.home)
    plan = Plan(remote=remote, site_url=pages_url(remote))

    tmp = Path(tempfile.mkdtemp(prefix="radar-publish-"))
    site = tmp / "site"
    try:
        has_branch = _git("ls-remote", "--exit-code", "--heads", remote, BRANCH,
                          check=False).returncode == 0
        if has_branch:
            _git("clone", "--quiet", "--branch", BRANCH, "--single-branch", "--depth", "1",
                 remote, str(site))
            _rmtree(site / ".git")        # start a fresh, parentless history
        else:
            site.mkdir()

        if (site / "radar.db").exists() and not force:
            plan.remote_runs = check_corpus(store, site / "radar.db")

        (site / "archive").mkdir(exist_ok=True)
        if (site / "index.html").exists():
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
            plan.archived_as = f"archive/{stamp}.html"
            shutil.copy2(site / "index.html", site / plan.archived_as)

        shutil.copy2(page, site / "index.html")
        shutil.copy2(digests[-1], site / "digest.md")
        # The backup API gives a consistent copy even with WAL pages pending.
        (site / "radar.db").unlink(missing_ok=True)
        dst = sqlite3.connect(site / "radar.db")
        try:
            store.conn.backup(dst)
        finally:
            dst.close()
        (site / ".nojekyll").touch()
        plan.snapshots = archive.build(site / "archive")

        for p in sorted(site.rglob("*")):
            if p.is_file():
                plan.files[p.relative_to(site).as_posix()] = p.stat().st_size

        if dry_run:
            return plan

        _git("init", "--quiet", "-b", BRANCH, cwd=site)
        ident = []
        if not _git("config", "user.email", cwd=site, check=False).stdout.strip():
            ident = ["-c", "user.name=radar", "-c", "user.email=radar@localhost"]
        _git("add", "-A", cwd=site)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        _git(*ident, "commit", "--quiet", "-m", f"radar snapshot {stamp}", cwd=site)
        _git("push", "--quiet", "--force", remote, f"HEAD:{BRANCH}", cwd=site)
        plan.pushed = True
        return plan
    finally:
        _rmtree(tmp)
