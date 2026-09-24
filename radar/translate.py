"""Simplified Chinese for the content, not just the interface.

The dashboard's interface strings are bilingual in the template. The content
-- item descriptions, paper and headline titles, briefs, dives, the board
summary, track hits -- comes from GitHub, arXiv, HN and Claude in English.
This translates it through Claude Code, the same way the other passes run.

How it stays cheap and consistent:
- the page is rendered once in a recording mode, which collects exactly the
  strings it will show, so nothing unused is translated;
- translations are stored by a hash of the source text, so each string is
  translated once, ever; a later run only sends what is new;
- anything not yet translated falls back to the English original, so the
  page is never broken by a failed or skipped pass.
The English is kept: the page's language toggle switches content too.
"""
from __future__ import annotations

import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field

from radar.config import Config
from radar.store import Store

log = logging.getLogger("radar.translate")

LANG = "zh-CN"

SYSTEM = """You translate short texts from a technical dashboard into natural, fluent \
Simplified Chinese (简体中文) for Chinese software engineers.

Rules:
- Keep product, repository, library, model and paper names, code identifiers, URLs, \
numbers and units exactly as written.
- Keep standard technical terms in the form Chinese engineers actually use; many stay \
in English (KV cache, MoE, CUDA, LLM, MCP, SCIP, RAG, tokenizer, benchmark names). \
Do not invent Chinese terms nobody uses.
- Translate meaning, not word order. Do not add, drop or soften information.
- A text cut off mid-sentence stays cut off; do not complete it.
- Return exactly one translation for every id, unchanged ids."""


class Pair(BaseModel):
    id: str
    zh: str = Field(description="The Simplified Chinese translation.")


class Batch(BaseModel):
    items: list[Pair]


_CJK = re.compile(r"[一-鿿]")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
_REPO_NAME = re.compile(r"^[\w.-]+/[\w.-]+$")
_URL = re.compile(r"^\s*https?://\S+\s*$")


def key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def translatable(text: str | None) -> bool:
    """Worth sending: real prose, not a name, a URL or already Chinese."""
    if not text or len(text.strip()) < 3:
        return False
    t = text.strip()
    if _URL.match(t) or _REPO_NAME.match(t):
        return False
    if len(_LATIN_WORD.findall(t)) < 2:
        return False
    return len(_CJK.findall(t)) < 0.3 * len(t)


class Translator:
    """text -> Chinese, from the store; records misses when asked to."""

    def __init__(self, store: Store | None, record: set | None = None):
        self.store = store
        self.record = record
        self.cache: dict[str, str] = store.translations(LANG) if store is not None else {}

    def __call__(self, text: str | None) -> str | None:
        if not text:
            return None
        zh = self.cache.get(key(text))
        if zh is None and self.record is not None and translatable(text):
            self.record.add(text)
        return zh


def missing(cfg: Config, store: Store) -> list[str]:
    """Every string the current page would show that has no translation yet."""
    from radar import report
    seen: set[str] = set()
    report.build(cfg, store, record=seen)
    have = store.translations(LANG)
    return sorted(t for t in seen if key(t) not in have)


def translate_missing(cfg: Config, store: Store, texts: list[str] | None = None,
                      progress=None) -> dict:
    """Translate what the page needs and store it. Returns counts."""
    from radar.ideate import ClaudeCodeError, require_login, run_claude

    texts = missing(cfg, store) if texts is None else texts
    if not texts:
        return {"needed": 0, "translated": 0, "failed": 0}
    exe = require_login(cfg)
    size = max(1, int(cfg.get("translate.per_call", 80)))
    batches = [texts[i:i + size] for i in range(0, len(texts), size)]
    effort = cfg.get("translate.effort", "low")

    def one(batch: list[str], retry: bool = True) -> list[tuple[str, str]]:
        ids = {f"t{i}": t for i, t in enumerate(batch)}
        prompt = "Translate each text. Answer with every id.\n\n" + "\n".join(
            f"[{i}] {' '.join(t.split())}" for i, t in ids.items())
        try:
            out = run_claude(cfg, exe, SYSTEM, prompt, Batch, effort=effort)
        except ClaudeCodeError as exc:
            log.warning("translation batch failed: %s", exc)
            return []
        pairs = []
        for p in out.items:
            src = ids.get(p.id)
            if src and p.zh.strip():
                pairs.append((src, p.zh.strip()))
        # A long batch sometimes comes back with ids missing; ask once more
        # for just those rather than leaving them for the next run.
        done = {src for src, _ in pairs}
        left = [t for t in batch if t not in done]
        if left and retry:
            pairs += one(left, retry=False)
        if progress:
            progress(len(pairs))
        return pairs

    # The first batch alone: it refreshes the login token for the others.
    results = one(batches[0])
    with ThreadPoolExecutor(max_workers=max(1, int(cfg.get("translate.max_workers", 3)))) as ex:
        for pairs in ex.map(one, batches[1:]):
            results += pairs
    store.put_translations(LANG, [(key(src), src, zh) for src, zh in results])
    return {"needed": len(texts), "translated": len(results),
            "failed": len(texts) - len(results)}
