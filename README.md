# radar

Finds technically interesting projects worth building, by watching what strong
engineers are actually doing.

Six free sources feed a scoring pipeline; the survivors go through two passes
in Claude Code that turn raw signal into concrete project briefs scoped for a
senior engineer with months rather than days. No API key is needed: the briefs
use your existing Claude Code login.

No X/Twitter API — it has no free search tier ($200/mo minimum). The free
sources below carry most of the same signal, because engineering threads on X
almost always point back at a repo or a paper. A new source is one class in
`radar/sources/`, so an X adapter drops in later without touching anything else.

## Install

Needs Python 3.11+ (for `tomllib`). Clone, then:

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.lock
```

`requirements.lock` holds the exact versions CI tests against;
`requirements.txt` holds the ranges it was resolved from. For the briefs you
also need [Claude Code](https://claude.com/claude-code), signed in once.

On macOS/Linux use `.venv/bin/python` and call it as `python -m radar` — the
`.cmd`/`.ps1` wrappers are Windows conveniences, not requirements.

## Quick start

Check credentials and rate limits:

```bash
.\radar.cmd doctor
```

Then run the pipeline:

```bash
.\radar.cmd run
```

`run` does the whole pipeline — fetch, rank, enrich, both Claude Code passes,
report — and opens the dashboard. If Claude Code is missing or signed out, `run`
says so and still builds the ranked feed; `--no-llm` skips the passes on purpose.

Run it whenever you want a fresh look. Nothing is scheduled.

## Where the signal comes from

| Source | What it gives you |
|---|---|
| `github_starred` | Recent stars of engineers **you** pick. The best source here. |
| `github_search` | Young repos that gained traction fast, filtered by topic |
| `github_trending` | Scraped `github.com/trending`, daily + weekly, per language |
| `hackernews` | Front page + Show HN above a point threshold |
| `lobsters` | Systems/PL-skewed, far less noise than HN |
| `arxiv` | Recent papers in your categories — usually with no implementation yet |
| `github_activity` | What the watched engineers **build**: their own pushes, new repos, releases |
| `hf_papers` | Hugging Face daily papers — gives arXiv papers an upvote count |
| `bluesky` | Posts linking to a repo or paper, via the public search API. Off by default: it refuses some networks with a 403 |

Everything is deduped onto a canonical key, so an HN thread, a Lobsters post and
a trending entry that all point at one repo collapse into a single item — and
that collapse is itself a ranking signal.

## How ranking works

Score is a weighted sum of six components in `[0,1]`, minus explicit penalties.
Every number is stored, so the dashboard and `radar show` can always tell you
why something is where it is.

| Component | Meaning |
|---|---|
| `velocity` | stars/day, HN points, Lobsters score — log-compressed |
| `corroboration` | independent sources agreeing (2 → 0.5, 3 → 0.75) |
| `watchlist` | how many watched engineers starred it |
| `fit` | weighted keyword match against `[interests]` |
| `freshness` | exponential decay, 45-day half-life |
| `depth` | language, topics, and systems vocabulary as a proxy for real engineering |

Penalties: `slop` (awesome-lists, tutorials, prompt collections), `chatter`
(a blog post with no code behind it), `stale`, `archived`, `mega` (already
famous — you can't do frontier work where everyone already is), `seen_before`.

`velocity` is a percentile against the live corpus, not a fixed ceiling. A fixed
ceiling collapses: capping stars/day at 40 when real values run 39–658 pinned a
sixth of the top 50 at exactly 1.00 and destroyed all ordering inside whatever
category was hottest that week.

## Redundancy control

A ranked list is not a useful list. Because items are scored independently, four
implementations of the same idea all score well and all reach the top — which is
what happened with local LLM inference engines (7 of the top 15).

So the shortlist gets an MMR pass: each pick is discounted by how much it
overlaps what's already above it. Redundancy is mostly *conceptual*, using the
theme taxonomy in `radar/themes.py`, with IDF-weighted text cosine as a
tiebreaker. Text alone doesn't work — "trillion-parameter model on one CPU in
8GB" and "frontier MoE on hardware you already own" are the same project and
score ~0.1 cosine.

At the default `lambda = 0.65` that takes inference from 7/15 to 3/15 and
effective language count from 3.4 to 5.6, for about 4% of mean score. Tune or
disable it under `[rank.diversify]`; `radar top --raw` shows pure score order.

Tune the weights in `config.toml`, then `radar rank` — no network, instant.

## Published dashboard

Publish from your machine, after a run:

```bash
.\radar.cmd run
.\radar.cmd publish --dry-run
.\radar.cmd publish
```

`publish` rebuilds the report and pushes it to the `gh-pages` branch, using
your normal git credentials. The site gets:

- **`/`** — the latest run
- **`/archive/`** — every previous page, dated, newest first
- **`/digest.md`** and **`/radar.db`** — the digest and the corpus

Your machine is the single source of truth. Briefs can only be generated here
(they need a Claude Code login), so the site is published from here too, and
your local `radar.db` is the corpus. The GitHub Actions workflow only runs the
tests.

Three decisions worth knowing:

**The page being replaced is what gets archived**, so `/archive/` holds what
was actually served rather than a re-render.

**`gh-pages` is one parentless commit**, force-pushed each time. The dashboard
plus the database is a few MB; keeping history would add that much per publish,
forever. The archived files in the tree are the history worth keeping.

**`publish` refuses to overwrite runs you don't have.** If the published
`radar.db` contains a run your local database lacks, from an older CI run or
another machine, publishing would silently discard it. `--force` overrides.

## The dashboard

The live page is at <https://cdydoodle.github.io/project-radar/>; `radar run`
writes the same thing to `out/index.html`, which stays gitignored.

`out/index.html` is a single static file — everything below is client-side, so
it works opened from disk with no server:

| Control | |
|---|---|
| language | English / 简体中文, top right; `report.language` sets the default |
| search | `/` focuses it, `Esc` clears |
| show | 25 / 50 / 100 / 250 / all |
| sort | curated (redundancy-filtered), score, velocity, newest, stars |
| group by theme | **on by default**; sections ordered by best score, `other` last |
| collapse a group | click its header (or `Enter`/`Space` when focused) |
| collapse all / expand all | acts on the groups currently matching your filters |
| theme chips | multi-select, matches any |
| source chips + lang | single-select |
| save / dismiss | hover a row; copies `radar save <key>` or `radar dismiss <key>` |
| theme toggle | light / dark / follow system |

Every interface string is rendered in both languages and swapped on the client,
so the toggle needs no rebuild. Item titles and descriptions are never
translated; they stay as their authors wrote them. Setting `brief.language`
too makes the briefs themselves Chinese.

The page is static, so save and dismiss can't write to the database; the
buttons copy the command to run. "Worth a look" also has a **Saved** lane, and
"Moving fastest" leaves out repos the `mega` penalty has already marked as
famous. Briefs from earlier runs are kept in a collapsed **Earlier briefs**
section.

Collapsed groups stay as a one-line header with their item count, and the
counter breaks out how many rows are hidden that way. Choices persist in
`localStorage`, including which groups you left collapsed — all storage access
is guarded, so the page still works where storage is unavailable (a `file://`
or `data:` context, or a browser blocking site data). The markdown digest is
grouped by theme too.

