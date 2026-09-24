"""`radar track`: once you pick a project, keep watching its space.

Choosing the project is not the end of radar's job. For a year-long project
the risk that matters is someone else shipping it first, or a paper that
changes the approach, and finding out three months late. A track is a named
set of search phrases, and every run checks three places for anything new:

1. the corpus: items matching two phrases, or every meaningful word of one;
2. GitHub: repos *created after the track started* matching a phrase;
3. arXiv: papers submitted after the track started matching a phrase.

Hits are stored once each (track_hits); the ones found in the current run are
"new" on the dashboard.
"""
from __future__ import annotations

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

from radar.config import Config
from radar.http import GITHUB_API, Http
from radar.models import UTC, canonical_key, now
from radar.rank import term_pattern
from radar.store import Store

log = logging.getLogger("radar.track")

SEARCH_INTERVAL = 2.1        # GitHub search: 30 requests a minute
ARXIV_INTERVAL = 3.1         # arXiv asks for 3 seconds between API calls
PHRASES_PER_SOURCE = 4
_sleep = time.sleep
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def add(store: Store, name: str, keywords: list[str]) -> int:
    keywords = [k.strip().lower() for k in keywords if k.strip()]
    if not keywords:
        raise ValueError("a track needs at least one search phrase")
    cur = store.conn.execute(
        "INSERT INTO tracks (name, keywords, created_at) VALUES (?,?,?)",
        (name, json.dumps(keywords), now().isoformat()))
    store.conn.commit()
    return cur.lastrowid


def tracks(store: Store, active_only: bool = True) -> list[dict]:
    sql = "SELECT * FROM tracks" + (" WHERE active = 1" if active_only else "") + " ORDER BY id"
    out = []
    for r in store.conn.execute(sql):
        d = dict(r)
        d["keywords"] = json.loads(d["keywords"])
        d["hits"] = [dict(h) for h in store.conn.execute(
            "SELECT * FROM track_hits WHERE track_id = ? ORDER BY found_at DESC", (r["id"],))]
        out.append(d)
    return out


def find(store: Store, name: str) -> dict | None:
    for t in tracks(store, active_only=False):
        if t["name"].lower() == name.lower() or str(t["id"]) == name:
            return t
    return None


def stop(store: Store, name: str) -> bool:
    t = find(store, name)
    if not t:
        return False
    store.conn.execute("UPDATE tracks SET active = 0 WHERE id = ?", (t["id"],))
    store.conn.commit()
    return True


def _record(store: Store, track_id: int, key: str, url: str, title: str, reason: str) -> bool:
    cur = store.conn.execute(
        "INSERT OR IGNORE INTO track_hits (track_id, key, url, title, reason, found_at, run) "
        "VALUES (?,?,?,?,?,?,?)",
        (track_id, key, url, title, reason, now().isoformat(), store.current_fetch()))
    return cur.rowcount > 0


def words(phrase: str) -> list[str]:
    """The meaningful words of a search phrase."""
    from radar.diversify import STOP
    return [w for w in re.findall(r"[a-z0-9][a-z0-9+#.-]*", phrase.lower())
            if len(w) > 2 and w not in STOP]


def phrase_hit(phrase: str, text: str, full: bool = False) -> bool:
    """Most of a phrase's words present as whole words (all of them if `full`).

    Search phrases are queries ("SCIP oracle tree-sitter call graph precision
    recall"), not exact strings: word order and filler vary.
    """
    ws = words(phrase)
    if not ws:
        return False
    need = len(ws) if full or len(ws) == 1 else max(2, -(-len(ws) * 3 // 5))
    return sum(1 for w in ws if term_pattern(w).search(text)) >= need


def match_corpus(store: Store, track: dict) -> int:
    """Items matching two phrases, or all the words of one."""
    phrases = track["keywords"]
    added = 0
    for r in store.items():
        title = (r["title"] or "").lower()
        text = " ".join([title, (r["summary"] or "").lower(),
                         " ".join(json.loads(r["topics"] or "[]"))])
        hit = [k for k in phrases if phrase_hit(k, text)]
        whole = [k for k in phrases if phrase_hit(k, text, full=True) and len(words(k)) >= 2]
        if len(hit) >= 2 or whole:
            reason = "in radar: matches " + ", ".join(sorted(set(hit)))
            added += _record(store, track["id"], r["key"], r["url"], r["title"], reason)
    return added


def _paced(state: dict, key: str = "github", interval: float = SEARCH_INTERVAL) -> None:
    wait = interval - (time.monotonic() - state.get(key, 0.0))
    if wait > 0:
        _sleep(wait)
    state[key] = time.monotonic()


def search_github(http: Http, store: Store, track: dict, state: dict, per_term: int = 10) -> int:
    since = track["created_at"][:10]
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if http.token:
        headers["Authorization"] = f"Bearer {http.token}"
    added = 0
    for kw in track["keywords"][:PHRASES_PER_SOURCE]:
        ws = words(kw)[:5]
        if not ws:
            continue
        _paced(state)
        resp = http.get(GITHUB_API + "/search/repositories", headers=headers,
                        params={"q": " ".join(ws) + f" created:>={since}", "sort": "stars",
                                "per_page": per_term}, ttl=3600)
        if resp is None:
            continue
        for repo in json.loads(resp.content).get("items") or []:
            full = repo.get("full_name")
            if not full or repo.get("fork"):
                continue
            stars = repo.get("stargazers_count") or 0
            reason = (f"new on GitHub since you started ({repo.get('created_at', '')[:10]}), "
                      f"matches “{kw}”, {stars} stars")
            added += _record(store, track["id"], f"gh:{full.lower()}",
                             repo.get("html_url") or f"https://github.com/{full}",
                             f"{full}: {(repo.get('description') or '')[:120]}", reason)
    return added


def search_arxiv(http: Http, store: Store, track: dict, state: dict | None = None,
                 per_term: int = 10) -> int:
    since = datetime.fromisoformat(track["created_at"]).astimezone(UTC)
    state = state if state is not None else {}
    added = 0
    for kw in track["keywords"][:PHRASES_PER_SOURCE]:
        ws = words(kw)[:4]
        if not ws:
            continue
        _paced(state, "arxiv", ARXIV_INTERVAL)
        resp = http.get("http://export.arxiv.org/api/query",
                        params={"search_query": " AND ".join(f"all:{w}" for w in ws),
                                "sortBy": "submittedDate", "sortOrder": "descending",
                                "max_results": per_term}, ttl=3600)
        if resp is None:
            continue
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            continue
        for entry in root.findall("a:entry", ATOM):
            link = (entry.findtext("a:id", "", ATOM) or "").strip()
            title = re.sub(r"\s+", " ", entry.findtext("a:title", "", ATOM) or "").strip()
            stamp = (entry.findtext("a:published", "", ATOM) or "").strip()
            try:
                published = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            if published < since or not link:
                continue
            reason = f"new paper ({published:%Y-%m-%d}), matches “{kw}”"
            added += _record(store, track["id"], canonical_key(link), link, title, reason)
    return added


def check_all(cfg: Config, store: Store, http: Http) -> dict:
    """Run every active track. Returns {track name: new hits}."""
    state: dict = {}
    out = {}
    for t in tracks(store):
        n = match_corpus(store, t)
        if cfg.get("track.search_github", True):
            n += search_github(http, store, t, state)
        if cfg.get("track.search_arxiv", True):
            n += search_arxiv(http, store, t, state)
        store.conn.commit()
        out[t["name"]] = n
    return out


def new_hits(track: dict, run: int) -> list[dict]:
    return [h for h in track["hits"] if h["run"] == run]
