"""GitHub sources: search, trending, and the watchlist.

`github_starred` is the one that answers "what are awesome engineers doing" --
it reads the recent stars of people you've chosen to follow. When several of
them independently star the same repo within a few weeks, that is a far better
signal than any trending algorithm.
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta

from bs4 import BeautifulSoup

from radar.config import Config
from radar.http import Http
from radar.models import UTC, Item, canonical_key, now
from radar.sources.base import register

log = logging.getLogger("radar.sources.github")

ISO = "%Y-%m-%dT%H:%M:%SZ"


def _parse_dt(s):
    from datetime import datetime
    if not s:
        return None
    try:
        return datetime.strptime(s, ISO).replace(tzinfo=UTC)
    except ValueError:
        return None


def _repo_item(repo: dict, source: str, evidence: str) -> Item | None:
    full = repo.get("full_name")
    if not full:
        return None
    created = _parse_dt(repo.get("created_at"))
    pushed = _parse_dt(repo.get("pushed_at"))
    stars = repo.get("stargazers_count", 0) or 0
    age_days = max((now() - created).total_seconds() / 86400, 1.0) if created else None
    metrics = {
        "stars": stars,
        "forks": repo.get("forks_count", 0) or 0,
        "open_issues": repo.get("open_issues_count", 0) or 0,
        "age_days": round(age_days, 1) if age_days else None,
        "stars_per_day": round(stars / age_days, 2) if age_days else None,
        "days_since_push": round((now() - pushed).total_seconds() / 86400, 1) if pushed else None,
        "archived": bool(repo.get("archived")),
    }
    return Item(
        key=f"gh:{full.lower()}",
        url=repo.get("html_url") or f"https://github.com/{full}",
        title=full,
        source=source,
        summary=(repo.get("description") or "").strip(),
        author=full.split("/")[0],
        lang=repo.get("language"),
        topics=[t.lower() for t in (repo.get("topics") or [])],
        created_at=created,
        metrics={k: v for k, v in metrics.items() if v is not None},
        evidence=[evidence],
    )


@register
class GitHubSearch:
    """Recently-created repos that gained traction fast."""

    name = "github_search"

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        conf = cfg.get("sources.github_search", {}) or {}
        window = int(conf.get("created_within_days", 180))
        min_stars = int(conf.get("min_stars", 150))
        per_query = int(conf.get("per_query", 40))
        queries = conf.get("queries") or ["stars:>%d" % min_stars]
        since = (now() - timedelta(days=window)).strftime("%Y-%m-%d")

        items: list[Item] = []
        for raw_q in queries:
            q = f"{raw_q} created:>{since} stars:>{min_stars}"
            data = http.gh(
                "/search/repositories",
                params={"q": q, "sort": "stars", "order": "desc",
                        "per_page": min(per_query, 100)},
            )
            if not data or "items" not in data:
                continue
            for repo in data["items"]:
                it = _repo_item(
                    repo, self.name,
                    f"GitHub search: matched `{raw_q}`, "
                    f"{repo.get('stargazers_count', 0):,} stars since {since}",
                )
                if it:
                    items.append(it)
            log.info("github_search %-28s -> %d", raw_q, len(data["items"]))
        return items


@register
class GitHubTrending:
    """Scrapes github.com/trending. No API, no key, genuinely useful."""

    name = "github_trending"
    _STARS_TODAY = re.compile(r"([\d,]+)\s+stars?\s+(today|this week|this month)")

    _PERIOD_METRIC = {"today": "stars_today", "this week": "stars_this_week",
                      "this month": "stars_this_month"}

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        conf = cfg.get("sources.github_trending", {}) or {}
        windows = conf.get("windows", ["daily", "weekly"])
        languages = conf.get("languages", [""])
        items: list[Item] = []
        for since in windows:
            for lang in languages:
                url = f"https://github.com/trending/{lang}" if lang else "https://github.com/trending"
                resp = http.get(url, params={"since": since})
                if resp is None:
                    continue
                items.extend(self.parse(resp.content, since))
                log.info("github_trending %s/%s -> %d", since, lang or "all", len(items))
        if conf.get("hydrate", True):
            items = hydrate(http, items, workers=int(conf.get("hydrate_workers", 8)))
        return items

    def parse(self, html: bytes | str, since: str) -> list[Item]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for art in soup.select("article.Box-row"):
            link = art.select_one("h2 a")
            if not link or not link.get("href"):
                continue
            full = link["href"].strip("/")
            desc_el = art.select_one("p")
            lang_el = art.select_one('[itemprop="programmingLanguage"]')
            period = ""
            metrics: dict = {"trending_windows": [since]}
            for span in art.select("span.d-inline-block.float-sm-right"):
                m = self._STARS_TODAY.search(span.get_text(" ", strip=True))
                if m:
                    period = m.group(0)
                    metrics[self._PERIOD_METRIC[m.group(2)]] = int(m.group(1).replace(",", ""))
            out.append(Item(
                key=f"gh:{full.lower()}",
                url=f"https://github.com/{full}",
                title=full,
                source=self.name,
                summary=desc_el.get_text(" ", strip=True) if desc_el else "",
                author=full.split("/")[0],
                lang=lang_el.get_text(strip=True) if lang_el else None,
                metrics=metrics,
                evidence=[f"GitHub trending ({since}){': ' + period if period else ''}"],
            ))
        return out


def hydrate(http: Http, items: list[Item], workers: int = 8) -> list[Item]:
    """Replace scraped trending rows with full API metadata.

    The trending page carries a name, a description and a language -- no
    star count, no creation date, no topics. Without them `fit`, `depth`,
    `freshness` and the `mega` penalty all score on nothing, for what was
    the second-largest bucket in the corpus. One cached API call per unique
    repo fixes that; a failed call keeps the scraped row as it was.
    """
    from concurrent.futures import ThreadPoolExecutor

    unique = list(dict.fromkeys(it.repo for it in items if it.repo))

    def one(name: str):
        return name, http.gh(f"/repos/{name}")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        meta = {name: data for name, data in pool.map(one, unique)
                if isinstance(data, dict) and data.get("full_name")}

    out = []
    for it in items:
        data = meta.get(it.repo or "")
        full = _repo_item(data, it.source, (it.evidence or [''])[0]) if data else None
        if full is None:
            out.append(it)
            continue
        full.evidence = list(it.evidence)
        full.metrics.update(it.metrics)          # keep trending_windows, stars_today
        full.summary = full.summary or it.summary
        full.lang = full.lang or it.lang
        out.append(full)
    log.info("github_trending hydrated %d/%d repos", len(meta), len(unique))
    return out


@register
class GitHubStarred:
    """What the engineers on your watchlist have starred recently."""

    name = "github_starred"

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        conf = cfg.get("sources.github_starred", {}) or {}
        users = cfg.watchlist
        if not users:
            log.info("github_starred: watchlist empty, skipping")
            return []
        window = int(conf.get("within_days", 120))
        pages = int(conf.get("pages_per_user", 1))
        cutoff = now() - timedelta(days=window)

        items: list[Item] = []
        for user in users:
            for page in range(1, pages + 1):
                data = http.gh(
                    f"/users/{user}/starred",
                    accept="application/vnd.github.star+json",
                    params={"per_page": 100, "page": page},
                )
                if not data:
                    break
                stopped = False
                for entry in data:
                    starred_at = _parse_dt(entry.get("starred_at"))
                    repo = entry.get("repo") or {}
                    if starred_at and starred_at < cutoff:
                        # The endpoint is newest-first, so we can stop early.
                        stopped = True
                        break
                    it = _repo_item(
                        repo, self.name,
                        f"@{user} starred this"
                        + (f" on {starred_at:%Y-%m-%d}" if starred_at else ""),
                    )
                    if it:
                        it.metrics["starred_by"] = [user]
                        items.append(it)
                if stopped or len(data) < 100:
                    break
            log.info("github_starred @%s -> running total %d", user, len(items))
        return items


def fetch_readme(http: Http, repo: str, max_chars: int = 8000) -> str:
    """Plain-text README for a `owner/name` repo, truncated."""
    import base64
    data = http.gh(f"/repos/{repo}/readme")
    if not data or "content" not in data:
        return ""
    try:
        text = base64.b64decode(data["content"]).decode("utf-8", "replace")
    except Exception:
        return ""
    # Strip badge spam and HTML blocks -- pure noise for the model.
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"<img[^>]*>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:max_chars]
