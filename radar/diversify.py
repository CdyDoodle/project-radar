"""Redundancy control.

Scoring ranks items independently, so four implementations of the same idea all
score well and all reach the top -- which is exactly what happened with local
LLM inference engines. A ranked list is not the same thing as a useful list:
the fourth inference engine tells you nothing the first didn't.

This applies Maximal Marginal Relevance: walk the ranked list and discount each
candidate by how similar it is to what has already been picked. Similarity is
IDF-weighted cosine over title/description/topic tokens, so rare, meaningful
words ("trillion", "kimi", "expert") dominate and boilerplate ("open", "source",
"rust") barely registers -- plain Jaccard rates those inference engines at only
0.13 and misses them entirely.
"""
from __future__ import annotations

import bisect
import math
import re
from collections import Counter

from radar.themes import jaccard

_WORD = re.compile(r"[a-z][a-z0-9+#.-]{2,}")

# Words that carry no discriminative signal in this corpus.
STOP = {
    "the", "and", "for", "with", "that", "this", "you", "your", "from", "are",
    "was", "has", "have", "not", "but", "all", "can", "its", "our", "out",
    "use", "using", "used", "via", "new", "get", "one", "two", "any", "how",
    "open", "source", "free", "based", "simple", "fast", "easy", "small",
    "built", "build", "building", "written", "write", "make", "makes", "made",
    "support", "supports", "library", "tool", "tools", "project", "code",
    "github", "https", "http", "com", "www", "org", "repo", "repository",
    "python", "javascript", "typescript",
}


def tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in STOP}


