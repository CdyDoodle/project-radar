"""Static HTML dashboard + markdown digest. No server, no build step.

The whole feed is rendered into the page with data attributes, and filtering,
sorting, grouping and paging all happen client-side. That keeps it a single
file you can open from disk, mail to yourself, or keep open in a tab while a
scheduled run rewrites it underneath.

Two languages. Every piece of interface text, and the content through
radar.translate, is rendered in English and Simplified Chinese (`data-en` /
`data-zh`); the page's toggle switches without a rebuild and
`report.language` picks the default. Repo names stay as written.

The markup and styles live in radar/templates.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment
from markupsafe import Markup

from radar import axis, diversify, themes
from radar.config import Config
from radar.models import now
from radar.rank import explain
from radar.store import Store

LANGS = ("en", "zh")


def norm_lang(value) -> str:
    """'zh-CN', 'zh_CN', 'ZH' and 'zh' all mean Simplified Chinese."""
    v = str(value or "en").lower().replace("_", "-")
    return "zh" if v.startswith("zh") else "en"


# The page lives in radar/templates: dashboard.html (Jinja) and dashboard.css,
# spliced in at __CSS__ so the output stays one self-contained file.
TEMPLATES = Path(__file__).resolve().parent / "templates"
TEMPLATE = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")


def _both(en: str, zh: str) -> dict:
    return {"en": en, "zh": zh}


def _metrics_line(metrics: dict) -> dict:
    en, zh = [], []
    if metrics.get("stars"):
        en.append(f"{int(metrics['stars']):,}*"); zh.append(f"{int(metrics['stars']):,} 星")
    if metrics.get("stars_per_day_recent") is not None:
        r = metrics["stars_per_day_recent"]
        en.append(f"{r}/day now"); zh.append(f"近期 {r}/天")
    elif metrics.get("stars_per_day"):
        en.append(f"{metrics['stars_per_day']}/day"); zh.append(f"{metrics['stars_per_day']}/天")
    if metrics.get("hn_points"):
        en.append(f"HN {int(metrics['hn_points'])}"); zh.append(f"HN {int(metrics['hn_points'])} 分")
    if metrics.get("lobsters_score"):
        en.append(f"lob {int(metrics['lobsters_score'])}"); zh.append(f"Lobsters {int(metrics['lobsters_score'])} 分")
    if metrics.get("hf_upvotes"):
        en.append(f"HF {int(metrics['hf_upvotes'])}"); zh.append(f"HF {int(metrics['hf_upvotes'])} 赞")
    if metrics.get("bsky_likes"):
        en.append(f"bsky {int(metrics['bsky_likes'])}"); zh.append(f"Bluesky {int(metrics['bsky_likes'])} 赞")
    if metrics.get("starred_by"):
        who = ",".join(metrics["starred_by"][:4])
        en.append("watched by " + who); zh.append("关注者 star：" + who)
    if metrics.get("worked_on_by"):
        who = ",".join(metrics["worked_on_by"][:4])
        en.append("built by " + who); zh.append("关注者在做：" + who)
    if metrics.get("days_since_push") is not None:
        d = metrics["days_since_push"]
        en.append(f"push {d}d ago"); zh.append(f"{d} 天前推送")
    return _both("  ".join(en), "  ".join(zh))


def _reason(item, sources: list[str], is_new: bool, signals: dict | None = None) -> dict:
    """Why this item is worth a glance, built from signals already computed.

    Deterministic on purpose: the briefs section needs Claude Code, and the
    summary at the top of the page should still say something useful without it.
    """
    en, zh = [], []
    if is_new:
        en.append("new this run"); zh.append("本次新增")
    m = item.metrics
    sig = signals or {}
    if sig.get("stars_per_day_recent") is not None:
        r = sig["stars_per_day_recent"]
        en.append(f"{r}/day lately"); zh.append(f"近期每天 {r} 星")
        if sig.get("accel", 0) >= 2:
            en.append(f"{sig['accel']}x its usual pace"); zh.append(f"是平常的 {sig['accel']} 倍")
    elif m.get("stars_per_day"):
        en.append(f"{m['stars_per_day']}/day"); zh.append(f"每天 {m['stars_per_day']} 星")
    if m.get("stars"):
        en.append(f"{int(m['stars']):,} stars"); zh.append(f"{int(m['stars']):,} 星")
    if m.get("hn_points"):
        en.append(f"{int(m['hn_points'])} HN points"); zh.append(f"HN {int(m['hn_points'])} 分")
    if m.get("hf_upvotes"):
        en.append(f"{int(m['hf_upvotes'])} HF upvotes"); zh.append(f"Hugging Face {int(m['hf_upvotes'])} 赞")
    if m.get("bsky_likes"):
        en.append(f"{int(m['bsky_likes'])} Bluesky likes"); zh.append(f"Bluesky {int(m['bsky_likes'])} 赞")
    if m.get("starred_by"):
        who = ", ".join(m["starred_by"][:3])
        en.append("starred by " + who); zh.append(who + " 已 star")
    if m.get("worked_on_by"):
        who = ", ".join(m["worked_on_by"][:3])
        en.append("built by " + who); zh.append(who + " 正在开发")
    if len(sources) > 1:
        en.append(f"{len(sources)} sources agree"); zh.append(f"{len(sources)} 个来源共同提到")
    if m.get("arxiv_category"):
        en.append(m["arxiv_category"]); zh.append(m["arxiv_category"])
    if m.get("impl_checked_at"):
        if m.get("impl_count"):
            repo = (m.get("impl_repos") or ["?"])[0]
            en.append(f"has code: {repo}"); zh.append(f"已有代码：{repo}")
        else:
            en.append("no code found"); zh.append("未找到代码")
    return _both(" · ".join(en), " · ".join(zh))


LANES = {
    "saved": (_both("Saved", "已保存"),
              _both("what you marked worth keeping", "你标记为值得保留的条目")),
    "new": (_both("New this run", "本次新增"),
            _both("highest-scoring things that were not here last time", "上次没有、这次得分最高的条目")),
    "fastest": (_both("Moving fastest", "增长最快"),
                _both("star velocity against the rest of the corpus, famous repos excluded",
                      "相对整个语料库的星增速，不含已成名的仓库")),
    "agree": (_both("Several sources agree", "多个来源共同提到"),
              _both("independent corroboration is the strongest signal here", "多个来源独立印证是这里最强的信号")),
    "breakout": (_both("Breaking out", "正在爆发"),
                 _both("growing at least twice as fast as its lifetime average, measured between runs",
                       "两次运行之间测得的增速，至少是其历史平均的两倍")),
    "watchlist": (_both("From your watchlist", "来自你的关注列表"),
                  _both("engineers whose taste you chose to borrow", "你选择借鉴其眼光的工程师")),
    "papers": (_both("Papers nobody has implemented", "尚无人实现的论文"),
               _both("checked: no code on Hugging Face or GitHub. The gap is the project",
                     "已核实：Hugging Face 和 GitHub 上都没有代码。空白本身就是项目")),
    "papers_unchecked": (_both("Papers, not yet checked for code", "论文，尚未核实是否有代码"),
                         _both("run radar gaps to check which have no implementation",
                               "运行 radar gaps 核实哪些还没有实现")),
}


def _highlights(store: Store, cfg: Config, since: str | None,
                per_lane: int = 4) -> list[dict]:
    """A few small lanes, each answering a different question.

    One ranked list cannot say "this is moving fast" and "several sources
    independently agree" and "someone whose taste you trust starred this" at
    once -- those are different reasons to look, and collapsing them into a
    single score is exactly what loses the reason.
    """
    pool = store.items(limit=400)
    prepared = []
    for row in pool:
        item = store.to_item(row)
        bd = json.loads(row["breakdown"] or "{}")
        penalties = bd.get("penalties", {})
        prepared.append({
            "row": row, "item": item,
            "sources": sorted(item.sources),
            "is_new": bool(since and (row["first_seen"] or "") >= since),
            "mega": "mega" in penalties,
            "signals": bd.get("signals", {}),
        })

    def entry(p) -> dict:
        item = p["item"]
        ax = axis.of_item(item)
        th = themes.primary(themes.of_item(item))
        return {
            "title": item.title, "url": item.url, "key": item.key,
            "summary": (item.summary or "").strip(),
            "score": p["row"]["score"],
            "axis": _both(axis.label(ax), axis.label(ax, "zh")),
            "theme": _both(th, themes.label(th, "zh")),
            "reason": _reason(item, p["sources"], p["is_new"], p["signals"]),
        }

    used: set[str] = set()

    def take(candidates, n=per_lane):
        out = []
        for p in candidates:
            key = p["row"]["id"]
            if key in used:
                continue
            used.add(key)
            out.append(entry(p))
            if len(out) >= n:
                break
        return out

    by_score = sorted(prepared, key=lambda p: -p["row"]["score"])
    lanes = [
        ("saved", take([p for p in by_score if p["row"]["status"] == "saved"], n=6)),
        ("new", take([p for p in by_score if p["is_new"]])),
        # A 200k-star repo is the fastest thing on the page and the least
        # useful: you can't do frontier work where everyone already is.
        ("fastest", take(sorted(
            [p for p in prepared if p["item"].metrics.get("stars_per_day") and not p["mega"]],
            key=lambda p: -p["item"].metrics["stars_per_day"]))),
        ("breakout", take(sorted(
            [p for p in prepared if not p["mega"]
             and (p["signals"].get("accel") or 0) >= 2
             and (p["signals"].get("stars_per_day_recent") or 0) >= 5],
            key=lambda p: -p["signals"]["stars_per_day_recent"]))),
        ("agree", take([p for p in by_score if len(p["sources"]) > 1])),
        ("watchlist", take([p for p in by_score
                            if p["item"].metrics.get("starred_by") or p["item"].metrics.get("worked_on_by")])),
    ]
    papers = [p for p in by_score if p["row"]["key"].startswith("arxiv:")]
    checked = [p for p in papers if p["item"].metrics.get("impl_checked_at")]
    if checked:
        lanes.append(("papers", take([p for p in checked if not p["item"].metrics.get("impl_count")])))
    else:
        lanes.append(("papers_unchecked", take(papers)))
    return [{"key": k, "title": LANES[k][0], "note": LANES[k][1], "items": i}
            for k, i in lanes if i]


def _rows(store: Store, cfg: Config, limit: int) -> list[dict]:
    """Feed rows in curated (redundancy-filtered) order.

    The client can re-sort by raw score, so curated order is emitted as a
    position index rather than being the only thing available.
    """
    ranked = store.items(limit=max(limit * 2, limit + 60))
    ordered = diversify.diversified(store, ranked, cfg, limit)

    items = [store.to_item(r) for r in ordered]
    theme_sets = [themes.of_item(it) for it in items]

    out = []
    for row, item, tset in zip(ordered, items, theme_sets):
        breakdown = json.loads(row["breakdown"] or "{}")
        age = None
        if item.created_at:
            age = (now() - item.created_at).total_seconds() / 86400
        ax = axis.of_item(item)
        out.append({
            "key": item.key, "status": row["status"], "note": row["note"] or "",
            "score": row["score"], "title": item.title, "url": item.url,
            "summary": item.summary or "", "lang": item.lang,
            "topics": item.topics, "sources": sorted(item.sources),
            "themes": sorted(tset),
            "theme_labels": [_both(t, themes.label(t, "zh")) for t in sorted(tset)],
            "primary": themes.primary(tset),
            "axis": ax,
            "axis_label": _both(axis.label(ax), axis.label(ax, "zh")),
            "why": _both(explain(breakdown), explain(breakdown, "zh")),
            "metrics_line": _metrics_line({**item.metrics, **breakdown.get("signals", {})}),
            "velocity": round(breakdown.get("components", {}).get("velocity", 0), 4),
            "age_days": round(age, 1) if age is not None else 99999,
            "stars": int(item.metrics.get("stars") or 0),
        })
    return out


def _run_date(run_id: str) -> str:
    try:
        return datetime.strptime(run_id[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return run_id


def _past_briefs(store: Store, current_run: str, max_runs: int = 5) -> list[dict]:
    """Briefs from earlier runs, newest run first, so ideas aren't lost."""
    groups: dict[str, list[dict]] = {}
    for b in store.briefs(limit=200):
        if b["_run"] != current_run:
            groups.setdefault(b["_run"], []).append(b)
    runs = sorted(groups, reverse=True)[:max_runs]
    return [{"run": r, "date": _run_date(r), "briefs": groups[r]} for r in runs]


