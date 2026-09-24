"""Static HTML dashboard + markdown digest. No server, no build step.

The whole feed is rendered into the page with data attributes, and filtering,
sorting, grouping and paging all happen client-side. That keeps it a single
file you can open from disk, mail to yourself, or keep open in a tab while a
scheduled run rewrites it underneath.

Two languages. Every piece of interface text is rendered with both an English
and a Simplified Chinese form (`data-en` / `data-zh` attributes); a toggle on
the page switches between them without a rebuild, and `report.language` in
config picks the default. Item titles and descriptions stay as their authors
wrote them.
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

LANGS = ("en", "zh")


def norm_lang(value) -> str:
    """'zh-CN', 'zh_CN', 'ZH' and 'zh' all mean Simplified Chinese."""
    v = str(value or "en").lower().replace("_", "-")
    return "zh" if v.startswith("zh") else "en"


TEMPLATE = """<!doctype html>
<html lang="{{ 'zh-CN' if lang == 'zh' else 'en' }}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>radar - {{ generated }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Instrument+Serif&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>
__CSS__
/* ---- served mode ---- */
.note{display:block;font-size:12.5px;color:var(--warn);margin:2px 0 6px;font-style:italic}
.served{font-family:var(--mono);font-size:10.5px;color:var(--good);margin-top:6px}
tr.item.gone{opacity:.35}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:var(--ink);
  color:var(--bg);padding:9px 16px;border-radius:99px;font-size:12.5px;z-index:99;
  display:flex;gap:12px;align-items:center;box-shadow:var(--shadow-lg)}
.toast button{background:transparent;color:inherit;border-color:currentColor;padding:3px 10px}
/* ---- dives ---- */
.dive{margin-top:18px;border-top:1px solid var(--line);padding-top:12px}
.dive>summary{cursor:pointer;list-style:none;display:flex;gap:8px;align-items:center;
  flex-wrap:wrap;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.11em;
  color:var(--muted)}
.dive>summary::-webkit-details-marker{display:none}
.dive:not([open])>summary .chev{transform:rotate(-90deg)}
.dive p,.dive li{font-size:13.5px}
.verdict{font-family:var(--mono);font-size:10.5px;padding:3px 10px;border-radius:99px;
  text-transform:none;letter-spacing:0}
.v-go{color:var(--good);background:var(--good-soft)}
.v-pivot{color:var(--warn);background:var(--sunken)}
.v-crowded,.v-kill{color:var(--accent);background:var(--accent-soft)}
.tag.ok{color:var(--good);background:var(--good-soft)}
.tag.bad{color:var(--accent);background:var(--accent-soft)}
/* ---- row actions, saved rows, language, earlier briefs ---- */
.acts{display:inline-flex;gap:4px;margin-left:6px;vertical-align:middle}
.acts button{font-size:9.5px;padding:2px 8px;opacity:0;transition:opacity .12s,all .15s}
tr.item:hover .acts button,.acts button:focus-visible,.acts button.done{opacity:1}
.acts button.done{border-color:var(--good);color:var(--good)}
.acts code.cmd{font-family:var(--mono);font-size:10.5px;background:var(--sunken);
  padding:2px 7px;border-radius:4px;user-select:all}
.tag.sv{color:var(--good);background:var(--good-soft)}
.mast-btns{display:flex;gap:8px;align-self:flex-start}
.past-run{padding:14px 0 6px;border-bottom:1px solid var(--line-soft)}
.past-run:last-child{border-bottom:none}
.past-run h3{margin:0 0 6px;font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:.11em;color:var(--ink)}
.past-run h3 span{color:var(--muted);font-weight:400;text-transform:none;letter-spacing:0;
  font-family:var(--mono);font-size:10.5px;margin-left:8px}
.past{padding:5px 0}
.past b{font-weight:600;font-size:13.5px}
.past .one{display:block;color:var(--ink-2);font-size:12.5px;margin-top:1px}
.past .pill{margin-right:5px;font-size:10px}
</style></head><body><div class="wrap">

