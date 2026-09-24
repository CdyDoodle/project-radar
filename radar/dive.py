"""`radar dive`: check one brief against the real world.

The briefs come from a model that only saw the signal cards -- no tools, no
search. Its "novelty 4/5" and "prior art: none close" are claims nobody has
checked, and the cost of a wrong one is months spent rebuilding something
that already exists. A dive gives Claude Code web search and page fetching,
asks it to go and look, and then radar checks the answer itself: every
prior-art link it cites is fetched, and links that don't resolve are marked
unverified on the page instead of being trusted.
"""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, Field

from radar.config import Config
from radar.http import Http
from radar.ideate import _language_rule, require_login, run_claude
from radar.models import canonical_key, now
from radar.store import Store

log = logging.getLogger("radar.dive")

TOOLS = ("WebSearch", "WebFetch")


class PriorArt(BaseModel):
    name: str
    url: str = Field(description="Exact URL you opened. Never guess one.")
    closeness: Literal["same", "overlapping", "adjacent"] = Field(
        description="same = already does the thesis; overlapping = covers a large part; "
                    "adjacent = related building block")
    note: str = Field(description="What it does and does not cover, in one or two sentences.")


class Experiment(BaseModel):
    goal: str = Field(description="The one question the first two weeks must answer.")
    steps: list[str] = Field(description="3-6 concrete steps, with the tools, datasets or "
                                         "repos to use by name.")
    success_metric: str = Field(description="What is measured, and on what.")
    kill_threshold: str = Field(description="The number that means stop.")
    time_needed: str


class DiveReport(BaseModel):
    verdict: Literal["go", "pivot", "crowded", "kill"] = Field(
        description="go = worth starting; pivot = worth it with a change of angle; "
                    "crowded = substantially exists already; kill = not feasible or not useful")
    verdict_reason: str = Field(description="Two or three sentences, citing what you found.")
    novelty_revised: int = Field(ge=1, le=5, description="Novelty after searching. 5 = nothing close exists.")
    novelty_reason: str
    prior_art: list[PriorArt] = Field(description="Every close project, paper or product you "
                                                  "actually opened. Empty only if you searched "
                                                  "thoroughly and found none.")
    feasibility: str = Field(description="Can one strong engineer do this in the stated time? "
                                         "What would make it slip?")
    risks: list[str] = Field(description="2-5 specific technical risks, most dangerous first.")
    needs: list[str] = Field(description="Hardware, datasets, accounts or access required.")
    two_week_experiment: Experiment
    pivot_ideas: list[str] = Field(description="0-3 sharper angles if the original is crowded or weak.")
    search_terms: list[str] = Field(description="4-8 short phrases that would find a competing "
                                                "project if one appeared later.")
    searched: list[str] = Field(description="The searches you ran and the main pages you read.")


DIVE_SYSTEM = """You are checking a project brief for a senior software engineer before \
they commit months of a career break to it. The brief was written by another model \
that could not search, so treat every claim in it -- novelty, prior art, feasibility \
-- as unverified.

Your job is to go and look. Use WebSearch and WebFetch:
- Search GitHub for existing implementations. The API works without a key: \
https://api.github.com/search/repositories?q=<terms>&sort=stars
- Search arXiv (https://export.arxiv.org/api/query?search_query=all:<terms>) and the \
wider web for papers, products and blog posts that already do this.
- Open the source repos the brief names and check what they already do.

Rules:
- List as prior art only things you actually opened, with the exact URL. A made-up \
or guessed link is worse than none: every URL will be checked afterwards.
- Be willing to say "crowded" or "kill". Finding that it already exists is a good \
result: it saves months.
- The two-week experiment must be runnable: name the repos, datasets, hardware and \
measurements. It should test the riskiest assumption first.
- Aim for roughly 10-25 searches and fetches, then stop and answer."""


def _brief_context(store: Store, brief: dict) -> str:
    fields = {k: v for k, v in brief.items() if not k.startswith("_")
              and k not in ("board_summary", "generated_at", "language")}
    lines = ["BRIEF", json.dumps(fields, indent=2, ensure_ascii=False)]
    cards = []
    for url in brief.get("source_urls") or []:
        row = store.get(canonical_key(url))
        if row and row["card"]:
            card = json.loads(row["card"])
            cards.append(f"- {row['title']} ({url}): {card.get('what_it_is', '')} "
                         f"Frontier: {card.get('frontier', '')}")
    if cards:
        lines += ["", "WHAT THE SOURCE ITEMS ARE (from earlier triage)", *cards]
    return "\n".join(lines)


def resolve_brief(store: Store, ident: str, run_id: str | None = None) -> dict | None:
    """A brief by id, or by its 1-based position in the current (or given) run."""
    if ident.isdigit():
        run_id = run_id or _current_run(store)
        briefs = store.briefs(run_id=run_id) if run_id else []
        n = int(ident)
        return briefs[n - 1] if 0 < n <= len(briefs) else None
    return store.brief(ident)


def _current_run(store: Store) -> str | None:
    """The run whose briefs the dashboard shows: the newest run that has any."""
    row = store.conn.execute(
        "SELECT run_id FROM briefs ORDER BY created_at DESC LIMIT 1").fetchone()
    return row["run_id"] if row else None


def verify_links(http: Http, report: dict, workers: int = 6) -> dict:
    """Fetch every cited URL and record whether it resolves.

    GitHub repos are checked through the API, which also brings the star
    count; anything else must answer an ordinary GET.
    """
    def check(entry: dict) -> dict:
        url = entry.get("url") or ""
        key = canonical_key(url)
        ok, stars = False, None
        if key.startswith("gh:"):
            data = http.gh(f"/repos/{key[3:]}")
            ok = isinstance(data, dict) and bool(data.get("full_name"))
            stars = data.get("stargazers_count") if ok else None
        elif url.startswith(("http://", "https://")):
            ok = http.get(url, ttl=86400) is not None
        return {**entry, "verified": ok, **({"stars": stars} if stars is not None else {})}

    arts = report.get("prior_art") or []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        checked = list(pool.map(check, arts))
    report["prior_art"] = checked
    report["links_checked"] = len(checked)
    report["links_unverified"] = sum(1 for a in checked if not a["verified"])
    return report


def dive(cfg: Config, store: Store, brief: dict, http: Http | None = None) -> dict:
    """Run one dive, verify its links, store it, and return the report."""
    from radar.collect import make_http

    exe = require_login(cfg)
    prompt = (
        f"ENGINEER PROFILE\n{cfg.profile}\n\n{_brief_context(store, brief)}\n\n"
        "Check this brief as instructed and return the report."
    )
    result = run_claude(
        cfg, exe, DIVE_SYSTEM + _language_rule(cfg), prompt, DiveReport,
        tools=TOOLS,
        effort=cfg.get("dive.effort", "high"),
        timeout=float(cfg.get("dive.timeout_seconds", 2400)),
    )
    report = verify_links(http or make_http(cfg), result.model_dump())
    report["brief_title"] = brief.get("title", "")
    report["dived_at"] = now().isoformat()
    dive_id = f"{brief['_id']}-dive-{now():%Y%m%d%H%M%S}"
    store.add_dive(dive_id, brief["_id"], report)
    report["_id"] = dive_id
    return report


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "project"