def build(cfg: Config, store: Store, run_id: str | None = None,
          feed_limit: int = 250, api_token: str | None = None,
          record: set | None = None) -> tuple[Path, Path]:
    """Write the dashboard and digest.

    `api_token` is set only by `radar serve`: the page then talks to the local
    server. The published page never carries one and stays fully static.

    `record` is for radar.translate: render without writing anything, adding
    every content string the page shows to the set.
    """
    from radar.translate import Translator
    tr = Translator(store, record)
    lang = norm_lang(cfg.get("report.language", "en"))
    run_id = run_id or store.latest_run() or "adhoc"
    briefs = store.briefs(run_id=run_id)
    if not briefs:
        # A run without briefs (--no-llm, a quick rerun) shows the latest run
        # that has them, in their own order: the numbers on the page must match
        # `radar dive <n>`. The old fallback took the newest N across runs,
        # newest first, which reversed them.
        latest = store.conn.execute(
            "SELECT run_id FROM briefs ORDER BY created_at DESC LIMIT 1").fetchone()
        briefs = store.briefs(run_id=latest["run_id"]) if latest else []
    shown_run = briefs[0]["_run"] if briefs else run_id
    past = _past_briefs(store, shown_run)
    dives = store.dives_for([b["_id"] for b in briefs])
    from radar import track as tk
    run_no = store.current_fetch()
    tracks = []
    for t in tk.tracks(store):
        t["new"] = tk.new_hits(t, run_no)
        tracks.append(t)
    rows = _rows(store, cfg, feed_limit)
    since = store.run_started(run_id)
    highlights = _highlights(store, cfg, since)
    counts_axis = Counter(r["axis"] for r in rows)
    mix = {
        # "new" counts the whole run, not just what reached the highlights.
        "new": store.count_since(since) if since else 0,
        "infra": counts_axis.get("ai-infra", 0),
        "applied": counts_axis.get("ai-application", 0),
        "nonai": counts_axis.get("non-ai", 0),
    }
    source_names = sorted({s for r in rows for s in r["sources"]})
    theme_ids = sorted({t for r in rows for t in r["themes"]})
    theme_names = [{"id": t, "en": t, "zh": themes.label(t, "zh")} for t in theme_ids]
    languages = sorted({r["lang"] for r in rows if r["lang"]})
    counts = store.counts()
    # "Tracked" is what recent runs still see; forgotten items are not in play.
    stats = {"total": len(store.items(include_dismissed=True)),
             "sources": source_names, **counts}
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    env = Environment(autoescape=True)

    def T(text):
        """Content in both languages; Chinese falls back to the original."""
        if not text:
            return ""
        zh = tr(text) or text
        return Markup('<span data-en="{0}" data-zh="{1}">{2}</span>').format(
            text, zh, zh if lang == "zh" else text)

    def TT(title, key):
        # Repo names are names; headlines and paper titles are prose.
        return title if str(key or "").startswith("gh:") else T(title)

    env.globals.update(T=T, TT=TT, tr=tr)
    html = env.from_string(TEMPLATE.replace("__CSS__", CSS)).render(
        generated=generated, run_id=run_id, briefs=briefs, past=past, rows=rows,
        dives=dives, api=api_token, tracks=tracks, run_no=run_no,
        source_names=source_names, theme_names=theme_names, languages=languages,
        theme_labels=themes.LABELS_ZH, lang=lang,
        axes=[{"id": a, "en": axis.label(a), "zh": axis.label(a, "zh")} for a in axis.ALL_AXES],
        stats=stats, summary=(briefs[0].get("board_summary") if briefs else ""),
        highlights=highlights, mix=mix,
    )
    if record is not None:
        return None, None
    if api_token:
        # Never overwrite index.html with a page carrying the local API token:
        # index.html is what `radar publish` ships.
        served = cfg.out_dir / "served.html"
        served.write_text(html, encoding="utf-8")
        return served, None
    html_path = cfg.out_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")

    md_path = cfg.out_dir / f"digest-{datetime.now():%Y-%m-%d}.md"
    md_path.write_text(_markdown(briefs, rows, generated, highlights, mix, lang,
                                 (lambda t: (tr(t) or t) if t else t) if lang == "zh" else None),
                       encoding="utf-8")
    return html_path, md_path