Items are filed under one theme by the explicit priority order in
`radar/themes.py`. That list is deliberately dumb — an earlier version picked
the *rarest* matching theme, which sounds principled and files an LLM inference
server under "graphics-media" because its README mentions rendering.

## Balance: is AI the subject or the tool?

Themes answer "what domain is this in". They can't answer the question that
actually shapes a project list: is this repo **building the AI plumbing**, or
**pointing AI at something else**? An inference engine and an agent-driven
decompiler are both `ai-agents` by theme, and only one of them is a project
about reverse engineering.

`radar/axis.py` sorts every item into three:

| | |
|---|---|
| `ai-infra` | engines, harnesses, routers, serving, training — the plumbing |
| `ai-application` | AI pointed at a domain: binaries, video, science, security |
| `non-ai` | no AI at all — databases, compilers, kernels |

Three values, not two, because ~45% of the corpus is the third one and forcing
a binary would file a Postgres rewrite as an "application".

This matters because **velocity favours infrastructure** — inference engines
are what trend — so the top of the list fills with them even though infra is
only ~12% of the corpus. `[rank.balance]` sets the shortlist mix (default
30/40/30) as targets rather than caps: a bucket that can't fill its share hands
the slots back instead of shortening the list. Filter by it with the `focus`
chips in the dashboard, or see one item's verdict with `radar show`.

