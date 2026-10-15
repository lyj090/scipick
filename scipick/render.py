"""Render: one self-contained bilingual HTML file.

Constraints that shape this module:

* **One file.** No external assets, no build step, no framework. The output is
  readable offline and works as a static GitHub Pages site unchanged.
* **Two languages.** Both are shipped and switched client-side, so a single
  artifact serves either audience. Tables are language-neutral (model and family
  names come from the data); only interface labels are swapped.
* **Readable without JS.** Panels are all present in the DOM and the first is
  visible by default, so a no-JS reader sees a complete leaderboard.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from .config import DEFAULT_PRESETS, Preset
from .curate import gate as _frontier_gate
from .i18n import DEFAULT_LANG, HTML_LANG, LANGS, LANG_LABEL, js_payload, strings_for

#: Benchmark provenance shown on the page: (metric key, display name, scale,
#: i18n key for the description). Order is the reading order.
BENCHMARKS: tuple[tuple[str, str, str, str], ...] = (
    ("scicode", "SciCode", "0-1", "bench.scicode"),
    ("hle", "HLE", "0-1", "bench.hle"),
    ("aa_intelligence_index", "AA Intelligence Index", "0-100", "bench.index"),
    ("long_context_reasoning", "Long-context reasoning", "0-1", "bench.lcr"),
    ("terminalbench_v4_0", "Terminal-Bench 4.0", "0-1", "bench.terminal"),
)

#: English descriptions, used as the static fallback markup.
_BENCH_DESC_EN = {
    "bench.scicode": "Scientific code generation - solving research-level programming problems.",
    "bench.hle": "Humanity's Last Exam - broad expert-level reasoning across disciplines.",
    "bench.index": "Aggregate reasoning index across many evaluations.",
    "bench.lcr": "Retrieving and reasoning over long inputs, such as whole repositories.",
    "bench.terminal": "Agentic execution in a real shell - multi-step command-line tasks.",
}

#: Presets shipped with scipick, whose descriptions have translations.
BUILTIN_KEYS = frozenset(DEFAULT_PRESETS)

CSS = """
:root{
--bg:#fbfbfa;--panel:#ffffff;--soft:#f4f4f2;--soft2:#ececea;
--line:#e6e6e3;--line2:#d6d6d2;
--fg:#171715;--fg2:#3a3a36;--dim:#71716b;--dim2:#9a9a93;
--accent:#2563eb;--accent-soft:#eff4ff;
--good:#1a7f4b;--good-soft:#e9f5ee;
--warn:#b45309;--warn-soft:#fdf4e7;
--bar1:#2563eb;--bar2:#60a5fa;
--shadow:0 1px 2px rgba(16,18,20,.04),0 4px 14px rgba(16,18,20,.04);
--radius:14px;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB",
  "Microsoft YaHei","Noto Sans SC",sans-serif;
--mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
[data-theme="dark"]{
--bg:#111113;--panel:#18181b;--soft:#212124;--soft2:#2a2a2e;
--line:#2c2c31;--line2:#3a3a40;
--fg:#f2f2f0;--fg2:#d4d4d0;--dim:#9a9a94;--dim2:#75756f;
--accent:#60a5fa;--accent-soft:#1a2333;
--good:#4ade80;--good-soft:#14261c;
--warn:#fbbf24;--warn-soft:#2a2113;
--bar1:#3b82f6;--bar2:#60a5fa;
--shadow:0 1px 2px rgba(0,0,0,.3),0 4px 14px rgba(0,0,0,.25);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.6 var(--sans);-webkit-font-smoothing:antialiased;
font-variant-numeric:tabular-nums}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{background:var(--soft);padding:2px 6px;border-radius:5px;font-size:.86em;
font-family:var(--mono);color:var(--fg2)}

/* ---------- layout ---------- */
.wrap{max-width:1240px;margin:0 auto;padding:0 24px 96px}
header.top{position:sticky;top:0;z-index:40;background:color-mix(in srgb,var(--bg) 88%,transparent);
backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.top-in{max-width:1240px;margin:0 auto;padding:12px 24px;display:flex;align-items:center;
gap:14px;flex-wrap:wrap}
.brand{font-weight:700;font-size:17px;letter-spacing:-.3px;display:flex;align-items:center;gap:8px}
.brand .dot{width:9px;height:9px;border-radius:3px;background:var(--accent);flex:none}
.spacer{flex:1}
.search{position:relative;display:flex;align-items:center}
.search input{font:inherit;font-size:14px;padding:7px 12px 7px 32px;border-radius:9px;
border:1px solid var(--line);background:var(--panel);color:var(--fg);width:210px;
transition:border-color .15s,width .2s}
.search input:focus{outline:none;border-color:var(--accent);width:280px}
.search svg{position:absolute;left:10px;width:14px;height:14px;color:var(--dim2);pointer-events:none}
.btn{font:inherit;font-size:13px;font-weight:600;padding:7px 12px;border-radius:9px;
border:1px solid var(--line);background:var(--panel);color:var(--fg2);cursor:pointer;
transition:border-color .15s,color .15s}
.btn:hover{border-color:var(--line2);color:var(--fg)}
.btn:active{transform:translateY(1px)}
.btn{transition:border-color .15s,color .15s,transform .08s ease}
.btn.icon{padding:7px 9px;line-height:1}

/* ---------- hero ---------- */
.hero{padding:38px 0 26px}
h1{font-size:34px;line-height:1.15;margin:0 0 12px;font-weight:750;letter-spacing:-.9px}
h1 .mark{color:var(--accent)}
.tagline{color:var(--dim);font-size:15px;max-width:700px;margin:0}
.stamp{color:var(--dim2);font-size:12.5px;margin-top:14px;font-family:var(--mono)}

/* ---------- tabs ---------- */
.tabs{display:flex;gap:4px;margin:26px 0 0;flex-wrap:wrap;
border-bottom:1px solid var(--line);padding-bottom:0}
.tab{appearance:none;border:1px solid transparent;border-bottom:none;background:transparent;
font:inherit;font-size:14.5px;font-weight:600;color:var(--dim);padding:10px 18px;
cursor:pointer;border-radius:10px 10px 0 0;position:relative;top:1px;
transition:color .15s,background .15s}
.tab:hover{color:var(--fg2)}
.tab[aria-selected="true"]{color:var(--fg);background:var(--panel);
border-color:var(--line);box-shadow:0 -2px 0 var(--accent) inset}
.tab .k{font-family:var(--mono);font-size:11px;color:var(--dim2);margin-left:7px;font-weight:400}

/* ---------- panels ---------- */
.panel{display:none;padding-top:26px}
.panel.on{display:block}
/* Entrance is a short, single-direction rise. Animating transform/opacity only
   keeps it off the layout path, so 60 rows and 24 bars stay cheap. */
.panel.on .cards,
.panel.on .plot,
.panel.on .tw,
.panel.on .desc{animation:rise .34s cubic-bezier(.22,.61,.36,1) backwards}
.panel.on .cards{animation-delay:.02s}
.panel.on .plot{animation-delay:.08s}
.panel.on .tw{animation-delay:.12s}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
/* Bars grow from the baseline. Delay is capped by nth-child so a long chart
   does not stagger for a full second. */
.panel.on .col .bx{animation:grow .5s cubic-bezier(.22,.61,.36,1) backwards;
transform-origin:bottom}
.panel.on .col:nth-child(1) .bx{animation-delay:.06s}
.panel.on .col:nth-child(2) .bx{animation-delay:.10s}
.panel.on .col:nth-child(3) .bx{animation-delay:.14s}
.panel.on .col:nth-child(4) .bx{animation-delay:.18s}
.panel.on .col:nth-child(5) .bx{animation-delay:.22s}
.panel.on .col:nth-child(n+6) .bx{animation-delay:.26s}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
.panel .desc{color:var(--dim);font-size:14px;margin:0 0 4px}

/* ---------- cards ---------- */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(216px,1fr));gap:14px;
margin:20px 0 8px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
padding:16px 18px 18px;box-shadow:var(--shadow);display:flex;flex-direction:column;
min-height:118px}
.card .k{font-size:12px;color:var(--dim);font-weight:650;letter-spacing:.02em;
text-transform:uppercase}
.card .v{font-size:27px;font-weight:750;margin-top:auto;letter-spacing:-.7px;line-height:1.25}
.card .v.sm{font-size:16px;font-family:var(--mono);letter-spacing:-.2px;
overflow-wrap:anywhere;font-weight:650}
.card .n{color:var(--dim);font-size:12.5px;margin-top:5px}
.card.accent{border-color:color-mix(in srgb,var(--accent) 35%,var(--line))}
.card.accent .v{color:var(--accent)}

