"""Scoring.

Every score is a weighted sum of components in [0, 1] minus explicit penalties,
and the full breakdown is stored so the report can always answer "why is this
here". If a ranking looks wrong, the breakdown tells you which weight to turn.
"""
from __future__ import annotations

import math
import re

from radar.config import Config
from radar.models import Item, now

# Content that trends hard and teaches a senior engineer nothing.
#
# Split deliberately. HARD patterns are unambiguous anywhere -- no legitimate
# systems project is called "awesome-x" or "leetcode-solutions". SOFT patterns
# are words that are slop in a repo name and perfectly normal in prose ("we
# give a tutorial introduction", "a handbook of methods"), so they only count
# against the title and topics, never against an abstract or README.
HARD_SLOP = [
    r"\bawesome[- ]", r"\broadmap\b", r"\bcheat[- ]?sheet", r"\bfree[- ]programming",
    r"\binterview[- ](questions|prep|guide)", r"\bcoding[- ]interview",
    r"\b(100|30|365)[- ]days?[- ]of\b", r"\bbootcamp\b",
    r"\blearn[- ](to[- ])?code\b", r"\bfor[- ]beginners\b",
    r"\bcurated list\b", r"\bebook",
    r"\bairdrop\b", r"\bcrypto[- ](bot|trading|signal)", r"\bmev[- ]bot\b",
    r"\bprompts?[- ](collection|library|list)\b", r"\bchatgpt[- ]prompts?\b",
    r"\bresume[- ](template|builder)", r"\bwallpapers?\b",
    r"\bicons?[- ]pack\b", r"\bhacktoberfest\b", r"\bleetcode\b",
    r"\bstudy[- ](plan|notes)\b",
]
SOFT_SLOP = [
    r"\btutorials?\b", r"\bcurriculum\b", r"\bhandbook\b", r"\bcollection of\b",
    r"\bdotfiles\b", r"\btelegram[- ]bot\b", r"\bexam\b", r"\bcourse\b",
    r"\bexamples?[- ]repo\b", r"\bboilerplate\b", r"\bstarter[- ]kit\b",
]
_HARD_SLOP = re.compile("|".join(HARD_SLOP), re.I)
_SOFT_SLOP = re.compile("|".join(SOFT_SLOP), re.I)

# A cheap proxy for "there is real engineering in here".
DEPTH_TOPICS = {
    "compiler", "compilers", "kernel", "operating-system", "database", "distributed",
    "distributed-systems", "consensus", "raft", "query-engine", "storage-engine",
    "virtual-machine", "jit", "runtime", "scheduler", "networking", "protocol",
    "cryptography", "zero-knowledge", "formal-verification", "type-theory",
    "static-analysis", "program-synthesis", "inference-engine", "cuda", "gpu",
    "simd", "wasm", "webassembly", "ebpf", "observability", "emulator",
    "interpreter", "parser", "garbage-collection", "concurrency", "io-uring",
}
DEPTH_LANGS = {
    "rust": 1.0, "zig": 1.0, "c": 0.9, "c++": 0.9, "go": 0.7, "ocaml": 0.9,
    "haskell": 0.9, "elixir": 0.7, "erlang": 0.8, "nim": 0.8, "julia": 0.7,
    "assembly": 1.0, "cuda": 1.0, "verilog": 1.0, "scala": 0.6, "swift": 0.5,
    "python": 0.35, "typescript": 0.3, "javascript": 0.2, "java": 0.35,
}

DEFAULT_WEIGHTS = {
    "velocity": 1.0,
    "corroboration": 1.4,
    "watchlist": 1.8,
    "fit": 1.6,
    "freshness": 0.7,
    "depth": 0.9,
}
DEFAULT_PENALTIES = {
    "slop": 2.5,
    "chatter": 1.2,
    "stale": 0.6,
    "archived": 1.5,
    "mega": 0.5,
    "seen_before": 0.3,
}


