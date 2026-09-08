"""Static HTML dashboard + markdown digest. No server, no build step.

The whole feed is rendered into the page with data attributes, and filtering,
sorting, grouping and paging all happen client-side. That keeps it a single
file you can open from disk, mail to yourself, or keep open in a tab while a
scheduled run rewrites it underneath.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment

from radar import axis, diversify, themes
from radar.config import Config
from radar.models import now
from radar.rank import explain
from radar.store import Store

TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>radar - {{ generated }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Instrument+Serif&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>
:root{
  /* Layered surfaces rather than one flat panel colour -- depth comes from
     stacking tones, not from drawing a border around everything. */
  --bg:#faf9f7; --surface:#fff; --sunken:#f4f2ee; --raised:#fff;
  --ink:#17161a; --ink-2:#46434e; --muted:#84818d;
  --line:#e9e6e0; --line-soft:#f2efe9;
  --accent:#b4472c; --accent-2:#8f3620; --accent-soft:#fdf2ee;
  --good:#2d6a4a; --good-soft:#eef5f1; --warn:#9a6b1f;
  --shadow:0 1px 2px rgba(23,22,26,.04), 0 4px 16px -6px rgba(23,22,26,.07);
  --shadow-lg:0 2px 4px rgba(23,22,26,.04), 0 12px 36px -12px rgba(23,22,26,.14);
  --display:"Instrument Serif",ui-serif,Georgia,serif;
  --sans:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --r:10px; --r-sm:6px;
}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
  --bg:#101013; --surface:#191920; --sunken:#141419; --raised:#1f1f27;
  --ink:#f1eff3; --ink-2:#c3c0cc; --muted:#8e8b99;
  --line:#2a2933; --line-soft:#212029;
  --accent:#e59273; --accent-2:#f0ab90; --accent-soft:#261914;
  --good:#7cc09a; --good-soft:#16241d; --warn:#d9ae68;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 4px 16px -6px rgba(0,0,0,.5);
  --shadow-lg:0 2px 4px rgba(0,0,0,.4), 0 12px 36px -12px rgba(0,0,0,.6);
}}
:root[data-theme=dark]{
  --bg:#101013; --surface:#191920; --sunken:#141419; --raised:#1f1f27;
  --ink:#f1eff3; --ink-2:#c3c0cc; --muted:#8e8b99;
  --line:#2a2933; --line-soft:#212029;
  --accent:#e59273; --accent-2:#f0ab90; --accent-soft:#261914;
  --good:#7cc09a; --good-soft:#16241d; --warn:#d9ae68;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 4px 16px -6px rgba(0,0,0,.5);
  --shadow-lg:0 2px 4px rgba(0,0,0,.4), 0 12px 36px -12px rgba(0,0,0,.6);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:var(--sans);font-size:15px;line-height:1.62;
  font-feature-settings:"cv05" 1,"ss01" 1;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.wrap{max-width:1180px;margin:0 auto;padding:56px 28px 120px}
@media(max-width:640px){.wrap{padding:32px 18px 80px}}
a{color:var(--ink);text-decoration:none}
a:hover{color:var(--accent)}
::selection{background:var(--accent-soft);color:var(--accent-2)}

/* ---- masthead ---- */
header{margin-bottom:38px}
.mast{display:flex;justify-content:space-between;align-items:flex-start;
  gap:24px;flex-wrap:wrap;padding-bottom:22px;
  border-bottom:1px solid var(--line)}
h1{font-family:var(--display);font-weight:400;font-size:44px;line-height:1;
  margin:0;letter-spacing:-.015em}
h1 span{color:var(--accent)}
.tagline{color:var(--muted);font-size:13.5px;margin-top:7px;max-width:46ch}
.statrow{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-sm);
  padding:8px 13px;min-width:82px;box-shadow:var(--shadow)}
.stat b{display:block;font-family:var(--mono);font-size:17px;font-weight:600;
  letter-spacing:-.02em;line-height:1.2}
.stat i{display:block;font-style:normal;font-size:10.5px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.09em;margin-top:2px}
.stat.is-accent b{color:var(--accent)}
.stat.is-good b{color:var(--good)}

h2{font-family:var(--sans);font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:.13em;color:var(--muted);margin:52px 0 16px;
  display:flex;align-items:center;gap:12px}
h2::after{content:"";flex:1;height:1px;background:var(--line)}

.summary{background:var(--accent-soft);border:1px solid var(--line);
  border-left:2px solid var(--accent);padding:18px 22px;
  border-radius:var(--r);margin-bottom:10px;font-size:14.5px;color:var(--ink-2)}
.summary strong{color:var(--ink)}

/* ---- highlights ---- */
.hl{border:1px solid var(--line);border-radius:var(--r);background:var(--surface);
  margin-bottom:28px;box-shadow:var(--shadow);overflow:hidden}
.hl>summary{cursor:pointer;user-select:none;list-style:none;padding:16px 22px;
  font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.13em;
  color:var(--accent);display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  transition:background .15s}
.hl>summary::-webkit-details-marker{display:none}
.hl>summary:hover{background:var(--accent-soft)}
.hl[open]>summary{border-bottom:1px solid var(--line-soft)}
.hl[open]>summary .chev{transform:none}
.hl:not([open])>summary .chev{transform:rotate(-90deg)}
/* Drawn in CSS, not a glyph: the triangle codepoints are missing from
   Inter and JetBrains Mono and fell back to something dash-shaped. */
.chev{display:inline-block;width:0;height:0;border-left:4.5px solid transparent;
  border-right:4.5px solid transparent;border-top:6px solid currentColor;
  transition:transform .18s cubic-bezier(.4,0,.2,1);vertical-align:middle}
.hl .chev{color:var(--accent)}
tr.grp .chev{color:var(--accent);margin-right:7px}
tr.grp.closed .chev{transform:rotate(-90deg)}
.hl-stat{margin-left:auto;text-transform:none;letter-spacing:0;color:var(--muted);
  font-weight:400;font-family:var(--mono);font-size:11px}
.hl-body{padding:2px 22px 22px;display:grid;grid-template-columns:1fr 1fr;
  gap:0 40px}
.hl:not([open]) .hl-body{display:none}
@media(max-width:820px){.hl-body{grid-template-columns:1fr}}
.lane{padding-top:22px}
.lane h3{margin:0 0 4px;font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:.11em;color:var(--ink)}
.lane h3 em{display:block;text-transform:none;letter-spacing:0;color:var(--muted);
  font-style:normal;font-weight:400;font-size:12.5px;margin-top:3px;line-height:1.45}
.pick{padding:11px 0;border-bottom:1px solid var(--line-soft)}
.pick:last-child{border-bottom:none;padding-bottom:2px}
.pick-h{display:flex;gap:10px;align-items:baseline}
.pick-h a{font-weight:600;font-size:14.5px;letter-spacing:-.008em}
.pick-score{margin-left:auto;font-family:var(--mono);font-size:11.5px;
  font-weight:500;color:var(--muted);font-variant-numeric:tabular-nums}
.pick-sum{color:var(--ink-2);font-size:13px;margin:3px 0 6px;line-height:1.5}
.pick-why{font-family:var(--mono);font-size:10.5px;color:var(--muted);
  display:flex;flex-wrap:wrap;align-items:center;gap:5px}

/* ---- control bar ---- */
.bar{position:sticky;top:0;z-index:30;background:var(--bg);
  background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:saturate(180%) blur(14px);-webkit-backdrop-filter:saturate(180%) blur(14px);
  padding:14px 0 12px;margin-bottom:2px;border-bottom:1px solid var(--line)}
.bar-row{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-bottom:9px}
.bar-row:last-child{margin-bottom:0}
input[type=search]{flex:1;min-width:220px;padding:9px 14px;border:1px solid var(--line);
  border-radius:99px;background:var(--surface);color:var(--ink);
  font-family:var(--sans);font-size:13.5px;transition:border-color .15s,box-shadow .15s}
input[type=search]::placeholder{color:var(--muted)}
input[type=search]:focus{outline:none;border-color:var(--accent);
  box-shadow:0 0 0 3px var(--accent-soft)}
select{padding:7px 9px;border:1px solid var(--line);border-radius:var(--r-sm);
  background:var(--surface);color:var(--ink);font-size:11.5px;font-family:var(--mono);
  cursor:pointer;transition:border-color .15s}
select:hover{border-color:var(--muted)}
label.ctl{font-size:10.5px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.09em;display:inline-flex;align-items:center;gap:6px}
button{font-family:var(--mono);font-size:11px;padding:6px 13px;
  border:1px solid var(--line);border-radius:99px;background:var(--surface);
  color:var(--muted);cursor:pointer;transition:all .15s}
button:hover{border-color:var(--accent);color:var(--accent)}
button.on{border-color:var(--accent);color:#fff;background:var(--accent)}
/* On dark the accent is a light peach, so an active chip needs dark text. */
:root[data-theme=dark] button.on{color:#17161a}
@media (prefers-color-scheme:dark){
  :root:not([data-theme=light]) button.on{color:#17161a}}
.chipset{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.chipset .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.11em;
  color:var(--muted);margin-right:3px;font-weight:600}
.count{font-family:var(--mono);font-size:11px;color:var(--muted);margin-left:auto}

/* ---- feed ---- */
.wide{overflow-x:auto;border-radius:var(--r)}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:14px}
th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.11em;
  color:var(--muted);font-weight:600;padding:16px 14px 9px}
td{padding:15px 14px;border-bottom:1px solid var(--line-soft);vertical-align:top}
tr.item{transition:background .12s}
tr.item:hover td{background:var(--surface)}
tr.item:hover .item-title{color:var(--accent)}
tr.grp td{background:transparent;border-bottom:1px solid var(--line);
  padding:34px 14px 10px;font-size:11px;font-weight:700;text-transform:uppercase;
  letter-spacing:.13em;color:var(--accent);cursor:pointer;user-select:none;
  transition:color .15s}
tr.grp:first-child td{padding-top:18px}
tr.grp td:hover{color:var(--accent-2)}
tr.grp td:focus-visible{outline:2px solid var(--accent);outline-offset:-3px;
  border-radius:var(--r-sm)}
tr.grp td span{color:var(--muted);font-weight:400;letter-spacing:.02em;
  text-transform:none;font-family:var(--mono);font-size:10.5px}
tr.grp.closed td{border-bottom:1px dashed var(--line)}
.score{font-family:var(--mono);font-weight:600;white-space:nowrap;font-size:14px;
  letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.item-title{font-weight:600;font-size:14.5px;letter-spacing:-.008em;
  transition:color .12s}
.desc{color:var(--ink-2);font-size:13px;display:block;margin:4px 0 8px;
  line-height:1.5;max-width:74ch}
.why{font-family:var(--mono);font-size:10.5px;color:var(--muted);line-height:1.6}

/* ---- tags ---- */
.tag{font-family:var(--mono);font-size:10px;color:var(--muted);
  background:var(--sunken);border:1px solid transparent;border-radius:99px;
  padding:2.5px 9px;margin:0 4px 4px 0;display:inline-block;
  letter-spacing:.01em;white-space:nowrap}
.tag.th{color:var(--accent);background:var(--accent-soft)}
.tag.ax{color:var(--good);background:var(--good-soft)}

.empty{padding:64px 8px;text-align:center;color:var(--muted);
  font-family:var(--mono);font-size:13px}

/* ---- briefs ---- */
.brief{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
  padding:28px 30px;margin-bottom:18px;box-shadow:var(--shadow)}
.brief h3{margin:0 0 4px;font-family:var(--display);font-weight:400;font-size:26px;
  letter-spacing:-.01em;line-height:1.2}
.brief .one{color:var(--accent);font-size:14.5px;margin-bottom:16px}
.brief p{color:var(--ink-2);max-width:78ch}
.pills{display:flex;flex-wrap:wrap;gap:7px;margin:14px 0 18px}
.pill{font-family:var(--mono);font-size:10.5px;padding:4px 11px;border-radius:99px;
  border:1px solid var(--line);color:var(--muted);white-space:nowrap;
  background:var(--sunken)}
.pill.hot{border-color:transparent;color:var(--accent);background:var(--accent-soft)}
.pill.ok{border-color:transparent;color:var(--good);background:var(--good-soft)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:18px}
@media(max-width:720px){.cols{grid-template-columns:1fr}}
.blk h4{margin:0 0 8px;font-size:10px;text-transform:uppercase;letter-spacing:.11em;
  color:var(--muted);font-weight:600}
.blk ul{margin:0;padding-left:17px}
.blk li{margin-bottom:6px;font-size:13.5px;color:var(--ink-2);line-height:1.5}
.kill{margin-top:18px;padding:13px 16px;border:1px solid var(--line);
  border-left:2px solid var(--warn);border-radius:var(--r-sm);
  font-size:13.5px;background:var(--sunken);color:var(--ink-2)}
.kill b{color:var(--warn)}
.srcs{margin-top:14px;font-size:11.5px;font-family:var(--mono);word-break:break-all}
.srcs a{color:var(--muted)}
.srcs a:hover{color:var(--accent)}

footer{margin-top:80px;padding-top:22px;border-top:1px solid var(--line);
  color:var(--muted);font-size:12px;line-height:1.7}
footer code{font-family:var(--mono);font-size:11px;background:var(--sunken);
  padding:2px 6px;border-radius:4px}
kbd{font-family:var(--mono);font-size:10px;border:1px solid var(--line);
  border-radius:4px;padding:2px 5px;background:var(--sunken)}
#theme-toggle{align-self:flex-start}
</style></head><body><div class="wrap">

<header>
  <div class="mast">
    <div>
      <h1>radar<span>.</span></h1>
      <div class="tagline">Technically interesting projects, ranked by what
        strong engineers are actually building &middot; {{ generated }}</div>
    </div>
    <button id="theme-toggle" title="toggle light/dark">theme</button>
  </div>
  <div class="statrow">
    <div class="stat"><b>{{ stats.total }}</b><i>tracked</i></div>
    <div class="stat is-accent"><b>{{ mix.new }}</b><i>new</i></div>
    <div class="stat"><b>{{ rows|length }}</b><i>in feed</i></div>
    <div class="stat"><b>{{ mix.infra }}</b><i>AI infra</i></div>
    <div class="stat is-good"><b>{{ mix.applied }}</b><i>AI applied</i></div>
    <div class="stat"><b>{{ mix.nonai }}</b><i>no AI</i></div>
    <div class="stat"><b>{{ briefs|length }}</b><i>briefs</i></div>
  </div>
</header>

{% if summary %}
<div class="summary"><strong>Where the board is pointing.</strong> {{ summary }}</div>
{% endif %}

{% if highlights %}
<details class="hl" id="hl" open>
  <summary><span class="chev"></span> Worth a look
    <span class="hl-stat">{{ highlights|length }} lanes</span></summary>
  <div class="hl-body">
  {% for lane in highlights %}
    <section class="lane">
      <h3>{{ lane.title }} <em>{{ lane.note }}</em></h3>
      {% for it in lane['items'] %}
      <div class="pick">
        <div class="pick-h">
          <a href="{{ it.url }}">{{ it.title }}</a>
          <span class="pick-score">{{ '%.2f'|format(it.score) }}</span>
        </div>
        {% if it.summary %}<div class="pick-sum">{{ it.summary[:150] }}</div>{% endif %}
        <div class="pick-why">
          <span class="tag ax">{{ it.axis }}</span><span class="tag th">{{ it.theme }}</span>
          {{ it.reason }}
        </div>
      </div>
      {% endfor %}
    </section>
  {% endfor %}
  </div>
</details>
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
    <span class="lbl">focus</span>
    {% for a, lbl in axes %}<button data-axis="{{ a }}">{{ lbl }}</button>{% endfor %}
    <span class="lbl" style="margin-left:12px">theme</span>
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
    data-primary="{{ r.primary }}" data-axis="{{ r.axis }}"
    data-lang="{{ r.lang or '' }}"
    data-score="{{ r.score }}" data-vel="{{ r.velocity }}"
    data-age="{{ r.age_days }}" data-stars="{{ r.stars }}"
    data-curated="{{ loop.index0 }}">
  <td class="score">{{ '%.2f'|format(r.score) }}</td>
  <td>
    <a href="{{ r.url }}" class="item-title">{{ r.title }}</a>
    <span class="desc">{{ r.summary[:190] }}</span>
    <span class="tag ax">{{ r.axis_label }}</span>
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
const state={src:'', themes:new Set(), axes:new Set(), group:true, collapsed:new Set()};

try{ const s=JSON.parse(localStorage.getItem('radar-prefs')||'{}');
  if(s.show) showSel.value=s.show; if(s.sort) sortSel.value=s.sort;
  if(s.lang) langSel.value=s.lang;
  // Explicit undefined check: a stored `false` must survive a `true` default.
  if(s.group!==undefined) state.group=!!s.group;
  if(Array.isArray(s.collapsed)) state.collapsed=new Set(s.collapsed);
  if(s.hl!==undefined && $('#hl')) $('#hl').open=!!s.hl;
}catch(e){}
function save(){ try{ localStorage.setItem('radar-prefs', JSON.stringify({
  show:showSel.value, sort:sortSel.value, lang:langSel.value, group:state.group,
  collapsed:[...state.collapsed], hl:$('#hl')?$('#hl').open:true}));
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
  if(state.axes.size && !state.axes.has(r.dataset.axis)) return false;
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
  chev.className='chev';
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

if($('#hl')) $('#hl').addEventListener('toggle',save);
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
document.querySelectorAll('button[data-axis]').forEach(b=>b.addEventListener('click',()=>{
  const v=b.dataset.axis;
  if(state.axes.has(v)){state.axes.delete(v); b.classList.remove('on');}
  else {state.axes.add(v); b.classList.add('on');}
  render();}));
document.querySelectorAll('button[data-theme]').forEach(b=>b.addEventListener('click',()=>{
  const v=b.dataset.theme;
  if(state.themes.has(v)){state.themes.delete(v); b.classList.remove('on');}
  else {state.themes.add(v); b.classList.add('on');}
  render();}));
$('#reset').addEventListener('click',()=>{
  q.value=''; langSel.value=''; state.src=''; state.themes.clear(); state.axes.clear();
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


def _reason(item, sources: list[str], is_new: bool) -> str:
    """Why this item is worth a glance, built from signals already computed.

    Deterministic on purpose: the briefs section needs an API key, and the
    summary at the top of the page should still say something useful without
    one.
    """
    bits = []
    if is_new:
        bits.append("new this run")
    m = item.metrics
    if m.get("stars_per_day"):
        bits.append(f"{m['stars_per_day']}/day")
    if m.get("stars"):
        bits.append(f"{int(m['stars']):,} stars")
    if m.get("hn_points"):
        bits.append(f"{int(m['hn_points'])} HN points")
    if m.get("starred_by"):
        bits.append("starred by " + ", ".join(m["starred_by"][:3]))
    if len(sources) > 1:
        bits.append(f"{len(sources)} sources agree")
    if m.get("arxiv_category"):
        bits.append(m["arxiv_category"])
    return " · ".join(bits)


def _highlights(store: Store, cfg: Config, since: str | None,
                per_lane: int = 4) -> list[dict]:
    """A few small lanes, each answering a different question.

    One ranked list cannot say "this is moving fast" and "several sources
    independently agree" and "someone whose taste you trust starred this" at
    once -- those are different reasons to look, and collapsing them into a
    single score is exactly what loses the reason.
    """
    from radar import axis, themes

    pool = store.items(limit=400)
    prepared = []
    for row in pool:
        item = store.to_item(row)
        prepared.append({
            "row": row, "item": item,
            "sources": sorted(item.sources),
            "is_new": bool(since and (row["first_seen"] or "") >= since),
        })

    def entry(p) -> dict:
        item = p["item"]
        return {
            "title": item.title, "url": item.url,
            "summary": (item.summary or "").strip(),
            "score": p["row"]["score"],
            "axis": axis.label(axis.of_item(item)),
            "theme": themes.primary(themes.of_item(item)),
            "reason": _reason(item, p["sources"], p["is_new"]),
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
        ("New this run", "highest-scoring things that were not here last time",
         take([p for p in by_score if p["is_new"]])),
        ("Moving fastest", "star velocity against the rest of the corpus",
         take(sorted([p for p in prepared if p["item"].metrics.get("stars_per_day")],
                     key=lambda p: -p["item"].metrics["stars_per_day"]))),
        ("Several sources agree", "independent corroboration is the strongest signal here",
         take([p for p in by_score if len(p["sources"]) > 1])),
        ("From your watchlist", "engineers whose taste you chose to borrow",
         take([p for p in by_score if p["item"].metrics.get("starred_by")])),
        ("Papers, usually with no implementation", "where the gap is the project",
         take([p for p in by_score if p["row"]["key"].startswith("arxiv:")])),
    ]
    return [{"title": t, "note": n, "items": i} for t, n, i in lanes if i]


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
            "axis": axis.of_item(item),
            "axis_label": axis.label(axis.of_item(item)),
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
    theme_names = sorted({t for r in rows for t in r["themes"]})
    languages = sorted({r["lang"] for r in rows if r["lang"]})
    counts = store.counts()
    stats = {"total": sum(counts.values()), "sources": source_names, **counts}
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    env = Environment(autoescape=True)
    html = env.from_string(TEMPLATE).render(
        generated=generated, run_id=run_id, briefs=briefs, rows=rows,
        source_names=source_names, theme_names=theme_names, languages=languages,
        axes=[(a, axis.label(a)) for a in axis.ALL_AXES],
        stats=stats, summary=(briefs[0].get("board_summary") if briefs else ""),
        highlights=highlights, mix=mix,
    )
    html_path = cfg.out_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")

    md_path = cfg.out_dir / f"digest-{datetime.now():%Y-%m-%d}.md"
    md_path.write_text(_markdown(briefs, rows, generated, highlights, mix), encoding="utf-8")
    return html_path, md_path


def _markdown(briefs: list[dict], rows: list[dict], generated: str,
              highlights: list[dict] | None = None, mix: dict | None = None) -> str:
    L = [f"# radar digest - {generated}", ""]
    if mix:
        L += [f"`{mix['new']} new` · `{mix['infra']} AI infra` · "
              f"`{mix['applied']} AI applied` · `{mix['nonai']} no AI`", ""]
    if highlights:
        L += ["<details open>", "<summary><b>Worth a look</b></summary>", ""]
        for lane in highlights:
            L += [f"### {lane['title']}", f"*{lane['note']}*", ""]
            for it in lane["items"]:
                L.append(f"- **[{it['title'].replace('|', chr(92) + '|')}]({it['url']})** "
                         f"`{it['score']:.2f}` — {it['reason']}")
                if it["summary"]:
                    L.append(f"  <br>{it['summary'][:150]}")
            L.append("")
        L += ["</details>", "", "---", ""]
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
