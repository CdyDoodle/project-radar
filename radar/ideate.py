"""Two-pass ideation, run through the Claude Code CLI.

Pass A (batched, parallel): read the top items and produce a "signal card" for
each -- what it actually is, how much real engineering is in it, and where its
unsolved edges are. This is also the last-resort noise filter: regexes can't
tell a serious project from a well-marketed empty one, and the model can.

Pass B (one call): take every card at once and synthesize project briefs. This
is where the value is. A per-item summariser would only ever say "you could
reimplement X". Giving the model the whole board lets it cross things over --
this paper has no implementation, that repo has the runtime it would need --
and propose work that doesn't exist yet.

Both passes shell out to `claude -p` (Claude Code's headless mode) and use the
Claude login you already have. No API key is read or needed; if one is set in
the environment it is deliberately withheld from the child process, so a run
can never be billed to an API account by accident.
"""
from __future__ import annotations

import copy
import glob
import json
import logging
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from radar import diversify
from radar.config import Config
from radar.models import UTC, now
from radar.rank import explain
from radar.store import Store

log = logging.getLogger("radar.ideate")


# -- schemas -----------------------------------------------------------------
class SignalCard(BaseModel):
    what_it_is: str = Field(description="One or two plain sentences. No marketing language.")
    technical_depth: int = Field(ge=1, le=5, description="1=trivial/wrapper, 5=genuinely hard systems work")
    depth_reason: str = Field(description="Why that number. Cite something concrete.")
    frontier: str = Field(description="What is still unsolved, missing, or obviously weak here.")
    adjacent_ideas: list[str] = Field(description="2-4 things a strong engineer could build next to this.")
    low_substance: bool = Field(description="True if this is content marketing, a tutorial, a list, or a thin wrapper.")


class KeyedCard(SignalCard):
    id: str = Field(description="The ITEM ID exactly as given.")


class CardBatch(BaseModel):
    cards: list[KeyedCard]


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
    difficulty: int = Field(ge=1, le=5, description="1-5, for a strong senior engineer new to the domain")
    novelty: int = Field(ge=1, le=5, description="1-5. 5 = nobody has built this")
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

You will get several items. Return exactly one card per item, carrying its ITEM ID \
unchanged. Judge each item on its own; do not let one item's card borrow detail \
from another.

Be concrete and terse. Never pad. If you don't know something, say so rather \
than inventing detail. Work only from the text provided; you have no tools."""

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
and at least one that plausibly fills the whole year.
- source_urls must be copied from the URLs on the board. Work only from the text \
provided; you have no tools."""

LANGUAGE_RULE = {
    "zh-CN": ("\n\nWrite every prose field in Simplified Chinese (简体中文). Keep "
              "project names, repository names, paper titles, URLs, code identifiers "
              "and standard technical terms (API names, file formats) in their "
              "original form."),
}


# -- the Claude Code CLI -------------------------------------------------------
class ClaudeCodeError(RuntimeError):
    pass


def find_claude(cfg: Config) -> str | None:
    """Locate the `claude` executable.

    Order: `brief.claude_path` in config, `RADAR_CLAUDE`, PATH, then the copy
    the Claude desktop app bundles on Windows (newest version wins).
    """
    for cand in (cfg.get("brief.claude_path"), os.environ.get("RADAR_CLAUDE")):
        if cand and Path(cand).exists():
            return str(cand)
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    bundled = bundled_claude_paths()
    if bundled:
        def version(path: str) -> tuple:
            name = Path(path).parent.name
            return tuple(int(p) if p.isdigit() else 0 for p in name.split("."))
        return max(bundled, key=version)
    return None


def bundled_claude_paths() -> list[str]:
    """Copies of claude.exe that ship with the Claude desktop app on Windows.

    The Store/MSIX build redirects the app's %APPDATA% into its package
    folder. Only the app's own processes see the redirected path; a normal
    terminal must look inside LocalAppData\\Packages\\Claude_*\\LocalCache.
    Both places are searched so radar works from either.
    """
    roots = []
    if os.environ.get("APPDATA"):
        roots.append(os.path.join(os.environ["APPDATA"], "Claude", "claude-code"))
    if os.environ.get("LOCALAPPDATA"):
        roots += glob.glob(os.path.join(os.environ["LOCALAPPDATA"], "Packages", "Claude_*",
                                        "LocalCache", "Roaming", "Claude", "claude-code"))
    found = []
    for root in roots:
        found += [p for p in glob.glob(os.path.join(root, "*", "claude.exe"))
                  if os.path.isfile(p)]
    return found


def _child_env() -> dict:
    env = dict(os.environ)
    # Never let a stray key turn a subscription run into a billed API run.
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(var, None)
    # Lets radar itself be launched from inside a Claude Code session.
    env.pop("CLAUDECODE", None)
    return env


def _invoke(args: list[str], stdin: str, timeout: float) -> str:
    """Run the CLI and return stdout. Split out so tests can replace it."""
    proc = subprocess.run(
        args, input=stdin, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, env=_child_env(),
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise ClaudeCodeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:400]}")
    return proc.stdout


def auth_status(cfg: Config) -> dict:
    """`claude auth status` as a dict, plus the executable path. Free to call."""
    exe = find_claude(cfg)
    if not exe:
        return {"found": False}
    try:
        out = _invoke([exe, "auth", "status"], "", timeout=60)
        data = json.loads(out)
    except (ClaudeCodeError, ValueError, subprocess.TimeoutExpired, OSError) as exc:
        return {"found": True, "path": exe, "loggedIn": False, "error": str(exc)}
    return {"found": True, "path": exe, **data}


def require_login(cfg: Config) -> str:
    """The executable path, or a SystemExit explaining how to get there."""
    st = auth_status(cfg)
    if not st.get("found"):
        raise SystemExit(
            "Claude Code not found. Install it (https://claude.com/claude-code), or set\n"
            "  brief.claude_path in config.toml to the claude executable.")
    if not st.get("loggedIn"):
        raise SystemExit(
            f"Claude Code is not logged in ({st['path']}).\n"
            "  Run `claude` in a terminal and use /login once, then retry.")
    return st["path"]


def _inline_schema(model: type[BaseModel]) -> dict:
    """JSON schema with $refs resolved and extra keys forbidden.

    Kept self-contained so it doesn't depend on how the CLI resolves $defs.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            out = {}
            for k, v in node.items():
                if k == "properties" and isinstance(v, dict):
                    # Field names, not schema keywords: a field may be called
                    # "title". Stripping it here once produced a schema that
                    # required `title` while forbidding it, and every brief
                    # was rejected.
                    out[k] = {name: walk(sub) for name, sub in v.items()}
                elif k == "title" and isinstance(v, str):
                    continue          # pydantic's display label, not a field
                else:
                    out[k] = walk(v)
            if out.get("type") == "object":
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


