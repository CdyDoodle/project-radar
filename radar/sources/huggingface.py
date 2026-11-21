"""Hugging Face: trending models and Spaces.

Small-model work surfaces here before it reaches GitHub, if it ever does: a
decision model or a 4M-parameter TTS is published as weights and a model
card, and its GitHub repo (when there is one) has a few dozen stars. The
public API needs no account.

Three listings, all sorted by trending score:

1. models overall -- the big releases everyone is talking about;
2. models up to `small_max` parameters -- the small end, which the overall
   list buries under the big releases;
3. Spaces -- running demos and apps, often one person's project.

Items keep their huggingface.co URL as the key, so an HN post linking to the
same model merges with it.
"""
from __future__ import annotations

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from radar.config import Config
from radar.http import Http
from radar.models import UTC, Item, canonical_key
from radar.sources.base import register

log = logging.getLogger("radar.sources.huggingface")

API = "https://huggingface.co/api"
SITE = "https://huggingface.co"
MODEL_FIELDS = ["author", "likes", "downloads", "trendingScore", "createdAt",
                "pipeline_tag", "library_name", "tags", "safetensors"]
SPACE_FIELDS = ["author", "likes", "trendingScore", "createdAt", "sdk", "cardData"]
CARD_TTL = 7 * 86400          # model cards change rarely; refetching each run is waste
OWNER_TTL = 30 * 86400

# Tags that describe hosting, licensing or provenance rather than the model.
_NOISE_TAG = re.compile(r"^(region|license|base_model|dataset|arxiv|doi|deploy|"
                        r"endpoints|autotrain|template|co2|text-generation-inference)\b")
_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([KMB])?\s*$", re.I)


def parse_size(text: str | int | None) -> int | None:
    """'3B' -> 3_000_000_000; plain numbers pass through."""
    if text is None or isinstance(text, int):
        return text
    m = _SIZE.match(str(text))
    if not m:
        return None
    return int(float(m.group(1)) * {"K": 1e3, "M": 1e6, "B": 1e9}.get((m.group(2) or "").upper(), 1))


def size_label(params: int) -> str:
    """4_500_000 -> '4.5M', 1_720_000_000 -> '1.7B': the form themes.py reads."""
    if params >= 1e9:
        return f"{params / 1e9:.1f}".rstrip("0").rstrip(".") + "B"
    if params >= 1e6:
        return f"{params / 1e6:.1f}".rstrip("0").rstrip(".") + "M"
    return f"{params / 1e3:.0f}K"


def card_description(card: str, limit: int = 400) -> str:
    """The first real paragraph of a model card: no front matter, headings,
    badges, tables, HTML or code."""
    text = re.sub(r"\A---\n.*?\n---\n", "", card or "", flags=re.S)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    for block in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in block.strip().splitlines()]
        lines = [ln for ln in lines if ln and not ln.startswith(("#", "|", "!", "[!", ">"))
                 and ln.count("|") < 2]                        # tables and link bars
        para = " ".join(lines)
        para = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", para)        # links keep their text
        para = re.sub(r"[*_`]+", "", para)
        para = re.sub(r"\s+", " ", para).strip()
        if len(re.findall(r"[A-Za-z一-鿿]", para)) >= 40:
            return para[:limit].rsplit(" ", 1)[0] + ("…" if len(para) > limit else "")
    return ""


def _when(stamp: str | None):
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _topics(entry: dict) -> list[str]:
    tags = [t.lower() for t in entry.get("tags") or [] if not _NOISE_TAG.match(t.lower())]
    if entry.get("pipeline_tag"):
        tags.insert(0, entry["pipeline_tag"].lower())
    return list(dict.fromkeys(t for t in tags if len(t) > 2 and ":" not in t))[:12]