Two classifier subtleties worth knowing if you tune the patterns. A bare "MCP
server" is *not* infrastructure — it usually bridges a domain tool (a debugger,
a database) to a model, which makes it an application; only MCP gateways and
frameworks are plumbing. And "give agents an operating system" needs matching
as a relationship rather than a phrase, because the words end up separated.

## Themes

26 of them, plus `other`. Two rules keep the taxonomy honest, both learned by
watching it fail:

**Match what a thing is, not what it mentions.** A bare `\bllm\b` pattern filed
agent frameworks and a video editor as inference engines, because everything
built this year mentions LLMs — it claimed 24% of the corpus. A bare `emulator`
caught every *terminal* emulator; a bare `orchestrat` caught a Dockerfile
linter; a bare `google` filed **googletest** as industry news. Patterns name
the artifact, not the buzzword, and `gpu-hpc` outranks `os-kernel` because a GPU
kernel is not an OS kernel.

**Some items have no theme because they aren't projects.** A third of the feed
arrives from HN and Lobsters as a bare headline — "Restroom Archive", "Europe's
summer drought is so extreme", "Commodore 64 released September 1, 1982". No
pattern list will ever bucket those. They're caught structurally instead: a
bare link with no repo and no paper behind it becomes `discussion`, which you
can collapse or filter in one click.

Together those took `other` from 30% of the corpus to 8%.

**Coverage is not precision.** Chasing the first number wrecked the second:
broad patterns tagged almost everything, and an audit of which regex branch
actually fired found `\bsilicon\b` matching *"Apple Silicon"*, `\bprotocol\b`
matching *"Model Context Protocol"*, `\blinux\b` matching every project that
merely runs on it, and `\bpolicy\b` carrying half of `industry` off RL and
scheduling policies. An inference server was tagged with seven themes.

Tightening those to phrases naming the artifact cut average tags per item from
2.09 to 1.62 and items with 5+ tags from 96 to 33, at the cost of `other` going
8% → 13%. That's the right trade: a tag nobody trusts is worse than no tag.
Judge changes here on **both** numbers, never coverage alone.

`radar/themes.py` refuses to import if any pattern matches the empty string — a
trailing `|` leaves an empty alternative that silently tags the entire corpus,
and it *improves* every coverage metric while doing so, so it hides.

**READMEs are not read for classification.** A README mentions everything a
project touches — install steps (`docker`, `cargo`, env vars), platform support
(`Linux kernel`, CUDA, Vulkan), the whole feature tour — so including it flipped
the primary theme of a third of enriched items to something wrong: Audacity
filed under `os-kernel` for the words "operating system", a document converter
under `wasm`, a video editor under `virtualization` for "container". Dropping it
cost zero coverage, because every enriched item is a repo that already has a
description and topics. Title, description and topics are what a maintainer
chose to say the project *is*, which is exactly the signal wanted.

This only shows up after `enrich` has run, and only on the top-ranked items —
i.e. precisely the rows anyone actually looks at. A corpus-wide average hides
it completely.

## How the briefs work

Two passes, because a per-item summariser can only ever say "reimplement this".
Both run through `claude -p`, Claude Code's headless mode, with tools disabled
and a JSON schema for the answer, which radar validates and retries once.

**Pass A — signal cards.** Each top item gets a card: what it actually is,
technical depth 1–5 with a reason, what's still unsolved, and a `low_substance`
flag. That flag is the noise filter regexes can't be: it catches the
well-marketed empty repo. Items go six to a call, each judged on its own.

Cards feed back into the ranking. A `low_substance` card and a depth of 1 or 2
become penalties on that item, so the feed and highlights benefit, not just the
briefs. There is deliberately no bonus: only the top few items are ever carded,
and a bonus would keep lifting exactly those. Cards expire after
`brief.card_ttl_days` (60) so a repo that changed gets read again.