def _norm_log(value: float, ceiling: float) -> float:
    """Log-compress a count into [0, 1]. `ceiling` is roughly 'as good as it gets'."""
    if not value or value <= 0:
        return 0.0
    return min(1.0, math.log1p(value) / math.log1p(ceiling))


def _text_of(item: Item) -> str:
    return " ".join([
        item.title or "", item.summary or "", " ".join(item.topics),
        item.lang or "", (item.readme or "")[:2500],
    ]).lower()


VELOCITY_METRICS = ("stars_per_day", "hn_points", "lobsters_score")


class Corpus:
    """Corpus-relative context for scoring.

    A fixed velocity ceiling collapses: capping stars/day at 40 made a 39/day
    repo and a 658/day repo score identically, which pinned a sixth of the top
    50 at exactly 1.00 and destroyed all ordering among whatever category was
    hottest that week. Percentile-within-metric is unit-free, self-calibrating,
    and keeps the spread.
    """

    def __init__(self, items: list[Item] | None = None):
        self.dists: dict[str, list[float]] = {}
        if items:
            for name in VELOCITY_METRICS:
                vals = sorted(
                    float(i.metrics[name]) for i in items
                    if isinstance(i.metrics.get(name), (int, float)) and i.metrics[name] > 0
                )
                if len(vals) >= 8:  # too few to be a distribution
                    self.dists[name] = vals

    def percentile(self, name: str, value: float) -> float | None:
        vals = self.dists.get(name)
        if not vals or not value or value <= 0:
            return None
        import bisect
        return bisect.bisect_left(vals, float(value)) / len(vals)


# Fallback ceilings, used only when the corpus is too small to form a distribution.
FALLBACK_CEILING = {"stars_per_day": 120, "hn_points": 700, "lobsters_score": 60}


def velocity(item: Item, corpus: Corpus | None = None) -> float:
    m = item.metrics
    parts = []
    for name in VELOCITY_METRICS:
        raw = m.get(name) or 0
        if not raw:
            continue
        pct = corpus.percentile(name, raw) if corpus else None
        parts.append(pct if pct is not None else _norm_log(raw, FALLBACK_CEILING[name]))
    if m.get("trending_windows"):
        parts.append(0.55 + 0.15 * len(m["trending_windows"]))
    return min(1.0, max(parts)) if parts else 0.0


def corroboration(item: Item) -> float:
    """Independent sources agreeing. 1 source = 0, 2 = 0.5, 3 = 0.75, 4 = 0.875."""
    n = len(item.sources)
    return 0.0 if n <= 1 else 1 - 0.5 ** (n - 1)


def watchlist(item: Item) -> float:
    watchers = item.metrics.get("starred_by") or []
    n = len(watchers)
    return 0.0 if n == 0 else 1 - 0.55 ** n


def fit(item: Item, interests: dict[str, float]) -> float:
    if not interests:
        return 0.0
    text = _text_of(item)
    total = sum(abs(w) for w in interests.values()) or 1.0
    hit = 0.0
    for term, weight in interests.items():
        if term in text:
            hit += weight
    return max(0.0, min(1.0, hit / (total * 0.35)))


def freshness(item: Item, half_life_days: float) -> float:
    if not item.created_at:
        return 0.35
    age = max((now() - item.created_at).total_seconds() / 86400, 0.0)
    return 0.5 ** (age / max(half_life_days, 1.0))


def depth(item: Item) -> float:
    topical = len(set(item.topics) & DEPTH_TOPICS)
    lang = DEPTH_LANGS.get((item.lang or "").lower(), 0.3)
    text = _text_of(item)
    keyword_hits = sum(1 for t in DEPTH_TOPICS if t.replace("-", " ") in text)
    if item.key.startswith("arxiv:"):
        return max(0.75, min(1.0, 0.75 + 0.05 * keyword_hits))
    return min(1.0, 0.45 * lang + 0.25 * min(topical, 2) + 0.06 * min(keyword_hits, 5))


