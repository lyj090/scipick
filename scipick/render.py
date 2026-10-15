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
import re
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

#: Categorical palette for the scatter, applied to the vendors that reach the
#: frontier in a given view. Chosen to stay distinguishable from each other and
#: from the grey mass, and to work on both the light and dark paper. Ordered so
#: the first few are the most separable, since most views have fewer than eight
#: notable vendors.
VENDOR_COLORS: tuple[str, ...] = (
    "#c2410c",  # burnt orange
    "#1d4ed8",  # blue
    "#0f766e",  # teal
    "#a21caf",  # magenta
    "#4d7c0f",  # olive
    "#b45309",  # amber-brown
    "#7c3aed",  # violet
    "#0369a1",  # steel blue
    "#be123c",  # crimson
    "#15803d",  # green
)

#: Presets shipped with scipick, whose descriptions have translations.
BUILTIN_KEYS = frozenset(DEFAULT_PRESETS)

CSS = """
:root{
/* Palette follows the reading-first sites this is modelled on: near-white
   paper, one restrained accent, and hierarchy carried by type and space
   rather than by borders and shadows. */
--bg:#fdfdfc;--panel:#ffffff;--soft:#f6f6f4;--soft2:#eeeeeb;
--line:#e8e8e4;--line2:#d8d8d3;
--fg:#17171a;--fg2:#3b3b3f;--dim:#6f6f75;--dim2:#9c9ca3;
--accent:#2563eb;--accent-soft:#f0f5ff;
--good:#18794e;--good-soft:#e9f5ee;
--warn:#a15c07;--warn-soft:#fdf5e9;
--gold:#b08324;--silver:#8a8a90;--bronze:#a2703f;
--bar1:#2563eb;--bar2:#7aa7f5;
--shadow:0 1px 2px rgba(16,18,20,.03);
--shadow-lift:0 2px 4px rgba(16,18,20,.04),0 12px 28px rgba(16,18,20,.07);
--radius:16px;
/* Height of the sticky bar, so sticky table headers can pin below it. */
--topbar:67px;
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
.wrap{max-width:1120px;margin:0 auto;padding:0 24px 120px}
header.top{position:sticky;top:0;z-index:40;background:color-mix(in srgb,var(--bg) 88%,transparent);
backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.top-in{max-width:1120px;margin:0 auto;padding:14px 24px;display:flex;align-items:center;
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
.hero{padding:64px 0 36px}
h1{font-size:46px;line-height:1.08;margin:0 0 18px;font-weight:760;letter-spacing:-1.8px}
h1 .mark{color:var(--accent)}
.tagline{color:var(--fg2);font-size:17px;line-height:1.65;max-width:640px;margin:0}
.stamp{color:var(--dim2);font-size:12.5px;margin-top:20px;font-family:var(--mono)}

/* ---------- tabs ---------- */
.tabs{display:flex;gap:4px;margin:34px 0 0;flex-wrap:wrap;
border-bottom:1px solid var(--line);padding-bottom:0}
.tab{appearance:none;border:1px solid transparent;border-bottom:none;background:transparent;
font:inherit;font-size:15px;font-weight:600;color:var(--dim);padding:11px 20px;
cursor:pointer;border-radius:10px 10px 0 0;position:relative;top:1px;
transition:color .15s,background .15s}
.tab:hover{color:var(--fg2)}
.tab[aria-selected="true"]{color:var(--fg);background:var(--panel);
border-color:var(--line);box-shadow:0 -2px 0 var(--accent) inset}
.tab .k{font-family:var(--mono);font-size:11px;color:var(--dim2);margin-left:7px;font-weight:400}

/* ---------- panels ---------- */
.panel{display:none;padding-top:26px}
.panel.on{display:block}
/* Entrance is a short, single-direction rise. Transform and opacity are the
   only animated properties, so the whole view stays off the layout path. */
.panel.on .podium,
.panel.on .cards,
.panel.on .fig,
.panel.on .tw,
.panel.on .note,
.panel.on .desc{animation:rise .34s cubic-bezier(.22,.61,.36,1) backwards}
.panel.on .desc{animation-delay:0s}
.panel.on .podium{animation-delay:.03s}
.panel.on .cards{animation-delay:.06s}
.panel.on .note{animation-delay:.08s}
.panel.on .fig{animation-delay:.10s}
.panel.on .tw{animation-delay:.13s}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
/* The frontier line draws itself in, and the points fade in behind it. Only
   stroke-dashoffset and opacity animate; the geometry is untouched, so this
   stays compositor-friendly. */
.panel.on .fline{stroke-dasharray:var(--len,2400);stroke-dashoffset:var(--len,2400);
animation:draw .75s cubic-bezier(.4,.1,.2,1) .12s forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.panel.on .fdot{animation:fade .4s ease backwards;animation-delay:.4s}
.panel.on .fl{animation:fade .5s ease backwards;animation-delay:.5s}
@keyframes fade{from{opacity:0}to{opacity:1}}
.panel .desc{color:var(--dim);font-size:14px;margin:0 0 4px}

/* ---------- cards ---------- */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(216px,1fr));gap:14px;
margin:20px 0 8px}

/* ---------- podium: each view's own top 3 ---------- */
.podium{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
padding:20px 22px 4px;box-shadow:var(--shadow);margin:22px 0 4px}
.phead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.podium h3{font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
color:var(--dim);margin:0}
.pview{font-size:11.5px;font-family:var(--mono);color:var(--dim2);
border:1px solid var(--line);border-radius:99px;padding:1px 9px}
.prow{display:flex;align-items:center;gap:14px;padding:12px 0;
border-top:1px solid var(--line)}
.prow:first-child{border-top:none}
.pmedal{flex:none;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;
justify-content:center;font-size:13px;font-weight:750;font-family:var(--mono);
background:var(--soft2);color:var(--dim)}
.prow.p1 .pmedal{background:#fdf3d8;color:var(--gold)}
.prow.p2 .pmedal{background:#f1f1f3;color:var(--silver)}
.prow.p3 .pmedal{background:#f9efe6;color:var(--bronze)}
[data-theme="dark"] .prow.p1 .pmedal{background:#2b2413;color:#e8c26a}
[data-theme="dark"] .prow.p2 .pmedal{background:#26262a;color:#b9b9c0}
[data-theme="dark"] .prow.p3 .pmedal{background:#2a2018;color:#d09a63}
.pbody{flex:1;min-width:0}
.pname{font-weight:660;font-size:15px;line-height:1.35;overflow-wrap:anywhere}
.pmeta{color:var(--dim);font-size:12.5px;margin-top:3px;font-family:var(--mono)}
.pval{flex:none;text-align:right;font-family:var(--mono);font-weight:700;font-size:17px;
letter-spacing:-.4px}
.pval small{display:block;font-size:11px;font-weight:500;color:var(--dim2);
letter-spacing:0;margin-top:2px}
/* The secondary leader sits on a tinted strip: it answers the other question
   without competing with the three ranked rows above it. */
.plead{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 -22px;
padding:11px 22px;background:var(--soft);border-top:1px solid var(--line);
border-radius:0 0 var(--radius) var(--radius);font-size:13px}
.plead-k{color:var(--dim);font-size:11.5px;letter-spacing:.04em;text-transform:uppercase;
font-weight:650}
.plead-n{font-weight:640;overflow-wrap:anywhere}
.plead-v{margin-left:auto;font-family:var(--mono);font-weight:700;font-size:14px}
.plead-v small{font-size:10.5px;font-weight:500;color:var(--dim2);margin-left:3px}

/* ---------- frontier: score vs price scatter ---------- */
.fig{margin:16px 0 8px;background:var(--panel);border:1px solid var(--line);
border-radius:var(--radius);padding:14px 16px 10px;box-shadow:var(--shadow)}
.fig svg{display:block;width:100%;height:auto}
.fg{stroke:var(--line);stroke-width:1;vector-effect:non-scaling-stroke}
.ft{fill:var(--dim2);font-size:11px;font-family:var(--mono)}
.fa{fill:var(--dim);font-size:12px;font-weight:600}
/* Labels carry a halo in the panel colour and are painted halo-first, so a
   label that lands on the frontier line or on a dot stays readable. This is
   more robust than chasing every collision, since the frontier is a staircase
   and some overlap is unavoidable at small widths. */
.fl{fill:var(--fg2);font-size:11px;font-family:var(--mono);
paint-order:stroke;stroke:var(--panel);stroke-width:3.2px;stroke-linejoin:round}
.fline{fill:none;stroke:var(--accent);stroke-width:2;stroke-linejoin:round;
stroke-linecap:round;opacity:.85;vector-effect:non-scaling-stroke}
/* Dots. Fill is either the vendor colour (set inline) or the neutral grey, so
   the frontier/top tiers are carried by opacity and ring instead — an inline
   fill would beat any stylesheet rule, and the two encodings must not fight.
   Order matters here: the vendor ring selector carries three attribute-level
   components, so the top-three gold ring has to match or exceed that
   specificity or it is silently overridden to the neutral colour. */
.fdot{fill:var(--dim2);opacity:.45}
.fdot.front{opacity:.95}
/* A vendor-coloured dot needs a ring in the panel colour, or the darker
   swatches merge into the frontier line they sit on. */
.fdot[data-vendor]:not([data-vendor=""]){stroke:var(--panel);stroke-width:1}
.fdot[data-vendor]:not([data-vendor=""]).front{stroke-width:1.8}
/* Top three: gold ring. Both selectors are needed — the bare one covers a
   model whose vendor has no swatch, the qualified one wins over the rule
   above. */
.fdot.top,
.fdot[data-vendor]:not([data-vendor=""]).top{opacity:1;stroke:var(--gold);stroke-width:1.8}
[data-theme="dark"] .fdot.top,
[data-theme="dark"] .fdot[data-vendor]:not([data-vendor=""]).top{stroke:#e8c26a}
.fdot:hover{opacity:1;stroke:var(--fg);stroke-width:1.6}
.flegend{display:flex;gap:18px;flex-wrap:wrap;padding:8px 2px 4px;
border-top:1px solid var(--line);margin-top:8px;font-size:12px;color:var(--dim)}
.flegend span{display:flex;align-items:center;gap:6px}
.fvendors{display:flex;gap:14px;flex-wrap:wrap;padding:0 2px 6px;
font-size:12px;color:var(--dim)}
.fvendors .vsw{display:flex;align-items:center;gap:6px}
.sw{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}
.sw.line{background:var(--accent);height:3px;border-radius:2px;width:14px}
.sw.top{background:var(--panel);border:2px solid var(--gold)}
.sw.other{background:var(--dim2);opacity:.55}
[data-theme="dark"] .sw.top{border-color:#e8c26a}

/* ---------- table controls: expand + sort ---------- */
.tctl{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0 -4px;
font-size:13px;color:var(--dim)}
.trows{display:flex;align-items:center;gap:7px}
.tsel{font:inherit;font-size:12.5px;padding:4px 8px;border-radius:8px;
border:1px solid var(--line);background:var(--panel);color:var(--fg2);cursor:pointer}
.tsel:focus{outline:none;border-color:var(--accent)}
.btn.tall{padding:5px 11px;font-size:12.5px;margin-left:auto}
th[data-sort]{cursor:pointer;user-select:none;white-space:nowrap}
th[data-sort]:hover{color:var(--fg)}
th[data-sort]::after{content:"";display:inline-block;width:0;height:0;margin-left:5px;
vertical-align:middle;border-left:3.5px solid transparent;
border-right:3.5px solid transparent;border-bottom:4px solid var(--line2);
opacity:0;transition:opacity .15s}
th[data-sort]:hover::after{opacity:.6}
th[data-sort][aria-sort="ascending"]::after{border-bottom-color:var(--accent);opacity:1}
th[data-sort][aria-sort="descending"]::after{border-bottom:none;
border-top:4px solid var(--accent);opacity:1}
/* Rows past the initial cap. Expressed as :not(.shown) rather than a bare
   .deep rule so that tr.hide still wins for a row that is both collapsed and
   filtered out — otherwise filtering could resurrect a hidden row. */
tr.deep:not(.shown){display:none}
@media(max-width:820px){.podium{padding:18px 18px 4px}
.plead{margin:0 -18px;padding:10px 18px}
.fig{padding:12px 10px 8px}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
padding:18px 20px 20px;box-shadow:var(--shadow);display:flex;flex-direction:column;
min-height:124px}
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

/* ---------- tables ---------- */
.tw{margin-top:6px}
/* Methodology and benchmark tables carry long unbreakable metric names, so
   they are always wider than a narrow page and need their own scroll container. */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
/* The ranking table is the exception. An overflow-x container is also a scroll
   container, which silently disables position:sticky on its header — so on any
   screen wide enough for the columns to fit, it must not have one. Below 860px
   the columns genuinely do not fit, and scrolling is the lesser evil. */
.panel .tw{overflow-x:visible}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);
white-space:nowrap}
/* The header pins just below the sticky page bar. ``top:0`` would tuck it
   underneath that bar, where its lower z-index loses to the page header.
   ``--topbar`` is set per breakpoint because the bar wraps to two rows on
   narrow screens. */
th{font-size:11.5px;color:var(--dim);font-weight:650;text-transform:uppercase;
letter-spacing:.05em;position:sticky;top:var(--topbar,67px);background:var(--bg);z-index:1}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono);
font-size:13px}
tbody tr{transition:background .12s ease}
tbody tr:hover{background:var(--soft)}
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
h2{font-size:23px;margin:72px 0 8px;font-weight:720;letter-spacing:-.5px;
display:flex;align-items:center;gap:10px}
h2::before{content:"";width:3px;height:20px;background:var(--accent);border-radius:2px;flex:none}
h3{font-size:15px;margin:0 0 4px;font-weight:650}
.lede{color:var(--dim);font-size:14.5px;line-height:1.7;margin:0 0 18px;max-width:760px}
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
.panel.on .podium,.panel.on .cards,.panel.on .fig,.panel.on .tw,.panel.on .note,
.panel.on .desc{animation:none}
/* The frontier must land fully drawn rather than mid-stroke: the draw-in is
   decorative, but an incomplete line would misstate the data. */
.panel.on .fline{animation:none;stroke-dasharray:none;stroke-dashoffset:0}
.panel.on .fdot,.panel.on .fl{animation:none}
}
/* The ranking table's seven columns stop fitting around 860px. Below that the
   panel table scrolls sideways like the others — which costs the sticky header
   on phones, but a table that overflows the viewport is worse. */
@media(max-width:860px){
.panel .tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
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
/* The bar wraps here, so sticky headers must pin lower. */
:root{--topbar:106px}
/* Below this width the ranking table genuinely overflows, so it scrolls
   sideways. Doing this unconditionally would be worse than useless: an
   overflow-x container is also a scroll container, and that silently disables
   position:sticky on the header inside it on every screen size. */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
.cards{grid-template-columns:1fr 1fr;gap:10px}
.card{padding:13px 14px 15px;min-height:104px}
.card .v{font-size:21px}
.card .v.sm{font-size:14px}
th,td{padding:9px 8px}
.bar{width:34px;margin-right:6px}
.podium{padding:16px 16px 2px}
.plead{margin:0 -16px;padding:10px 16px}
.fig{padding:10px 8px 6px}
/* The scatter is a fixed viewBox, so at phone width its 11px labels would
   scale down to ~4px and be unreadable. Below this breakpoint the figure pans
   horizontally instead, keeping the labels legible rather than discarding them. */
.fig{overflow-x:auto;-webkit-overflow-scrolling:touch}
.fig svg{min-width:660px}
}
@media(max-width:430px){
.cards{grid-template-columns:1fr}
/* Family is the first thing to go: it is the least informative column when
   the model name usually implies it. Eff. and Cov. keep their space. */
.fam,.th.family,td.fam{display:none}
h1{font-size:24px}
.tab{padding:9px 12px;font-size:13.5px}
.tab .k{display:none}
.pval{font-size:15px}
.plead{font-size:12.5px}
.tctl{gap:8px}
.btn.tall{margin-left:0}
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
    // Exclusion notes carry an interpolated count. Each cause gets its own
    // sentence, so the wording always matches why the model is missing.
    document.querySelectorAll('[data-floor-n]').forEach(function(el){
      var n = el.getAttribute('data-floor-n');
      var pct = el.getAttribute('data-floor-pct');
      el.textContent = t(lang,'panel.floor').replace('{n}',n).replace('{pct}',pct);
    });
    document.querySelectorAll('[data-noprice-n]').forEach(function(el){
      el.textContent = t(lang,'panel.noprice')
        .replace('{n}', el.getAttribute('data-noprice-n'));
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

  /* ---------- full ranking: expand ---------- */
  // Two separate ideas, deliberately kept apart:
  //   data-cap  - how many rows the *user* asked to see (their choice, sticky)
  //   applyRows - what is visible right now (may be temporarily overridden)
  // A search overrides visibility so it can reach rows below the fold, then the
  // cap is restored when the query clears. Conflating the two would either
  // reset the user's choice on every keystroke, or leave a filtered view stuck
  // expanded. The cap is applied positionally over the table's rows, not by
  // trusting the class the server emitted, because sorting reorders the rows:
  // "top N" must mean the top N *after* a sort.
  function applyRows(wrap, visible){
    var rows = wrap.querySelectorAll('tbody tr');
    var total = rows.length;
    var lim = Math.min(visible, total);
    rows.forEach(function(tr, i){
      var over = i >= lim;
      tr.classList.toggle('deep', over);
      tr.classList.toggle('shown', !over);
    });
    var btn = wrap.querySelector('[data-more]');
    if (btn){
      btn.hidden = lim >= total;
      var lbl = btn.querySelector('[data-tpl]');
      if (lbl) lbl.setAttribute('data-v-n', String(total - lim));
    }
    var sel = wrap.querySelector('.tsel');
    if (sel){
      var want = String(lim >= total ? 0 : lim);
      if (sel.value !== want) sel.value = want;
    }
    if (current.lang) applyLang(current.lang);
  }
  function capOf(wrap){
    return parseInt(wrap.getAttribute('data-cap') || '0', 10) ||
           wrap.querySelectorAll('tbody tr').length;
  }
  // Declared here, before the sort handler that reads it. `var box` is
  // assigned further down, but a function declaration is hoisted, so
  // searchActive() is safe to call from any handler defined below.
  function searchActive(){ return !!(box && box.value.trim()); }
  document.querySelectorAll('.tw[data-total]').forEach(function(wrap){
    wrap.setAttribute('data-cap',
      String(wrap.querySelectorAll('tbody tr:not(.deep)').length));
    var sel = wrap.querySelector('.tsel');
    if (sel) sel.addEventListener('change', function(){
      var n = parseInt(sel.value, 10) || 0;
      var rows = wrap.querySelectorAll('tbody tr').length;
      wrap.setAttribute('data-cap', String(n === 0 ? rows : n));
      applyRows(wrap, capOf(wrap));
    });
    var btn = wrap.querySelector('[data-more]');
    if (btn) btn.addEventListener('click', function(){
      wrap.setAttribute('data-cap',
        String(wrap.querySelectorAll('tbody tr').length));
      applyRows(wrap, capOf(wrap));
    });
  });

  /* ---------- full ranking: sort ---------- */
  // Sorting reads pre-rendered data-k-* attributes rather than cell text, so it
  // never has to parse "$1.20" or an em dash, and missing values sort last in
  // both directions instead of being treated as zero.
  var TEXT_COLS = { model: 1, family: 1 };
  function sortTable(th){
    var table = th.closest('table');
    var key = th.getAttribute('data-sort');
    var numeric = !TEXT_COLS[key];
    var prev = th.getAttribute('aria-sort');
    // Text sorts A-Z first; numbers sort best-first, which is what a reader
    // expects from a score or price column. Clicking the active column flips it.
    var dir;
    if (prev) dir = (prev === 'ascending') ? 'descending' : 'ascending';
    else dir = numeric ? 'descending' : 'ascending';

    table.querySelectorAll('th[data-sort]').forEach(function(x){
      x.removeAttribute('aria-sort');
    });
    th.setAttribute('aria-sort', dir);

    var tbody = table.querySelector('tbody');
    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    var attr = 'data-k-' + key;
    rows.sort(function(a, b){
      var av = a.getAttribute(attr) || '';
      var bv = b.getAttribute(attr) || '';
      if (numeric){
        var an = av === '', bn = bv === '';
        if (an && bn) return 0;
        if (an) return 1;                 // missing always sorts last
        if (bn) return -1;
        var d = parseFloat(av) - parseFloat(bv);
        return (dir === 'ascending') ? d : -d;
      }
      var c = av < bv ? -1 : (av > bv ? 1 : 0);
      return (dir === 'ascending') ? c : -c;
    });
    rows.forEach(function(tr){ tbody.appendChild(tr); });

    // Re-number: the rank column must show the visible order, not the order the
    // rows happened to be rendered in.
    rows.forEach(function(tr, i){
      var cell = tr.querySelector('td.rk');
      if (cell){
        cell.textContent = String(i + 1);
        cell.classList.toggle('top', i < 3);
      }
    });
    var wrap = table.closest('.tw');
    if (wrap) applyRows(wrap, searchActive() ? wrap.querySelectorAll('tbody tr').length
                                             : capOf(wrap));
  }
  document.querySelectorAll('th[data-sort]').forEach(function(th){
    th.setAttribute('tabindex', '0');
    th.addEventListener('click', function(){ sortTable(th); });
    th.addEventListener('keydown', function(e){
      if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); sortTable(th); }
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
    // A match below the fold would otherwise be invisible and the count would
    // read 0, so while a query is active every row is eligible and only the
    // filter decides visibility. Clearing the query restores the row cap.
    document.querySelectorAll('.tw[data-total]').forEach(function(w){
      applyRows(w, q ? w.querySelectorAll('tbody tr').length : capOf(w));
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
    rows.forEach(function(r){
      // "Shown" means actually visible: not filtered out, and not still
      // collapsed behind the row cap.
      if (r.classList.contains('hide')) return;
      if (r.classList.contains('deep') && !r.classList.contains('shown')) return;
      shown++;
    });
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


def _frontier(models: list[dict], preset: Preset, top: int = 3) -> str:
    """Score-versus-price scatter with the efficient frontier line.

    This is the view Artificial Analysis leads with, and it answers a question
    the tables cannot: *where* a model sits relative to what its price buys.
    A ranked list tells you the order; this tells you the shape of the trade-off
    and which models are actually dominated.

    The frontier is the usual Pareto staircase in log-price: walking from
    cheapest to dearest, keep a model only when it beats the best score seen so
    far. Everything else is dominated — something is either cheaper with the
    same score, or better for the same money. Points on the line are the only
    ones where spending more strictly buys more.

    Dots are coloured by vendor, but only for the vendors that actually reach
    the frontier or the top three in this view. Colouring all 33 creators would
    need a palette nobody can tell apart and a legend longer than the chart;
    colouring the handful that matter answers "who is competing at this price".
    Everything else is a plain grey dot, which is also the honest reading —
    it is not in contention.

    Rendered as inline SVG in a fixed viewBox so it scales responsively without
    JS layout, and stays crisp at any width. Prices are log-scaled because the
    usable range spans more than two orders of magnitude.
    """
    import math

    rows = []
    for m in models:
        score = m["scores"].get(preset.key)
        price = m["pricing"].get("blended")
        if score is None or not price or price <= 0:
            continue
        if not _eligible(m, preset):
            continue
        rows.append((price, score, m))
    if not rows:
        return (f'<p class="lede" data-i18n="frontier.nopriced">'
                f'{esc(strings_for(DEFAULT_LANG)["frontier.nopriced"])}</p>')

    rows.sort(key=lambda r: r[0])
    prices = [r[0] for r in rows]
    scores = [r[1] for r in rows]

    # Pareto frontier: best score available at or below each price.
    frontier, best = [], -1e9
    for price, score, m in rows:
        if score > best:
            best = score
            frontier.append((price, score, m))
    frontier_keys = {id(m) for _, _, m in frontier}

    # Viewport. Width matches the page measure; height keeps roughly 3:2.
    W, H, PL, PR, PT, PB = 1000.0, 380.0, 52.0, 16.0, 18.0, 40.0
    lp = [math.log10(p) for p in prices]
    pmin, pmax = min(lp), max(lp)
    if pmax - pmin < 0.25:            # keep a single-price board from collapsing
        mid = (pmax + pmin) / 2
        pmin, pmax = mid - 0.125, mid + 0.125
    smin = min(scores)
    smax = max(scores)
    pad = (smax - smin) * 0.08 or 1.0
    smin, smax = max(0.0, smin - pad), smax + pad

    def x(price: float) -> float:
        return PL + (math.log10(price) - pmin) / (pmax - pmin) * (W - PL - PR)

    def y(score: float) -> float:
        return PT + (smax - score) / (smax - smin) * (H - PT - PB)

    # Log-decade gridlines, labelled with the price they represent.
    ticks = []
    lo, hi = math.floor(pmin), math.ceil(pmax)
    for d in range(lo, hi + 1):
        for mult in (1, 2, 5):
            v = mult * (10 ** d)
            if pmin <= math.log10(v) <= pmax:
                ticks.append(v)
    grid = "".join(
        f'<line x1="{x(v):.1f}" y1="{PT:.0f}" x2="{x(v):.1f}" y2="{H-PB:.0f}" '
        f'class="fg"/>'
        f'<text x="{x(v):.1f}" y="{H-PB+16:.0f}" class="ft" text-anchor="middle">'
        f'{fmt_price(v)}</text>'
        for v in ticks
    )
    # Y gridlines. The label precision adapts to the range: with a narrow
    # spread, fixed integers all render as the same number ("50 50 50 50"),
    # which is worse than no axis at all. Pick the decimals needed to tell the
    # ticks apart.
    span = smax - smin
    if span >= 8:
        decimals = 0
    elif span >= 0.8:
        decimals = 1
    else:
        decimals = 2
    yticks = []
    steps = 4
    for i in range(steps + 1):
        v = smin + span * i / steps
        yticks.append(
            f'<line x1="{PL:.0f}" y1="{y(v):.1f}" x2="{W-PR:.0f}" y2="{y(v):.1f}" '
            f'class="fg"/>'
            f'<text x="{PL-8:.0f}" y="{y(v)+3.5:.1f}" class="ft" '
            f'text-anchor="end">{v:.{decimals}f}</text>'
        )
    grid += "".join(yticks)

    # The frontier staircase: horizontal runs to each step, then the step up.
    # Segment lengths are accumulated so the draw-in animation can set an exact
    # stroke-dashoffset; a guessed constant would leave a visible gap or an
    # over-long dash on a board with many steps.
    path = []
    path_len = 0.0
    prev_y = None
    prev_x = None
    for i, (price, score, _m) in enumerate(frontier):
        px, py = x(price), y(score)
        if i == 0:
            path.append(f"M{px:.1f},{py:.1f}")
        else:
            path.append(f"L{px:.1f},{prev_y:.1f}")
            path.append(f"L{px:.1f},{py:.1f}")
            path_len += abs(px - prev_x) + abs(py - prev_y)
        prev_y, prev_x = py, px
    frontier_path = " ".join(path)
    path_len = path_len or 1.0

    top_names = {m["name"] for m in _ranked_for(models, preset)[:top]} if top else set()

    # Vendors worth a colour: those on the frontier, plus the top three. Sorted
    # so a given vendor always gets the same swatch across views and rebuilds
    # rather than depending on iteration order.
    notable = sorted(
        {m["creator"] for _, _, m in frontier if m.get("creator")}
        | {m["creator"] for _, _, m in rows
           if m["name"] in top_names and m.get("creator")}
    )
    palette = {}
    for i, vendor in enumerate(notable):
        palette[vendor] = VENDOR_COLORS[i % len(VENDOR_COLORS)]

    dots = []
    for price, score, m in rows:
        is_f = id(m) in frontier_keys
        is_top = m["name"] in top_names
        r = 5.0 if is_top else (3.6 if is_f else 2.6)
        vendor = m.get("creator") or ""
        colour = palette.get(vendor)
        # Notable vendors get a ring so they read against the grey mass; the
        # frontier and top-three tiers are conveyed by radius.
        style = f' style="fill:{colour}"' if colour else ""
        cls = "fdot top" if is_top else ("fdot front" if is_f else "fdot")
        dots.append(
            f'<circle cx="{x(price):.1f}" cy="{y(score):.1f}" r="{r}" class="{cls}"'
            f'{style} data-vendor="{esc(vendor)}">'
            f'<title>{esc(m["name"])} — {score:.1f} @ {fmt_price(price)}/1M</title>'
            f"</circle>"
        )

    # Only the frontier and the top three get labels; labelling everything is
    # noise. Points near the right edge are anchored to the left of the marker so
    # the text stays inside the viewBox.
    #
    # The frontier is a staircase, so consecutive steps routinely sit at almost
    # the same x (Qwen 3.5 -> Gemma 4 -> Nemotron, for instance) and their
    # labels would overprint into an unreadable smear. Greedy vertical nudging
    # fixes it: each label is pushed down until it clears every label already
    # placed in an overlapping column band. That is O(n^2) on a few dozen
    # labels, entirely at render time, and needs no runtime layout.
    CHAR_W = 6.4          # ~11px monospace, plus a little slack
    LINE_H = 12.5
    PAD = 3.0
    placed: list[tuple[float, float, float, float]] = []   # x0,y0,x1,y1
    labels = []
    cands = [r for r in rows
             if id(r[2]) in frontier_keys or r[2]["name"] in top_names]
    # The labelled markers are obstacles in their own right: a label must not
    # print over the dot it belongs to, nor over a neighbouring one.
    for price, score, m in cands:
        cx, cy = x(price), y(score)
        r = 6.0
        placed.append((cx - r, cy - r, cx + r, cy + r))
    # Right-most first, so the tightest cluster gets first choice of position.
    cands.sort(key=lambda r: -x(r[0]))
    for price, score, m in cands:
        text = _short_name(m["name"])
        anchor = "end" if x(price) > W * 0.72 else "start"
        dx = -10 if anchor == "end" else 10
        tx = x(price) + dx
        ty = y(score) - 9
        w = len(text) * CHAR_W + PAD
        x0, x1 = (tx - w, tx) if anchor == "end" else (tx, tx + w)
        for _ in range(40):
            hit = None
            for (px0, py0, px1, py1) in placed:
                if x0 < px1 and px0 < x1 and ty - LINE_H * 0.8 < py1 and py0 < ty + LINE_H * 0.8:
                    hit = py1
                    break
            if hit is None:
                break
            ty = hit + LINE_H * 0.8
        ty = min(ty, H - PB - 4)
        placed.append((x0, ty - LINE_H * 0.8, x1, ty + LINE_H * 0.8))
        labels.append(
            f'<text x="{tx:.1f}" y="{ty:.1f}" class="fl" '
            f'text-anchor="{anchor}">{esc(text)}</text>'
        )

    s = strings_for(DEFAULT_LANG)
    # Vendor swatches, most-represented first among the notable set, so the
    # legend reads in order of how much of the chart each colour accounts for.
    counts = {}
    for price, score, m in rows:
        v = m.get("creator") or ""
        if v in palette:
            counts[v] = counts.get(v, 0) + 1
    vendor_legend = "".join(
        f'<span class="vsw"><i class="sw" style="background:{palette[v]}"></i>'
        f"{esc(v)}</span>"
        for v, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    vendor_row = (f'<div class="fvendors">{vendor_legend}</div>'
                  if vendor_legend else "")
    return (
        f'<figure class="fig">'
        f'<svg viewBox="0 0 {W:.0f} {H:.0f}" role="img" '
        f'aria-label="{esc(s["frontier.title"])}" preserveAspectRatio="xMidYMid meet">'
        f"{grid}"
        f'<path d="{frontier_path}" class="fline" style="--len:{path_len:.0f}"/>'
        f'{"".join(dots)}{"".join(labels)}'
        f'<text x="{(PL+W-PR)/2:.0f}" y="{H-6:.0f}" class="fa" text-anchor="middle" '
        f'data-i18n="frontier.axis.price">{esc(s["frontier.axis.price"])}</text>'
        f'<text x="14" y="{(PT+H-PB)/2:.0f}" class="fa" text-anchor="middle" '
        f'transform="rotate(-90 14 {(PT+H-PB)/2:.0f})" '
        f'data-i18n="frontier.axis.score">{esc(s["frontier.axis.score"])}</text>'
        f"</svg>"
        f'<div class="flegend">'
        f'<span><i class="sw line"></i><span data-i18n="frontier.legend.frontier">'
        f'{esc(s["frontier.legend.frontier"])}</span></span>'
        f'<span><i class="sw top"></i><span data-i18n="frontier.legend.top">'
        f'{esc(s["frontier.legend.top"])}</span></span>'
        f'<span><i class="sw other"></i><span data-i18n="frontier.legend.other">'
        f'{esc(s["frontier.legend.other"])}</span></span>'
        f"</div>"
        f"{vendor_row}</figure>"
    )


def _short_name(name: str, limit: int = 22) -> str:
    """Trim a model name for an axis label.

    Names carry a parenthesised serving variant (e.g. "(Max, Default
    Fallback)") which is irrelevant once the model is identified.
    """
    base = name.split(" (")[0]
    return base if len(base) <= limit else base[: limit - 1] + "…"


def _median(values: list[float]) -> float:
    """Median of a non-empty list."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


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