MD = {
    "en": {"digest": "radar digest", "new": "new", "infra": "AI infra", "applied": "AI applied",
           "nonai": "no AI", "worth": "Worth a look", "briefs": "Project briefs",
           "difficulty": "difficulty", "novelty": "novelty", "weeks": "weeks",
           "why_now": "Why now.", "hard": "Hard parts", "learn": "You will learn",
           "milestones": "Milestones", "prior": "Prior art", "kill": "Kill criteria.",
           "sources": "Sources", "ranked": "Ranked signal"},
    "zh": {"digest": "radar 摘要", "new": "本次新增", "infra": "AI 基础设施", "applied": "AI 应用",
           "nonai": "非 AI", "worth": "值得一看", "briefs": "项目简报",
           "difficulty": "难度", "novelty": "新颖度", "weeks": "周",
           "why_now": "为什么是现在。", "hard": "难点", "learn": "你会学到",
           "milestones": "里程碑", "prior": "已有工作", "kill": "放弃标准。",
           "sources": "来源", "ranked": "排名信号"},
}


def _markdown(briefs: list[dict], rows: list[dict], generated: str,
              highlights: list[dict] | None = None, mix: dict | None = None,
              lang: str = "en", tr=None) -> str:
    W = MD.get(lang, MD["en"])
    t = tr or (lambda x: x)
    L = [f"# {W['digest']} - {generated}", ""]
    if mix:
        L += [f"`{mix['new']} {W['new']}` · `{mix['infra']} {W['infra']}` · "
              f"`{mix['applied']} {W['applied']}` · `{mix['nonai']} {W['nonai']}`", ""]
    if highlights:
        L += ["<details open>", f"<summary><b>{W['worth']}</b></summary>", ""]
        for lane in highlights:
            L += [f"### {lane['title'][lang]}", f"*{lane['note'][lang]}*", ""]
            for it in lane["items"]:
                # Repo names stay; paper and headline titles are translated.
                title = it["title"] if str(it.get("key", "")).startswith("gh:") else t(it["title"])
                L.append(f"- **[{title.replace('|', chr(92) + '|')}]({it['url']})** "
                         f"`{it['score']:.2f}` — {it['reason'][lang]}")
                if it["summary"]:
                    L.append(f"  <br>{t(it['summary'][:150])}")
            L.append("")
        L += ["</details>", "", "---", ""]
    if briefs and briefs[0].get("board_summary"):
        L += ["> " + t(briefs[0]["board_summary"]), ""]
    if briefs:
        L += [f"## {W['briefs']}", ""]
        for i, b in enumerate(briefs, 1):
            weeks = (f"约 {b['effort_weeks']} 周" if lang == "zh"
                     else f"~{b['effort_weeks']} weeks")
            L += [
                f"### {i}. {t(b['title'])}",
                f"*{t(b['one_liner'])}*", "",
                f"`{W['difficulty']} {b['difficulty']}/5`  `{W['novelty']} {b['novelty']}/5`  "
                f"`{weeks}`", "",
                t(b["pitch"]), "",
                f"**{W['why_now']}** {t(b['why_now'])}", "",
                f"**{W['hard']}**", *[f"- {t(h)}" for h in b["hard_parts"]], "",
                f"**{W['learn']}**", *[f"- {t(h)}" for h in b["you_will_learn"]], "",
                f"**{W['milestones']}**", *[f"- {t(m)}" for m in b["milestones"]], "",
                f"**{W['prior']}**", *[f"- {t(p)}" for p in b["prior_art"]], "",
                f"**{W['kill']}** {t(b['kill_criteria'])}", "",
                f"**{W['sources']}**", *[f"- {u}" for u in b["source_urls"]], "", "---", "",
            ]
    # Group the digest by theme -- reads far better than a flat 60-row table.
    L += [f"## {W['ranked']}", ""]
    by_theme: dict[str, list[dict]] = {}
    for r in rows[:80]:
        by_theme.setdefault(r["primary"], []).append(r)

    def order(kv):
        theme, group = kv
        # Unclassified last; otherwise best-scoring theme first.
        return (theme == themes.UNCLASSIFIED, -max(r["score"] for r in group))

    for theme, group in sorted(by_theme.items(), key=order):
        L += [f"### {themes.label(theme, lang)}  ({len(group)})", ""]
        for r in group:
            title = (r["title"] if r["key"].startswith("gh:") else t(r["title"])).replace("|", "\\|")
            L.append(f"- **{r['score']:.2f}** [{title}]({r['url']}) — {r['why'][lang]}")
        L.append("")
    return "\n".join(L) + "\n"


CSS = (TEMPLATES / "dashboard.css").read_text(encoding="utf-8")