def run_claude(cfg: Config, exe: str, system: str, prompt: str,
               model: type[BaseModel]) -> BaseModel:
    """One headless call with a structured answer, validated. Retries once."""
    args = [
        exe, "-p", "--output-format", "json",
        "--tools", "", "--strict-mcp-config", "--no-session-persistence",
        "--system-prompt", system,
        "--json-schema", json.dumps(_inline_schema(model)),
    ]
    if cfg.get("brief.model"):
        args += ["--model", str(cfg.get("brief.model"))]
    if cfg.get("brief.effort"):
        args += ["--effort", str(cfg.get("brief.effort"))]
    timeout = float(cfg.get("brief.timeout_seconds", 1200))

    last: Exception | None = None
    waits = list(TRANSIENT_WAITS)
    attempt = 0
    while attempt < 2:
        try:
            raw = json.loads(_invoke(args, prompt, timeout))
        except (ValueError, subprocess.TimeoutExpired) as exc:
            last = exc
            attempt += 1
            continue
        if raw.get("is_error"):
            msg = str(raw.get("result") or raw.get("terminal_reason") or "unknown error")
            if "not logged in" in msg.lower():
                raise ClaudeCodeError(f"{msg} -- run `claude` and /login once")
            last = ClaudeCodeError(msg)
            if _is_transient(msg) and waits:
                # Waiting does not use up a real attempt: these clear on their own.
                wait = waits.pop(0)
                log.warning("transient Claude Code error, retrying in %ss: %s", wait, msg[:160])
                _sleep(wait)
                continue
            attempt += 1
            continue
        attempt += 1
        payload = raw.get("structured_output")
        if payload is None:
            payload = _json_from_text(raw.get("result") or "")
        if payload is None:
            # No answer at all. The model usually says why in plain text; that
            # explanation is the only useful diagnostic, so carry it through.
            said = " ".join(str(raw.get("result") or "").split())[:400]
            last = ClaudeCodeError(f"no structured answer. Claude Code said: {said}")
            log.warning("attempt %d: %s", attempt, last)
            continue
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            last = exc
            log.warning("attempt %d: answer did not match the schema: %s", attempt,
                        str(exc)[:300])
    raise ClaudeCodeError(f"no valid answer after 2 attempts: {last}")


# Errors that clear on their own: several Claude Code processes refreshing the
# same login token at once (the first run after the token expires), or load.
TRANSIENT_MARKERS = ("refresh oauth token", "refreshing it", "overloaded",
                     "rate limit", "temporarily unavailable")
TRANSIENT_WAITS = (20, 60)       # seconds before the 1st and 2nd extra try
_sleep = time.sleep              # replaced in tests


