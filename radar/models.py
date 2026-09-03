"""Core data types. One Item per *thing in the world*, merged across sources."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

UTC = timezone.utc


def now() -> datetime:
    return datetime.now(UTC)


_TRACKING = re.compile(r"^(utm_|ref$|ref_|source$|via$|s$)", re.I)
_GH_REPO = re.compile(r"^https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)", re.I)
_ARXIV = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", re.I)
_GH_NON_REPO = {
    "features", "topics", "trending", "collections", "sponsors", "marketplace",
    "settings", "notifications", "explore", "orgs", "about", "pricing", "login",
}


def canonical_key(url: str) -> str:
    """Identity for dedupe.

    The whole point: an HN thread, a Lobsters post and a GitHub trending entry
    that all point at the same repo collapse into one Item, and that collapse is
    itself the strongest ranking signal we have.
    """
    if not url:
        return ""
    m = _ARXIV.search(url)
    if m:
        return f"arxiv:{m.group(1)}"
    m = _GH_REPO.match(url)
    if m:
        owner, repo = m.group(1), m.group(2)
        if owner.lower() not in _GH_NON_REPO:
            return f"gh:{owner.lower()}/{repo.lower().removesuffix('.git')}"
    p = urlparse(url)
    host = (p.netloc or "").lower().removeprefix("www.")
    path = (p.path or "/").rstrip("/") or "/"
    query = "&".join(
        q for q in sorted((p.query or "").split("&"))
        if q and not _TRACKING.match(q.split("=")[0])
    )
    return f"url:{urlunparse(('', host, path, '', query, '')).lstrip('/')}"


def stable_id(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


@dataclass
class Item:
    key: str
    url: str
    title: str
    source: str
    summary: str = ""
    author: str | None = None
    lang: str | None = None
    topics: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    metrics: dict = field(default_factory=dict)
    # Human-readable reasons this surfaced, accumulated as sources merge.
    evidence: list[str] = field(default_factory=list)
    sources: set[str] = field(default_factory=set)
    readme: str = ""

    def __post_init__(self) -> None:
        self.sources.add(self.source)

    @property
    def id(self) -> str:
        return stable_id(self.key)

    @property
    def repo(self) -> str | None:
        return self.key[3:] if self.key.startswith("gh:") else None

    def merge(self, other: "Item") -> None:
        """Fold another sighting of the same thing into this one."""
        self.sources |= other.sources
        self.evidence += other.evidence
        self.topics = list(dict.fromkeys(self.topics + other.topics))
        # Prefer the richer text and the more specific metadata.
        if len(other.summary) > len(self.summary):
            self.summary = other.summary
        for attr in ("author", "lang", "created_at"):
            if getattr(self, attr) in (None, "") and getattr(other, attr) is not None:
                setattr(self, attr, getattr(other, attr))
        if not self.title or (other.source == "github" and other.title):
            self.title = other.title or self.title
        for k, v in other.metrics.items():
            # Keep the largest observation of any numeric metric; union the sets.
            if isinstance(v, (int, float)) and isinstance(self.metrics.get(k), (int, float)):
                self.metrics[k] = max(self.metrics[k], v)
            elif isinstance(v, list) and isinstance(self.metrics.get(k), list):
                self.metrics[k] = sorted(set(self.metrics[k]) | set(v))
            else:
                self.metrics.setdefault(k, v)