<header>
  <div class="mast">
    <div>
      <h1>radar<span>.</span></h1>
      {% if api %}<div class="served" data-en="live: buttons write to your local database" data-zh="本地模式：按钮直接写入本地数据库"></div>{% endif %}
      <div class="tagline" data-en="Technically interesting projects, ranked by what strong engineers are actually building &middot; {{ generated }}"
           data-zh="值得做的技术项目，按优秀工程师正在真正做的事情排名 &middot; {{ generated }}"></div>
    </div>
    <div class="mast-btns">
      <button id="lang-toggle" title="English / 简体中文"></button>
      <button id="theme-toggle" title="toggle light/dark" data-en="theme" data-zh="配色"></button>
    </div>
  </div>
  <div class="statrow">
    <div class="stat"><b>{{ stats.total }}</b><i data-en="tracked" data-zh="跟踪中"></i></div>
    <div class="stat is-accent"><b>{{ mix.new }}</b><i data-en="new" data-zh="本次新增"></i></div>
    <div class="stat"><b>{{ rows|length }}</b><i data-en="in feed" data-zh="列表中"></i></div>
    <div class="stat"><b>{{ mix.infra }}</b><i data-en="AI infra" data-zh="AI 基础设施"></i></div>
    <div class="stat is-good"><b>{{ mix.applied }}</b><i data-en="AI applied" data-zh="AI 应用"></i></div>
    <div class="stat"><b>{{ mix.nonai }}</b><i data-en="no AI" data-zh="非 AI"></i></div>
    <div class="stat"><b>{{ briefs|length }}</b><i data-en="briefs" data-zh="简报"></i></div>
  </div>
</header>

{% if summary %}
<div class="summary"><strong data-en="Where the board is pointing." data-zh="整体信号指向。"></strong> {{ summary }}</div>
{% endif %}

{% if highlights %}
<details class="hl" id="hl" open>
  <summary><span class="chev"></span> <span data-en="Worth a look" data-zh="值得一看"></span>
    <span class="hl-stat" data-en="{{ highlights|length }} lanes" data-zh="{{ highlights|length }} 个栏目"></span></summary>
  <div class="hl-body">
  {% for lane in highlights %}
    <section class="lane">
      <h3><span data-en="{{ lane.title.en }}" data-zh="{{ lane.title.zh }}"></span>
        <em data-en="{{ lane.note.en }}" data-zh="{{ lane.note.zh }}"></em></h3>
      {% for it in lane['items'] %}
      <div class="pick">
        <div class="pick-h">
          <a href="{{ it.url }}">{{ it.title }}</a>
          <span class="pick-score">{{ '%.2f'|format(it.score) }}</span>
        </div>
        {% if it.summary %}<div class="pick-sum">{{ it.summary[:150] }}</div>{% endif %}
        <div class="pick-why">
          <span class="tag ax" data-en="{{ it.axis.en }}" data-zh="{{ it.axis.zh }}"></span><span class="tag th" data-en="{{ it.theme.en }}" data-zh="{{ it.theme.zh }}"></span>
          <span data-en="{{ it.reason.en }}" data-zh="{{ it.reason.zh }}"></span>
        </div>
      </div>
      {% endfor %}
    </section>
  {% endfor %}
  </div>
</details>
{% endif %}

