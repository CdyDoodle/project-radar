"""`radar gaps`: papers that nobody has implemented yet -- checked, not assumed.

A strong paper with no code is the most direct kind of project there is: the
thesis is written, the gap is real, and the result is useful to everyone who
read it. The dashboard used to *assume* arXiv items had no implementation.
This checks, for the top-ranked papers:

1. Hugging Face daily papers already records a linked GitHub repo when the
   authors published one;
2. otherwise GitHub repository search for the arXiv number in a README or
   description, which is where every serious implementation cites its paper.

Results live in the item's metrics (impl_count, impl_repos, impl_checked_at)
and are rechecked after `gaps.recheck_days`. GitHub's search API allows 30
requests a minute, so uncached checks are paced.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta

from radar.config import Config
from radar.http import GITHUB_API, Http
from radar.models import UTC, now
from radar.store import Store

log = logging.getLogger("radar.gaps")

SEARCH_INTERVAL = 2.1        # seconds between uncached searches (30/min limit)
_sleep = time.sleep          # replaced in tests


def _arxiv_id(key: str) -> str:
    return key.split(":", 1)[1]


def _due(metrics: dict, recheck_days: float) -> bool:
    stamp = metrics.get("impl_checked_at")
    if not stamp:
        return True
    try:
        when = datetime.fromisoformat(stamp).astimezone(UTC)
    except ValueError:
        return True
    return now() - when > timedelta(days=recheck_days)


def search_implementations(http: Http, arxiv_id: str) -> tuple[list[str], bool]:
    """Repos citing this arXiv id, and whether the answer came from cache."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if http.token:
        headers["Authorization"] = f"Bearer {http.token}"
    resp = http.get(GITHUB_API + "/search/repositories", headers=headers,
                    params={"q": f'"{arxiv_id}" in:readme,description', "sort": "stars",
                            "per_page": 5}, ttl=86400)
    if resp is None:
        raise RuntimeError("GitHub search failed")
    data = json.loads(resp.content)
    repos = [r["full_name"] for r in data.get("items") or []
             if r.get("full_name") and is_implementation(r)]
    return repos, resp.headers.get("X-Radar-Cache") == "hit"


# Repos that cite arXiv numbers without implementing anything: curated lists,
# daily paper digests, reading notes, personal sites.
_NOT_CODE = re.compile(
    r"awesome|arxiv[-_ ]?daily|paper[-_ ]?(daily|list|digest|reading|notes)|"
    r"daily[-_ ]?papers?|reading[-_ ]?list|survey|digest|radar|\.github\.io|"
    r"curated|collection of papers|paper collection", re.I)
_NO_CODE_LANGS = {None, "", "HTML", "TeX", "CSS", "Markdown", "MDX"}


def is_implementation(repo: dict) -> bool:
    text = " ".join([repo.get("full_name") or "", repo.get("description") or ""])
    if _NOT_CODE.search(text):
        return False
    return repo.get("language") not in _NO_CODE_LANGS


def check(cfg: Config, store: Store, http: Http, limit: int | None = None,
          recheck: bool = False) -> dict:
    """Check the top papers; returns counts."""
    limit = limit or int(cfg.get("gaps.check", 25))
    recheck_days = float(cfg.get("gaps.recheck_days", 14))
    papers = [r for r in store.items(limit=2000) if r["key"].startswith("arxiv:")]
    todo = [r for r in papers if recheck or _due(json.loads(r["metrics"] or "{}"), recheck_days)]
    todo = todo[:limit]
    stats = {"checked": 0, "with_code": 0, "no_code": 0, "failed": 0}
    last_search = 0.0
    for row in todo:
        metrics = json.loads(row["metrics"] or "{}")
        repos: list[str] = []
        linked = metrics.get("hf_github_repo")
        if linked:
            repos = [linked.rstrip("/").split("github.com/")[-1]]
        else:
            wait = SEARCH_INTERVAL - (time.monotonic() - last_search)
            if wait > 0:
                _sleep(wait)
            try:
                repos, cached = search_implementations(http, _arxiv_id(row["key"]))
            except (RuntimeError, ValueError) as exc:
                log.warning("gap check failed for %s: %s", row["key"], exc)
                stats["failed"] += 1
                continue
            if not cached:
                last_search = time.monotonic()
        store.update_metrics(row["key"], {
            "impl_count": len(repos), "impl_repos": repos[:3],
            "impl_checked_at": now().isoformat(),
        })
        stats["checked"] += 1
        stats["with_code" if repos else "no_code"] += 1
    return stats


def gaps(store: Store, limit: int = 20) -> list:
    """Checked papers with no implementation, best first."""
    out = []
    for r in store.items(limit=2000):
        if not r["key"].startswith("arxiv:"):
            continue
        m = json.loads(r["metrics"] or "{}")
        if m.get("impl_checked_at") and not m.get("impl_count"):
            out.append(r)
        if len(out) >= limit:
            break
    return out