/* ---------- notes ---------- */
.note{background:var(--soft);border-left:3px solid var(--line2);padding:12px 16px;
border-radius:0 10px 10px 0;margin:18px 0;font-size:13.5px;color:var(--fg2)}
.note.warn{background:var(--warn-soft);border-left-color:var(--warn)}
.note.info{background:var(--accent-soft);border-left-color:var(--accent)}
.note b{color:var(--fg)}

/* ---------- chart ---------- */
.plot{display:flex;align-items:flex-end;gap:5px;height:236px;margin-top:18px;
border-bottom:1px solid var(--line2);position:relative}
.col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;
height:100%;position:relative;min-width:0}
.col .bv{font-size:10.5px;font-family:var(--mono);color:var(--dim);margin-bottom:4px;
font-variant-numeric:tabular-nums}
.col .bx{width:100%;border-radius:4px 4px 0 0;
background:linear-gradient(180deg,var(--bar2),var(--bar1));transition:opacity .15s}
.col{transition:transform .14s ease}
.col:hover{transform:translateY(-2px)}
.col:first-child .bx{background:linear-gradient(180deg,var(--accent),var(--bar1))}
.xlab{display:flex;gap:5px;margin-top:8px}
.xlab .c{flex:1;min-width:0}
.xlab span{display:block;font-size:10.5px;color:var(--dim);writing-mode:vertical-rl;
transform:rotate(180deg);height:100px;overflow:hidden;margin:0 auto}

