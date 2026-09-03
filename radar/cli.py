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
from radar.store import Store

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
    return cfg, Store(cfg.db_path)


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
    with console.status("fetching sources..."):
        stats = collect.collect(cfg, store)
    table = Table(title="fetch", show_edge=False, header_style="dim")
    table.add_column("source"); table.add_column("items", justify="right")
    for k, v in stats.items():
        if not k.startswith("_"):
            table.add_row(k, str(v))
    console.print(table)
    console.print(f"[dim]{stats['_raw']} raw -> {stats['_merged']} unique "
                  f"({stats['_collapsed']} cross-source duplicates collapsed)[/]")
    return 0


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

    rank.rank_all(store, cfg)
    console.print("[green]rank[/]    scored")

    with console.status("3/5 fetching READMEs..."):
        n = collect.enrich(cfg, store, limit=int(cfg.get("brief.cards", 18)))
    console.print(f"[green]enrich[/]  {n} READMEs")

    if args.no_llm:
        console.print("[yellow]skipping LLM passes (--no-llm)[/]")
    else:
        with console.status("4/5 triaging items with Claude (pass A)..."):
            cards = ideate.make_cards(cfg, store)
        console.print(f"[green]cards[/]   {cards}")
        with console.status("5/5 synthesizing project briefs (pass B)..."):
            briefs = ideate.make_briefs(cfg, store, run_id)
        console.print(f"[green]briefs[/]  {len(briefs)}")

    store.finish_run(run_id, stats)
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
    console.print(f"[dim]sources[/]  {', '.join(sorted(item.sources))}")
    console.print(f"[dim]status[/]   {row['status']}")
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
    return 0


def cmd_watch(args) -> int:
    cfg, _ = _open(config.load(args.home))
    users = cfg.watchlist
    if args.add:
        console.print("Add to [bold]sources.github_starred.users[/] in config.toml:")
        for u in args.add:
            console.print(f'  "{u}",')
        return 0
    console.print(f"watching {len(users)} engineers: {', '.join(users)}")
    return 0


def cmd_doctor(args) -> int:
    import os
    cfg = config.load(args.home)
    store = Store(cfg.db_path)
    http = collect.make_http(cfg)
    console.print(f"config     {cfg.home / config.CONFIG_NAME}")
    console.print(f"database   {cfg.db_path}  {store.counts()}")
    token = config.github_token()
    console.print(f"gh token   {'[green]yes[/]' if token else '[red]no[/]'}")
    if token:
        core = http.gh_rate().get("core", {})
        search = http.gh_rate().get("search", {})
        console.print(f"  core   {core.get('remaining')}/{core.get('limit')}")
        console.print(f"  search {search.get('remaining')}/{search.get('limit')}")
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    console.print(f"anthropic  {'[green]key set[/]' if key else '[yellow]no key -- `brief` will not run[/]'}")
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

    s = sub.add_parser("cards", help="LLM pass A: triage top items")
    s.add_argument("-n", "--limit", type=int)
    s.set_defaults(fn=cmd_cards)

    s = sub.add_parser("brief", help="LLM pass B: synthesize project briefs")
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
    s.add_argument("--no-llm", action="store_true", help="skip the Claude passes")
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("show", help="everything known about one item")
    s.add_argument("ident", help="item id or key (e.g. gh:owner/repo)")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("save", help="mark items as saved")
    s.add_argument("idents", nargs="+")
    s.set_defaults(fn=lambda a: cmd_verdict(a, "saved"))

    s = sub.add_parser("dismiss", help="never show these again")
    s.add_argument("idents", nargs="+")
    s.set_defaults(fn=lambda a: cmd_verdict(a, "dismissed"))

    s = sub.add_parser("watch", help="show or extend the engineer watchlist")
    s.add_argument("--add", nargs="+")
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
