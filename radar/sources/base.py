"""Source protocol.

A Source turns one corner of the internet into Items. Adding X/Twitter later
means writing one of these and registering it -- nothing else changes.
"""
from __future__ import annotations

import logging
from typing import Protocol

from radar.config import Config
from radar.http import Http
from radar.models import Item

log = logging.getLogger("radar.sources")


class Source(Protocol):
    name: str

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        ...


_REGISTRY: dict[str, type] = {}


def register(cls):
    _REGISTRY[cls.name] = cls
    return cls


def enabled_sources(cfg: Config) -> list:
    """Instantiate every source not explicitly disabled in config."""
    out = []
    for name, cls in _REGISTRY.items():
        conf = cfg.get(f"sources.{name}", {}) or {}
        if conf.get("enabled", True):
            out.append(cls())
    return out


def all_source_names() -> list[str]:
    return sorted(_REGISTRY)