{% if briefs %}
<h2 data-en="Project briefs" data-zh="项目简报"></h2>
{% for b in briefs %}
<article class="brief">
  <h3>{{ loop.index }}. {{ b.title }}</h3>
  <div class="one">{{ b.one_liner }}</div>
  <div class="pills">
    <span class="pill hot" data-en="difficulty {{ b.difficulty }}/5" data-zh="难度 {{ b.difficulty }}/5"></span>
    <span class="pill" data-en="novelty {{ b.novelty }}/5" data-zh="新颖度 {{ b.novelty }}/5"></span>
    <span class="pill" data-en="~{{ b.effort_weeks }} weeks" data-zh="约 {{ b.effort_weeks }} 周"></span>
    {% if b.ai_leverage %}<span class="pill ok">AI: {{ b.ai_leverage[:60] }}</span>{% endif %}
  </div>
  <p>{{ b.pitch }}</p>
  <p><strong data-en="Why now." data-zh="为什么是现在。"></strong> {{ b.why_now }}</p>
  <div class="cols">
    <div class="blk"><h4 data-en="Hard parts" data-zh="难点"></h4><ul>
      {% for h in b.hard_parts %}<li>{{ h }}</li>{% endfor %}</ul></div>
    <div class="blk"><h4 data-en="You will learn" data-zh="你会学到"></h4><ul>
      {% for h in b.you_will_learn %}<li>{{ h }}</li>{% endfor %}</ul></div>
  </div>
  <div class="cols">
    <div class="blk"><h4 data-en="Milestones" data-zh="里程碑"></h4><ul>
      {% for m in b.milestones %}<li>{{ m }}</li>{% endfor %}</ul></div>
    <div class="blk"><h4 data-en="Prior art" data-zh="已有工作"></h4><ul>
      {% for p in b.prior_art %}<li>{{ p }}</li>{% endfor %}</ul></div>
  </div>
  <div class="kill"><b data-en="Kill criteria." data-zh="放弃标准。"></b> {{ b.kill_criteria }}</div>
  <div class="srcs">{% for u in b.source_urls %}<a href="{{ u }}">{{ u }}</a><br>{% endfor %}</div>
  {% set d = dives.get(b._id) %}
  {% if d %}
  <details class="dive" open>
    <summary><span class="chev"></span>
      <span data-en="Checked against the web" data-zh="联网核实结果"></span>
      <span class="verdict v-{{ d.verdict }}" data-en="{{ d.verdict }}" data-zh="{{ {'go':'可以做','pivot':'换个角度','crowded':'已有人做','kill':'放弃'}[d.verdict] }}"></span>
      <span class="pill" data-en="novelty {{ b.novelty }}/5 &rarr; {{ d.novelty_revised }}/5" data-zh="新颖度 {{ b.novelty }}/5 &rarr; {{ d.novelty_revised }}/5"></span>
      <span class="hl-stat" data-en="{{ d.dived_at[:10] }}" data-zh="{{ d.dived_at[:10] }}"></span>
    </summary>
    <p>{{ d.verdict_reason }}</p>
    <p><strong data-en="Novelty." data-zh="新颖度。"></strong> {{ d.novelty_reason }}</p>
    {% if d.prior_art %}
    <div class="blk"><h4 data-en="Prior art found" data-zh="找到的已有工作"></h4><ul>
      {% for a in d.prior_art %}<li><span class="tag {{ 'ok' if a.verified else 'bad' }}" data-en="{{ 'link ok' if a.verified else 'link failed' }}" data-zh="{{ '链接有效' if a.verified else '链接失效' }}"></span>
        <span class="tag" data-en="{{ a.closeness }}" data-zh="{{ {'same':'相同','overlapping':'大量重叠','adjacent':'相关'}[a.closeness] }}"></span>
        <a href="{{ a.url }}">{{ a.name }}</a>{% if a.stars %} <span class="why">{{ '{:,}'.format(a.stars) }}*</span>{% endif %} &mdash; {{ a.note }}</li>{% endfor %}
    </ul></div>
    {% endif %}
    <div class="cols">
      <div class="blk"><h4 data-en="Two-week experiment" data-zh="两周实验"></h4>
        <p style="margin:0 0 6px">{{ d.two_week_experiment.goal }}</p><ul>
        {% for st in d.two_week_experiment.steps %}<li>{{ st }}</li>{% endfor %}</ul>
        <p style="margin:6px 0 0"><b data-en="Measure:" data-zh="衡量："></b> {{ d.two_week_experiment.success_metric }}<br>
        <b data-en="Stop if:" data-zh="放弃条件："></b> {{ d.two_week_experiment.kill_threshold }}</p></div>
      <div class="blk"><h4 data-en="Risks" data-zh="风险"></h4><ul>
        {% for r in d.risks %}<li>{{ r }}</li>{% endfor %}</ul>
        {% if d.needs %}<h4 data-en="Needs" data-zh="需要"></h4><ul>{% for n in d.needs %}<li>{{ n }}</li>{% endfor %}</ul>{% endif %}
        {% if d.pivot_ideas %}<h4 data-en="Sharper angles" data-zh="更好的切入点"></h4><ul>{% for n in d.pivot_ideas %}<li>{{ n }}</li>{% endfor %}</ul>{% endif %}
      </div>
    </div>
  </details>
  {% else %}
  <div class="srcs"><span data-en="Not checked yet: radar dive {{ loop.index }}" data-zh="尚未联网核实：radar dive {{ loop.index }}"></span>
    {% if api %} <button class="dive-btn" data-brief="{{ b._id }}" data-en="check it now" data-zh="立即核实"></button>{% endif %}</div>
  {% endif %}
</article>
{% endfor %}
{% endif %}

