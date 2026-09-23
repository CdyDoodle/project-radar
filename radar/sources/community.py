"""Hacker News, Lobsters and arXiv.

These matter mostly as *corroboration*: when a repo GitHub is trending also has
an HN thread and a paper behind it, that combination is the signal. Items here
that link to a repo get the repo's canonical key and merge into it.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from radar.config import Config
from radar.http import Http
from radar.models import UTC, Item, canonical_key, now
from radar.sources.base import register

log = logging.getLogger("radar.sources.community")

HN_ITEM = "https://news.ycombinator.com/item?id={}"

_TAG = re.compile(r"<[^>]+>")


def _plain(html: str | None) -> str:
    """HN's story_text is HTML. Stored raw it renders as markup soup in the
    dashboard -- anchor tags and &#x2F; entities inline in the description."""
    if not html:
        return ""
    import html as _html
    text = _TAG.sub(" ", html)
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


@register
class HackerNews:
    """High-signal HN stories via the free Algolia index."""

    name = "hackernews"

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        conf = cfg.get("sources.hackernews", {}) or {}
        days = int(conf.get("within_days", 21))
        min_points = int(conf.get("min_points", 120))
        show_hn_min = int(conf.get("show_hn_min_points", 40))
        limit = int(conf.get("limit", 120))
        since = int((now() - timedelta(days=days)).timestamp())

        queries = [
            ("story", f"points>{min_points},created_at_i>{since}", "front page"),
            ("show_hn", f"points>{show_hn_min},created_at_i>{since}", "Show HN"),
        ]
        items: list[Item] = []
        for tag, numeric, label in queries:
            data = http.json(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={"tags": tag, "numericFilters": numeric,
                        "hitsPerPage": min(limit, 200)},
            )
            if not data:
                continue
            for hit in data.get("hits", []):
                title = (hit.get("title") or "").strip()
                if not title:
                    continue
                hn_id = hit.get("objectID")
                url = (hit.get("url") or "").strip() or HN_ITEM.format(hn_id)
                points = hit.get("points") or 0
                comments = hit.get("num_comments") or 0
                created = None
                if hit.get("created_at"):
                    try:
                        created = datetime.fromisoformat(
                            hit["created_at"].replace("Z", "+00:00")
                        ).astimezone(UTC)
                    except ValueError:
                        pass
                items.append(Item(
                    key=canonical_key(url),
                    url=url,
                    title=title,
                    source=self.name,
                    summary=_plain(hit.get("story_text"))[:1500],
                    author=hit.get("author"),
                    created_at=created,
                    metrics={"hn_points": points, "hn_comments": comments,
                             "hn_id": hn_id},
                    evidence=[f"HN {label}: {points} points, {comments} comments "
                              f"({HN_ITEM.format(hn_id)})"],
                ))
            log.info("hackernews %s -> %d", label, len(data.get("hits", [])))
        return items


@register
class Lobsters:
    """Lobste.rs skews systems/PL and has far less noise than HN."""

    name = "lobsters"

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        conf = cfg.get("sources.lobsters", {}) or {}
        pages = int(conf.get("pages", 3))
        min_score = int(conf.get("min_score", 8))
        items: list[Item] = []
        for page in range(1, pages + 1):
            data = http.json(f"https://lobste.rs/hottest.json?page={page}")
            if not isinstance(data, list):
                break
            for story in data:
                score = story.get("score") or 0
                if score < min_score:
                    continue
                url = (story.get("url") or "").strip() or story.get("short_id_url", "")
                if not url:
                    continue
                created = None
                if story.get("created_at"):
                    try:
                        created = datetime.fromisoformat(story["created_at"]).astimezone(UTC)
                    except ValueError:
                        pass
                items.append(Item(
                    key=canonical_key(url),
                    url=url,
                    title=(story.get("title") or "").strip(),
                    source=self.name,
                    summary=(story.get("description_plain") or "")[:1500],
                    author=(story.get("submitter_user") or {}).get("username")
                    if isinstance(story.get("submitter_user"), dict)
                    else story.get("submitter_user"),
                    topics=[t.lower() for t in (story.get("tags") or [])],
                    created_at=created,
                    metrics={"lobsters_score": score,
                             "lobsters_comments": story.get("comment_count", 0)},
                    evidence=[f"Lobsters: {score} points "
                              f"({story.get('comments_url', '')})"],
                ))
        log.info("lobsters -> %d", len(items))
        return items


