"""`radar watch --suggest`: find engineers whose taste matches your watchlist.

The watchlist is the most important signal in radar and the only one kept by
hand. Two cheap, independent signs that someone belongs on it:

1. several of the engineers you already watch follow them;
2. what they starred recently overlaps with what your watchlist starred or
   is building (the corpus already knows that set).

Candidates come from (1); the strongest are then checked for (2), and both
counts are shown with the overlapping repos as evidence. Around 40 API calls.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from radar.config import Config
from radar.http import Http
from radar.models import now
from radar.sources.github import _parse_dt
from radar.store import Store

log = logging.getLogger("radar.watch")


@dataclass
class Candidate:
    login: str
    followed_by: list[str]
    overlap: list[str] = field(default_factory=list)
    recent_stars: int = 0
    name: str = ""
    bio: str = ""
    followers: int = 0

    @property
    def score(self) -> float:
        return len(self.followed_by) + 0.5 * len(self.overlap)


def watched_repos(store: Store, top: int = 300) -> set[str]:
    """Repos that define your taste: what the watchlist starred or works on,
    plus the repos radar currently ranks highest."""
    out = set()
    for r in store.items(include_forgotten=True):
        m = json.loads(r["metrics"] or "{}")
        if r["key"].startswith("gh:") and (m.get("starred_by") or m.get("worked_on_by")):
            out.add(r["key"][3:])
    ranked = [r for r in store.items(limit=top * 2) if r["key"].startswith("gh:")][:top]
    out |= {r["key"][3:] for r in ranked}
    return out


def suggest(cfg: Config, store: Store, http: Http, limit: int = 10,
            min_followers: int = 2, check_top: int = 20) -> list[Candidate]:
    users = cfg.watchlist
    watched = {u.lower() for u in users}
    followed_by: dict[str, set[str]] = defaultdict(set)
    for u in users:
        for page in (1, 2):
            data = http.gh(f"/users/{u}/following", params={"per_page": 100, "page": page})
            if not isinstance(data, list) or not data:
                break
            for f in data:
                login = f.get("login")
                if login and login.lower() not in watched and f.get("type", "User") == "User":
                    followed_by[login].add(u)
            if len(data) < 100:
                break

    everyone = sorted(followed_by.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    strong = [c for c, v in everyone if len(v) >= min_followers]
    # Watchlists that share few follows leave almost nobody at two or more.
    # Then widen to people followed by one watcher, but only keep those whose
    # stars actually overlap -- a single follow alone says little.
    widened = len(strong) < 5
    pool = (strong + [c for c, v in everyone if len(v) < min_followers])[:check_top if not widened else 60]
    cands = [Candidate(login=c, followed_by=sorted(followed_by[c])) for c in pool]

    ours = watched_repos(store)
    cutoff = now() - timedelta(days=int(cfg.get("sources.github_starred.within_days", 120)))

    def inspect(c: Candidate) -> Candidate:
        stars = http.gh(f"/users/{c.login}/starred",
                        accept="application/vnd.github.star+json",
                        params={"per_page": 100})
        if isinstance(stars, list):
            recent = [s for s in stars if (_parse_dt(s.get("starred_at")) or now()) >= cutoff]
            c.recent_stars = len(recent)
            names = {((s.get("repo") or {}).get("full_name") or "").lower() for s in recent}
            c.overlap = sorted(n for n in names if n in ours)
        return c

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex:
        cands = list(ex.map(inspect, cands))
    cands = [c for c in cands
             if len(c.followed_by) >= min_followers or len(c.overlap) >= 2]
    cands.sort(key=lambda c: (-c.score, -len(c.overlap), c.login.lower()))
    cands = cands[:limit]
    for c in cands:
        prof = http.gh(f"/users/{c.login}")
        if isinstance(prof, dict):
            c.name = prof.get("name") or ""
            c.bio = (prof.get("bio") or "").strip()
            c.followers = int(prof.get("followers") or 0)
    return cands


def add(cfg: Config, logins: list[str]) -> list[str]:
    from radar import configedit
    return configedit.append_to_array(cfg.home / "config.toml", "sources.github_starred",
                                      "users", logins)