def _is_transient(msg: str) -> bool:
    low = msg.lower()
    return any(m in low for m in TRANSIENT_MARKERS)


def _json_from_text(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except ValueError:
        return None


def _language_rule(cfg: Config) -> str:
    return LANGUAGE_RULE.get(str(cfg.get("brief.language", "en")), "")


# -- pass A --------------------------------------------------------------------
def _item_context(store: Store, row) -> str:
    item = store.to_item(row)
    breakdown = json.loads(row["breakdown"] or "{}")
    lines = [
        f"ITEM ID: {row['id']}",
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


def card_is_fresh(card_json: str | None, ttl_days: float) -> bool:
    """A stored card counts until it is older than `brief.card_ttl_days`."""
    if not card_json:
        return False
    try:
        stamp = json.loads(card_json).get("carded_at")
        when = datetime.fromisoformat(stamp).astimezone(UTC) if stamp else None
    except (ValueError, TypeError, AttributeError):
        return False
    # Cards written before the timestamp existed are treated as expired.
    return bool(when) and now() - when < timedelta(days=ttl_days)


def make_cards(cfg: Config, store: Store, limit: int | None = None) -> int:
    """Pass A. Skips items whose card is still fresh."""
    exe = require_login(cfg)
    limit = limit or int(cfg.get("brief.cards", 18))
    ttl = float(cfg.get("brief.card_ttl_days", 60))
    # Diversify before spending usage: carding five near-identical inference
    # engines wastes calls and makes pass B synthesize from a narrow board.
    pool = [r for r in store.items(limit=limit * 4) if not card_is_fresh(r["card"], ttl)]
    rows = diversify.diversified(store, pool, cfg, limit)
    if not rows:
        log.info("every top item already has a fresh card")
        return 0

    per_call = max(1, int(cfg.get("brief.cards_per_call", 6)))
    batches = [rows[i:i + per_call] for i in range(0, len(rows), per_call)]
    system = CARD_SYSTEM + _language_rule(cfg)

    def one(batch):
        prompt = (f"Triage these {len(batch)} items.\n\n"
                  + "\n\n---\n\n".join(_item_context(store, r) for r in batch))
        try:
            return batch, run_claude(cfg, exe, system, prompt, CardBatch)
        except ClaudeCodeError as exc:
            log.warning("card batch failed (%s...): %s", batch[0]["title"][:40], exc)
            return batch, None

    made = 0
    stamp = now().isoformat()
    workers = max(1, int(cfg.get("brief.max_workers", 3)))
    # The first batch runs alone. If the login token needs refreshing, one
    # process refreshes it; starting all batches at once made every process
    # race for the refresh and all of them fail.
    results = [one(batches[0])]
    with ThreadPoolExecutor(max_workers=workers) as pool_:
        results += list(pool_.map(one, batches[1:]))
    for batch, result in results:
        if result is None:
            continue
        wanted = {r["id"] for r in batch}
        for card in result.cards:
            if card.id not in wanted:
                log.warning("ignoring a card for an item not in the batch: %s", card.id)
                continue
            data = card.model_dump(exclude={"id"})
            data["carded_at"] = stamp
            store.set_card(card.id, data)
            made += 1
    log.info("wrote %d signal cards", made)
    return made


# -- pass B --------------------------------------------------------------------
def make_briefs(cfg: Config, store: Store, run_id: str) -> list[dict]:
    """Pass B. Synthesizes across every carded item."""
    exe = require_login(cfg)
    count = int(cfg.get("brief.count", 8))
    ttl = float(cfg.get("brief.card_ttl_days", 60))

    rows = [r for r in store.items(limit=int(cfg.get("brief.cards", 18)) * 2)
            if card_is_fresh(r["card"], ttl)]
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
    prompt = (
        f"ENGINEER PROFILE\n{cfg.profile}\n\n"
        f"STATED INTERESTS (weighted)\n"
        f"{json.dumps(cfg.interests, indent=0)}\n\n"
        f"CURRENT SIGNAL ({len(board)} items, ranked)\n\n" + "\n\n".join(board) + "\n\n"
        f"Produce exactly {count} project briefs plus a board_summary. "
        f"Order them best-first for this specific engineer."
    )
    bundle = run_claude(cfg, exe, BRIEF_SYSTEM + _language_rule(cfg), prompt, BriefBundle)

    out = []
    for i, brief in enumerate(bundle.briefs):
        payload = brief.model_dump()
        payload["board_summary"] = bundle.board_summary
        payload["generated_at"] = now().isoformat()
        payload["language"] = str(cfg.get("brief.language", "en"))
        brief_id = f"{run_id}-{i:02d}"
        store.add_brief(brief_id, run_id, payload)
        payload["_id"] = brief_id
        out.append(payload)
    return out
