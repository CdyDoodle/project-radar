"""Two-pass LLM ideation.

Pass A (per item, parallel): read the item and produce a "signal card" -- what
it actually is, how much real engineering is in it, and where its unsolved
edges are. This is also the last-resort noise filter: regexes can't tell a
serious project from a well-marketed empty one, and the model can.

Pass B (one call): take every card at once and synthesize project briefs. This
is where the value is. A per-item summariser would only ever say "you could
reimplement X". Giving the model the whole board lets it cross things over --
this paper has no implementation, that repo has the runtime it would need --
and propose work that doesn't exist yet.
"""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field

from radar import diversify
from radar.config import Config
from radar.models import now
from radar.rank import explain
from radar.store import Store

log = logging.getLogger("radar.ideate")


# -- schemas (kept flat on purpose: no nested models, no $ref) --------------
class SignalCard(BaseModel):
    what_it_is: str = Field(description="One or two plain sentences. No marketing language.")
    technical_depth: int = Field(description="1=trivial/wrapper, 5=genuinely hard systems work")
    depth_reason: str = Field(description="Why that number. Cite something concrete.")
    frontier: str = Field(description="What is still unsolved, missing, or obviously weak here.")
    adjacent_ideas: list[str] = Field(description="2-4 things a strong engineer could build next to this.")
    low_substance: bool = Field(description="True if this is content marketing, a tutorial, a list, or a thin wrapper.")


class ProjectBrief(BaseModel):
    title: str
    one_liner: str = Field(description="What you'd build, in under 20 words.")
    pitch: str = Field(description="2-4 sentences: the technical thesis and what exists at the end.")
    why_now: str = Field(description="What changed recently that makes this newly possible or newly interesting.")
    hard_parts: list[str] = Field(description="3-5 genuinely difficult technical problems. Be specific and concrete.")
    you_will_learn: list[str] = Field(description="3-5 durable skills or bodies of knowledge.")
    milestones: list[str] = Field(description="4-6 items, each 'Week N-M: outcome'. Front-load the risky part.")
    prior_art: list[str] = Field(description="Existing work that overlaps. Be honest; say if it's crowded.")
    kill_criteria: str = Field(description="A concrete result in the first 2 weeks that means abandon this.")
    effort_weeks: int
    difficulty: int = Field(description="1-5, for a strong senior engineer new to the domain")
    novelty: int = Field(description="1-5. 5 = nobody has built this")
    ai_leverage: str = Field(description="Specifically how AI is used: as the subject, as a tool, or both.")
    source_urls: list[str] = Field(description="URLs of the radar items this came from.")


class BriefBundle(BaseModel):
    briefs: list[ProjectBrief]
    board_summary: str = Field(description="3-5 sentences on what the current signal collectively suggests.")


CARD_SYSTEM = """You are triaging technical signal for a senior software engineer \
who is taking a year off to build something hard.

Judge substance, not popularity. A repo with 20k stars can be a wrapper; a paper \
with no code can be the most valuable thing on the page. Set low_substance=true \
for tutorials, awesome-lists, prompt collections, course material, thin API \
wrappers, and launch posts with no engineering behind them -- regardless of how \
much traction they have.

Be concrete and terse. Never pad. If you don't know something, say so rather \
than inventing detail."""

BRIEF_SYSTEM = """You generate project briefs for a senior software engineer on a \
funded career break. They can absorb hard material fast and have months, not days.

Rules that matter:
- Propose work that does not already exist. "Reimplement X in Rust" is only \
acceptable if the reimplementation itself teaches something the original can't.
- The best briefs CROSS items: a technique from a paper applied to a runtime from \
a repo, a tool that only becomes possible because two separate things now exist. \
At least half your briefs should combine two or more sources.
- Be honest about prior art. If something is crowded, say so in prior_art and \
lower novelty rather than pretending.
- hard_parts must name real technical obstacles (specific algorithms, specific \
systems constraints), not project-management risks like "scoping" or "time".
- kill_criteria must be a falsifiable result reachable in ~2 weeks.
- Do not propose CRUD apps, dashboards, or "an AI agent that does X" unless the \
difficulty is in the systems underneath.
- Vary difficulty and effort across the set. Include at least one 3-4 week project \
and at least one that plausibly fills the whole year."""


def _client(cfg: Config):
    import anthropic

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise SystemExit(
            "No Anthropic credentials found.\n"
            "  set ANTHROPIC_API_KEY=sk-ant-...   (PowerShell: $env:ANTHROPIC_API_KEY='sk-ant-...')\n"
            "Everything except `brief` works without it."
        )
    # Ideation is a background task; give it room rather than racing a timeout.
    return anthropic.Anthropic(timeout=900.0, max_retries=3)


def _final(stream_ctx):
    """Get the parsed object out of a streamed structured response."""
    with stream_ctx as stream:
        msg = stream.get_final_message()
    if getattr(msg, "stop_reason", None) == "refusal":
        detail = getattr(msg, "stop_details", None)
        raise RuntimeError(f"model declined this request ({detail})")
    parsed = getattr(msg, "parsed_output", None)
    if parsed is not None:
        return parsed, msg
    text = next((b.text for b in msg.content if b.type == "text"), "")
    return json.loads(text), msg


