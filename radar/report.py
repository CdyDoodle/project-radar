"""Static HTML dashboard + markdown digest. No server, no build step.

The whole feed is rendered into the page with data attributes, and filtering,
sorting, grouping and paging all happen client-side. That keeps it a single
file you can open from disk, mail to yourself, or keep open in a tab while a
scheduled run rewrites it underneath.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment

from radar import diversify, themes
from radar.config import Config
from radar.models import now
from radar.rank import explain
from radar.store import Store

TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>radar - {{ generated }}</title>
<style>
:root{
  --bg:#fbfaf8; --panel:#fff; --ink:#1a1a19; --muted:#6b6a67; --line:#e6e3dd;
  --accent:#b8563a; --accent-soft:#fdf1ec; --good:#2f6f4f; --warn:#96702a;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
  --bg:#17171a; --panel:#1f1f23; --ink:#eceae6; --muted:#9b9994; --line:#33333a;
  --accent:#e08a6c; --accent-soft:#2a201d; --good:#7bbd97; --warn:#d4ab61;
}}
:root[data-theme=dark]{
  --bg:#17171a; --panel:#1f1f23; --ink:#eceae6; --muted:#9b9994; --line:#33333a;
  --accent:#e08a6c; --accent-soft:#2a201d; --good:#7bbd97; --warn:#d4ab61;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;}
.wrap{max-width:1120px;margin:0 auto;padding:32px 20px 80px}
header{border-bottom:2px solid var(--ink);padding-bottom:14px;margin-bottom:24px;
  display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
h1 span{color:var(--accent)}
.sub{color:var(--muted);font-size:13px;font-family:var(--mono)}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);
  margin:44px 0 14px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.summary{background:var(--accent-soft);border-left:3px solid var(--accent);
  padding:16px 18px;border-radius:0 6px 6px 0;margin-bottom:8px}
.brief{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:20px 22px;margin-bottom:16px}
.brief h3{margin:0 0 2px;font-size:19px;letter-spacing:-.01em}
.brief .one{color:var(--accent);font-size:14px;margin-bottom:12px}
.pills{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}
.pill{font-family:var(--mono);font-size:11px;padding:2px 8px;border-radius:99px;
  border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.pill.hot{border-color:var(--accent);color:var(--accent)}
.pill.ok{border-color:var(--good);color:var(--good)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:14px}
@media(max-width:720px){.cols{grid-template-columns:1fr}}
.blk h4{margin:0 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--muted)}
.blk ul{margin:0;padding-left:18px}.blk li{margin-bottom:4px;font-size:14px}
.kill{margin-top:14px;padding:10px 12px;border:1px dashed var(--line);border-radius:6px;
  font-size:13px}.kill b{color:var(--warn)}
.srcs{margin-top:12px;font-size:12px;font-family:var(--mono);word-break:break-all}
.srcs a{color:var(--muted)}

/* ---- control bar ---- */
.bar{position:sticky;top:0;z-index:20;background:var(--bg);
  padding:12px 0 10px;border-bottom:1px solid var(--line);margin-bottom:4px}
.bar-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.bar-row:last-child{margin-bottom:0}
input[type=search]{flex:1;min-width:200px;padding:7px 11px;border:1px solid var(--line);
  border-radius:6px;background:var(--panel);color:var(--ink);font-size:14px}
select{padding:6px 8px;border:1px solid var(--line);border-radius:6px;
  background:var(--panel);color:var(--ink);font-size:12px;font-family:var(--mono)}
label.ctl{font-family:var(--mono);font-size:11px;color:var(--muted);
  display:inline-flex;align-items:center;gap:5px}
button{font-family:var(--mono);font-size:11px;padding:4px 10px;border:1px solid var(--line);
  border-radius:99px;background:var(--panel);color:var(--muted);cursor:pointer}
button:hover{border-color:var(--accent)}
button.on{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
.chipset{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
.chipset .lbl{font-family:var(--mono);font-size:10px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--muted);margin-right:2px}
.count{font-family:var(--mono);font-size:11px;color:var(--muted);margin-left:auto}

/* ---- feed ---- */
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--muted);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--line)}
td{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
tr.item:hover td{background:var(--panel)}
tr.grp td{background:transparent;border-bottom:2px solid var(--ink);
  padding:22px 8px 5px;font-family:var(--mono);font-size:11px;text-transform:uppercase;
  letter-spacing:.1em;color:var(--accent);font-weight:700;
  cursor:pointer;user-select:none}
tr.grp td:hover{background:var(--accent-soft)}
tr.grp td:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
tr.grp td span{color:var(--muted);font-weight:400;letter-spacing:0;text-transform:none}
tr.grp.closed td{border-bottom:1px dashed var(--line)}
.chev{display:inline-block;width:11px;font-weight:700}
.score{font-family:var(--mono);font-weight:600;white-space:nowrap}
.why{font-family:var(--mono);font-size:11px;color:var(--muted)}
a{color:var(--ink)}a:hover{color:var(--accent)}
.desc{color:var(--muted);font-size:13px;display:block;margin:2px 0 4px}
.tag{font-family:var(--mono);font-size:10px;color:var(--muted);
  border:1px solid var(--line);border-radius:3px;padding:1px 5px;
  margin:0 3px 3px 0;display:inline-block}
.tag.th{border-color:var(--accent);color:var(--accent)}
.wide{overflow-x:auto}
.empty{padding:40px 8px;text-align:center;color:var(--muted);font-family:var(--mono);
  font-size:13px}
footer{margin-top:60px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--muted);font-size:12px;font-family:var(--mono)}
kbd{font-family:var(--mono);font-size:10px;border:1px solid var(--line);
  border-radius:3px;padding:1px 4px}
</style></head><body><div class="wrap">

<header>
  <div>
    <h1>radar<span>.</span></h1>
    <div class="sub">{{ generated }} &middot; {{ stats.total }} tracked &middot;
      {{ rows|length }} in feed &middot; {{ briefs|length }} briefs</div>
  </div>
  <button id="theme-toggle" title="toggle light/dark">theme</button>
</header>

{% if summary %}
<div class="summary"><strong>Where the board is pointing.</strong> {{ summary }}</div>
{% endif %}

{% if briefs %}
<h2>Project briefs</h2>
{% for b in briefs %}
<article class="brief">
  <h3>{{ loop.index }}. {{ b.title }}</h3>
  <div class="one">{{ b.one_liner }}</div>
  <div class="pills">
    <span class="pill hot">difficulty {{ b.difficulty }}/5</span>
    <span class="pill">novelty {{ b.novelty }}/5</span>
    <span class="pill">~{{ b.effort_weeks }} weeks</span>
    {% if b.ai_leverage %}<span class="pill ok">AI: {{ b.ai_leverage[:60] }}</span>{% endif %}
  </div>
  <p>{{ b.pitch }}</p>
  <p><strong>Why now.</strong> {{ b.why_now }}</p>
  <div class="cols">
    <div class="blk"><h4>Hard parts</h4><ul>
      {% for h in b.hard_parts %}<li>{{ h }}</li>{% endfor %}</ul></div>
    <div class="blk"><h4>You will learn</h4><ul>
      {% for h in b.you_will_learn %}<li>{{ h }}</li>{% endfor %}</ul></div>
  </div>
  <div class="cols">
    <div class="blk"><h4>Milestones</h4><ul>
      {% for m in b.milestones %}<li>{{ m }}</li>{% endfor %}</ul></div>
    <div class="blk"><h4>Prior art</h4><ul>
      {% for p in b.prior_art %}<li>{{ p }}</li>{% endfor %}</ul></div>
  </div>
  <div class="kill"><b>Kill criteria.</b> {{ b.kill_criteria }}</div>
  <div class="srcs">{% for u in b.source_urls %}<a href="{{ u }}">{{ u }}</a><br>{% endfor %}</div>
</article>
{% endfor %}
{% endif %}

<h2>Ranked signal</h2>
<div class="bar">
  <div class="bar-row">
    <input type="search" id="q" placeholder="filter by name, description, topic, language...   ( / )">
    <label class="ctl">show
      <select id="show">
        <option value="25">25</option>
        <option value="50" selected>50</option>
        <option value="100">100</option>
        <option value="250">250</option>
        <option value="0">all</option>
      </select></label>
    <label class="ctl">sort
      <select id="sort">
        <option value="curated">curated (redundancy-filtered)</option>
        <option value="score">score</option>
        <option value="velocity">velocity</option>
        <option value="newest">newest</option>
        <option value="stars">stars</option>
      </select></label>
    <label class="ctl">lang
      <select id="lang"><option value="">any</option>
        {% for l in languages %}<option value="{{ l }}">{{ l }}</option>{% endfor %}
      </select></label>
    <button id="group">group by theme</button>
    <button id="collapse">collapse all</button>
  </div>
  <div class="bar-row chipset">
    <span class="lbl">theme</span>
    {% for t in theme_names %}<button data-theme="{{ t }}">{{ t }}</button>{% endfor %}
  </div>
  <div class="bar-row chipset">
    <span class="lbl">source</span>
    {% for s in source_names %}<button data-src="{{ s }}">{{ s }}</button>{% endfor %}
    <button id="reset">reset</button>
    <span class="count" id="count"></span>
  </div>
</div>

<div class="wide"><table id="feed">
<thead><tr><th style="width:56px">score</th><th>item</th><th style="width:230px">signal</th></tr></thead>
<tbody id="body">
{% for r in rows %}
<tr class="item"
    data-text="{{ (r.title ~ ' ' ~ r.summary ~ ' ' ~ (r.lang or '') ~ ' ' ~ r.topics|join(' ') ~ ' ' ~ r.themes|join(' '))|lower }}"
    data-sources="{{ r.sources|join(' ') }}"
    data-themes="{{ r.themes|join(' ') }}"
    data-primary="{{ r.primary }}"
    data-lang="{{ r.lang or '' }}"
    data-score="{{ r.score }}" data-vel="{{ r.velocity }}"
    data-age="{{ r.age_days }}" data-stars="{{ r.stars }}"
    data-curated="{{ loop.index0 }}">
  <td class="score">{{ '%.2f'|format(r.score) }}</td>
  <td>
    <a href="{{ r.url }}"><strong>{{ r.title }}</strong></a>
    <span class="desc">{{ r.summary[:190] }}</span>
    {% if r.lang %}<span class="tag">{{ r.lang }}</span>{% endif %}
    {% for t in r.themes %}<span class="tag th">{{ t }}</span>{% endfor %}
    {% for s in r.sources %}<span class="tag">{{ s }}</span>{% endfor %}
  </td>
  <td class="why">{{ r.why }}<br>{{ r.metrics_line }}</td>
</tr>
{% endfor %}
</tbody></table>
<div class="empty" id="empty" hidden>nothing matches those filters</div></div>

<footer>
  generated by radar &middot; sources: {{ stats.sources|join(', ') }}<br>
  &quot;curated&quot; order is redundancy-filtered so near-identical projects don't stack;
  switch sort to <em>score</em> for raw ranking. Tune in config.toml, then
  <code>radar rank</code>.
</footer>
</div>
<script>
(function(){
const $=s=>document.querySelector(s);
const body=$('#body'), q=$('#q'), showSel=$('#show'), sortSel=$('#sort'),
      langSel=$('#lang'), groupBtn=$('#group'), collapseBtn=$('#collapse'),
      countEl=$('#count'), emptyEl=$('#empty');
const items=[...body.querySelectorAll('tr.item')];
const state={src:'', themes:new Set(), group:true, collapsed:new Set()};

try{ const s=JSON.parse(localStorage.getItem('radar-prefs')||'{}');
  if(s.show) showSel.value=s.show; if(s.sort) sortSel.value=s.sort;
  if(s.lang) langSel.value=s.lang;
  // Explicit undefined check: a stored `false` must survive a `true` default.
  if(s.group!==undefined) state.group=!!s.group;
  if(Array.isArray(s.collapsed)) state.collapsed=new Set(s.collapsed);
}catch(e){}
function save(){ try{ localStorage.setItem('radar-prefs', JSON.stringify({
  show:showSel.value, sort:sortSel.value, lang:langSel.value, group:state.group,
  collapsed:[...state.collapsed]}));
}catch(e){} }

const num=(r,k)=>parseFloat(r.dataset[k])||0;
const CMP={
  curated:(a,b)=>num(a,'curated')-num(b,'curated'),
  score:  (a,b)=>num(b,'score')-num(a,'score'),
  velocity:(a,b)=>num(b,'vel')-num(a,'vel'),
  newest: (a,b)=>num(a,'age')-num(b,'age'),
  stars:  (a,b)=>num(b,'stars')-num(a,'stars'),
};

function matches(r){
  const t=q.value.toLowerCase().trim();
  if(t && !r.dataset.text.includes(t)) return false;
  if(state.src && !r.dataset.sources.split(' ').includes(state.src)) return false;
  if(langSel.value && r.dataset.lang!==langSel.value) return false;
  if(state.themes.size){
    const own=r.dataset.themes.split(' ').filter(Boolean);
    if(!own.some(x=>state.themes.has(x))) return false;
  }
  return true;
}

function toggleGroup(name){
  if(state.collapsed.has(name)) state.collapsed.delete(name);
  else state.collapsed.add(name);
  render();
}

function header(name, n, closed){
  const tr=document.createElement('tr'); tr.className='grp'+(closed?' closed':'');
  const td=document.createElement('td'); td.colSpan=3;
  td.setAttribute('role','button'); td.tabIndex=0;
  td.setAttribute('aria-expanded', String(!closed));
  const chev=document.createElement('b');
  chev.className='chev'; chev.textContent = closed ? '\\u25B8' : '\\u25BE';
  td.appendChild(chev);
  td.appendChild(document.createTextNode(' '+name));
  const s=document.createElement('span');
  s.textContent='  '+n+' item'+(n===1?'':'s')+(closed?' (hidden)':'');
  td.appendChild(s);
  td.addEventListener('click',()=>toggleGroup(name));
  td.addEventListener('keydown',e=>{
    if(e.key==='Enter'||e.key===' '){e.preventDefault();toggleGroup(name);}});
  tr.appendChild(td); return tr;
}

function render(){
  let vis=items.filter(matches);
  vis.sort(CMP[sortSel.value]||CMP.curated);
  const total=vis.length;
  const lim=parseInt(showSel.value,10);
  if(lim>0) vis=vis.slice(0,lim);
  items.forEach(r=>r.remove());
  body.textContent='';
  let hidden=0, groupNames=[];
  if(state.group){
    const groups=new Map();
    vis.forEach(r=>{const k=r.dataset.primary||'other';
      if(!groups.has(k)) groups.set(k,[]); groups.get(k).push(r);});
    const best=rs=>Math.max(...rs.map(r=>parseFloat(r.dataset.score)||0));
    const ordered=[...groups.entries()].sort((a,b)=>{
        if(a[0]==='other') return 1; if(b[0]==='other') return -1;
        return best(b[1])-best(a[1]);});
    groupNames=ordered.map(g=>g[0]);
    ordered.forEach(([name,rs])=>{
      const closed=state.collapsed.has(name);
      body.appendChild(header(name,rs.length,closed));
      if(closed) hidden+=rs.length; else rs.forEach(r=>body.appendChild(r));
    });
  } else vis.forEach(r=>body.appendChild(r));
  emptyEl.hidden = total>0;
  const collapsedHere=groupNames.filter(n=>state.collapsed.has(n));
  countEl.textContent = `showing ${vis.length-hidden} of ${total} matched`
    + (hidden ? ` · ${hidden} collapsed` : '') + ` · ${items.length} in feed`;
  groupBtn.classList.toggle('on', state.group);
  collapseBtn.hidden = !state.group;
  collapseBtn.textContent = collapsedHere.length ? 'expand all' : 'collapse all';
  save();
}

q.addEventListener('input',render);
[showSel,sortSel,langSel].forEach(el=>el.addEventListener('change',render));
groupBtn.addEventListener('click',()=>{state.group=!state.group;render();});
collapseBtn.addEventListener('click',()=>{
  // Only act on groups currently on screen, so "collapse all" can't strand a
  // stale name in the persisted set and leave the button stuck on "expand all".
  const names=[...new Set(items.filter(matches).map(r=>r.dataset.primary||'other'))];
  if(names.some(n=>state.collapsed.has(n))) names.forEach(n=>state.collapsed.delete(n));
  else names.forEach(n=>state.collapsed.add(n));
  render();});
document.querySelectorAll('button[data-src]').forEach(b=>b.addEventListener('click',()=>{
  const v=b.dataset.src, on=state.src===v;
  document.querySelectorAll('button[data-src]').forEach(x=>x.classList.remove('on'));
  state.src = on?'':v; if(!on) b.classList.add('on'); render();}));
document.querySelectorAll('button[data-theme]').forEach(b=>b.addEventListener('click',()=>{
  const v=b.dataset.theme;
  if(state.themes.has(v)){state.themes.delete(v); b.classList.remove('on');}
  else {state.themes.add(v); b.classList.add('on');}
  render();}));
$('#reset').addEventListener('click',()=>{
  q.value=''; langSel.value=''; state.src=''; state.themes.clear();
  document.querySelectorAll('.chipset button').forEach(x=>x.classList.remove('on'));
  render();});
document.addEventListener('keydown',e=>{
  if(e.key==='/' && document.activeElement!==q){e.preventDefault();q.focus();}
  if(e.key==='Escape' && document.activeElement===q){q.value='';q.blur();render();}});
$('#theme-toggle').addEventListener('click',()=>{
  const cur=document.documentElement.getAttribute('data-theme');
  const next = cur==='dark' ? 'light' : cur==='light' ? '' : 'dark';
  if(next) document.documentElement.setAttribute('data-theme',next);
  else document.documentElement.removeAttribute('data-theme');});
render();
})();
</script>
</body></html>
"""