def _row(rank: int, m: dict, preset: Preset, max_score: float,
         deep: bool = False) -> str:
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

    # Sort keys let the client reorder without re-parsing the rendered cells.
    # Missing values sort last in both directions rather than as zero, which
    # would otherwise rank "no published price" as if it were free.
    def sk(v):
        return "" if v is None else f"{v:.6f}"

    # Collapsed rows carry a class rather than the [hidden] attribute: the
    # attribute cannot be undone by toggling a class, and the JS cap re-assigns
    # this class positionally after every sort.
    deep_attr = ' class="deep"' if deep else ""
    return (
        f'<tr data-name="{hay}"{deep_attr}'
        f' data-k-model="{esc(m["name"].lower())}"'
        f' data-k-family="{esc(m["family"].lower())}"'
        f' data-k-score="{sk(score)}"'
        f' data-k-price="{sk(price)}"'
        f' data-k-eff="{sk(eff)}"'
        f' data-k-cov="{sk(cov)}">'
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
    """Full ranking with progressive disclosure and client-side sorting.

    Every row is in the DOM, so sorting and filtering need no round trip and
    the page keeps working offline. ``limit`` decides how many rows are *shown*
    initially; the rest are revealed in place. Rendering all rows rather than
    paging keeps search honest — a filter must be able to find a model that is
    not on the first screen — while the collapsed default keeps the page short.
    """
    total = len(models)
    if not total:
        return '<p class="lede" data-i18n="panel.empty">No models matched this view.</p>'
    max_score = max((m["scores"].get(preset.key) or 0) for m in models) or 1
    # Rows past the initial cap are marked so the client can reveal them without
    # moving any data around. Only the first screen's worth is built for the
    # browser's first paint; the rest is in the same string and costs nothing
    # extra to store.
    # ``limit`` of 0 or None means "no cap": show every row outright. Both must
    # disable the collapsing, or a 0 would mark all rows collapsed while the
    # control that reveals them is suppressed — an empty table.
    cap = limit if limit else None
    body = "".join(
        _row(i, m, preset, max_score, deep=(cap is not None and i > cap))
        for i, m in enumerate(models, 1)
    )
    sort_key = "panel.sorted.eff" if preset.rank_by == "efficiency" else "panel.sorted.score"

    hidden = max(0, total - cap) if cap else 0
    if hidden:
        # Offer only caps smaller than the board, de-duplicated against the
        # default, so no option is a no-op.
        caps = sorted({c for c in (25, 50, 100, 200) if c < total} | {cap})
        opts = "".join(
            f'<option value="{c}"{" selected" if c == limit else ""}>{c}</option>'
            for c in caps
        )
        # The "All" option carries an i18n hook; the numeric caps do not need
        # one. aria-label is set to the same string so the control is not
        # announced as an unlabelled combobox.
        all_label = esc(strings_for(DEFAULT_LANG)["table.all"])
        opts += (f'<option value="0" data-i18n="table.all">{all_label}</option>')
        ctl = (
            f'<div class="tctl">'
            f'<label class="trows">'
            f'<span data-i18n="table.rows">Rows</span>'
            f'<select class="tsel" data-i18n-title="table.rows" '
            f'title="{esc(strings_for(DEFAULT_LANG)["table.rows"])}">{opts}</select>'
            f'</label>'
            f'<button type="button" class="btn tall" data-more>'
            f'<span data-tpl="table.showall" data-v-n="{hidden}">Show all {hidden}</span>'
            f"</button></div>"
        )
    else:
        ctl = ""

    all_attr = "" if hidden else " data-all"
    return (
        f'<div class="tw" data-total="{total}"{all_attr}>'
        f"{ctl}"
        '<table class="rank"><thead><tr>'
        '<th class="rk">#</th>'
        '<th data-i18n="th.model" data-sort="model">Model</th>'
        '<th data-i18n="th.family" data-sort="family">Family</th>'
        '<th class="num" data-i18n="th.score" data-sort="score">Score</th>'
        '<th class="num" data-i18n="th.price" data-sort="price">$/1M</th>'
        '<th class="num" data-i18n="th.eff" data-sort="eff">Eff.</th>'
        '<th class="num" data-i18n="th.cov" data-sort="cov">Cov.</th>'
        f'</tr></thead><tbody>{body}</tbody></table></div>'
        f'<p class="lede"><span data-i18n="{sort_key}">Sorted.</span> '
        f'<span data-i18n="panel.cov_note">Cov. is coverage.</span> '
        f'<span data-i18n="table.hint">Click a column heading to sort.</span></p>'
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


def _podium_rows(rows: list[dict], preset: Preset, mode: str) -> str:
    """Render up to three ranked rows for one podium column.

    ``mode`` is "ability" (show the score) or "value" (show points per dollar).
    The headline figure differs, but the layout is shared so the two columns
    read as a pair rather than two unrelated widgets.
    """
    if not rows:
        return '<div class="prow"><div class="pbody"><div class="pname">' \
               '<span class="mdash">&mdash;</span></div></div></div>'
    out = []
    for i, m in enumerate(rows[:3], 1):
        if mode == "value":
            num = f'{m["efficiency"][preset.key]:.0f}'
            unit = f'<small data-i18n="podium.per_dollar">/$</small>'
        else:
            num = f'{m["scores"][preset.key]:.1f}'
            price = m["pricing"].get("blended")
            unit = f'<small>{fmt_price(price)}/1M</small>' if price else \
                   '<small data-i18n="card.noprice">no published price</small>'
        badges = ""
        if m.get("available_locally"):
            badges = '<span class="pill local" data-i18n="row.local">local</span>'
        out.append(
            f'<div class="prow p{i}">'
            f'<div class="pmedal">{i}</div>'
            f'<div class="pbody">'
            f'<div class="pname">{esc(m["name"])}{badges}</div>'
            f'<div class="pmeta">{esc(m["family"])} &middot; '
            f'cov {m["coverage"][preset.key]:.2f}</div>'
            f"</div>"
            f'<div class="pval">{num}{unit}</div>'
            "</div>"
        )
    return "".join(out)


def _ranked_for(models: list[dict], preset: Preset) -> list[dict]:
    """Rankable models for a view, best first under that view's own criterion.

    The frontier gate is applied first, so "best value" means best value among
    models worth using rather than the best ratio in the whole catalogue.
    """
    gated, _, _ = _frontier_gate(models, preset)
    rows = [m for m in gated if _eligible(m, preset)]
    if preset.rank_by == "efficiency":
        rows.sort(key=lambda m: -(m["efficiency"].get(preset.key) or 0))
    else:
        rows.sort(key=lambda m: -(m["scores"].get(preset.key) or 0))
    return rows


def _podium(models: list[dict], preset: Preset, value_floor: float = 0.0) -> str:
    """One view's leaders, rendered inside that view's panel.

    The previous design hoisted a single capability+value podium above the tab
    strip. Because the tab strip only toggles panels, that podium never changed:
    every view showed the same six names, and for views whose top rows differ
    (coding, long context) it silently disagreed with the table directly below
    it. Rendering the podium per panel is what makes it describe the view you
    are actually looking at.

    Each view leads with its own ranking criterion, then names the leader on the
    other axis. That keeps both "what is strongest" and "what is best value"
    answerable for every view without printing two near-identical top-threes.
    """
    ranked = _ranked_for(models, preset)
    if not ranked:
        return ""

    primary_is_value = preset.rank_by == "efficiency"
    # ``ranked`` is already ordered by this view's own criterion.
    primary = ranked

    # The opposite axis, held to the value floor so a cheap small model does not
    # appear here as "best value" while the value board excludes it.
    other_metric = "scores" if primary_is_value else "efficiency"
    best_score = ranked[0]["scores"].get(preset.key) or 0
    floor = best_score * value_floor if value_floor else None
    other = sorted(
        (m for m in ranked
         if m[other_metric].get(preset.key) is not None
         and (floor is None or (m["scores"].get(preset.key) or 0) >= floor)),
        key=lambda m: -(m[other_metric].get(preset.key) or 0),
    )

    head_key = "podium.by.value" if primary_is_value else "podium.by.score"
    lead_key = ("podium.leader.score" if primary_is_value
                else "podium.leader.value")
    mode = "value" if primary_is_value else "ability"
    lead_mode = "ability" if primary_is_value else "value"

    label_attr = (f' data-i18n="preset.{esc(preset.key)}.label"'
                  if preset.key in BUILTIN_KEYS else "")

    lead = ""
    if other:
        top = other[0]
        if lead_mode == "value":
            num = f'{top["efficiency"][preset.key]:.0f}'
            unit = '<small data-i18n="podium.per_dollar">/$</small>'
        else:
            price = top["pricing"].get("blended")
            num = f'{top["scores"][preset.key]:.1f}'
            unit = f'<small>{fmt_price(price)}/1M</small>' if price else \
                '<small data-i18n="card.noprice">no published price</small>'
        lead = (
            f'<div class="plead">'
            f'<span class="plead-k" data-i18n="{lead_key}">{lead_key}</span>'
            f'<span class="plead-n">{esc(top["name"])}</span>'
            f'<span class="plead-v">{num}{unit}</span></div>'
        )

    return (
        f'<div class="podium" data-podium="{esc(preset.key)}">'
        f'<div class="phead">'
        f'<h3 data-i18n="{head_key}">{head_key}</h3>'
        f'<span class="pview"{label_attr}>{esc(preset.label)}</span></div>'
        f'<div class="prows">{_podium_rows(primary, preset, mode)}</div>'
        f"{lead}</div>"
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

    # Exclusions are split by actual cause. ``_eligible`` fails for two quite
    # different reasons — too little benchmark coverage, or (on an efficiency
    # view) no published price — and reporting either one under the other's
    # heading would put a false claim on the page. The coverage note used to
    # say "fall below the 50% coverage floor" about models whose coverage was
    # 1.00, which is exactly the kind of thing a leaderboard cannot afford.
    below_coverage = [
        m for m in gated
        if m["scores"].get(preset.key) is not None
        and not _eligible(m, preset)
        and m["coverage"].get(preset.key, 0.0) < preset.min_coverage
    ]
    no_price = [
        m for m in gated
        if m["scores"].get(preset.key) is not None
        and not _eligible(m, preset)
        and m["coverage"].get(preset.key, 0.0) >= preset.min_coverage
        and m["efficiency"].get(preset.key) is None
    ]
    excluded = below_coverage + no_price

    best = ranked[0] if ranked else None
    priced_count = sum(1 for m in ranked if m["pricing"].get("blended"))

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

    # The podium inside this panel already names the leaders, so these cards
    # carry the counts and the ranking caveats instead of repeating the winners.
    # On an efficiency board every ranked model has a price by definition, so a
    # "models with a published price" card would print the same number as the
    # ranked count right beside it. Show the count of models that qualified but
    # have no price instead — that is the number actually being hidden here.
    if preset.rank_by == "efficiency":
        unpriced = sum(1 for m in gated
                       if m["scores"].get(preset.key) is not None
                       and m["efficiency"].get(preset.key) is None)
        priced_card = (
            "card.unpriced",
            f'{unpriced}',
            '<span data-i18n="card.unpriced.note">excluded: no published price</span>',
            False,
        )
    else:
        priced_card = (
            "card.priced",
            f'{priced_count}',
            '<span data-i18n="card.priced.note">models with a published price</span>',
            False,
        )

    cards = [
        (
            "card.ranked",
            str(len(ranked)),
            f'<span data-tpl="card.ranked.note" data-v-pct="{preset.min_coverage:.0%}">'
            f'coverage ≥ {preset.min_coverage:.0%}</span>',
            True,
        ),
        (
            "card.median",
            (f'{_median([m["scores"][preset.key] for m in ranked]):.1f}'
             if ranked else "&mdash;"),
            '<span data-i18n="card.median.note">median score in this view</span>',
            False,
        ),
        priced_card,
    ]
    cards_html = "".join(_card(*c) for c in cards)

    # One note per actual reason, each carrying its own count so the translated
    # sentence can interpolate the right number.
    notes = []
    if below_coverage:
        notes.append(
            f'<div class="note warn" data-floor-n="{len(below_coverage)}" '
            f'data-floor-pct="{preset.min_coverage:.0%}"></div>'
        )
    if no_price:
        notes.append(
            f'<div class="note warn" data-noprice-n="{len(no_price)}"></div>'
        )
    floor_note = "".join(notes)

    return (
        f'<section class="panel{" on" if first else ""}" data-key="{esc(preset.key)}" '
        f'role="tabpanel" id="panel-{esc(preset.key)}" '
        f'aria-labelledby="tab-{esc(preset.key)}">'
        f'<p class="desc"{_desc_attr(preset)}>{esc(preset.description)}</p>'
        f"{_podium(models, preset, value_floor=value_floor)}"
        f'<div class="cards">{cards_html}</div>'
        f"{floor_note}"
        f'<h2 data-i18n="frontier.title">Score vs price</h2>'
        f'<p class="lede" data-i18n="frontier.desc"></p>'
        f"{_frontier(models, preset)}"
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

    ``limit`` is how many rows each panel *initially shows*, not how many it
    contains. Every row is rendered so search and sort work over the whole set;
    the excess ships collapsed and is revealed client-side. 290 models x 4 views
    is roughly 7,000 rows in one file, which compresses to a reasonable size and
    keeps the page a single offline-capable document.
    """
    meta = meta or {}
    generated = generated or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    s = strings_for(DEFAULT_LANG)

    keys = list(presets.keys())

    def _norm_label(v: str) -> str:
        return re.sub(r"[^a-z0-9]", "", v.lower())

    def _tab(key: str) -> str:
        preset = presets[key]
        # Show the raw key only when it adds information over the label. Compare
        # on letters and digits alone, so "Long context" does not print a
        # redundant "longcontext" suffix.
        suffix = (f'<span class="k">{esc(key)}</span>'
                  if _norm_label(key) != _norm_label(preset.label) else "")
        label_attr = (f' data-i18n="preset.{esc(key)}.label"'
                      if key in BUILTIN_KEYS else "")
        # id/aria-controls wire the tab to its panel, which is what lets a
        # screen reader announce the panel the tab governs instead of reading
        # two unrelated widgets.
        return (f'<button class="tab" data-key="{esc(key)}" role="tab" '
                f'id="tab-{esc(key)}" aria-controls="panel-{esc(key)}" '
                f'aria-selected="false"><span{label_attr}>{esc(preset.label)}</span>'
                f'{suffix}</button>')

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