def _item_context(store: Store, row) -> str:
    item = store.to_item(row)
    breakdown = json.loads(row["breakdown"] or "{}")
    lines = [
        f"URL: {item.url}",
        f"TITLE: {item.title}",
        f"SOURCES: {', '.join(sorted(item.sources))}",
        f"LANGUAGE: {item.lang or 'n/a'}",
        f"TOPICS: {', '.join(item.topics) or 'n/a'}",
        f"METRICS: {json.dumps(item.metrics, default=str)}",
        f"WHY IT SURFACED: {explain(breakdown)}",
    ]
    if item.evidence:
        lines.append("EVIDENCE:\n  - " + "\n  - ".join(item.evidence[:6]))
    if item.summary:
        lines.append(f"DESCRIPTION:\n{item.summary}")
    if item.readme:
        lines.append(f"README (truncated):\n{item.readme}")
    return "\n".join(lines)


def make_cards(cfg: Config, store: Store, limit: int | None = None) -> int:
    """Pass A. Skips items that already have a card."""
    client = _client(cfg)
    model = cfg.get("brief.model", "claude-opus-5")
    effort = cfg.get("brief.effort", "high")
    limit = limit or int(cfg.get("brief.cards", 18))
    # Diversify before spending money: carding five near-identical inference
    # engines wastes calls and makes pass B synthesize from a narrow board.
    pool = [r for r in store.items(limit=limit * 4) if not r["card"]]
    rows = diversify.diversified(store, pool, cfg, limit)
    if not rows:
        log.info("every top item already has a card")
        return 0

    def one(row):
        try:
            parsed, msg = _final(client.messages.stream(
                model=model,
                max_tokens=8000,
                system=CARD_SYSTEM,
                thinking={"type": "adaptive"},
                output_config={"effort": effort},
                output_format=SignalCard,
                messages=[{"role": "user", "content":
                           "Triage this item.\n\n" + _item_context(store, row)}],
            ))
            data = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
            return row["id"], data
        except Exception as exc:
            log.warning("card failed for %s: %s", row["title"][:50], exc)
            return row["id"], None

    workers = int(cfg.get("brief.max_workers", 6))
    made = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for item_id, data in pool.map(one, rows):
            if data:
                store.set_card(item_id, data)
                made += 1
    log.info("wrote %d signal cards", made)
    return made


def make_briefs(cfg: Config, store: Store, run_id: str) -> list[dict]:
    """Pass B. Synthesizes across every carded item."""
    client = _client(cfg)
    model = cfg.get("brief.model", "claude-opus-5")
    effort = cfg.get("brief.effort", "high")
    count = int(cfg.get("brief.count", 8))

    rows = [r for r in store.items(limit=int(cfg.get("brief.cards", 18)) * 2) if r["card"]]
    if not rows:
        raise SystemExit("No signal cards yet. Run `radar cards` (or `radar run`) first.")

    board = []
    for row in rows:
        card = json.loads(row["card"])
        if card.get("low_substance"):
            continue  # the model's own filter, applied before synthesis
        board.append(
            f"### {row['title']}\n"
            f"{row['url']}\n"
            f"depth {card.get('technical_depth')}/5 -- {card.get('depth_reason', '')}\n"
            f"what it is: {card.get('what_it_is', '')}\n"
            f"frontier: {card.get('frontier', '')}\n"
            f"adjacent: {'; '.join(card.get('adjacent_ideas', []))}"
        )
    if not board:
        raise SystemExit("Every carded item was judged low-substance. Widen the sources.")

    log.info("synthesizing %d briefs from %d substantive items", count, len(board))
    user = (
        f"ENGINEER PROFILE\n{cfg.profile}\n\n"
        f"STATED INTERESTS (weighted)\n"
        f"{json.dumps(cfg.interests, indent=0)}\n\n"
        f"CURRENT SIGNAL ({len(board)} items, ranked)\n\n" + "\n\n".join(board) + "\n\n"
        f"Produce exactly {count} project briefs plus a board_summary. "
        f"Order them best-first for this specific engineer."
    )
    parsed, msg = _final(client.messages.stream(
        model=model,
        max_tokens=32000,
        system=BRIEF_SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        output_format=BriefBundle,
        messages=[{"role": "user", "content": user}],
    ))
    bundle = parsed if isinstance(parsed, BriefBundle) else BriefBundle.model_validate(parsed)

    out = []
    for i, brief in enumerate(bundle.briefs):
        payload = brief.model_dump()
        payload["board_summary"] = bundle.board_summary
        payload["generated_at"] = now().isoformat()
        brief_id = f"{run_id}-{i:02d}"
        store.add_brief(brief_id, run_id, payload)
        payload["_id"] = brief_id
        out.append(payload)

    usage = getattr(msg, "usage", None)
    if usage:
        log.info("brief pass tokens: in=%s out=%s",
                 getattr(usage, "input_tokens", "?"), getattr(usage, "output_tokens", "?"))
    return out