class Similarity:
    """IDF-weighted cosine over a fixed corpus of documents."""

    def __init__(self, docs: list[str]):
        self.idf: dict[str, float] = {}
        n = max(len(docs), 1)
        df: Counter[str] = Counter()
        for doc in docs:
            df.update(tokens(doc))
        for term, count in df.items():
            # Smoothed IDF: a term in every document contributes ~nothing.
            self.idf[term] = math.log((n + 1) / (count + 1)) + 1.0

    def vector(self, text: str) -> dict[str, float]:
        vec = {t: self.idf.get(t, 1.0) for t in tokens(text)}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def between(self, a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(v * b.get(t, 0.0) for t, v in a.items())


def mmr(candidates: list, texts: list[str], theme_sets: list[set[str]], *,
        k: int, lam: float = 0.65, theme_weight: float = 0.75,
        scores: list[float] | None = None) -> list:
    """Greedy MMR re-rank over a blended redundancy signal.

    Redundancy is mostly *conceptual* (do these occupy the same theme) with text
    similarity as a tiebreaker. Pure text cosine misses near-duplicate projects
    that use different vocabulary, which is the common case.

    `lam` = 1.0 keeps the original ranking exactly; lower values trade score for
    spread. 0.6-0.8 is the useful band.
    """
    if not candidates or k <= 0:
        return []
    if lam >= 1.0:
        return candidates[:k]

    sim = Similarity(texts)
    vecs = [sim.vector(t) for t in texts]
    if scores is None:
        scores = [1.0 - i / max(len(candidates) - 1, 1) for i in range(len(candidates))]
    lo, hi = min(scores), max(scores)
    span = (hi - lo) or 1.0
    rel = [(s - lo) / span for s in scores]

    def redundancy(i: int, j: int) -> float:
        return (theme_weight * jaccard(theme_sets[i], theme_sets[j])
                + (1 - theme_weight) * sim.between(vecs[i], vecs[j]))

    # Each candidate keeps a running list of its similarities to already-chosen
    # items, so every pair is computed exactly once. Recomputing the full set
    # each round is O(k^2 * pool) and takes ~30s at k=250; this is ~0.3s.
    # The decay makes terms past ~10 contribute under 2%, so the list is capped.
    DECAY, KEEP = 0.65, 12
    chosen: list[int] = [0]
    remaining = set(range(1, len(candidates)))
    top: dict[int, list[float]] = {}
    for i in remaining:
        top[i] = [redundancy(i, 0)]

    while remaining and len(chosen) < k:
        best_idx, best_val = None, -1e9
        for i in remaining:
            # Saturating, not max: the second item in a theme is a mild cost,
            # the fourth is a heavy one. A much stronger item can still win.
            # top[i] is ascending for cheap insertion; decay must weight the
            # strongest overlap first, so walk it backwards.
            crowd = 0.0
            for n, s in enumerate(reversed(top[i])):
                crowd += s * (DECAY ** n)
            val = lam * rel[i] - (1 - lam) * crowd
            if val > best_val:
                best_idx, best_val = i, val
        chosen.append(best_idx)
        remaining.discard(best_idx)
        top.pop(best_idx, None)
        for i in remaining:
            bisect.insort(top[i], redundancy(i, best_idx))
            if len(top[i]) > KEEP:
                top[i].pop(0)          # list is ascending; drop the smallest
    return [candidates[i] for i in chosen]


def row_text(store, row) -> str:
    """The text MMR compares. Title and description carry the concept."""
    item = store.to_item(row)
    return " ".join([item.title, item.summary or "", " ".join(item.topics),
                     item.lang or ""])


def _mmr_rows(store, rows: list, cfg, k: int) -> list:
    from radar import themes

    lam = float(cfg.get("rank.diversify.lambda", 0.65))
    tw = float(cfg.get("rank.diversify.theme_weight", 0.75))
    texts, theme_sets = [], []
    for r in rows:
        item = store.to_item(r)
        texts.append(" ".join([item.title, item.summary or "",
                               " ".join(item.topics), item.lang or ""]))
        theme_sets.append(themes.of_item(item))
    return mmr(rows, texts, theme_sets, k=k, lam=lam, theme_weight=tw,
               scores=[r["score"] for r in rows])


def _quotas(targets: dict[str, float], k: int, available: dict[str, int]) -> dict[str, int]:
    """Largest-remainder apportionment, capped by what each bucket actually has.

    Slots freed by an under-supplied bucket are handed to the others rather
    than left empty -- asking for a third infrastructure when only two good
    ones exist should not shrink the list.
    """
    weights = {k_: max(0.0, float(v)) for k_, v in targets.items()}
    total = sum(weights.values()) or 1.0
    quota, leftover = {}, k
    for name, w in weights.items():
        want = min(int(k * w / total), available.get(name, 0))
        quota[name] = want
        leftover -= want
    # Hand out remaining slots to whoever still has candidates, richest first.
    while leftover > 0:
        room = [n for n in weights if available.get(n, 0) > quota.get(n, 0)]
        if not room:
            break
        room.sort(key=lambda n: -(available[n] - quota[n]))
        quota[room[0]] += 1
        leftover -= 1
    return quota


def diversified(store, rows: list, cfg, k: int) -> list:
    """Redundancy-filter a ranked row list, optionally balanced across axes.

    Two separate concerns. MMR stops near-identical projects stacking; the
    balance step stops one *kind* of project owning the list. Velocity favours
    AI infrastructure -- inference engines are what trend -- so without an
    explicit quota the top fills with them even when the corpus is mostly
    something else.
    """
    if not cfg.get("rank.diversify.enabled", True):
        return rows[:k]
    # A wider pool than we return, so there is something to swap in.
    pool = rows[:max(k * 4, k + 35)]

    targets = cfg.get("rank.balance", {}) or {}
    targets = {k_: v for k_, v in targets.items() if k_ != "enabled"}
    if not cfg.get("rank.balance.enabled", True) or not targets:
        return _mmr_rows(store, pool, cfg, k)

    from radar import axis

    buckets: dict[str, list] = {name: [] for name in targets}
    for r in pool:
        name = axis.of_item(store.to_item(r))
        buckets.setdefault(name, []).append(r)

    quota = _quotas(targets, k, {n: len(v) for n, v in buckets.items()})
    picked = []
    for name, want in quota.items():
        if want > 0 and buckets.get(name):
            picked.extend(_mmr_rows(store, buckets[name], cfg, want))

    # Restore the original ranked order across buckets: balance is about
    # membership, not about interleaving the list in a fixed pattern.
    position = {id(r): i for i, r in enumerate(pool)}
    picked.sort(key=lambda r: position.get(id(r), 1 << 30))
    return picked[:k]
