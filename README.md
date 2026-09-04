# radar

Finds technically interesting projects worth building, by watching what strong
engineers are actually doing.

Six free sources feed a scoring pipeline; the survivors go through two Claude
passes that turn raw signal into concrete project briefs scoped for a senior
engineer with months rather than days.

No X/Twitter API — it has no free search tier ($200/mo minimum). The free
sources below carry most of the same signal, because engineering threads on X
almost always point back at a repo or a paper. A new source is one class in
`radar/sources/`, so an X adapter drops in later without touching anything else.

## Install

Needs Python 3.11+ (for `tomllib`). Clone, then:

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
```

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

`run` does the whole pipeline — fetch, rank, enrich, both Claude passes, report —
and opens the dashboard. Without an Anthropic key, use `--no-llm` to get the
ranked feed only.

## Where the signal comes from

| Source | What it gives you |
|---|---|
| `github_starred` | Recent stars of engineers **you** pick. The best source here. |
| `github_search` | Young repos that gained traction fast, filtered by topic |
| `github_trending` | Scraped `github.com/trending`, daily + weekly, per language |
| `hackernews` | Front page + Show HN above a point threshold |
| `lobsters` | Systems/PL-skewed, far less noise than HN |
| `arxiv` | Recent papers in your categories — usually with no implementation yet |

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

## The dashboard

`out/index.html` is a single static file — everything below is client-side, so
it works opened from disk with no server:

| Control | |
|---|---|
| search | `/` focuses it, `Esc` clears |
| show | 25 / 50 / 100 / 250 / all |
| sort | curated (redundancy-filtered), score, velocity, newest, stars |
| group by theme | **on by default**; sections ordered by best score, `other` last |
| collapse a group | click its header (or `Enter`/`Space` when focused) |
| collapse all / expand all | acts on the groups currently matching your filters |
| theme chips | multi-select, matches any |
| source chips + lang | single-select |
| theme toggle | light / dark / follow system |

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

## How the briefs work

Two passes, because a per-item summariser can only ever say "reimplement this".

**Pass A — signal cards.** Each top item is read individually: what it actually
is, technical depth 1–5 with a reason, what's still unsolved, and a
`low_substance` flag. That flag is the noise filter regexes can't be: it catches
the well-marketed empty repo.

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
radar cards     Claude pass A: triage top items
radar brief     Claude pass B: synthesize project briefs
radar report    build the HTML dashboard + markdown digest
radar run       all of the above
radar show      everything known about one item, incl. score breakdown
radar save      mark items worth keeping
radar dismiss   never show these again
radar doctor    check config, credentials, rate limits
```

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
- **Anthropic** — `ANTHROPIC_API_KEY`. Only `cards` and `brief` need it;
  everything else works without.

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

## Cost

Pass A is one call per item (18 by default), pass B is a single call. On
`claude-opus-5` at high effort a full run is roughly $1–3. Lower it by dropping
`brief.cards`, setting `brief.effort = "medium"`, or pointing `brief.model` at
`claude-sonnet-5`.

Re-running `fetch` inside 30 minutes is served from `.cache/`, so tuning weights
costs nothing.

## Running it daily

```powershell
$repo = "C:\path\to\project-radar"
$a = New-ScheduledTaskAction -Execute "$repo\radar.cmd" -Argument "run --no-open" -WorkingDirectory $repo
Register-ScheduledTask -TaskName "radar" -Trigger (New-ScheduledTaskTrigger -Daily -At 7am) -Action $a
```

Dismissed items never come back, and items that have sat in the feed across
multiple runs decay, so the top of the list stays fresh.

## Adding a source

Implement `fetch(cfg, http) -> list[Item]`, decorate with `@register`, import it
in `radar/sources/__init__.py`. Set the right `canonical_key` and merging,
dedupe, scoring and reporting all work for free.