/* ---------- tables ---------- */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:6px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);
white-space:nowrap}
th{font-size:11.5px;color:var(--dim);font-weight:650;text-transform:uppercase;
letter-spacing:.05em;position:sticky;top:0;background:var(--bg);z-index:1}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono);
font-size:13px}
tbody tr{transition:background .12s ease}
tbody tr:hover{background:var(--soft)}
/* Dim siblings so the hovered bar is unambiguous in a dense chart. */
.plot:hover .col .bx{opacity:.45}
.plot .col:hover .bx{opacity:1}
.col .bx{transition:opacity .14s ease}
/* Keyboard users get the same affordance as pointer users. */
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
/* Filtered-out rows collapse rather than vanishing, so filtering reads as a
   state change instead of a jump. display is still toggled (see JS) so the
   row genuinely leaves the layout. */
tr.hide{display:none}
tbody tr{will-change:background}
.rk{color:var(--dim2);font-family:var(--mono);font-size:12.5px;width:40px}
.rk.top{color:var(--accent);font-weight:700}
.nm{font-weight:650}
.fam{color:var(--dim);font-size:13px}
.pill{display:inline-block;background:var(--soft2);border-radius:20px;padding:1px 9px;
font-size:11px;color:var(--dim);margin-left:7px;font-weight:600;vertical-align:1px}
.pill.local{background:var(--good-soft);color:var(--good)}
.bar{display:inline-block;width:52px;height:6px;background:var(--soft2);border-radius:3px;
overflow:hidden;vertical-align:middle;margin-right:8px}
.bar i{display:block;height:100%;background:var(--accent);border-radius:3px}
.mdash{color:var(--dim2)}
.cov-lo{color:var(--warn)}

/* ---------- methodology ---------- */
h2{font-size:20px;margin:52px 0 6px;font-weight:700;letter-spacing:-.3px;
display:flex;align-items:center;gap:10px}
h2::before{content:"";width:4px;height:19px;background:var(--accent);border-radius:2px;flex:none}
h3{font-size:15px;margin:0 0 4px;font-weight:650}
.lede{color:var(--dim);font-size:14px;margin:0 0 16px;max-width:820px}
.wt{font-family:var(--mono);font-size:12.5px}
.wt em{font-style:normal;color:var(--dim2)}
.wt b{font-weight:650;color:var(--fg)}

/* ---------- footer ---------- */
footer{margin-top:64px;padding-top:22px;border-top:1px solid var(--line);
color:var(--dim);font-size:13px;display:flex;gap:18px;flex-wrap:wrap;align-items:center}
footer .sep{color:var(--line2)}