@register
class Arxiv:
    """Recent papers in the categories you care about.

    Papers are where the genuinely hard project ideas come from -- most have no
    usable implementation, which is exactly the gap worth filling.
    """

    name = "arxiv"
    NS = {"a": "http://www.w3.org/2005/Atom"}

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        conf = cfg.get("sources.arxiv", {}) or {}
        cats = conf.get("categories", ["cs.LG", "cs.AI"])
        per_cat = int(conf.get("per_category", 40))
        days = int(conf.get("within_days", 21))
        cutoff = now() - timedelta(days=days)

        items: list[Item] = []
        for cat in cats:
            resp = http.get(
                "http://export.arxiv.org/api/query",
                params={"search_query": f"cat:{cat}", "sortBy": "submittedDate",
                        "sortOrder": "descending", "max_results": per_cat},
            )
            if resp is None:
                continue
            try:
                root = ET.fromstring(resp.content)
            except ET.ParseError:
                log.warning("arxiv: unparseable feed for %s", cat)
                continue
            for entry in root.findall("a:entry", self.NS):
                def text(tag):
                    el = entry.find(f"a:{tag}", self.NS)
                    return (el.text or "").strip() if el is not None else ""

                link = text("id")
                published = None
                if text("published"):
                    try:
                        published = datetime.fromisoformat(
                            text("published").replace("Z", "+00:00")
                        ).astimezone(UTC)
                    except ValueError:
                        pass
                if published and published < cutoff:
                    continue
                authors = [
                    (a.find("a:name", self.NS).text or "")
                    for a in entry.findall("a:author", self.NS)
                    if a.find("a:name", self.NS) is not None
                ]
                items.append(Item(
                    key=canonical_key(link),
                    url=link,
                    title=re.sub(r"\s+", " ", text("title")),
                    source=self.name,
                    summary=re.sub(r"\s+", " ", text("summary"))[:2500],
                    author=", ".join(authors[:4]) + (" et al." if len(authors) > 4 else ""),
                    topics=[cat.lower()],
                    created_at=published,
                    metrics={"arxiv_category": cat},
                    evidence=[f"arXiv {cat}, submitted {published:%Y-%m-%d}"
                              if published else f"arXiv {cat}"],
                ))
            log.info("arxiv %s -> running total %d", cat, len(items))
        return items


@register
class HFPapers:
    """Hugging Face daily papers: arXiv papers with an upvote count.

    arXiv itself carries no popularity signal, so papers could only rank on
    fit and freshness. These merge onto the same `arxiv:` key and give the
    ranker a velocity number for them. The listing also links the GitHub
    repo when one exists.
    """

    name = "hf_papers"
    URL = "https://huggingface.co/api/daily_papers"

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        conf = cfg.get("sources.hf_papers", {}) or {}
        days = int(conf.get("days", 7))
        limit = int(conf.get("per_day", 50))
        items: list[Item] = []
        for back in range(days):
            day = (now() - timedelta(days=back)).date().isoformat()
            data = http.json(self.URL, params={"date": day, "limit": limit})
            if not isinstance(data, list):
                continue
            for entry in data:
                paper = entry.get("paper") or {}
                pid = str(paper.get("id") or "").strip()
                if not pid:
                    continue
                url = f"https://arxiv.org/abs/{pid}"
                upvotes = int(paper.get("upvotes") or 0)
                published = None
                stamp = paper.get("publishedAt") or entry.get("publishedAt")
                if stamp:
                    try:
                        published = datetime.fromisoformat(
                            stamp.replace("Z", "+00:00")).astimezone(UTC)
                    except ValueError:
                        pass
                authors = [a.get("name", "") for a in paper.get("authors") or [] if a.get("name")]
                metrics: dict = {"hf_upvotes": upvotes,
                                 "hf_comments": int(entry.get("numComments") or 0)}
                if paper.get("githubRepo"):
                    metrics["hf_github_repo"] = paper["githubRepo"]
                items.append(Item(
                    key=canonical_key(url), url=url,
                    title=re.sub(r"\s+", " ", paper.get("title") or entry.get("title") or "").strip(),
                    source=self.name,
                    summary=re.sub(r"\s+", " ", paper.get("summary") or entry.get("summary") or "")[:2500],
                    author=", ".join(authors[:4]) + (" et al." if len(authors) > 4 else ""),
                    created_at=published,
                    metrics=metrics,
                    evidence=[f"Hugging Face daily papers {day}: {upvotes} upvotes"],
                ))
            log.info("hf_papers %s -> running total %d", day, len(items))
        return items