**Pass B — synthesis.** Every surviving card goes into one call together with
your profile. Because the model sees the whole board at once, it can cross items
over — a technique from a paper applied to a runtime from a repo, a tool that
only becomes possible because two separate things now exist. The prompt requires
at least half the briefs to combine two or more sources.

Each brief carries `hard_parts`, `milestones`, honest `prior_art`, and
`kill_criteria` — a falsifiable result reachable in ~2 weeks that means abandon
it. That last field matters more than the rest when you have one year.

## Commands

```
radar init      write a starter config, create the db
radar fetch     pull every enabled source
radar rank      rescore everything (no network, instant)
radar top       show the current ranking
radar enrich    fetch READMEs for the top repos
radar cards     Claude Code pass A: triage top items
radar brief     Claude Code pass B: synthesize project briefs
radar report    build the HTML dashboard + markdown digest
radar run       all of the above
radar show      everything known about one item, incl. score breakdown
radar save      mark items worth keeping
radar dismiss   never show these again
radar prune     delete items no recent run has seen (--dry-run to count)
radar hydrate   backfill GitHub metadata for repos stored without it
radar publish   build the report and push it to GitHub Pages
radar doctor    check config, GitHub rate limits, Claude Code login
```

## Runs, not days

Runs are manual and occasional, so time in the corpus is counted in runs. A
fetch within `rank.run_gap_hours` (6) of the previous one belongs to the same
run, so a rerun never counts as a second sighting.

- An item no run has seen in `rank.forget_after_runs` (3) runs drops out of the
  feed and out of the velocity percentiles, however long the gap between runs.
  Saved items always stay. `radar prune` deletes forgotten items for good;
  dismissed items are kept so they can't come back as new.
- The `seen_before` penalty grows with each run that has already shown an item
  and reaches its full weight after `rank.seen_before_full_after_runs` (6).

The database carries a schema version and upgrades itself when opened.

`radar show gh:owner/repo` is the one to reach for when a ranking looks wrong —
it prints every component and penalty that produced the score.

## Configuration

Everything lives in `config.toml`. Two fields matter far more than the rest:

**`sources.github_starred.users`** — the engineers whose taste you're borrowing.
The defaults are reasonable, but this tool gets dramatically better when the list
is personal. Twelve people you genuinely respect beats a hundred famous ones.

**`profile.description`** — free text passed verbatim into the ideation prompt.
Be specific about what you already know, what you want to learn, and what you'd
hate building. Vague profiles produce vague briefs.

## Credentials

- **GitHub** — picked up automatically from `gh auth token` if you're logged in.
  Otherwise set `GITHUB_TOKEN`. Without one you'll hit rate limits fast.
- **Claude Code** — only `cards` and `brief` need it. Run `claude` once and
  sign in with /login; `radar doctor` confirms it. radar finds `claude` on PATH,
  or the copy the Claude desktop app bundles on Windows; set `brief.claude_path`
  otherwise. No API key is read. If `ANTHROPIC_API_KEY` is set in your shell,
  radar withholds it from Claude Code so a run can't be billed to an API account.

## Usage

Pass A is one Claude Code call per six items (18 items by default, so three
calls), pass B is a single call. Both count against your Claude plan's usage
limits. Use less by lowering `brief.cards` or setting `brief.effort = "medium"`.
Cards are reused until they expire, so a rerun mostly pays for pass B.

Set `brief.language = "zh-CN"` to get cards and briefs in Simplified Chinese.

Re-running `fetch` inside 30 minutes is served from `.cache/`, so tuning weights
costs nothing.

## Tests

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -q
```

The theme and axis tests are a regression corpus of past misclassifications.
Before and after any change to scoring or patterns, compare the corpus numbers:

```bash
.venv/Scripts/python scripts/audit.py
```

Dismissed items never come back, and items that have sat in the feed across
multiple runs decay, so the top of the list stays fresh.

After each fetch, radar compares every source's count with the previous run
and warns when one returned nothing or fell below a fifth of what it did
before — a scraper whose page changed would otherwise fail silently.

## Adding a source

Implement `fetch(cfg, http) -> list[Item]`, decorate with `@register`, import it
in `radar/sources/__init__.py`. Set the right `canonical_key` and merging,
dedupe, scoring and reporting all work for free.
