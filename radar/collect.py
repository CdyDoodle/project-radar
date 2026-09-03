"""Fetch every enabled source, merge duplicates, persist."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from radar.config import Config, github_token
from radar.http import Http
from radar.models import Item
from radar.sources import enabled_sources
from radar.sources.github import fetch_readme
from radar.store import Store

log = logging.getLogger("radar.collect")


def make_http(cfg: Config) -> Http:
    return Http(
        cache_dir=cfg.cache_dir,
        ttl=int(cfg.get("storage.http_cache_seconds", 1800)),
        token=github_token(),
    )


def merge_items(items: list[Item]) -> dict[str, Item]:
    """Collapse sightings of the same thing into one Item keyed by canonical id."""
    merged: dict[str, Item] = {}
    for item in items:
        if not item.key or not item.url:
            continue
        existing = merged.get(item.key)
        if existing is None:
            merged[item.key] = item
        else:
            existing.merge(item)
    return merged


def collect(cfg: Config, store: Store, http: Http | None = None) -> dict:
    http = http or make_http(cfg)
    sources = enabled_sources(cfg)
    raw: list[Item] = []
    stats: dict[str, int] = {}

    def run(src):
        try:
            got = src.fetch(cfg, http)
            return src.name, got
        except Exception as exc:  # one bad source must not kill the run
            log.warning("source %s failed: %s", src.name, exc, exc_info=True)
            return src.name, []

    with ThreadPoolExecutor(max_workers=min(6, len(sources) or 1)) as pool:
        for name, got in pool.map(run, sources):
            stats[name] = len(got)
            raw.extend(got)

    merged = merge_items(raw)
    with store.tx():
        for item in merged.values():
            store.upsert(item)

    stats["_raw"] = len(raw)
    stats["_merged"] = len(merged)
    stats["_collapsed"] = len(raw) - len(merged)
    return stats


def enrich(cfg: Config, store: Store, http: Http | None = None,
           limit: int = 25) -> int:
    """Pull READMEs for the top-ranked GitHub repos that don't have one yet."""
    http = http or make_http(cfg)
    rows = [r for r in store.items(limit=limit * 3) if r["key"].startswith("gh:")]
    todo = [r for r in rows if not (r["readme"] or "").strip()][:limit]
    if not todo:
        return 0

    def one(row):
        text = fetch_readme(http, row["key"][3:],
                            max_chars=int(cfg.get("brief.readme_chars", 8000)))
        return row["id"], text

    count = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for item_id, text in pool.map(one, todo):
            if text:
                store.set_readme(item_id, text)
                count += 1
    return count