def penalties(item: Item, cfg: Config, row=None) -> dict[str, float]:
    out: dict[str, float] = {}
    name_and_tags = " ".join([item.title or "", " ".join(item.topics)])
    body = item.summary or ""
    if _HARD_SLOP.search(name_and_tags) or _HARD_SLOP.search(body):
        out["slop"] = 1.0
    elif _SOFT_SLOP.search(name_and_tags):
        out["slop"] = 0.6

    # A link with no code and no paper behind it. Fine to read, not a project.
    # Blog posts ride corroboration (HN + Lobsters) without carrying substance,
    # so make them earn their place on depth instead.
    if item.key.startswith("url:") and not item.metrics.get("stars"):
        out["chatter"] = max(0.0, 1.0 - depth(item) * 2.5)

    if item.metrics.get("archived"):
        out["archived"] = 1.0
    dsp = item.metrics.get("days_since_push")
    if dsp is not None and dsp > float(cfg.get("rank.stale_after_days", 120)):
        out["stale"] = min(1.0, (dsp - 120) / 365)
    stars = item.metrics.get("stars") or 0
    mega = int(cfg.get("rank.mega_star_threshold", 40000))
    if stars > mega:
        # Already famous. You can't do frontier work on something everyone found.
        out["mega"] = min(1.0, math.log1p(stars - mega) / math.log1p(mega))
    if row is not None and row["first_seen"] and row["last_seen"]:
        # Mild decay for things that have sat in the feed across many runs.
        if row["first_seen"] != row["last_seen"]:
            out["seen_before"] = 0.5
    return out


def score_item(item: Item, cfg: Config, row=None,
               corpus: Corpus | None = None) -> tuple[float, dict]:
    weights = {**DEFAULT_WEIGHTS, **(cfg.get("rank.weights", {}) or {})}
    pen_w = {**DEFAULT_PENALTIES, **(cfg.get("rank.penalties", {}) or {})}
    half_life = float(cfg.get("rank.freshness_half_life_days", 45))

    comps = {
        "velocity": velocity(item, corpus),
        "corroboration": corroboration(item),
        "watchlist": watchlist(item),
        "fit": fit(item, cfg.interests),
        "freshness": freshness(item, half_life),
        "depth": depth(item),
    }
    pens = penalties(item, cfg, row)

    positive = sum(weights.get(k, 0) * v for k, v in comps.items())
    negative = sum(pen_w.get(k, 0) * v for k, v in pens.items())
    total = positive - negative

    breakdown = {
        "components": {k: round(v, 3) for k, v in comps.items()},
        "contributions": {k: round(weights.get(k, 0) * v, 3) for k, v in comps.items()},
        "penalties": {k: round(-pen_w.get(k, 0) * v, 3) for k, v in pens.items()},
        "positive": round(positive, 3),
        "negative": round(negative, 3),
        "total": round(total, 3),
    }
    return total, breakdown


def rank_all(store, cfg: Config) -> list:
    """Rescore everything in the store. Cheap -- run it after any config change."""
    rows = store.items(include_dismissed=True)
    items = [(row, store.to_item(row)) for row in rows]
    corpus = Corpus([it for _, it in items])
    with store.tx():
        for row, item in items:
            total, breakdown = score_item(item, cfg, row, corpus)
            store.set_score(row["id"], total, breakdown)
    return store.items(include_dismissed=False)


def explain(breakdown: dict) -> str:
    """One-line human summary of why something scored what it did."""
    contrib = breakdown.get("contributions", {})
    pens = breakdown.get("penalties", {})
    parts = sorted(contrib.items(), key=lambda kv: -kv[1])[:3]
    text = ", ".join(f"{k} +{v:.2f}" for k, v in parts if v > 0.01)
    if pens:
        text += "  |  " + ", ".join(f"{k} {v:.2f}" for k, v in pens.items())
    return text or "no signal"