@register
class Bluesky:
    """Posts on Bluesky that link to a repo or a paper.

    The X substitute: engineering threads point at code, and the public
    search endpoint can filter posts by the domain they link to. Off by
    default -- the public API refuses some networks outright (HTTP 403 with
    "forbidden by administrative rules"), so enable it and run `radar fetch`
    once to see whether it answers from yours.
    """

    name = "bluesky"
    URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        conf = cfg.get("sources.bluesky", {}) or {}
        queries = conf.get("queries") or list(cfg.interests)[:12]
        domains = conf.get("domains") or ["github.com", "arxiv.org"]
        min_likes = int(conf.get("min_likes", 5))
        limit = min(int(conf.get("per_query", 50)), 100)
        since = (now() - timedelta(days=int(conf.get("within_days", 14)))).strftime("%Y-%m-%dT%H:%M:%SZ")

        items: list[Item] = []
        for q in queries:
            for domain in domains:
                data = http.json(self.URL, params={"q": q, "domain": domain, "sort": "top",
                                                   "since": since, "limit": limit})
                if not isinstance(data, dict):
                    continue
                for post in data.get("posts") or []:
                    likes = int(post.get("likeCount") or 0)
                    if likes < min_likes:
                        continue
                    items.extend(self._items(post, likes))
            log.info("bluesky %-24s -> running total %d", q, len(items))
        from radar.sources.github import hydrate
        return hydrate(http, items)

    def _items(self, post: dict, likes: int) -> list[Item]:
        record = post.get("record") or {}
        links: list[tuple[str, str]] = []           # (url, title)
        embed = post.get("embed") or {}
        ext = embed.get("external") or {}
        if ext.get("uri"):
            links.append((ext["uri"], ext.get("title") or ""))
        for facet in record.get("facets") or []:
            for feat in facet.get("features") or []:
                if str(feat.get("$type", "")).endswith("#link") and feat.get("uri"):
                    links.append((feat["uri"], ""))
        handle = (post.get("author") or {}).get("handle") or "?"
        rkey = str(post.get("uri") or "").rsplit("/", 1)[-1]
        post_url = f"https://bsky.app/profile/{handle}/post/{rkey}"
        created = None
        stamp = post.get("indexedAt") or record.get("createdAt")
        if stamp:
            try:
                created = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC)
            except ValueError:
                pass
        out, seen = [], set()
        for url, title in links:
            key = canonical_key(url)
            if not (key.startswith("gh:") or key.startswith("arxiv:")) or key in seen:
                continue
            seen.add(key)
            out.append(Item(
                key=key, url=url,
                title=title or (key[3:] if key.startswith("gh:") else url),
                source=self.name,
                summary=_plain(record.get("text"))[:500],
                author=handle, created_at=created,
                metrics={"bsky_likes": likes, "bsky_reposts": int(post.get("repostCount") or 0)},
                # The post text is the reason a human shared it; keep it as
                # evidence (hydration replaces summary with the repo's own).
                evidence=[f"Bluesky: {likes} likes from @{handle}: "
                          f"“{_plain(record.get('text'))[:140]}” ({post_url})"],
            ))
        return out
