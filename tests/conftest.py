"""Shared fixtures: an isolated radar home with a minimal config and empty db."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from radar import config
from radar.models import Item, canonical_key, now
from radar.store import Store

CONFIG = """
[profile]
description = "test engineer"

[interests]
"inference" = 1.0
"compiler" = 1.0
"rust" = 0.7
"agent" = 0.8

[rank]
freshness_half_life_days = 45
stale_after_days = 120
mega_star_threshold = 40000
forget_after_runs = 3

[rank.diversify]
enabled = true
lambda = 0.65
theme_weight = 0.75

[rank.balance]
enabled = true
"ai-infra" = 0.30
"ai-application" = 0.40
"non-ai" = 0.30

[sources.github_starred]
users = ["alice", "bob"]

[cards]
count = 3

[translate]
# Tests never call the real Claude Code CLI; translation tests enable it
# explicitly with a fake one.
enabled = false

[storage]
db = "radar.db"
out_dir = "out"
http_cache_seconds = 0
"""


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / "config.toml").write_text(CONFIG, encoding="utf-8")
    return tmp_path


@pytest.fixture
def cfg(home: Path) -> config.Config:
    return config.load(home)


@pytest.fixture
def store(cfg) -> Store:
    return Store(cfg.db_path)


def repo(name: str, desc: str = "", *, source: str = "github_search",
         topics=(), lang: str | None = "Rust", age_days: float = 10,
         **metrics) -> Item:
    """A GitHub-shaped Item for tests."""
    return Item(
        key=f"gh:{name.lower()}", url=f"https://github.com/{name}", title=name,
        source=source, summary=desc, topics=list(topics), lang=lang,
        created_at=now() - timedelta(days=age_days), metrics=dict(metrics),
        evidence=[f"{source} saw {name}"],
    )


def link(url: str, title: str, *, source: str = "hackernews", **metrics) -> Item:
    """A bare-link Item, as HN or Lobsters would produce."""
    return Item(key=canonical_key(url), url=url, title=title, source=source,
                created_at=now() - timedelta(days=2), metrics=dict(metrics),
                evidence=[f"{source}: {title}"])