@register
class HFModels:
    """Trending Hugging Face models (overall and small) and Spaces."""

    name = "hf_models"

    def fetch(self, cfg: Config, http: Http) -> list[Item]:
        conf = cfg.get("sources.hf_models", {}) or {}
        min_likes = int(conf.get("min_likes", 20))
        small_max = parse_size(conf.get("small_max", "3B")) or 3_000_000_000
        listings = [("trending", int(conf.get("trending", 60)), {}),
                    ("small", int(conf.get("small", 60)),
                     {"num_parameters": f"min:0,max:{size_label(small_max)}"})]

        seen: dict[str, dict] = {}
        for label, limit, extra in listings:
            if limit <= 0:
                continue
            data = http.json(f"{API}/models", params={
                "sort": "trendingScore", "direction": -1, "limit": limit,
                "expand[]": MODEL_FIELDS, **extra})
            if not isinstance(data, list):
                log.warning("hf_models: no answer for the %s listing", label)
                continue
            for entry in data:
                mid = entry.get("id") or ""
                # An empty shell (no task, no library, no weights) farming likes.
                substance = entry.get("pipeline_tag") or entry.get("library_name") or entry.get("safetensors")
                if mid and substance and (entry.get("likes") or 0) >= min_likes:
                    seen.setdefault(mid, {**entry, "_listing": label})
            log.info("hf_models %s -> %d", label, len(data))

        workers = int(conf.get("workers", 8))
        card_chars = int(cfg.get("cards.readme_chars", 8000))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            cards = dict(zip(seen, pool.map(
                lambda mid: self._card(http, mid, card_chars), seen)))
        items = [self._model_item(e, cards.get(mid, "")) for mid, e in seen.items()]

        n_spaces = int(conf.get("spaces", 30))
        if n_spaces > 0:
            data = http.json(f"{API}/spaces", params={
                "sort": "trendingScore", "direction": -1, "limit": n_spaces,
                "expand[]": SPACE_FIELDS})
            for entry in data if isinstance(data, list) else []:
                if entry.get("id") and (entry.get("likes") or 0) >= min_likes:
                    items.append(self._space_item(entry))
            log.info("hf_models spaces -> %d", len(data) if isinstance(data, list) else 0)

        authors = sorted({i.author for i in items if i.author})
        with ThreadPoolExecutor(max_workers=workers) as pool:
            kinds = dict(zip(authors, pool.map(lambda a: self._owner_type(http, a), authors)))
        for it in items:
            if kinds.get(it.author):
                it.metrics["owner_type"] = kinds[it.author]
        return items

    # -- pieces ---------------------------------------------------------------
    @staticmethod
    def _card(http: Http, model_id: str, max_chars: int) -> str:
        resp = http.get(f"{SITE}/{model_id}/raw/main/README.md", ttl=CARD_TTL, quiet=True)
        return resp.text[:max_chars] if resp is not None else ""

    @staticmethod
    def _owner_type(http: Http, author: str) -> str:
        """Hugging Face has no type field: a user overview exists only for people."""
        resp = http.get(f"{API}/users/{author}/overview", ttl=OWNER_TTL, quiet=True)
        return "User" if resp is not None else "Organization"

    def _model_item(self, e: dict, card: str) -> Item:
        mid = e["id"]
        url = f"{SITE}/{mid}"
        # A model whose card links its own GitHub repo (same owner/name) is the
        # same project: file it under the repo's key so the two merge instead
        # of showing up twice.
        own_repo = f"https://github.com/{mid}"
        key = (canonical_key(own_repo)
               if re.search(rf"github\.com/{re.escape(mid)}(?![\w.-])", card, re.I)
               else canonical_key(url))
        params = (e.get("safetensors") or {}).get("total")
        task = (e.get("pipeline_tag") or "").replace("-", " ")
        head = " ".join(x for x in [f"{size_label(params)}-parameter" if params else "",
                                    task, "model"] if x).strip()
        desc = card_description(card)
        summary = f"{head[0].upper()}{head[1:]}. {desc}" if desc else f"{head[0].upper()}{head[1:]}."
        likes, trend = int(e.get("likes") or 0), float(e.get("trendingScore") or 0)
        metrics = {"hf_kind": "model", "hf_likes": likes, "hf_trending": trend,
                   "hf_downloads": int(e.get("downloads") or 0), "hf_url": url}
        if params:
            metrics["params"] = int(params)
        listing = "small models" if e.get("_listing") == "small" else "models"
        return Item(
            key=key, url=url, title=mid, source=self.name,
            summary=summary, author=e.get("author") or mid.split("/")[0],
            topics=_topics(e), created_at=_when(e.get("createdAt")), metrics=metrics,
            readme=card,
            evidence=[f"Hugging Face trending {listing}: {likes} likes, "
                      f"trending score {trend:g}"],
        )

    def _space_item(self, e: dict) -> Item:
        sid = e["id"]
        url = f"{SITE}/spaces/{sid}"
        card = e.get("cardData") or {}
        title = (card.get("title") or sid).strip()
        likes, trend = int(e.get("likes") or 0), float(e.get("trendingScore") or 0)
        summary = (card.get("short_description") or "").strip()
        return Item(
            key=canonical_key(url), url=url,
            title=title if title.lower() == sid.lower() else f"{title} ({sid})",
            source=self.name, summary=summary or f"A {e.get('sdk') or ''} app on Hugging Face Spaces.",
            author=e.get("author") or sid.split("/")[0],
            topics=[t for t in [e.get("sdk"), "hf-space"] if t],
            created_at=_when(e.get("createdAt")),
            metrics={"hf_kind": "space", "hf_likes": likes, "hf_trending": trend},
            evidence=[f"Hugging Face trending Spaces: {likes} likes, trending score {trend:g}"],
        )
