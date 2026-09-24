"""`radar tune`: learn the ranking weights from your own verdicts.

Every save and dismiss is logged with the score breakdown the item had when
you decided (store.feedback). Saved items should outrank dismissed ones; this
finds the component weights that make that true more often, without letting
a handful of verdicts swing the ranker around:

- pairwise ranking loss (RankNet): for every saved/dismissed pair, push the
  saved item's score above the dismissed one's;
- an L2 pull toward the current weights, so the data has to earn every move,
  and weights stay on the same scale as before;
- weights stay positive -- a component can matter less, never count against.

It reports pairwise accuracy before and after, and leave-one-out accuracy
(each verdict predicted by a model fitted without it), which is the honest
number. Interest terms are suggested separately, from which words show up in
what you saved versus what you dismissed. Nothing changes without --apply.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from radar.config import Config
from radar.rank import DEFAULT_WEIGHTS, _text_of, term_pattern
from radar.store import Store

COMPONENTS = list(DEFAULT_WEIGHTS)
MIN_EACH = 5


@dataclass
class Example:
    key: str
    x: list[float]
    saved: bool
    text: str = ""
    topics: list[str] = field(default_factory=list)


@dataclass
class Proposal:
    n_saved: int
    n_dismissed: int
    current: dict[str, float]
    proposed: dict[str, float] = field(default_factory=dict)
    acc_before: float | None = None
    acc_after: float | None = None
    loo_before: float | None = None
    loo_after: float | None = None
    raise_terms: list[tuple[str, int, int]] = field(default_factory=list)
    lower_terms: list[tuple[str, int, int]] = field(default_factory=list)
    add_terms: list[tuple[str, int]] = field(default_factory=list)
    enough: bool = False


def examples(store: Store) -> list[Example]:
    out = []
    for r in store.feedback():
        comps = json.loads(r["breakdown"] or "{}").get("components", {})
        if not comps:
            continue
        row = store.get(r["key"])
        item = store.to_item(row) if row else None
        out.append(Example(
            key=r["key"], x=[float(comps.get(c, 0.0)) for c in COMPONENTS],
            saved=r["action"] == "saved",
            text=_text_of(item) if item else "", topics=item.topics if item else [],
        ))
    return out


def _score(w, x):
    return sum(a * b for a, b in zip(w, x))


def pair_accuracy(w, exs: list[Example]) -> float | None:
    pos = [e for e in exs if e.saved]
    neg = [e for e in exs if not e.saved]
    if not pos or not neg:
        return None
    wins = sum(1 for p in pos for n in neg
               if _score(w, p.x) > _score(w, n.x)) + \
        0.5 * sum(1 for p in pos for n in neg if _score(w, p.x) == _score(w, n.x))
    return wins / (len(pos) * len(neg))


def fit(exs: list[Example], w0: list[float], lam: float = 1.0,
        steps: int = 400, lr: float = 0.05, floor: float = 0.05) -> list[float]:
    """Pairwise logistic loss + lam * ||w - w0||^2, projected to w >= floor."""
    pos = [e.x for e in exs if e.saved]
    neg = [e.x for e in exs if not e.saved]
    if not pos or not neg:
        return list(w0)
    npairs = len(pos) * len(neg)
    w = list(w0)
    shrink = 1.0 + 2 * lr * lam
    for _ in range(steps):
        grad = [0.0] * len(w)
        for p in pos:
            sp = _score(w, p)
            for n in neg:
                margin = sp - _score(w, n)
                # d/dw log(1 + e^-margin) = -sigmoid(-margin) * (p - n)
                g = -1.0 / (1.0 + math.exp(min(margin, 50)))
                for k in range(len(w)):
                    grad[k] += g * (p[k] - n[k]) / npairs * 10
        # Proximal step for the pull toward w0: exact for the quadratic, so it
        # stays stable however strong the pull (a plain gradient step overshoots).
        w = [max(floor, (wi - lr * gi + 2 * lr * lam * w0i) / shrink)
             for wi, gi, w0i in zip(w, grad, w0)]
    return w


def leave_one_out(exs: list[Example], w0: list[float], lam: float) -> float | None:
    """Fraction of held-out verdicts ranked on the right side of the others."""
    hits, total = 0.0, 0
    for i, held in enumerate(exs):
        rest = exs[:i] + exs[i + 1:]
        w = fit(rest, w0, lam, steps=200)
        others = [e for e in rest if e.saved != held.saved]
        if not others:
            continue
        s = _score(w, held.x)
        for o in others:
            so = _score(w, o.x)
            good = s > so if held.saved else s < so
            hits += 1.0 if good else (0.5 if s == so else 0.0)
            total += 1
    return hits / total if total else None


_WORD = re.compile(r"[a-z][a-z0-9+#-]{2,}")


def term_suggestions(exs: list[Example], interests: dict[str, float]):
    pos = [e for e in exs if e.saved]
    neg = [e for e in exs if not e.saved]
    raise_, lower = [], []
    for term in interests:
        pat = term_pattern(term)
        a = sum(1 for e in pos if pat.search(e.text))
        b = sum(1 for e in neg if pat.search(e.text))
        # smoothed log-odds of appearing in a saved vs a dismissed item
        lo = math.log((a + 0.5) / (len(pos) + 1)) - math.log((b + 0.5) / (len(neg) + 1))
        if a >= 2 and lo > 0.7:
            raise_.append((term, a, b))
        elif b >= 2 and lo < -0.7:
            lower.append((term, a, b))
    # candidate new terms: topics shared by several saved items, never dismissed
    pos_topics = Counter(t for e in pos for t in set(e.topics))
    neg_topics = Counter(t for e in neg for t in set(e.topics))
    known = {t.lower() for t in interests}
    add = [(t.replace("-", " "), c) for t, c in pos_topics.most_common(30)
           if c >= 2 and neg_topics[t] == 0 and t.replace("-", " ") not in known
           and len(t) > 2]
    return raise_, lower, add[:8]


def propose(cfg: Config, store: Store, lam: float = 1.0) -> Proposal:
    current = {**DEFAULT_WEIGHTS, **(cfg.get("rank.weights", {}) or {})}
    w0 = [float(current[c]) for c in COMPONENTS]
    exs = examples(store)
    n_pos = sum(1 for e in exs if e.saved)
    prop = Proposal(n_saved=n_pos, n_dismissed=len(exs) - n_pos,
                    current={c: float(current[c]) for c in COMPONENTS})
    prop.enough = n_pos >= MIN_EACH and prop.n_dismissed >= MIN_EACH
    if not prop.enough:
        return prop
    w = fit(exs, w0, lam)
    prop.proposed = {c: round(v, 2) for c, v in zip(COMPONENTS, w)}
    prop.acc_before = pair_accuracy(w0, exs)
    prop.acc_after = pair_accuracy(w, exs)
    prop.loo_before = pair_accuracy(w0, exs)          # w0 is not fitted: no leakage
    prop.loo_after = leave_one_out(exs, w0, lam)
    prop.raise_terms, prop.lower_terms, prop.add_terms = term_suggestions(exs, cfg.interests)
    return prop


def apply(cfg: Config, prop: Proposal) -> list[str]:
    """Write the proposal into config.toml, keeping its comments."""
    from radar import configedit

    path = cfg.home / "config.toml"
    changes = []
    if prop.proposed:
        changes += configedit.set_values(path, "rank.weights", prop.proposed)
    interests = cfg.interests
    new_int = {}
    for term, _, _ in prop.raise_terms:
        new_int[term] = round(min(1.5, interests[term] + 0.1), 2)
    for term, _, _ in prop.lower_terms:
        new_int[term] = round(max(0.1, interests[term] - 0.1), 2)
    for term, _ in prop.add_terms:
        new_int[term] = 0.6
    if new_int:
        changes += configedit.set_values(path, "interests", new_int, quote_keys=True)
    return changes