def _metrics_line(metrics: dict) -> str:
    bits = []
    if metrics.get("stars"):
        bits.append(f"{int(metrics['stars']):,}*")
    if metrics.get("stars_per_day"):
        bits.append(f"{metrics['stars_per_day']}/day")
    if metrics.get("hn_points"):
        bits.append(f"HN {int(metrics['hn_points'])}")
    if metrics.get("lobsters_score"):
        bits.append(f"lob {int(metrics['lobsters_score'])}")
    if metrics.get("starred_by"):
        bits.append("watched by " + ",".join(metrics["starred_by"][:4]))
    if metrics.get("days_since_push") is not None:
        bits.append(f"push {metrics['days_since_push']}d ago")
    return "  ".join(bits)


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
        out.append({
            "score": row["score"], "title": item.title, "url": item.url,
            "summary": item.summary or "", "lang": item.lang,
            "topics": item.topics, "sources": sorted(item.sources),
            "themes": sorted(tset),
            "primary": themes.primary(tset),
            "why": explain(breakdown),
            "metrics_line": _metrics_line(item.metrics),
            "velocity": round(breakdown.get("components", {}).get("velocity", 0), 4),
            "age_days": round(age, 1) if age is not None else 99999,
            "stars": int(item.metrics.get("stars") or 0),
        })
    return out