@media(prefers-reduced-motion:reduce){
*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;
transition-duration:.01ms!important;scroll-behavior:auto!important}
.panel.on .cards,.panel.on .plot,.panel.on .tw,.panel.on .desc,
.panel.on .col .bx{animation:none}
.plot:hover .col .bx{opacity:1}
.col:hover{transform:none}
}
@media(max-width:720px){
.wrap{padding:0 16px 72px}
.top-in{padding:10px 16px;gap:8px}
.brand{font-size:16px}
h1{font-size:26px}
.hero{padding:26px 0 18px}
.tagline{font-size:14px}
/* Search takes a full row of its own rather than being squeezed beside the
   brand and buttons, which wrapped awkwardly at 390px. */
/* Search and its count share the second row: the count belongs to the filter,
   so keeping them adjacent reads as one control. */
.search{order:10;flex:1 1 auto;margin-top:2px;min-width:0}
.search input,.search input:focus{width:100%}
#qcount{order:11;flex:0 0 auto;margin-top:2px;padding:4px 0 4px 6px}
.plot{height:190px}
.xlab span{height:78px}
.cards{grid-template-columns:1fr 1fr;gap:10px}
.card{padding:13px 14px 15px;min-height:104px}
.card .v{font-size:21px}
.card .v.sm{font-size:14px}
th,td{padding:9px 8px}
.bar{width:34px;margin-right:6px}
}
@media(max-width:430px){
.cards{grid-template-columns:1fr}
/* Family is the first thing to go: it is the least informative column when
   the model name usually implies it. Eff. and Cov. keep their space. */
.fam,.th.family,td.fam{display:none}
h1{font-size:24px}
.tab{padding:9px 12px;font-size:13.5px}
.tab .k{display:none}
.plot{height:165px}
.xlab span{height:70px;font-size:9.5px}
.col .bv{font-size:9.5px}
}
"""

JS = r"""
(function(){
  var STR = __STRINGS__;
  var LANGS = __LANGS__;
  var DEFAULT_LANG = __DEFAULT_LANG__;
  var root = document.documentElement;

  /* ---------- language ---------- */
  function t(lang, key){
    var pack = STR[lang] || STR[DEFAULT_LANG] || {};
    return pack[key] != null ? pack[key] : ((STR[DEFAULT_LANG]||{})[key] || '');
  }
  function applyLang(lang){
    root.setAttribute('lang', __HTML_LANG__[lang] || 'en');
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      el.textContent = t(lang, el.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-html]').forEach(function(el){
      el.innerHTML = t(lang, el.getAttribute('data-i18n-html'));
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(function(el){
      el.setAttribute('placeholder', t(lang, el.getAttribute('data-i18n-ph')));
    });
    document.querySelectorAll('[data-i18n-title]').forEach(function(el){
      el.setAttribute('title', t(lang, el.getAttribute('data-i18n-title')));
    });
    document.title = t(lang, 'page.title');
    var m = document.querySelector('meta[name="description"]');
    if (m) m.setAttribute('content', t(lang, 'page.desc'));
    // Coverage-floor notes carry an interpolated count.
    document.querySelectorAll('[data-floor-n]').forEach(function(el){
      var n = el.getAttribute('data-floor-n');
      var pct = el.getAttribute('data-floor-pct');
      el.innerHTML = t(lang,'panel.floor').replace('{n}',n).replace('{pct}',pct);
    });
    // Summary-card notes carry interpolated values.
    document.querySelectorAll('[data-tpl]').forEach(function(el){
      var out = t(lang, el.getAttribute('data-tpl'));
      for (var i = 0; i < el.attributes.length; i++){
        var a = el.attributes[i];
        if (a.name.indexOf('data-v-') === 0) out = out.replace('{'+a.name.slice(7)+'}', a.value);
      }
      el.textContent = out;
    });
    var lb = document.getElementById('langbtn');
    if (lb) lb.textContent = __LANG_LABEL__[lang];
    try { localStorage.setItem('scipick.lang', lang); } catch(e){}
    current.lang = lang;
    updateCount();
  }

  /* ---------- theme ---------- */
  function applyTheme(mode){
    if (mode === 'auto'){
      root.removeAttribute('data-theme');
      var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (dark) root.setAttribute('data-theme','dark');
    } else {
      root.setAttribute('data-theme', mode);
    }
    try { localStorage.setItem('scipick.theme', mode); } catch(e){}
    current.theme = mode;
  }
  function cycleTheme(){
    var order = ['auto','light','dark'];
    var i = order.indexOf(current.theme);
    applyTheme(order[(i+1) % order.length]);
  }

  /* ---------- tabs ---------- */
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
  var panels = Array.prototype.slice.call(document.querySelectorAll('.panel'));
  function show(key){
    tabs.forEach(function(x){
      var on = x.dataset.key === key;
      x.setAttribute('aria-selected', String(on));
      // Roving tabindex: only the selected tab is in the tab order, so Tab
      // moves past the tab strip instead of through every tab.
      x.setAttribute('tabindex', on ? '0' : '-1');
    });
    panels.forEach(function(p){ p.classList.toggle('on', p.dataset.key===key); });
    current.tab = key;
    if (history.replaceState) history.replaceState(null,'','#'+key);
    updateCount();
  }
  tabs.forEach(function(x, i){
    x.addEventListener('click', function(){ show(x.dataset.key); });
    // ARIA tabs pattern: arrow keys move between tabs, Home/End jump to the
    // ends. Without this the tabs are reachable but not navigable by keyboard.
    x.addEventListener('keydown', function(e){
      var k = e.key, next = null;
      if (k === 'ArrowRight') next = tabs[(i+1) % tabs.length];
      else if (k === 'ArrowLeft') next = tabs[(i-1+tabs.length) % tabs.length];
      else if (k === 'Home') next = tabs[0];
      else if (k === 'End') next = tabs[tabs.length-1];
      if (!next) return;
      e.preventDefault();
      show(next.dataset.key);
      next.focus();
    });
  });

  /* ---------- search ---------- */
  var box = document.getElementById('q');
  function norm(s){ return (s||'').toLowerCase(); }
  function filter(){
    var q = norm(box ? box.value.trim() : '');
    document.querySelectorAll('tbody tr[data-name]').forEach(function(tr){
      var hit = !q || tr.getAttribute('data-name').indexOf(q) >= 0;
      tr.classList.toggle('hide', !hit);
    });
    updateCount();
  }
  if (box) box.addEventListener('input', filter);

  /* ---------- count, scoped to the visible panel ---------- */
  var counter = document.getElementById('qcount');
  function updateCount(){
    if (!counter) return;
    var panel = document.querySelector('.panel.on');
    if (!panel) { counter.textContent=''; return; }
    var rows = panel.querySelectorAll('tbody tr[data-name]');
    var shown = 0;
    rows.forEach(function(r){ if (!r.classList.contains('hide')) shown++; });
    var tpl = current.lang ? t(current.lang,'search.count') : '{shown} of {total}';
    counter.textContent = tpl.replace('{shown}', shown).replace('{total}', rows.length);
  }

  /* ---------- boot ---------- */
  var current = { lang: null, theme: 'auto', tab: null };
  var initLang = null, initTheme = null;
  try { initLang = localStorage.getItem('scipick.lang');
        initTheme = localStorage.getItem('scipick.theme'); } catch(e){}
  var hash = (location.hash||'').replace('#','');
  var known = tabs.map(function(x){ return x.dataset.key; });
  show(known.indexOf(hash) >= 0 ? hash : (tabs[0] && tabs[0].dataset.key));
  applyTheme(initTheme || 'auto');
  applyLang(initLang || DEFAULT_LANG);

  var lb = document.getElementById('langbtn');
  if (lb) lb.addEventListener('click', function(){
    var i = LANGS.indexOf(current.lang);
    applyLang(LANGS[(i+1) % LANGS.length]);
  });
  var tb = document.getElementById('themebtn');
  if (tb) tb.addEventListener('click', cycleTheme);
  if (window.matchMedia){
    try { window.matchMedia('(prefers-color-scheme: dark)')
      .addEventListener('change', function(){ if (current.theme==='auto') applyTheme('auto'); }); }
    catch(e){}
  }
})();
"""


def esc(v) -> str:
    return html.escape(str(v))


def fmt_score(v) -> str:
    return '<span class="mdash">&mdash;</span>' if v is None else f"{v:.1f}"


def fmt_price(v) -> str:
    """AA reports 0 for "price not published" — must not read as free."""
    if v is None or v <= 0:
        return '<span class="mdash">&mdash;</span>'
    return "$" + f"{v:.2f}".rstrip("0").rstrip(".")


def fmt_eff(v) -> str:
    if v is None:
        return '<span class="mdash">&mdash;</span>'
    if v >= 100:
        return f"{v:.0f}"
    return f"{v:.1f}"


def bar(pct: float) -> str:
    pct = max(0.0, min(100.0, pct))
    return f'<span class="bar"><i style="width:{pct:.0f}%"></i></span>'


def _chart(models: list[dict], value_key: str, top: int = 24) -> str:
    rows = [m for m in models if m.get(value_key) is not None][:top]
    if not rows:
        return '<p class="lede">&mdash;</p>'
    vals = [m[value_key] for m in rows]
    vmax, vmin = max(vals), min(vals)
    span = (vmax - vmin) or max(abs(vmax) * 0.2, 1)
    floor = max(0.0, vmin - span * 0.28)
    rng = (vmax - floor) or 1

    bars, labs = [], []
    for m in rows:
        v = m[value_key]
        h = max(2.5, min(93.0, (v - floor) / rng * 93.0))
        name = m["name"]
        short = name if len(name) <= 26 else name[:25] + "…"
        bars.append(
            f'<div class="col" title="{esc(name)} — {v:.1f}">'
            f'<span class="bv">{v:.1f}</span>'
            f'<div class="bx" style="height:{h:.1f}%"></div></div>'
        )
        labs.append(f'<div class="c"><span>{esc(short)}</span></div>')
    return f'<div class="plot">{"".join(bars)}</div><div class="xlab">{"".join(labs)}</div>'


def _eligible(model: dict, preset: Preset) -> bool:
    """Whether a model has enough data to be ranked under this preset.

    A coverage floor, not just a non-null score: renormalisation alone would let
    a model with one of five metrics top the chart.
    """
    if model["scores"].get(preset.key) is None:
        return False
    if model["coverage"].get(preset.key, 0.0) < preset.min_coverage:
        return False
    if preset.rank_by == "efficiency" and model["efficiency"].get(preset.key) is None:
        return False
    return True


def _row(rank: int, m: dict, preset: Preset, max_score: float) -> str:
    name = esc(m["name"])
    if m.get("available_locally"):
        name += f'<span class="pill local" data-i18n="row.local">local</span>'
    if m["sources"]:
        name += f'<span class="pill">{esc("·".join(m["sources"]))}</span>'

    score = m["scores"].get(preset.key)
    eff = m["efficiency"].get(preset.key)
    price = m["pricing"].get("blended")
    cov = m["coverage"].get(preset.key, 0)
    pct = (score / max_score * 100) if (score is not None and max_score) else 0

    rk_cls = "rk top" if rank <= 3 else "rk"
    cov_cls = "num cov-lo" if cov < 0.75 else "num"
    # Search haystack: model name plus family, so "claude" finds the family.
    hay = esc((m["name"] + " " + m["family"]).lower())

    return (
        f'<tr data-name="{hay}">'
        f'<td class="{rk_cls}">{rank}</td>'
        f'<td><span class="nm">{name}</span></td>'
        f'<td class="fam">{esc(m["family"])}</td>'
        f'<td class="num">{bar(pct)}{fmt_score(score)}</td>'
        f'<td class="num">{fmt_price(price)}</td>'
        f'<td class="num">{fmt_eff(eff)}</td>'
        f'<td class="{cov_cls}">{cov:.2f}</td>'
        "</tr>"
    )


def _table(models: list[dict], preset: Preset, limit: int | None = None) -> str:
    total = len(models)
    shown = models[:limit] if limit else models
    if not shown:
        return '<p class="lede" data-i18n="panel.empty">No models matched this view.</p>'
    max_score = max((m["scores"].get(preset.key) or 0) for m in shown) or 1
    body = "".join(_row(i, m, preset, max_score) for i, m in enumerate(shown, 1))
    sort_key = "panel.sorted.eff" if preset.rank_by == "efficiency" else "panel.sorted.score"
    trunc = ""
    if limit and total > limit:
        trunc = (
            f'<div class="note"><span data-tpl="table.truncated" '
            f'data-v-shown="{len(shown)}" data-v-total="{total}">'
            f'Showing the top {len(shown)} of {total}. The JSON export has all models.'
            f"</span></div>"
        )
    return (
        '<div class="tw"><table><thead><tr>'
        '<th class="rk">#</th>'
        '<th data-i18n="th.model">Model</th>'
        '<th data-i18n="th.family">Family</th>'
        '<th class="num" data-i18n="th.score">Score</th>'
        '<th class="num" data-i18n="th.price">$/1M</th>'
        '<th class="num" data-i18n="th.eff">Eff.</th>'
        '<th class="num" data-i18n="th.cov">Cov.</th>'
        f'</tr></thead><tbody>{body}</tbody></table></div>'
        f"{trunc}"
        f'<p class="lede"><span data-i18n="{sort_key}">Sorted.</span> '
        f'<span data-i18n="panel.cov_note">Cov. is coverage.</span></p>'
    )


def _desc_attr(preset: Preset) -> str:
    """Translation hook for built-in preset descriptions."""
    if preset.key in BUILTIN_KEYS:
        return f' data-i18n="preset.{esc(preset.key)}.desc"'
    return ""


def _card(label_key: str, value: str, note_html: str, accent: bool = False) -> str:
    cls = "card accent" if accent else "card"
    size = " sm" if len(value) > 16 else ""
    return (
        f'<div class="{cls}">'
        f'<div class="k" data-i18n="{label_key}">{esc(label_key)}</div>'
        f'<div class="v{size}">{value}</div>'
        f'<div class="n">{note_html}</div>'
        f"</div>"
    )


def _panel(models: list[dict], preset: Preset, first: bool,
           limit: int | None = None, value_floor: float = 0.0) -> str:
    # Frontier gate first: "best value" should mean best value among models
    # worth using, not best ratio among everything ever released.
    gated, below_frontier, threshold = _frontier_gate(models, preset)

    ranked = [m for m in gated if _eligible(m, preset)]
    if preset.rank_by == "efficiency":
        ranked.sort(key=lambda m: -(m["efficiency"].get(preset.key) or 0))
    else:
        ranked.sort(key=lambda m: -(m["scores"].get(preset.key) or 0))

    excluded = [
        m for m in gated
        if m["scores"].get(preset.key) is not None and not _eligible(m, preset)
    ]

    best = ranked[0] if ranked else None

    # The value card must not contradict the value board. Ranking efficiency
    # over *this* view's whole set would surface a cheap 4B model here (the
    # capability view has no gate of its own), while the value board correctly
    # excludes it. Apply the value floor to this view's scores as well, so the
    # card means "best value among models within reach of this view's frontier".
    floor_score = (best["scores"][preset.key] * value_floor) if (best and value_floor) else None
    by_value = sorted(
        (m for m in ranked
         if m["efficiency"].get(preset.key) is not None
         and (floor_score is None or (m["scores"].get(preset.key) or 0) >= floor_score)),
        key=lambda m: -(m["efficiency"].get(preset.key) or 0),
    )
    best_value = by_value[0] if by_value else None

    chart_rows = []
    for m in ranked[:24]:
        v = (m["efficiency"].get(preset.key) if preset.rank_by == "efficiency"
             else m["scores"].get(preset.key))
        if v is None:
            continue
        row = dict(m)
        row["_chart"] = v
        chart_rows.append(row)

    cards = [
        (
            "card.ranked",
            str(len(ranked)),
            f'<span data-tpl="card.ranked.note" data-v-pct="{preset.min_coverage:.0%}">'
            f'coverage ≥ {preset.min_coverage:.0%}</span>',
            True,
        ),
        (
            "card.best",
            esc(best["name"]) if best else "&mdash;",
            (f'<span data-tpl="card.best.note" data-v-score="{best["scores"][preset.key]:.1f}">'
             f'{best["scores"][preset.key]:.1f} pts</span>') if best
            else '<span data-i18n="card.none">no data</span>',
            False,
        ),
        (
            "card.value",
            esc(best_value["name"]) if best_value else "&mdash;",
            (f'<span data-tpl="card.value.note" '
             f'data-v-eff="{best_value["efficiency"][preset.key]:.0f}">'
             f'{best_value["efficiency"][preset.key]:.0f} pts/$</span>') if best_value
            else '<span data-i18n="card.noprice">no published price</span>',
            False,
        ),
    ]
    cards_html = "".join(_card(*c) for c in cards)

    floor_note = ""
    if excluded:
        floor_note = (
            f'<div class="note warn" data-floor-n="{len(excluded)}" '
            f'data-floor-pct="{preset.min_coverage:.0%}">{len(excluded)} further model(s) '
            f'fall below the {preset.min_coverage:.0%} coverage floor.</div>'
        )

    return (
        f'<section class="panel{" on" if first else ""}" data-key="{esc(preset.key)}">'
        f'<p class="desc"{_desc_attr(preset)}>{esc(preset.description)}</p>'
        f'<div class="cards">{cards_html}</div>'
        f"{floor_note}"
        f'<h2><span data-tpl="panel.top" data-v-n="{len(chart_rows)}">'
        f'Top {len(chart_rows)}</span></h2>'
        f"{_chart(chart_rows, '_chart')}"
        f'<h2 data-i18n="panel.full">Full ranking</h2>'
        f"{_table(ranked, preset, limit)}"
        "</section>"
    )


def render(
    models: list[dict],
    presets: dict[str, Preset],
    meta: dict | None = None,
    generated: str | None = None,
    source_labels: dict[str, str] | None = None,
    limit: int | None = 60,
) -> str:
    """Render the full self-contained bilingual HTML page.

    ``limit`` caps rows per panel. 475 models x 4 views is ~1100 rows, which
    makes the file needlessly heavy for a page nobody scrolls to the bottom of;
    the JSON export remains complete for programmatic use.
    """
    meta = meta or {}
    generated = generated or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    s = strings_for(DEFAULT_LANG)

    keys = list(presets.keys())

    def _tab(key: str) -> str:
        preset = presets[key]
        # Show the raw key only when it adds information over the label.
        suffix = (f'<span class="k">{esc(key)}</span>'
                  if key.lower() != preset.label.lower() else "")
        return (f'<button class="tab" data-key="{esc(key)}" role="tab" '
                f'aria-selected="false">{esc(preset.label)}{suffix}</button>')

    tabs = "".join(_tab(k) for k in keys)
    # Efficiency floor from whichever preset ranks by value, so every panel's
    # value card uses the same bar the value board uses.
    value_floor = 0.0
    for p in presets.values():
        if p.rank_by == "efficiency" and p.min_relative_score:
            value_floor = max(value_floor, p.min_relative_score)

    panels = "".join(_panel(models, presets[k], first=(i == 0), limit=limit,
                            value_floor=value_floor)
                     for i, k in enumerate(keys))

    weight_rows = "".join(
        f"<tr><td><b>{esc(p.label)}</b><br><em class='wt'>{esc(k)}</em></td>"
        f"<td class='wt'>{' · '.join(f'<b>{esc(mk)}</b> {w:.2f}' for mk, w in p.weights.items())}</td>"
        f"<td class='wt'><em>{esc(p.rank_by)}</em></td>"
        f"<td class='num'>{p.min_coverage:.0%}</td></tr>"
        for k, p in presets.items()
    )

    # Benchmark provenance: what each metric measures, its scale, and how many
    # board models report it. Stating coverage up front is the difference between
    # a ranking and a defensible one.
    total = len(models) or 1
    bench_rows = ""
    for key, label, scale, desc_key in BENCHMARKS:
        n = sum(1 for m in models if m["metrics"].get(key) is not None)
        pct = n / total * 100
        bench_rows += (
            f"<tr><td><b>{esc(label)}</b><br><em class='wt'>{esc(key)}</em></td>"
            f"<td><span data-i18n='{desc_key}'>{esc(_BENCH_DESC_EN[desc_key])}</span></td>"
            f"<td class='wt'><em>{esc(scale)}</em></td>"
            f"<td class='num'>{n} <em class='wt'>({pct:.0f}%)</em></td></tr>"
        )

    sources = ", ".join(sorted(source_labels)) if source_labels else ""
    local_note = ""
    if meta.get("local_base"):
        src_txt = esc(sources) if sources else esc(meta["local_base"])
        local_note = (
            f'<span class="sep">·</span>'
            f'<span><span data-i18n="meta.localgateway">Local gateway</span>: '
            f'<code>{src_txt}</code></span>'
        )

    lang_switch = "".join(
        f'<button class="btn" id="langbtn" data-langs="{",".join(LANGS)}">'
        f'{esc(LANG_LABEL[DEFAULT_LANG])}</button>'
    )

    # Serialise the translation table safely for inline <script>.
    payload = js_payload().replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="{HTML_LANG[DEFAULT_LANG]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(s['page.title'])}</title>
<meta name="description" content="{esc(s['page.desc'])}">
<meta name="color-scheme" content="light dark">
<style>{CSS}</style>
</head>
<body>

<header class="top"><div class="top-in">
  <span class="brand"><i class="dot"></i>{esc(s['brand'])}</span>
  <span class="spacer"></span>
  <label class="search">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
      stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
    <input id="q" type="search" autocomplete="off"
      placeholder="{esc(s['search.placeholder'])}" data-i18n-ph="search.placeholder"
      aria-label="{esc(s['search.placeholder'])}">
  </label>
  <span class="btn icon" id="qcount" role="status" aria-live="polite"
    style="border:none;background:none;color:var(--dim2);
    font-family:var(--mono);font-size:12px;padding:7px 2px"></span>
  {lang_switch}
  <button class="btn icon" id="themebtn" data-i18n-title="theme.toggle"
    title="{esc(s['theme.toggle'])}" aria-label="{esc(s['theme.toggle'])}">◐</button>
</div></header>

<div class="wrap">
  <div class="hero">
    <h1><span class="mark">sci</span>pick</h1>
    <p class="tagline" data-i18n="tagline">{esc(s['tagline'])}</p>
    <p class="stamp"><span data-i18n="generated">Generated</span> {esc(generated)}</p>
  </div>

  <div class="tabs" role="tablist" aria-label="{esc(s['tab.aria'])}">{tabs}</div>
  {panels}

  <h2 data-i18n="method.title">Weighting</h2>
  <p class="lede" data-i18n-html="method.desc">{s['method.desc']}</p>
  <div class="tw"><table><thead><tr>
    <th data-i18n="method.preset">View</th>
    <th data-i18n="method.weights">Weights</th>
    <th data-i18n="method.rankby">Rank by</th>
    <th class="num" data-i18n="method.floor">Coverage floor</th>
  </tr></thead><tbody>{weight_rows}</tbody></table></div>
  <p class="lede" data-i18n="method.note">Weights are relative and renormalised per model.</p>

  <h2 data-i18n="bench.title">Benchmarks</h2>
  <p class="lede" data-i18n="bench.desc">What the weighted metrics measure.</p>
  <div class="tw"><table><thead><tr>
    <th data-i18n="bench.metric">Benchmark</th>
    <th data-i18n="bench.measures">What it measures</th>
    <th data-i18n="bench.scale">Scale</th>
    <th class="num" data-i18n="bench.coverage">Coverage</th>
  </tr></thead><tbody>{bench_rows}</tbody></table></div>

  <h2 data-i18n="howto.title">How to read this</h2>
  <div class="note info" data-i18n-html="howto.body">{s['howto.body']}</div>

  <h2 data-i18n="meta.title">Data</h2>
  <p class="lede" data-tpl="meta.selection"
     data-v-aa="{meta.get('aa_total', 0)}"
     data-v-superseded="{meta.get('superseded_removed', 0)}"
     data-v-vendors="{meta.get('vendors_removed', 0)}">
    Selected from {meta.get('aa_total', 0)} models: latest generation per product line,
    mainstream vendors only.</p>
  <footer>
    <span><a href="https://artificialanalysis.ai">Artificial Analysis</a>
      <span data-i18n="meta.aa">data API</span> &mdash;
      <span data-tpl="meta.fetched" data-v-n="{meta.get('aa_total', 0)}">
        {meta.get('aa_total', 0)} models fetched</span>,
      <span data-tpl="meta.rankable" data-v-n="{meta.get('board_size', 0)}">
        {meta.get('board_size', 0)} rankable</span></span>
    {local_note}
    <span class="sep">·</span>
    <span data-i18n="meta.byline">Scoring and presentation by scipick.</span>
    <span class="sep">·</span>
    <span><a href="https://github.com/lyj090/scipick" data-i18n="meta.source_code">Source</a>
      (<span data-i18n="meta.license">MIT</span>)</span>
  </footer>
</div>

<script>
var __STRINGS__ = {payload};
var __LANGS__ = {json.dumps(list(LANGS))};
var __DEFAULT_LANG__ = {json.dumps(DEFAULT_LANG)};
var __LANG_LABEL__ = {json.dumps(LANG_LABEL, ensure_ascii=False)};
var __HTML_LANG__ = {json.dumps(HTML_LANG)};
{JS}
</script>
</body>
</html>
"""


def render_json(models: list[dict], presets: dict[str, Preset], meta: dict,
                generated: str) -> str:
    """Machine-readable dump, for reuse by other tools."""
    return json.dumps(
        {
            "generated_at": generated,
            "weights": {k: p.weights for k, p in presets.items()},
            "meta": meta,
            "models": models,
        },
        ensure_ascii=False,
        indent=2,
    )
