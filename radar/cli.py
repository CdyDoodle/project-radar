"""radar CLI."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from radar import collect, config, diversify, rank, report
from radar.store import Store, open_store

console = Console()


def _setup(verbose: bool) -> None:
    # Windows consoles still default to cp1252; item titles are full of emoji.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def _open(cfg: config.Config) -> tuple[config.Config, Store]:
    return cfg, open_store(cfg)


def _run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# -- commands --------------------------------------------------------------
def cmd_init(args) -> int:
    home = Path(args.home or config.DEFAULT_HOME)
    dest = home / config.CONFIG_NAME
    src = Path(__file__).resolve().parent.parent / config.CONFIG_NAME
    if dest.exists() and not args.force:
        console.print(f"[yellow]{dest} already exists[/] (use --force to overwrite)")
    else:
        home.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        console.print(f"[green]wrote[/] {dest}")
    cfg = config.load(home)
    Store(cfg.db_path)
    console.print(f"[green]db ready[/]  {cfg.db_path}")
    token = config.github_token()
    console.print(f"github token: {'[green]found[/]' if token else '[yellow]none (rate limits will be tight)[/]'}")
    console.print("\nNext: edit [bold]config.toml[/] -- especially "
                  "[bold]sources.github_starred.users[/] and [bold]profile.description[/].")
    return 0


def cmd_fetch(args) -> int:
    cfg, store = _open(config.load(args.home))
    run_id = _run_id()
    store.start_run(run_id)
    with console.status("fetching sources..."):
        stats = collect.collect(cfg, store)
    store.finish_run(run_id, stats)
    table = Table(title="fetch", show_edge=False, header_style="dim")
    table.add_column("source"); table.add_column("items", justify="right")
    for k, v in stats.items():
        if not k.startswith("_"):
            table.add_row(k, str(v))
    console.print(table)
    console.print(f"[dim]{stats['_raw']} raw -> {stats['_merged']} unique "
                  f"({stats['_collapsed']} cross-source duplicates collapsed)[/]")
    _warn(stats)
    return 0


def _warn(stats: dict) -> None:
    for w in stats.get("_warnings", []):
        console.print(f"[yellow]warning:[/] {w}")


def cmd_rank(args) -> int:
    cfg, store = _open(config.load(args.home))
    rank.rank_all(store, cfg)
    _print_top(store, cfg, args.limit, raw=args.raw)
    return 0


def cmd_top(args) -> int:
    cfg, store = _open(config.load(args.home))
    _print_top(store, cfg, args.limit, raw=args.raw)
    return 0


def _print_top(store: Store, cfg, limit: int, raw: bool = False) -> None:
    pool = store.items(limit=max(limit * 3, limit + 30))
    rows = pool[:limit] if raw else diversify.diversified(store, pool, cfg, limit)
    if not raw and cfg.get("rank.diversify.enabled", True):
        console.print("[dim]redundancy-filtered (use --raw for pure score order)[/]")
    table = Table(show_edge=False, header_style="dim", row_styles=["", "dim"])
    table.add_column("score", justify="right", style="bold")
    table.add_column("item", overflow="fold")
    table.add_column("why", overflow="fold", style="dim")
    for row in rows[:limit]:
        item = store.to_item(row)
        meta = f"[dim]{item.lang or ''} {'/'.join(sorted(item.sources))}[/]"
        table.add_row(
            f"{row['score']:.2f}",
            f"[link={item.url}]{item.title}[/]\n{meta}\n{(item.summary or '')[:110]}",
            rank.explain(json.loads(row["breakdown"] or "{}")),
        )
    console.print(table)


def cmd_enrich(args) -> int:
    cfg, store = _open(config.load(args.home))
    with console.status("fetching READMEs..."):
        n = collect.enrich(cfg, store, limit=args.limit)
    console.print(f"[green]{n}[/] READMEs fetched")
    return 0


def cmd_cards(args) -> int:
    from radar import ideate
    cfg, store = _open(config.load(args.home))
    with console.status("reading items (pass A)..."):
        n = ideate.make_cards(cfg, store, limit=args.limit)
    console.print(f"[green]{n}[/] signal cards written")
    return 0


def cmd_brief(args) -> int:
    from radar import ideate
    cfg, store = _open(config.load(args.home))
    run_id = args.run or _run_id()
    store.start_run(run_id)
    with console.status("synthesizing project briefs (pass B)..."):
        briefs = ideate.make_briefs(cfg, store, run_id)
    for i, b in enumerate(briefs, 1):
        console.print(f"\n[bold]{i}. {b['title']}[/]")
        console.print(f"   [italic]{b['one_liner']}[/]")
        console.print(f"   [dim]difficulty {b['difficulty']}/5 · novelty {b['novelty']}/5 "
                      f"· ~{b['effort_weeks']}w[/]")
    console.print(f"\n[green]{len(briefs)}[/] briefs stored under run {run_id}")
    return 0


def cmd_report(args) -> int:
    cfg, store = _open(config.load(args.home))
    html, md = report.build(cfg, store, run_id=args.run, feed_limit=args.limit)
    console.print(f"[green]html[/] {html}\n[green]md  [/] {md}")
    if not args.no_open:
        webbrowser.open(html.resolve().as_uri())
    return 0


def cmd_run(args) -> int:
    from radar import ideate
    cfg, store = _open(config.load(args.home))
    run_id = _run_id()
    store.start_run(run_id)

    with console.status("1/5 fetching sources..."):
        stats = collect.collect(cfg, store)
    console.print(f"[green]fetch[/]   {stats['_merged']} unique items "
                  f"({stats['_collapsed']} collapsed)")
    _warn(stats)

    rank.rank_all(store, cfg)
    console.print("[green]rank[/]    scored")

    with console.status("3/5 fetching READMEs..."):
        n = collect.enrich(cfg, store, limit=int(cfg.get("brief.cards", 18)))
    console.print(f"[green]enrich[/]  {n} READMEs")

    from radar import track as tk
    if tk.tracks(store):
        with console.status("checking your tracked projects for competitors..."):
            found = tk.check_all(cfg, store, collect.make_http(cfg))
        for name, n in found.items():
            console.print(f"[green]track[/]   {name}: {n} new")

    if cfg.get("gaps.enabled", True):
        from radar import gaps as gp
        with console.status("checking top papers for existing code..."):
            g = gp.check(cfg, store, collect.make_http(cfg))
        console.print(f"[green]gaps[/]    {g['checked']} papers checked, "
                      f"{g['no_code']} with no implementation")

    if args.no_llm:
        console.print("[yellow]skipping Claude passes (--no-llm)[/]")
    else:
        # The feed and report never depend on Claude Code: if it is missing or
        # signed out, say so and publish everything else.
        try:
            with console.status("4/5 triaging items with Claude Code (pass A)..."):
                cards = ideate.make_cards(cfg, store)
            console.print(f"[green]cards[/]   {cards}")
            rank.rank_all(store, cfg)   # fold new card penalties into the scores
            with console.status("5/5 synthesizing project briefs (pass B)..."):
                briefs = ideate.make_briefs(cfg, store, run_id)
            console.print(f"[green]briefs[/]  {len(briefs)}")
        except (SystemExit, ideate.ClaudeCodeError) as exc:
            console.print(f"[yellow]skipping Claude passes:[/] {exc}")

    store.finish_run(run_id, stats)
    if not args.no_llm and cfg.get("translate.enabled", True):
        _translate(cfg, store)
    html, md = report.build(cfg, store, run_id=run_id, feed_limit=args.limit)
    console.print(f"\n[green]report[/]  {html}")
    if not args.no_open:
        webbrowser.open(html.resolve().as_uri())
    return 0


def cmd_show(args) -> int:
    cfg, store = _open(config.load(args.home))
    row = store.get(args.ident)
    if not row:
        console.print(f"[red]no item[/] {args.ident}")
        return 1
    item = store.to_item(row)
    console.print(f"[bold]{item.title}[/]  [dim]{row['score']:.2f}[/]")
    console.print(f"{item.url}\n")
    console.print(f"[dim]key[/]      {item.key}")
    from radar import axis as _axis, themes as _themes
    console.print(f"[dim]focus[/]    {_axis.label(_axis.of_item(item))}")
    console.print(f"[dim]themes[/]   {', '.join(sorted(_themes.of_item(item))) or '-'}")
    console.print(f"[dim]sources[/]  {', '.join(sorted(item.sources))}")
    console.print(f"[dim]status[/]   {row['status']}"
                  + ("" if store.is_active(row) else "  [yellow](forgotten)[/]"))
    console.print(f"[dim]seen[/]     in {row['runs_seen']} run(s), last in run "
                  f"#{row['last_fetch']} of {store.current_fetch()}")
    console.print(f"[dim]metrics[/]  {json.dumps(item.metrics, default=str)}")
    if item.evidence:
        console.print("\n[dim]evidence[/]")
        for e in item.evidence:
            console.print(f"  · {e}")
    console.print(f"\n{item.summary}")
    bd = json.loads(row["breakdown"] or "{}")
    if bd:
        console.print("\n[dim]score breakdown[/]")
        for k, v in sorted(bd.get("contributions", {}).items(), key=lambda kv: -kv[1]):
            console.print(f"  {k:>14s} {v:+.3f}")
        for k, v in bd.get("penalties", {}).items():
            console.print(f"  {k:>14s} [red]{v:+.3f}[/]")
    if row["card"]:
        card = json.loads(row["card"])
        console.print(f"\n[bold]signal card[/] (depth {card.get('technical_depth')}/5)")
        console.print(f"  {card.get('what_it_is')}")
        console.print(f"  [dim]frontier:[/] {card.get('frontier')}")
        for idea in card.get("adjacent_ideas", []):
            console.print(f"  · {idea}")
    return 0


def cmd_verdict(args, status: str) -> int:
    cfg, store = _open(config.load(args.home))
    n = sum(store.set_status(i, status) for i in args.idents)
    console.print(f"[green]{n}[/] item(s) marked {status}")
    if getattr(args, "note", None):
        for i in args.idents:
            store.set_note(i, args.note)
    return 0


def cmd_dive(args) -> int:
    from radar import dive as dv
    cfg, store = _open(config.load(args.home))
    if args.list or not args.brief:
        run_id = args.run or dv._current_run(store)
        briefs = store.briefs(run_id=run_id) if run_id else []
        if not briefs:
            console.print("no briefs yet -- run `radar run` (or `radar brief`) first")
            return 1
        dives = store.dives_for([b["_id"] for b in briefs])
        console.print(f"[dim]briefs from run {run_id}; `radar dive <n>` checks one[/]")
        for i, b in enumerate(briefs, 1):
            d = dives.get(b["_id"])
            mark = (f"[green]{d['verdict']}[/] novelty {d['novelty_revised']}/5" if d
                    else "[dim]not checked[/]")
            console.print(f"  {i}. {b['title'][:70]}  [{mark}]")
        return 0
    brief = dv.resolve_brief(store, args.brief, args.run)
    if not brief:
        console.print(f"[red]no brief[/] {args.brief}")
        return 1
    console.print(f"checking [bold]{brief['title']}[/]")
    console.print("[dim]Claude Code will search the web; this usually takes several minutes[/]")
    with console.status("searching for prior art..."):
        rep = dv.dive(cfg, store, brief)
    colour = {"go": "green", "pivot": "yellow", "crowded": "red", "kill": "red"}[rep["verdict"]]
    console.print(f"\n[bold {colour}]{rep['verdict'].upper()}[/]  novelty "
                  f"{brief.get('novelty')}/5 -> {rep['novelty_revised']}/5")
    console.print(f"  {rep['verdict_reason']}")
    if rep["prior_art"]:
        console.print("\n[dim]prior art[/]")
        for a in rep["prior_art"]:
            ok = "[green]ok[/]" if a["verified"] else "[red]link failed[/]"
            console.print(f"  {ok} [{a['closeness']}] {a['name']}  {a['url']}")
    x = rep["two_week_experiment"]
    console.print(f"\n[dim]two-week experiment[/]  {x['goal']}")
    for st in x["steps"]:
        console.print(f"  · {st}")
    console.print(f"  [dim]kill if:[/] {x['kill_threshold']}")
    console.print(f"\n[green]stored[/] {rep['_id']}  ({rep['links_checked']} links checked, "
                  f"{rep['links_unverified']} failed)")
    if cfg.get("translate.enabled", True):
        _translate(cfg, store)
    return 0


def cmd_serve(args) -> int:
    from radar import serve as sv
    cfg = config.load(args.home)
    sv.serve(cfg, port=args.port, open_browser=not args.no_open)
    return 0


def cmd_tune(args) -> int:
    from radar import tune as tn
    cfg, store = _open(config.load(args.home))
    prop = tn.propose(cfg, store, lam=args.strength)
    console.print(f"feedback: [bold]{prop.n_saved}[/] saved, [bold]{prop.n_dismissed}[/] dismissed")
    if not prop.enough:
        console.print(f"[yellow]need at least {tn.MIN_EACH} of each to tune[/] -- save and "
                      "dismiss items in `radar serve` (or with `radar save` / `radar dismiss`)")
        return 0

    def pct(v):
        return "-" if v is None else f"{v:.0%}"

    table = Table(title="component weights", show_edge=False, header_style="dim")
    for col in ("component", "now", "proposed", ""):
        table.add_column(col, justify="right" if col in ("now", "proposed") else "left")
    for c in tn.COMPONENTS:
        now_, new = prop.current[c], prop.proposed[c]
        arrow = "[green]up[/]" if new > now_ + 0.05 else "[red]down[/]" if new < now_ - 0.05 else ""
        table.add_row(c, f"{now_:.2f}", f"{new:.2f}", arrow)
    console.print(table)
    console.print(f"saved above dismissed: {pct(prop.acc_before)} now -> "
                  f"{pct(prop.acc_after)} fitted; [bold]{pct(prop.loo_after)}[/] on held-out verdicts")
    for t, a, b in prop.raise_terms:
        console.print(f"  [green]raise[/] interest {t!r} (in {a} saved, {b} dismissed)")
    for t, a, b in prop.lower_terms:
        console.print(f"  [red]lower[/] interest {t!r} (in {a} saved, {b} dismissed)")
    for t, c in prop.add_terms:
        console.print(f"  [green]add[/] interest {t!r} (a topic of {c} saved items, no dismissed)")
    if prop.loo_after is not None and prop.loo_before is not None and prop.loo_after < prop.loo_before:
        console.print("[yellow]held-out accuracy is lower than now: the change would not "
                      "generalise; not recommended[/]")
    if not args.apply:
        console.print("\n[dim]nothing changed; rerun with --apply to write this into config.toml[/]")
        return 0
    for change in tn.apply(cfg, prop):
        console.print(f"  [green]wrote[/] {change}")
    rank.rank_all(store, config.load(args.home))
    console.print("rescored with the new weights")
    return 0


def cmd_gaps(args) -> int:
    from radar import gaps as gp
    cfg, store = _open(config.load(args.home))
    if not args.no_check:
        with console.status("checking papers for existing code (paced for GitHub search)..."):
            st = gp.check(cfg, store, collect.make_http(cfg), limit=args.check, recheck=args.recheck)
        console.print(f"checked {st['checked']}: [green]{st['no_code']} with no code[/], "
                      f"{st['with_code']} with code" + (f", {st['failed']} failed" if st["failed"] else ""))
    rows = gp.gaps(store, limit=args.limit)
    if not rows:
        console.print("no checked paper without code yet")
        return 0
    table = Table(title="papers nobody has implemented", show_edge=False, header_style="dim")
    table.add_column("score", justify="right")
    table.add_column("paper", overflow="fold")
    table.add_column("signal", overflow="fold", style="dim")
    for r in rows:
        m = json.loads(r["metrics"] or "{}")
        sig = " · ".join(x for x in [
            f"{m['hf_upvotes']} HF upvotes" if m.get("hf_upvotes") else "",
            f"HN {m['hn_points']}" if m.get("hn_points") else "",
            m.get("arxiv_category", "")] if x)
        table.add_row(f"{r['score']:.2f}", f"[link={r['url']}]{r['title']}[/]\n[dim]{r['url']}[/]", sig)
    console.print(table)
    return 0


def cmd_track(args) -> int:
    from radar import track as tk
    cfg, store = _open(config.load(args.home))
    if args.action == "add":
        if not args.name:
            console.print("[red]give the project a name[/]: radar track add \"my project\" ...")
            return 1
        keywords, brief_id = [], None
        if args.from_brief:
            from radar import dive as dv
            brief = dv.resolve_brief(store, args.from_brief)
            if not brief:
                console.print(f"[red]no brief[/] {args.from_brief}")
                return 1
            brief_id = brief["_id"]
            d = store.dives_for([brief_id]).get(brief_id)
            if d and d.get("search_terms"):
                keywords = d["search_terms"]
            else:
                console.print("[yellow]that brief has no dive yet[/] -- run `radar dive "
                              f"{args.from_brief}` for good search terms, or pass --keywords")
        if args.keywords:
            keywords += [k for k in args.keywords.split(",")]
        try:
            tk.add(store, args.name, keywords, brief_id)
        except ValueError as exc:
            console.print(f"[red]{exc}[/]")
            return 1
        except Exception as exc:   # sqlite unique constraint
            console.print(f"[red]could not add:[/] {exc}")
            return 1
        console.print(f"[green]tracking[/] {args.name}: {', '.join(k.strip() for k in keywords)}")
        console.print("[dim]checked on every `radar run`, or now with `radar track check`[/]")
        return 0
    if args.action == "check":
        found = tk.check_all(cfg, store, collect.make_http(cfg))
        for name, n in found.items():
            console.print(f"{name}: [green]{n}[/] new")
        if not found:
            console.print("no active tracks")
        return 0
    if args.action == "stop":
        ok = tk.stop(store, args.name or "")
        console.print("stopped" if ok else f"[red]no track[/] {args.name}")
        return 0 if ok else 1
    if args.action == "show":
        t = tk.find(store, args.name or "")
        if not t:
            console.print(f"[red]no track[/] {args.name}")
            return 1
        console.print(f"[bold]{t['name']}[/]  [dim]since {t['created_at'][:10]}: "
                      f"{', '.join(t['keywords'])}[/]")
        for h in t["hits"][:args.limit]:
            console.print(f"  [dim]{h['found_at'][:10]}[/] [link={h['url']}]{h['title'][:90]}[/]\n"
                          f"      [dim]{h['reason']}[/]")
        if not t["hits"]:
            console.print("  nothing yet")
        return 0
    ts = tk.tracks(store)
    if not ts:
        console.print("no tracks. Start one: radar track add \"name\" --from-brief 3")
    for t in ts:
        new = len(tk.new_hits(t, store.current_fetch()))
        console.print(f"  [bold]{t['name']}[/]  {len(t['hits'])} hits"
                      + (f", [green]{new} new this run[/]" if new else "")
                      + f"  [dim]{', '.join(t['keywords'][:5])}[/]")
    return 0


def _translate(cfg, store) -> None:
    from radar import ideate, translate as tl
    try:
        with console.status("translating new content into Chinese..."):
            st = tl.translate_missing(cfg, store)
        if st["needed"]:
            console.print(f"[green]translate[/] {st['translated']} of {st['needed']} new strings"
                          + (f" ({st['failed']} left in English)" if st["failed"] else ""))
    except (SystemExit, ideate.ClaudeCodeError) as exc:
        console.print(f"[yellow]skipping translation:[/] {exc}")


def cmd_translate(args) -> int:
    from radar import translate as tl
    cfg, store = _open(config.load(args.home))
    todo = tl.missing(cfg, store)
    have = len(store.translations(tl.LANG))
    console.print(f"{have} strings already translated, {len(todo)} to do")
    if args.dry_run or not todo:
        for t in todo[:10]:
            console.print(f"  [dim]{t[:100]}[/]")
        return 0
    _translate(cfg, store)
    report.build(cfg, store)
    return 0


def cmd_prune(args) -> int:
    cfg, store = _open(config.load(args.home))
    gone = store.forgotten()
    if args.dry_run or not gone:
        console.print(f"{len(gone)} item(s) not seen in the last "
                      f"{store.forget_after_runs} runs" + (" (dry run)" if gone else ""))
        return 0
    n = store.prune()
    console.print(f"[green]{n}[/] forgotten item(s) deleted; saved and dismissed items kept")
    return 0


def cmd_hydrate(args) -> int:
    """Backfill GitHub metadata for repos that were stored without it."""
    from radar.sources.github import hydrate
    cfg, store = _open(config.load(args.home))
    rows = [r for r in store.items(include_forgotten=args.all)
            if r["key"].startswith("gh:") and "stars" not in json.loads(r["metrics"] or "{}")]
    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        console.print("nothing to backfill")
        return 0
    with console.status(f"looking up {len(rows)} repos..."):
        out = hydrate(collect.make_http(cfg), [store.to_item(r) for r in rows])
    done = 0
    with store.tx():
        for it in out:
            if "stars" in it.metrics and store.refresh(it):
                done += 1
    rank.rank_all(store, cfg)
    console.print(f"[green]{done}[/] of {len(rows)} repos backfilled "
                  f"({len(rows) - done} not found: renamed, deleted or private); rescored")
    return 0


def cmd_publish(args) -> int:
    from radar import publish as pub
    cfg, store = _open(config.load(args.home))
    if not args.no_build:
        report.build(cfg, store, feed_limit=args.limit)
    try:
        with console.status("preparing the site..." if args.dry_run else "publishing..."):
            plan = pub.publish(cfg, store, remote=args.remote,
                               dry_run=args.dry_run, force=args.force)
    except pub.PublishConflict as exc:
        console.print(f"[red]not published:[/] {exc}")
        return 1
    except pub.PublishError as exc:
        console.print(f"[red]publish failed:[/] {exc}")
        return 1
    total = sum(plan.files.values())
    console.print(f"{'would publish' if args.dry_run else '[green]published[/]'} "
                  f"{len(plan.files)} files, {total / 1_048_576:.1f} MB, to the "
                  f"gh-pages branch as one commit")
    if plan.archived_as:
        console.print(f"  previous page -> {plan.archived_as} ({plan.snapshots} archived"
                      + (f", {len(plan.thinned)} older ones thinned to one a week" if plan.thinned else "")
                      + ")")
    if plan.remote_runs:
        console.print(f"  published corpus had {plan.remote_runs} runs, all present locally")
    if plan.site_url:
        console.print(f"  {plan.site_url}" + ("" if plan.pushed else "  (nothing pushed)"))
    return 0


def cmd_watch(args) -> int:
    from radar import watch as wt
    cfg, store = _open(config.load(args.home))
    if args.add:
        changes = wt.add(cfg, args.add)
        for c in changes:
            console.print(f"[green]added[/] {c.rsplit(' ', 1)[-1]} to the watchlist")
        if not changes:
            console.print("already watching all of them")
        else:
            console.print("[dim]their stars and activity are picked up on the next fetch[/]")
        return 0
    if args.suggest:
        with console.status("reading who your watchlist follows..."):
            cands = wt.suggest(cfg, store, collect.make_http(cfg), limit=args.limit)
        if not cands:
            console.print("no one is followed by two or more of your watched engineers")
            return 0
        table = Table(title="engineers your watchlist points at", show_edge=False,
                      header_style="dim")
        table.add_column("who", overflow="fold")
        table.add_column("followed by", overflow="fold")
        table.add_column("same recent stars", overflow="fold", style="dim")
        for c in cands:
            who = f"[bold]{c.login}[/]" + (f" {c.name}" if c.name and c.name != c.login else "")
            if c.bio:
                who += f"\n[dim]{c.bio[:90]}[/]"
            shared = (f"{len(c.overlap)} of {c.recent_stars}: " + ", ".join(c.overlap[:3])
                      if c.overlap else f"0 of {c.recent_stars}")
            table.add_row(who, ", ".join(c.followed_by), shared)
        console.print(table)
        console.print(f"[dim]add with: radar watch --add {' '.join(c.login for c in cands[:3])}[/]")
        return 0
    users = cfg.watchlist
    console.print(f"watching {len(users)} engineers: {', '.join(users)}")
    return 0


def cmd_doctor(args) -> int:
    import os
    cfg = config.load(args.home)
    store = open_store(cfg)
    http = collect.make_http(cfg)
    console.print(f"config     {cfg.home / config.CONFIG_NAME}")
    console.print(f"database   {cfg.db_path}  {store.counts()}")
    console.print(f"           schema v{store.schema_version} · run #{store.current_fetch()} · "
                  f"{len(store.forgotten())} forgotten (not seen in "
                  f"{store.forget_after_runs} runs; `radar prune` deletes them)")
    token = config.github_token()
    console.print(f"gh token   {'[green]yes[/]' if token else '[red]no[/]'}")
    if token:
        core = http.gh_rate().get("core", {})
        search = http.gh_rate().get("search", {})
        console.print(f"  core   {core.get('remaining')}/{core.get('limit')}")
        console.print(f"  search {search.get('remaining')}/{search.get('limit')}")
    from radar import ideate
    st = ideate.auth_status(cfg)
    if not st.get("found"):
        console.print("claude     [yellow]not found -- `cards`/`brief` will not run "
                      "(set brief.claude_path)[/]")
    elif not st.get("loggedIn"):
        console.print(f"claude     [yellow]not logged in -- run `claude`, then /login[/]\n"
                      f"           {st['path']}")
    else:
        console.print(f"claude     [green]logged in[/] ({st.get('authMethod', '?')})\n"
                      f"           {st['path']}")
    if os.environ.get("ANTHROPIC_API_KEY"):
        console.print("           [dim]ANTHROPIC_API_KEY is set; radar withholds it from "
                      "Claude Code so briefs use your Claude login[/]")
    fb = store.feedback()
    n_saved = sum(1 for r in fb if r["action"] == "saved")
    console.print(f"feedback   {n_saved} saved, {len(fb) - n_saved} dismissed "
                  f"(`radar tune` needs 5 of each)")
    console.print(f"watchlist  {len(cfg.watchlist)} engineers")
    console.print(f"interests  {len(cfg.interests)} weighted terms")
    from radar.sources import all_source_names
    console.print(f"sources    {', '.join(all_source_names())}")
    return 0


# -- parser ----------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="radar",
        description="Find technically interesting projects worth building.",
    )
    p.add_argument("--home", help="directory holding config.toml and the db")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="write a starter config and create the db")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("fetch", help="pull every enabled source")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("rank", help="rescore everything (no network)")
    s.add_argument("-n", "--limit", type=int, default=25)
    s.add_argument("--raw", action="store_true", help="pure score order, no redundancy filter")
    s.set_defaults(fn=cmd_rank)

    s = sub.add_parser("top", help="show the current ranking")
    s.add_argument("-n", "--limit", type=int, default=25)
    s.add_argument("--raw", action="store_true", help="pure score order, no redundancy filter")
    s.set_defaults(fn=cmd_top)

    s = sub.add_parser("enrich", help="fetch READMEs for top repos")
    s.add_argument("-n", "--limit", type=int, default=25)
    s.set_defaults(fn=cmd_enrich)

    s = sub.add_parser("cards", help="Claude Code pass A: triage top items")
    s.add_argument("-n", "--limit", type=int)
    s.set_defaults(fn=cmd_cards)

    s = sub.add_parser("brief", help="Claude Code pass B: synthesize project briefs")
    s.add_argument("--run")
    s.set_defaults(fn=cmd_brief)

    s = sub.add_parser("report", help="build the HTML dashboard + markdown digest")
    s.add_argument("--run")
    s.add_argument("-n", "--limit", type=int, default=250,
                   help="rows rendered into the page (the UI pages client-side)")
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("run", help="fetch + rank + enrich + brief + report")
    s.add_argument("-n", "--limit", type=int, default=250,
                   help="rows rendered into the page (the UI pages client-side)")
    s.add_argument("--no-llm", action="store_true", help="skip the Claude Code passes")
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("show", help="everything known about one item")
    s.add_argument("ident", help="item id or key (e.g. gh:owner/repo)")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("save", help="mark items as saved")
    s.add_argument("idents", nargs="+")
    s.add_argument("--note", help="a note to keep with the item")
    s.set_defaults(fn=lambda a: cmd_verdict(a, "saved"))

    s = sub.add_parser("dismiss", help="never show these again")
    s.add_argument("idents", nargs="+")
    s.set_defaults(fn=lambda a: cmd_verdict(a, "dismissed"))

    s = sub.add_parser("undo", help="clear a save or dismiss")
    s.add_argument("idents", nargs="+")
    s.set_defaults(fn=lambda a: cmd_verdict(a, "new"))

    s = sub.add_parser("publish", help="build the report and push it to GitHub Pages")
    s.add_argument("--dry-run", action="store_true", help="prepare and check, push nothing")
    s.add_argument("--force", action="store_true",
                   help="overwrite a published corpus that has runs you lack")
    s.add_argument("--no-build", action="store_true", help="publish out/ as it is")
    s.add_argument("--remote", help="git remote URL (default: origin)")
    s.add_argument("-n", "--limit", type=int, default=250,
                   help="rows rendered into the page")
    s.set_defaults(fn=cmd_publish)

    s = sub.add_parser("dive", help="check a brief against the web with Claude Code")
    s.add_argument("brief", nargs="?", help="brief number on the page (1, 2, ...) or brief id")
    s.add_argument("--run", help="pick the brief from this run instead of the latest")
    s.add_argument("--list", action="store_true", help="list briefs and their dive status")
    s.set_defaults(fn=cmd_dive)

    s = sub.add_parser("serve", help="the dashboard on localhost, with working buttons")
    s.add_argument("--port", type=int, default=8766)
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("tune", help="learn ranking weights from your saves and dismissals")
    s.add_argument("--apply", action="store_true", help="write the proposal into config.toml")
    s.add_argument("--strength", type=float, default=1.0,
                   help="pull toward the current weights (higher = more cautious)")
    s.set_defaults(fn=cmd_tune)

    s = sub.add_parser("gaps", help="papers checked to have no implementation")
    s.add_argument("-n", "--limit", type=int, default=20)
    s.add_argument("--check", type=int, help="how many unchecked papers to check now")
    s.add_argument("--recheck", action="store_true", help="check again even if checked recently")
    s.add_argument("--no-check", action="store_true", help="just list, no network")
    s.set_defaults(fn=cmd_gaps)

    s = sub.add_parser("track", help="watch a chosen project's space for competitors")
    s.add_argument("action", nargs="?", default="list",
                   choices=["list", "add", "check", "show", "stop"])
    s.add_argument("name", nargs="?")
    s.add_argument("--from-brief", help="brief number or id; uses its dive's search terms")
    s.add_argument("--keywords", help="comma-separated search phrases")
    s.add_argument("-n", "--limit", type=int, default=30)
    s.set_defaults(fn=cmd_track)

    s = sub.add_parser("translate", help="translate page content into Simplified Chinese")
    s.add_argument("--dry-run", action="store_true", help="count and list, translate nothing")
    s.set_defaults(fn=cmd_translate)

    s = sub.add_parser("prune", help="delete items no recent run has seen")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_prune)

    s = sub.add_parser("hydrate", help="backfill GitHub metadata for repos missing it")
    s.add_argument("-n", "--limit", type=int)
    s.add_argument("--all", action="store_true", help="include forgotten items too")
    s.set_defaults(fn=cmd_hydrate)

    s = sub.add_parser("watch", help="show, extend, or get suggestions for the watchlist")
    s.add_argument("--add", nargs="+", help="GitHub logins to add to config.toml")
    s.add_argument("--suggest", action="store_true",
                   help="engineers your watchlist follows and whose stars overlap theirs")
    s.add_argument("-n", "--limit", type=int, default=10)
    s.set_defaults(fn=cmd_watch)

    s = sub.add_parser("doctor", help="check config, credentials and rate limits")
    s.set_defaults(fn=cmd_doctor)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    _setup(args.verbose)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        console.print("[yellow]interrupted[/]")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
