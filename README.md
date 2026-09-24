# radar

Finds technically interesting projects worth building, by watching what strong
engineers are actually doing.

Free sources feed a scoring pipeline that ranks repos, papers and threads by
momentum, corroboration, fit and engineering depth. Claude Code reads the top
items to weed out thin wrappers and marketing, and translates the page into
Chinese. No API key is needed: it uses your existing Claude Code login.

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
`requirements.txt` holds the ranges it was resolved from. For the card pass and
translation you also need [Claude Code](https://claude.com/claude-code), signed
in once.

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

`run` does the whole pipeline — fetch, rank, enrich, the Claude Code card pass,
translation, report — and opens the dashboard. If Claude Code is missing or signed out, `run`
says so and still builds the ranked feed; `--no-llm` skips them on purpose.

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

Stars per day is measured, not averaged. Every run stores a snapshot of each
item's counters, and once two readings at least a day apart exist, velocity uses
the stars gained between them instead of `stars / age`. The lifetime average
hid an old repo that just took off and flattered one that peaked a year ago.
Items growing at least twice their lifetime pace, at 5+ stars a day, get their
own **Breaking out** lane.

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

Your machine is the single source of truth. The Claude Code passes need a
login that only exists here, so the site is published from here too, and your
local `radar.db` is the corpus. The GitHub Actions workflow only runs the
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

The page has up to three views, switched from the top bar without reloading,
and the address keeps your place (`#overview`, `#feed`, `#tracks`):

- **Overview** — this run at a glance: counts, how many items several sources
  agree on, the AI-focus split of the feed as a bar, and the "worth a look"
  lanes as cards.
- **Signal** — the ranked feed as cards, with search and sort in a sticky bar and
  the focus, theme, source and language filters folded into one panel.
- **Your projects** — tracked projects and what each run found; only shown once
  you track something.

The template lives in `radar/templates/` (`dashboard.html`, `dashboard.css`) and
is inlined into one file at build time.

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
so the toggle needs no rebuild. The page opens in Chinese by default
(`report.language = "zh-CN"`).

The content is translated too: item descriptions, paper and headline titles,
and track hits. `radar run` renders the page once in a recording mode to collect exactly the strings it
will show, translates the new ones through Claude Code in batches, and stores
them by a hash of the source text, so each string is translated once and later
runs only send what is new. Repo names, URLs, code and standard technical terms
stay as written. The English is kept, so the toggle switches content as well,
and anything not yet translated falls back to English. `radar translate` does
the same by hand; `--dry-run` counts what is left. Search works in both
languages.

The page is static, so save and dismiss can't write to the database; the
buttons copy the command to run. "Worth a look" also has a **Saved** lane, and
"Moving fastest" leaves out repos the `mega` penalty has already marked as
famous.

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

## Signal cards

Claude Code reads the top-ranked items (`cards.count`, 18) and writes a card
for each: what it actually is, technical depth 1–5 with a reason, what's still
unsolved, and a `low_substance` flag. That flag is the noise filter regexes
can't be: it catches the well-marketed empty repo. Items go six to a call, each
judged on its own, through `claude -p` with no tools and a JSON schema for the
answer, which radar validates and retries once.

Cards feed back into the ranking. A `low_substance` card and a depth of 1 or 2
become penalties on that item, so thin projects sink in the feed and the
highlights. There is deliberately no bonus: only the top few items are ever
carded, and a bonus would keep lifting exactly those. Cards expire after
`cards.ttl_days` (60) so a repo that changed gets read again.

## After you pick a project

```bash
.\radar.cmd track add "code-map benchmark" --keywords "call graph accuracy,SCIP oracle,code map benchmark"
.\radar.cmd track
```

Choosing is not the end of radar's job. On a year-long project the risk that
matters is someone shipping it first, or a paper that changes the approach, and
finding out three months late. A track is a named set of search phrases, and
every `radar run` checks:

- **radar's own corpus** for items matching two phrases, or every word of one;
- **GitHub** for repos created since you started tracking;
- **arXiv** for papers submitted since then.

Phrases are treated as search queries rather than exact strings, so matching
uses the meaningful words of each phrase, not the literal phrase. New hits sit at the top of the
dashboard under **Your projects**; `radar track show <name>` lists them all and
`radar track stop <name>` ends a track. GitHub searches are paced for its
30-a-minute limit and arXiv's for its three-second rule, four phrases per track
each, so a check takes a minute or two.

## The live local dashboard

```bash
.\radar.cmd serve
```

opens the dashboard at `http://127.0.0.1:8766/` with working buttons: save,
dismiss and undo write straight to the database, and notes can be added to any
item. The published page stays static and never contains any of this.

It listens on 127.0.0.1 only. Writes need a random token that exists only
inside the served page, so another site open in the same browser can't post to
it, and requests whose Host header isn't the server's own address are refused,
which stops DNS rebinding. The served page is written to `out/served.html`,
never over the `index.html` that `publish` ships.

Every save, dismiss and undo, from here or the CLI, is logged with the item's
score breakdown at that moment. That log is what `radar tune` learns from.

## Papers nobody has implemented

A strong paper with no code is the most direct project there is: the thesis is
written and the gap is real. `radar run` checks the top 25 papers (`[gaps]`) for
existing code, and the dashboard's papers lane lists only the ones checked to
have none. The lane used to assume it.

A paper counts as implemented if Hugging Face links a repo, or if a GitHub repo
cites its arXiv number in the README or description and actually contains code.
Paper lists, daily digests, reading notes and personal sites cite arXiv numbers
too, so repos named like those, or with no programming language, don't count.
The check leans toward "has code": a leftover false match hides a paper, it
never invents a gap. GitHub search allows 30 requests a minute, so unchecked
papers take about two seconds each; results are kept for 14 days.

```bash
.\radar.cmd gaps
```

lists the gaps with their upvotes and scores, checking any that are due first.

## Learning your taste

```bash
.\radar.cmd tune
.\radar.cmd tune --apply
```

Once you have saved and dismissed at least five items each, `tune` proposes
new weights for the six score components: saved items should outrank dismissed
ones, so it fits the weights that make that true more often, using a pairwise
ranking loss pulled toward the current weights. A handful of verdicts can only
nudge the ranker, never swing it (`--strength` sets how hard it pulls back), and
no component can go negative.

It prints how often saved items outrank dismissed ones now, after fitting, and
on held-out verdicts, each predicted by a model fitted without it. The held-out
figure is the honest one, and tune says so when the change wouldn't generalise.
It also suggests interest terms to raise, lower or add, from the words and
topics that separate what you kept from what you threw away.

Nothing changes until `--apply`, which edits `config.toml` in place and keeps
its comments, then rescores.

## Commands

```
radar init      write a starter config, create the db
radar fetch     pull every enabled source
radar rank      rescore everything (no network, instant)
radar top       show the current ranking
radar enrich    fetch READMEs for the top repos
radar cards     Claude Code: read the top items and card them
radar report    build the HTML dashboard + markdown digest
radar run       fetch, rank, enrich, cards, translate, report
radar show      everything known about one item, incl. score breakdown
radar save      mark items worth keeping (--note to add a note)
radar dismiss   never show these again
radar undo      clear a save or dismiss
radar serve     the dashboard on localhost, with working buttons
radar tune      learn ranking weights from your saves and dismissals (--apply)
radar gaps      papers checked to have no implementation
radar watch     the watchlist: --suggest people, --add them
radar track     watch a chosen project's space: add, list, show, check, stop
radar translate translate page content into Simplified Chinese (--dry-run)
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

`radar watch --suggest` helps grow that list. It looks for people several of
your watched engineers follow, then checks what those people starred recently
against what your watchlist starred or builds and what radar ranks highest.
When too few are followed by two or more, it widens to single follows but only
keeps people with at least two overlapping stars. Each suggestion shows who
follows them and the overlapping repos. `radar watch --add <login>` writes to
`config.toml` directly and keeps its comments. With the default list the
suggestions are modest, because those engineers follow few people in common;
the more personal the list, the better this gets.

**`profile.description`** — free text describing you. Nothing reads it at the
moment: it fed the project briefs, which were removed. It is kept for reference.

## Credentials

- **GitHub** — picked up automatically from `gh auth token` if you're logged in.
  Otherwise set `GITHUB_TOKEN`. Without one you'll hit rate limits fast.
- **Claude Code** — only the card pass and translation need it. Run `claude` once and
  sign in with /login; `radar doctor` confirms it. radar finds `claude` on PATH,
  or the copy the Claude desktop app bundles on Windows; set `claude.claude_path`
  otherwise. No API key is read. If `ANTHROPIC_API_KEY` is set in your shell,
  radar withholds it from Claude Code so a run can't be billed to an API account.

## Usage

The card pass is one Claude Code call per six items (18 by default, so three
calls), and cards are reused until they expire, so a rerun sends only new top
items. Translation sends only strings it has never seen. Both count against your
Claude plan's usage limits; lower `cards.count` or set `cards.effort = "medium"`
to use less.

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
