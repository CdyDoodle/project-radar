"""Is AI the subject, the tool, or absent?

The theme taxonomy answers "what domain is this in". It cannot answer the
question that actually shapes a project list: is this repo *building the AI
plumbing*, or *pointing AI at something else*? Both are `ai-agents` by theme,
and a feed that doesn't separate them fills with inference engines, because
infrastructure is what trends.

Three values, because most of the corpus is neither -- a database, a compiler
and a terminal emulator are all worth surfacing and none of them are about AI.
Forcing a binary would file them as "application" and drown the real ones.
"""
from __future__ import annotations

import re

INFRA = "ai-infra"
APPLICATION = "ai-application"
NON_AI = "non-ai"
ALL_AXES = [INFRA, APPLICATION, NON_AI]

# Does AI appear at all? Deliberately generous -- the infra/application split
# below does the discriminating, so a false positive here is cheap.
_AI_PRESENT = re.compile(
    r"\bllm[s]?\b|\bai\b|\bai-|\bagent[s]?\b|\bmcp\b|\bgpt\b|\bclaude\b|\bgemini\b|"
    r"\bmodel[s]?\b|neural|machine learning|\bml\b|transformer|diffusion|"
    r"embedding|inferenc|prompt|\bnlp\b|deep learning",
    re.I,
)

# The artifact IS the AI plumbing: it runs, serves, trains, routes or
# orchestrates models, or it is the scaffolding other AI software is built on.
_INFRA = re.compile(
    r"inference (server|engine|runtime|framework)|model (serving|server|hub|router|"
    r"routing|gateway|registry|weights)|serving (llm|model)|\bvllm\b|llama\.cpp|"
    r"\bgguf\b|\bggml\b|quantiz|kv.?cache|speculative decod|prefill|tokens? per second|"
    r"tokenizer|context window|\bmoe\b|mixture.of.experts|experts? streamed|"
    # An engine whose whole pitch is getting weights to execute somewhere.
    r"run(s|ning)? [^.]{0,30}(model|llm)s? (on|locally|from|beyond|in)|"
    r"models? on [^.]{0,20}hardware|"
    r"agent (framework|harness|runtime|sdk|platform|os|operating system)|"
    r"multi.?agent (framework|system|orchestrat)|agent orchestrat|"
    # "give agents an operating system", "a runtime for agents", "sandbox for
    # agents" -- the words get separated, so match the relationship instead.
    r"(operating system|runtime|harness|sandbox|framework|platform|scaffold)"
    r"[^.]{0,24}\bfor (ai )?agents\b|"
    r"agents? [^.]{0,20}(an? )?(operating system|runtime|harness)\b|"
    r"llm (framework|gateway|proxy|router|api|sdk|application)|"
    r"vector (db|database|store|search)|embedding (store|database|model)|"
    r"\brag\b|retrieval.?augmented|"
    r"fine.?tun|pretrain|post.?train|\brlhf\b|training (framework|pipeline|infrastructure)|"
    r"eval(uation)? (harness|framework|suite)|prompt (library|framework|management)|"
    # NOT a bare "mcp server": an MCP server usually bridges a *domain* tool
    # (a debugger, a database) to a model, which makes it an application.
    # Only the plumbing around MCP itself is infrastructure.
    r"mcp (gateway|framework|registry|router|proxy)|"
    r"gpu (cluster|scheduler|orchestrat)|distributed training|"
    r"build .{0,20}(llm|ai) (app|application|agent)s?\b",
    re.I,
)


def classify_text(text: str) -> str:
    if not _AI_PRESENT.search(text or ""):
        return NON_AI
    return INFRA if _INFRA.search(text) else APPLICATION


def of_item(item) -> str:
    """Axis for an Item.

    Topics count heavily -- `topic:mcp-server` or `topic:agent-framework` is a
    stronger declaration of intent than anything in a marketing description.

    The README is deliberately excluded, for the same reason `themes.of_item`
    excludes it: a document converter with no AI in it was read as an AI
    application because its README said "agent to". See that docstring.
    """
    text = " ".join([
        item.title or "", item.summary or "", " ".join(item.topics),
    ])
    return classify_text(text)


def label(axis: str) -> str:
    return {INFRA: "AI infra", APPLICATION: "AI applied", NON_AI: "no AI"}.get(axis, axis)