def build(cfg: Config, store: Store, run_id: str | None = None,
          feed_limit: int = 250) -> tuple[Path, Path]:
    run_id = run_id or store.latest_run() or "adhoc"
    briefs = store.briefs(run_id=run_id) or store.briefs(limit=int(cfg.get("brief.count", 8)))
    rows = _rows(store, cfg, feed_limit)
    source_names = sorted({s for r in rows for s in r["sources"]})
    theme_names = sorted({t for r in rows for t in r["themes"]})
    languages = sorted({r["lang"] for r in rows if r["lang"]})
    counts = store.counts()
    stats = {"total": sum(counts.values()), "sources": source_names, **counts}
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    env = Environment(autoescape=True)
    html = env.from_string(TEMPLATE).render(
        generated=generated, run_id=run_id, briefs=briefs, rows=rows,
        source_names=source_names, theme_names=theme_names, languages=languages,
        stats=stats, summary=(briefs[0].get("board_summary") if briefs else ""),
    )
    html_path = cfg.out_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")

    md_path = cfg.out_dir / f"digest-{datetime.now():%Y-%m-%d}.md"
    md_path.write_text(_markdown(briefs, rows, generated), encoding="utf-8")
    return html_path, md_path


def _markdown(briefs: list[dict], rows: list[dict], generated: str) -> str:
    L = [f"# radar digest - {generated}", ""]
    if briefs and briefs[0].get("board_summary"):
        L += ["> " + briefs[0]["board_summary"], ""]
    if briefs:
        L += ["## Project briefs", ""]
        for i, b in enumerate(briefs, 1):
            L += [
                f"### {i}. {b['title']}",
                f"*{b['one_liner']}*", "",
                f"`difficulty {b['difficulty']}/5`  `novelty {b['novelty']}/5`  "
                f"`~{b['effort_weeks']} weeks`", "",
                b["pitch"], "",
                f"**Why now.** {b['why_now']}", "",
                "**Hard parts**", *[f"- {h}" for h in b["hard_parts"]], "",
                "**You will learn**", *[f"- {h}" for h in b["you_will_learn"]], "",
                "**Milestones**", *[f"- {m}" for m in b["milestones"]], "",
                "**Prior art**", *[f"- {p}" for p in b["prior_art"]], "",
                f"**Kill criteria.** {b['kill_criteria']}", "",
                "**Sources**", *[f"- {u}" for u in b["source_urls"]], "", "---", "",
            ]
    # Group the digest by theme -- reads far better than a flat 60-row table.
    L += ["## Ranked signal", ""]
    by_theme: dict[str, list[dict]] = {}
    for r in rows[:80]:
        by_theme.setdefault(r["primary"], []).append(r)
    def order(kv):
        theme, group = kv
        # Unclassified last; otherwise best-scoring theme first.
        return (theme == themes.UNCLASSIFIED, -max(r["score"] for r in group))

    for theme, group in sorted(by_theme.items(), key=order):
        L += [f"### {theme}  ({len(group)})", ""]
        for r in group:
            title = r["title"].replace("|", "\\|")
            L.append(f"- **{r['score']:.2f}** [{title}]({r['url']}) — {r['why']}")
        L.append("")
    return "\n".join(L) + "\n"