{% if past %}
<details class="hl" id="past">
  <summary><span class="chev"></span> <span data-en="Earlier briefs" data-zh="以前的简报"></span>
    <span class="hl-stat" data-en="{{ past|length }} runs" data-zh="{{ past|length }} 次运行"></span></summary>
  <div class="hl-body" style="display:block">
  {% for run in past %}
    <div class="past-run">
      <h3>{{ run.date }}<span data-en="{{ run.briefs|length }} briefs" data-zh="{{ run.briefs|length }} 份"></span></h3>
      {% for b in run.briefs %}
      <div class="past"><b>{{ b.title }}</b>
        <span class="one">{{ b.one_liner }}</span>
        <span class="pill hot" data-en="difficulty {{ b.difficulty }}/5" data-zh="难度 {{ b.difficulty }}/5"></span><span class="pill" data-en="novelty {{ b.novelty }}/5" data-zh="新颖度 {{ b.novelty }}/5"></span><span class="pill" data-en="~{{ b.effort_weeks }} weeks" data-zh="约 {{ b.effort_weeks }} 周"></span>
      </div>
      {% endfor %}
    </div>
  {% endfor %}
  </div>
</details>
{% endif %}

<h2 data-en="Ranked signal" data-zh="排名信号"></h2>
<div class="bar">
  <div class="bar-row">
    <input type="search" id="q" data-en-placeholder="filter by name, description, topic, language...   ( / )" data-zh-placeholder="按名称、描述、主题、语言筛选...   ( / )">
    <label class="ctl"><span data-en="show" data-zh="显示"></span>
      <select id="show">
        <option value="25">25</option>
        <option value="50" selected>50</option>
        <option value="100">100</option>
        <option value="250">250</option>
        <option value="0" data-en="all" data-zh="全部"></option>
      </select></label>
    <label class="ctl"><span data-en="sort" data-zh="排序"></span>
      <select id="sort">
        <option value="curated" data-en="curated (redundancy-filtered)" data-zh="精选（去重后）"></option>
        <option value="score" data-en="score" data-zh="分数"></option>
        <option value="velocity" data-en="velocity" data-zh="热度"></option>
        <option value="newest" data-en="newest" data-zh="最新"></option>
        <option value="stars" data-en="stars" data-zh="星数"></option>
      </select></label>
    <label class="ctl"><span data-en="lang" data-zh="编程语言"></span>
      <select id="lang"><option value="" data-en="any" data-zh="不限"></option>
        {% for l in languages %}<option value="{{ l }}">{{ l }}</option>{% endfor %}
      </select></label>
    <button id="group" data-en="group by theme" data-zh="按主题分组"></button>
    <button id="collapse"></button>
  </div>
  <div class="bar-row chipset">
    <span class="lbl" data-en="focus" data-zh="方向"></span>
    {% for a in axes %}<button data-axis="{{ a.id }}" data-en="{{ a.en }}" data-zh="{{ a.zh }}"></button>{% endfor %}
    <span class="lbl" style="margin-left:12px" data-en="theme" data-zh="主题"></span>
    {% for t in theme_names %}<button data-theme="{{ t.id }}" data-en="{{ t.en }}" data-zh="{{ t.zh }}"></button>{% endfor %}
  </div>
  <div class="bar-row chipset">
    <span class="lbl" data-en="source" data-zh="来源"></span>
    {% for s in source_names %}<button data-src="{{ s }}">{{ s }}</button>{% endfor %}
    <button id="reset" data-en="reset" data-zh="重置"></button>
    <span class="count" id="count"></span>
  </div>
</div>

<div class="wide"><table id="feed">
<thead><tr><th style="width:56px" data-en="score" data-zh="分数"></th><th data-en="item" data-zh="条目"></th><th style="width:230px" data-en="signal" data-zh="信号"></th></tr></thead>
<tbody id="body">
{% for r in rows %}
<tr class="item"
    data-key="{{ r.key }}" data-status="{{ r.status }}"
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
    <span class="acts"><button class="act" data-cmd="save" data-en="save" data-zh="保存"></button><button class="act" data-cmd="dismiss" data-en="dismiss" data-zh="忽略"></button>{% if api %}<button class="act" data-cmd="note" data-en="note" data-zh="备注"></button>{% endif %}</span>
    <span class="desc">{{ r.summary[:190] }}</span>
    {% if r.status == 'saved' %}<span class="tag sv" data-en="saved" data-zh="已保存"></span>{% endif %}
    {% if r.note %}<span class="note">{{ r.note }}</span>{% endif %}
    <span class="tag ax" data-en="{{ r.axis_label.en }}" data-zh="{{ r.axis_label.zh }}"></span>
    {% if r.lang %}<span class="tag">{{ r.lang }}</span>{% endif %}
    {% for t in r.theme_labels %}<span class="tag th" data-en="{{ t.en }}" data-zh="{{ t.zh }}"></span>{% endfor %}
    {% for s in r.sources %}<span class="tag">{{ s }}</span>{% endfor %}
  </td>
  <td class="why"><span data-en="{{ r.why.en }}" data-zh="{{ r.why.zh }}"></span><br><span data-en="{{ r.metrics_line.en }}" data-zh="{{ r.metrics_line.zh }}"></span></td>
