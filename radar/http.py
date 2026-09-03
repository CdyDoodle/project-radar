"""Shared HTTP with retries and an on-disk GET cache.

The cache exists so that re-running `fetch` while tuning weights doesn't burn
GitHub's search quota (30 req/min) or hammer anyone's free API.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("radar.http")

USER_AGENT = "radar/0.1 (+https://github.com/topics/project-discovery)"
GITHUB_API = "https://api.github.com"


class Http:
    def __init__(self, cache_dir: Path, ttl: int = 1800, token: str | None = None):
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.token = token
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        retry = Retry(
            total=3, backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"], respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    # -- cache -----------------------------------------------------------
    def _cache_file(self, url: str, headers: dict | None) -> Path:
        h = hashlib.sha1(
            (url + json.dumps(headers or {}, sort_keys=True)).encode()
        ).hexdigest()[:20]
        return self.cache_dir / f"{h}.cache"

    def get(self, url: str, *, headers: dict | None = None, params: dict | None = None,
            cache: bool = True, ttl: int | None = None) -> requests.Response | None:
        if params:
            req = requests.Request("GET", url, params=params).prepare()
            url = req.url
        path = self._cache_file(url, headers)
        ttl = self.ttl if ttl is None else ttl
        if cache and ttl > 0 and path.exists():
            if time.time() - path.stat().st_mtime < ttl:
                body = path.read_bytes()
                resp = requests.Response()
                resp.status_code = 200
                resp._content = body
                resp.url = url
                resp.headers["X-Radar-Cache"] = "hit"
                return resp
        try:
            resp = self.session.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            log.warning("GET %s failed: %s", url, exc)
            return None
        if resp.status_code >= 400:
            log.warning("GET %s -> %s %s", url, resp.status_code, resp.text[:180])
            return None
        if cache and ttl > 0:
            path.write_bytes(resp.content)
        return resp

    def json(self, url: str, **kw) -> dict | list | None:
        resp = self.get(url, **kw)
        if resp is None:
            return None
        try:
            return resp.json()
        except ValueError:
            log.warning("non-JSON body from %s", url)
            return None

    # -- github ----------------------------------------------------------
    def gh(self, path: str, *, accept: str = "application/vnd.github+json",
           params: dict | None = None, **kw):
        headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        url = path if path.startswith("http") else GITHUB_API + path
        return self.json(url, headers=headers, params=params, **kw)

    def gh_rate(self) -> dict:
        data = self.gh("/rate_limit", cache=False) or {}
        return data.get("resources", {})
