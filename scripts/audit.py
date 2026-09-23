"""Corpus health numbers. Run before and after any scoring or taxonomy change.

The README's rule is to judge classification and ranking changes on numbers,
never on a handful of rows that happen to look better. This prints the numbers.

    python scripts/audit.py            # uses ./config.toml and its db
    python scripts/audit.py --json     # machine-readable, for diffing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import axis, config, rank, themes  # noqa: E402
from radar.store import Store, open_store  # noqa: E402


def _substring_false_positives(items, terms) -> dict[str, int]:
    out = {}
    texts = [rank._text_of(i) for i in items]
    for term in terms:
        wb = re.compile(r"\b" + re.escape(term) + r"s?\b")
        out[term] = sum(1 for t in texts if term in t and not wb.search(t))
    return out


def audit(cfg, store: Store, top_n: int = 250) -> dict:
    rows = store.items(include_dismissed=True, include_forgotten=True)
    items = [store.to_item(r) for r in rows]
    n = len(items) or 1
    tags = [themes.of_item(i) for i in items]
    top = store.items(limit=top_n)

    trending_only = [i for i in items if i.sources == {"github_trending"}]
    pens = Counter()
    seen_vals = Counter()
    for r in rows:
        p = json.loads(r["breakdown"] or "{}").get("penalties", {})
        pens.update(p.keys())
        if "seen_before" in p:
            seen_vals[round(p["seen_before"], 2)] += 1

    return {
        "corpus": len(items),
        "other_share": round(sum(1 for t in tags if not t) / n, 4),
        "avg_tags": round(sum(len(t) for t in tags) / n, 3),
        "items_5plus_tags": sum(1 for t in tags if len(t) >= 5),
        "multi_source": sum(1 for i in items if len(i.sources) > 1),
        "trending_only": len(trending_only),
        "trending_only_without_stars": sum(1 for i in trending_only if not i.metrics.get("stars")),
        "without_created_at": sum(1 for i in items if not i.created_at),
        # Mentions a substring test would count and the word-boundary test does not.
        "substring_only_mentions": _substring_false_positives(
            items, ["rust", "agent", "gpu", "llm", "zig"]),
        "top_axis_mix": dict(Counter(axis.of_item(store.to_item(r)) for r in top)),
        "run": store.current_fetch(),
        "forgotten": len(store.forgotten()),
        "active": len(store.items()),
        "active_repos_without_stars": sum(
            1 for r in store.items()
            if r["key"].startswith("gh:") and "stars" not in json.loads(r["metrics"] or "{}")),
        "top_forgotten_rows": sum(1 for r in top if not store.is_active(r)),
        "penalty_counts": dict(pens),
        "distinct_seen_before_values": len(seen_vals),
        "carded": sum(1 for r in rows if r["card"]),
        "low_substance": sum(1 for r in rows
                             if r["card"] and json.loads(r["card"]).get("low_substance")),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-n", "--top", type=int, default=250)
    args = ap.parse_args(argv)
    cfg = config.load(args.home)
    result = audit(cfg, open_store(cfg), args.top)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for k, v in result.items():
            print(f"{k:32s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