</tr>
{% endfor %}
</tbody></table>
<div class="empty" id="empty" hidden data-en="nothing matches those filters" data-zh="没有符合筛选条件的条目"></div></div>

<footer>
  <span data-en="generated by radar &middot; sources: {{ stats.sources|join(', ') }}" data-zh="由 radar 生成 &middot; 来源：{{ stats.sources|join(', ') }}"></span><br>
  <span data-en="&quot;curated&quot; order is redundancy-filtered so near-identical projects don't stack; switch sort to score for raw ranking. Hover a row for save / dismiss, which copy the radar command to your clipboard."
        data-zh="&quot;精选&quot;顺序做过去重，避免几乎相同的项目堆在一起；切换到按分数排序可看原始排名。鼠标悬停在条目上会出现保存 / 忽略按钮，点击后会把对应的 radar 命令复制到剪贴板。"></span>
</footer>
</div>
<script>
(function(){
const $=s=>document.querySelector(s);
const body=$('#body'), q=$('#q'), showSel=$('#show'), sortSel=$('#sort'),
      langSel=$('#lang'), groupBtn=$('#group'), collapseBtn=$('#collapse'),
      countEl=$('#count'), emptyEl=$('#empty'), langBtn=$('#lang-toggle');
const items=[...body.querySelectorAll('tr.item')];
const TL={{ theme_labels|tojson }};
const API={{ api|tojson }};
const T={
  en:{count:(v,t,h,n)=>`showing ${v} of ${t} matched`+(h?` · ${h} collapsed`:'')+` · ${n} in feed`,
      items:n=>n+' item'+(n===1?'':'s'), hidden:' (hidden)', collapse:'collapse all',
      expand:'expand all', other:'other', copied:'copied', toggle:'中文'},
  zh:{count:(v,t,h,n)=>`显示 ${v} / ${t} 条匹配`+(h?` · ${h} 条已折叠`:'')+` · 列表共 ${n} 条`,
      items:n=>n+' 条', hidden:'（已折叠）', collapse:'全部折叠', expand:'全部展开',
      other:'其他', copied:'已复制', toggle:'EN'},
};
const state={src:'', themes:new Set(), axes:new Set(), group:true, collapsed:new Set(),
             lang:{{ lang|tojson }}};

try{ const s=JSON.parse(localStorage.getItem('radar-prefs')||'{}');
  if(s.show) showSel.value=s.show; if(s.sort) sortSel.value=s.sort;
  if(s.lang) langSel.value=s.lang;
  if(s.ui==='en'||s.ui==='zh') state.lang=s.ui;
  // Explicit undefined check: a stored `false` must survive a `true` default.
  if(s.group!==undefined) state.group=!!s.group;
  if(Array.isArray(s.collapsed)) state.collapsed=new Set(s.collapsed);
  if(s.hl!==undefined && $('#hl')) $('#hl').open=!!s.hl;
}catch(e){}
function save(){ try{ localStorage.setItem('radar-prefs', JSON.stringify({
  show:showSel.value, sort:sortSel.value, lang:langSel.value, group:state.group,
  ui:state.lang, collapsed:[...state.collapsed], hl:$('#hl')?$('#hl').open:true}));
}catch(e){} }

function themeLabel(name){ return state.lang==='zh' ? (TL[name]||name) : name; }
function applyLang(){
  const L=state.lang;
  document.documentElement.lang = L==='zh' ? 'zh-CN' : 'en';
  document.querySelectorAll('[data-zh]').forEach(el=>{
    const v = L==='zh' ? el.dataset.zh : el.dataset.en;
    if(v!==undefined) el.textContent=v;
  });
  document.querySelectorAll('[data-zh-placeholder]').forEach(el=>{
    el.placeholder = L==='zh' ? el.dataset.zhPlaceholder : el.dataset.enPlaceholder;
  });
  langBtn.textContent=T[L].toggle;
}

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
  const L=T[state.lang];
  const tr=document.createElement('tr'); tr.className='grp'+(closed?' closed':'');
  const td=document.createElement('td'); td.colSpan=3;
  td.setAttribute('role','button'); td.tabIndex=0;
  td.setAttribute('aria-expanded', String(!closed));
  const chev=document.createElement('b');
  chev.className='chev';
  td.appendChild(chev);
  td.appendChild(document.createTextNode(' '+themeLabel(name)));
  const s=document.createElement('span');
  s.textContent='  '+L.items(n)+(closed?L.hidden:'');
  td.appendChild(s);
  td.addEventListener('click',()=>toggleGroup(name));
  td.addEventListener('keydown',e=>{
    if(e.key==='Enter'||e.key===' '){e.preventDefault();toggleGroup(name);}});
  tr.appendChild(td); return tr;
}

function render(){
  const L=T[state.lang];
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
  countEl.textContent = L.count(vis.length-hidden, total, hidden, items.length);
  groupBtn.classList.toggle('on', state.group);
  collapseBtn.hidden = !state.group;
  collapseBtn.textContent = collapsedHere.length ? L.expand : L.collapse;
  save();
}

// Served by `radar serve`: buttons talk to the local server instead.
async function call(path, body){
  const r = await fetch(path, {method: body ? 'POST' : 'GET',
    headers: {'Content-Type': 'application/json', 'X-Radar-Token': API},
    body: body ? JSON.stringify(body) : undefined});
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}
function toast(msg, undo){
  document.querySelectorAll('.toast').forEach(t=>t.remove());
  const t=document.createElement('div'); t.className='toast'; t.textContent=msg;
  if(undo){ const b=document.createElement('button');
    b.textContent = state.lang==='zh' ? '撤销' : 'undo';
    b.onclick=()=>{ undo(); t.remove(); }; t.appendChild(b); }
  document.body.appendChild(t); setTimeout(()=>t.remove(), 6000);
}
async function verdict(tr, status){
  await call('/api/verdict', {key: tr.dataset.key, status});
  tr.dataset.status = status;
  tr.classList.toggle('gone', status==='dismissed');
  let tag = tr.querySelector('.tag.sv');
  if(status==='saved' && !tag){ tag=document.createElement('span'); tag.className='tag sv';
    tag.dataset.en='saved'; tag.dataset.zh='已保存'; tr.querySelector('.desc').after(tag); applyLang(); }
  if(status!=='saved' && tag) tag.remove();
}
if(API){
  document.querySelectorAll('button.act').forEach(b=>b.addEventListener('click', async e=>{
    e.preventDefault(); e.stopImmediatePropagation();
    const tr=b.closest('tr'), zh=state.lang==='zh';
    try{
      if(b.dataset.cmd==='note'){
        const cur=(tr.querySelector('.note')||{}).textContent||'';
        const note=window.prompt(zh?'备注：':'Note:', cur); if(note===null) return;
        await call('/api/note', {key: tr.dataset.key, note});
        let el=tr.querySelector('.note');
        if(!el){ el=document.createElement('span'); el.className='note'; tr.querySelector('.desc').after(el); }
        el.textContent=note; if(!note) el.remove(); return;
      }
      const target = b.dataset.cmd==='save'
        ? (tr.dataset.status==='saved' ? 'new' : 'saved') : 'dismissed';
      const prev = tr.dataset.status;
      await verdict(tr, target);
      toast((zh ? {saved:'已保存', dismissed:'已忽略', new:'已取消保存'}
                : {saved:'saved', dismissed:'dismissed', new:'unsaved'})[target] + ' · ' + tr.dataset.key,
            ()=>verdict(tr, prev));
    }catch(err){ toast((zh?'失败：':'failed: ') + err.message); }
  }, true));
  document.querySelectorAll('button.dive-btn').forEach(b=>b.addEventListener('click', async ()=>{
    const zh=state.lang==='zh';
    try{
      await call('/api/dive', {brief: b.dataset.brief});
      b.disabled=true; b.textContent = zh ? '核实中，可能要几分钟…' : 'checking, may take minutes…';
      const poll=setInterval(async ()=>{
        const jobs=await call('/api/jobs'); const j=jobs[b.dataset.brief];
        if(j && j.state!=='running'){ clearInterval(poll);
          if(j.state==='done') location.reload();
          else { b.disabled=false; b.textContent=(zh?'失败：':'failed: ')+j.error; } }
      }, 5000);
    }catch(err){ toast((zh?'失败：':'failed: ') + err.message); }
  }));
}

// save / dismiss: the page is static, so the buttons copy the radar command.
// Clipboard access can be refused (file://, embedded views, permissions), so
// fall back to the legacy copy command, and failing that show the command
// inline where it can be selected by hand.
function legacyCopy(text){
  const ta=document.createElement('textarea'); ta.value=text;
  ta.style.position='fixed'; ta.style.opacity='0'; document.body.appendChild(ta);
  ta.select(); let ok=false; try{ ok=document.execCommand('copy'); }catch(e){}
  ta.remove(); return ok;
}
async function copyText(text){
  if(navigator.clipboard && window.isSecureContext){
    try{ await navigator.clipboard.writeText(text); return true; }catch(e){}
  }
  return legacyCopy(text);
}
document.querySelectorAll('button.act').forEach(b=>b.addEventListener('click',async e=>{
  e.preventDefault();
  const key=b.closest('tr').dataset.key, cmd=`radar ${b.dataset.cmd} ${key}`;
  const ok=await copyText(cmd);
  const was=b.textContent;
  if(ok){ b.textContent=T[state.lang].copied; b.classList.add('done');
    setTimeout(()=>{b.textContent=was; b.classList.remove('done');},1400); }
  else { let code=b.parentNode.querySelector('code');
    if(!code){ code=document.createElement('code'); code.className='cmd'; b.parentNode.appendChild(code); }
    code.textContent=cmd; b.classList.add('done'); }
}));

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
langBtn.addEventListener('click',()=>{ state.lang = state.lang==='zh' ? 'en' : 'zh';
  applyLang(); render(); });
applyLang();
render();
})();
</script>
</body></html>
"""


def _both(en: str, zh: str) -> dict:
    return {"en": en, "zh": zh}


def _metrics_line(metrics: dict) -> dict:
    en, zh = [], []
    if metrics.get("stars"):
        en.append(f"{int(metrics['stars']):,}*"); zh.append(f"{int(metrics['stars']):,} 星")
    if metrics.get("stars_per_day"):
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


def _reason(item, sources: list[str], is_new: bool) -> dict:
    """Why this item is worth a glance, built from signals already computed.

    Deterministic on purpose: the briefs section needs Claude Code, and the
    summary at the top of the page should still say something useful without it.
    """
    en, zh = [], []
    if is_new:
        en.append("new this run"); zh.append("本次新增")
    m = item.metrics
    if m.get("stars_per_day"):
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
    "watchlist": (_both("From your watchlist", "来自你的关注列表"),
                  _both("engineers whose taste you chose to borrow", "你选择借鉴其眼光的工程师")),
    "papers": (_both("Papers, usually with no implementation", "论文，通常还没有实现"),
               _both("where the gap is the project", "空白本身就是项目")),
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
        penalties = json.loads(row["breakdown"] or "{}").get("penalties", {})
        prepared.append({
            "row": row, "item": item,
            "sources": sorted(item.sources),
            "is_new": bool(since and (row["first_seen"] or "") >= since),
            "mega": "mega" in penalties,
        })

    def entry(p) -> dict:
        item = p["item"]
        ax = axis.of_item(item)
        th = themes.primary(themes.of_item(item))
        return {
            "title": item.title, "url": item.url,
            "summary": (item.summary or "").strip(),
            "score": p["row"]["score"],
            "axis": _both(axis.label(ax), axis.label(ax, "zh")),
            "theme": _both(th, themes.label(th, "zh")),
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
        ("saved", take([p for p in by_score if p["row"]["status"] == "saved"], n=6)),
        ("new", take([p for p in by_score if p["is_new"]])),
        # A 200k-star repo is the fastest thing on the page and the least
        # useful: you can't do frontier work where everyone already is.
        ("fastest", take(sorted(
            [p for p in prepared if p["item"].metrics.get("stars_per_day") and not p["mega"]],
            key=lambda p: -p["item"].metrics["stars_per_day"]))),
        ("agree", take([p for p in by_score if len(p["sources"]) > 1])),
        ("watchlist", take([p for p in by_score
                            if p["item"].metrics.get("starred_by") or p["item"].metrics.get("worked_on_by")])),
        ("papers", take([p for p in by_score if p["row"]["key"].startswith("arxiv:")])),
    ]
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
            "metrics_line": _metrics_line(item.metrics),
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
          feed_limit: int = 250, api_token: str | None = None) -> tuple[Path, Path]:
    """Write the dashboard and digest.

    `api_token` is set only by `radar serve`: the page then talks to the local
    server. The published page never carries one and stays fully static.
    """
    lang = norm_lang(cfg.get("report.language", "en"))
    run_id = run_id or store.latest_run() or "adhoc"
    briefs = store.briefs(run_id=run_id) or store.briefs(limit=int(cfg.get("brief.count", 8)))
    shown_run = briefs[0]["_run"] if briefs else run_id
    past = _past_briefs(store, shown_run)
    dives = store.dives_for([b["_id"] for b in briefs])
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
    html = env.from_string(TEMPLATE.replace("__CSS__", CSS)).render(
        generated=generated, run_id=run_id, briefs=briefs, past=past, rows=rows,
        dives=dives, api=api_token,
        source_names=source_names, theme_names=theme_names, languages=languages,
        theme_labels=themes.LABELS_ZH, lang=lang,
        axes=[{"id": a, "en": axis.label(a), "zh": axis.label(a, "zh")} for a in axis.ALL_AXES],
        stats=stats, summary=(briefs[0].get("board_summary") if briefs else ""),
        highlights=highlights, mix=mix,
    )
    if api_token:
        # Never overwrite index.html with a page carrying the local API token:
        # index.html is what `radar publish` ships.
        served = cfg.out_dir / "served.html"
        served.write_text(html, encoding="utf-8")
        return served, None
    html_path = cfg.out_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")

    md_path = cfg.out_dir / f"digest-{datetime.now():%Y-%m-%d}.md"
    md_path.write_text(_markdown(briefs, rows, generated, highlights, mix, lang),
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
              lang: str = "en") -> str:
    W = MD.get(lang, MD["en"])
    L = [f"# {W['digest']} - {generated}", ""]
    if mix:
        L += [f"`{mix['new']} {W['new']}` · `{mix['infra']} {W['infra']}` · "
              f"`{mix['applied']} {W['applied']}` · `{mix['nonai']} {W['nonai']}`", ""]
    if highlights:
        L += ["<details open>", f"<summary><b>{W['worth']}</b></summary>", ""]
        for lane in highlights:
            L += [f"### {lane['title'][lang]}", f"*{lane['note'][lang]}*", ""]
            for it in lane["items"]:
                L.append(f"- **[{it['title'].replace('|', chr(92) + '|')}]({it['url']})** "
                         f"`{it['score']:.2f}` — {it['reason'][lang]}")
                if it["summary"]:
                    L.append(f"  <br>{it['summary'][:150]}")
            L.append("")
        L += ["</details>", "", "---", ""]
    if briefs and briefs[0].get("board_summary"):
        L += ["> " + briefs[0]["board_summary"], ""]
    if briefs:
        L += [f"## {W['briefs']}", ""]
        for i, b in enumerate(briefs, 1):
            weeks = (f"约 {b['effort_weeks']} 周" if lang == "zh"
                     else f"~{b['effort_weeks']} weeks")
            L += [
                f"### {i}. {b['title']}",
                f"*{b['one_liner']}*", "",
                f"`{W['difficulty']} {b['difficulty']}/5`  `{W['novelty']} {b['novelty']}/5`  "
                f"`{weeks}`", "",
                b["pitch"], "",
                f"**{W['why_now']}** {b['why_now']}", "",
                f"**{W['hard']}**", *[f"- {h}" for h in b["hard_parts"]], "",
                f"**{W['learn']}**", *[f"- {h}" for h in b["you_will_learn"]], "",
                f"**{W['milestones']}**", *[f"- {m}" for m in b["milestones"]], "",
                f"**{W['prior']}**", *[f"- {p}" for p in b["prior_art"]], "",
                f"**{W['kill']}** {b['kill_criteria']}", "",
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
            title = r["title"].replace("|", "\\|")
            L.append(f"- **{r['score']:.2f}** [{title}]({r['url']}) — {r['why'][lang]}")
        L.append("")
    return "\n".join(L) + "\n"


CSS = """:root{
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
"""
