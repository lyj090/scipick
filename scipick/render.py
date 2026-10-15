"""Render: a single self-contained HTML file.

No external assets, no build step, no JavaScript framework. The preset tabs are
plain DOM toggling, which is what lets the same file work as a static GitHub
Pages site.

The whole board is emitted once and switched client-side. That keeps every preset
in the same document, so switching is instant and the page works offline.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from .config import METRIC_LABELS, Preset

CSS = """
:root{
--bg:#fff;--page:#f8f8f6;--panel:#fff;--soft:#f4f4f2;--line:#e7e7e4;--line2:#d9d9d5;
--fg:#191917;--fg2:#3d3d3a;--dim:#75756f;--dim2:#9b9b94;
--accent:#1a6ef5;--accent2:#6b2d84;--green:#2e7d4f;--orange:#e07b1f;--red:#d33b2c;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
--mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--fg);font:14px/1.55 var(--sans);
-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:38px 26px 100px}
header{margin-bottom:8px}
h1{font-size:30px;line-height:1.2;margin:0 0 10px;font-weight:700;letter-spacing:-.5px}
h2{font-size:20px;margin:46px 0 8px;font-weight:700;letter-spacing:-.2px}
.lede{color:var(--dim);font-size:14px;max-width:680px;margin:0 0 6px}
a{color:var(--accent)}
code{background:var(--soft);padding:2px 6px;border-radius:5px;font-size:12.5px;
font-family:var(--mono);color:var(--fg2)}

.tabs{display:flex;gap:6px;margin:24px 0 0;flex-wrap:wrap;border-bottom:1px solid var(--line);
padding-bottom:0}
.tab{appearance:none;border:1px solid transparent;border-bottom:none;background:transparent;
font:inherit;font-size:14px;font-weight:600;color:var(--dim);padding:9px 16px;cursor:pointer;
border-radius:8px 8px 0 0;position:relative;top:1px}
.tab:hover{color:var(--fg2)}
.tab[aria-selected="true"]{color:var(--fg);background:var(--panel);border-color:var(--line)}
.tab .k{font-family:var(--mono);font-size:11.5px;color:var(--dim2);margin-left:7px;font-weight:400}

.panel{display:none}
.panel.on{display:block}
.panel .desc{color:var(--dim);font-size:13.5px;margin:14px 0 0}

.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:13px;margin:22px 0 6px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px 17px 17px}
.card .k{font-size:12.5px;color:var(--dim);font-weight:600}
.card .v{font-size:25px;font-weight:700;margin-top:9px;letter-spacing:-.5px;
font-variant-numeric:tabular-nums}
.card .v.sm{font-size:15px;font-family:var(--mono);word-break:break-all}
.card .n{color:var(--dim);font-size:12px;margin-top:4px}

table{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:10px}
th,td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line)}
th{font-size:12px;color:var(--dim);font-weight:600;text-transform:uppercase;letter-spacing:.04em;
white-space:nowrap}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono);font-size:12.5px}
tbody tr:hover{background:var(--soft)}
.rk{color:var(--dim2);font-family:var(--mono);font-size:12px;width:34px}
.nm{font-weight:600}
.fam{color:var(--dim);font-size:12.5px}
.pill{display:inline-block;background:var(--soft);border-radius:20px;padding:2px 9px;
font-size:11.5px;color:var(--dim);margin-left:6px}
.local{background:#e8f2ec;color:var(--green)}
.mdash{color:var(--dim2)}

.bar{display:inline-block;width:56px;height:6px;background:var(--soft);border-radius:3px;
overflow:hidden;vertical-align:middle;margin-right:7px}
.bar i{display:block;height:100%;background:var(--accent)}
.plot{display:flex;align-items:flex-end;gap:5px;height:230px;margin-top:16px;
border-bottom:1px solid var(--line2);position:relative}
.col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;
height:100%;position:relative;min-width:0}
.col .bv{font-size:10.5px;font-family:var(--mono);color:var(--dim);margin-bottom:3px}
.col .bx{width:100%;border-radius:3px 3px 0 0;background:var(--accent)}
.xlab{display:flex;gap:5px;margin-top:7px}
.xlab .c{flex:1;min-width:0}
.xlab span{display:block;font-size:10.5px;color:var(--dim);writing-mode:vertical-rl;
transform:rotate(180deg);height:96px;overflow:hidden;margin:0 auto}
footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
color:var(--dim);font-size:12.5px}
.note{background:var(--soft);border-left:3px solid var(--line2);padding:12px 15px;
border-radius:0 8px 8px 0;margin:18px 0;font-size:13px;color:var(--fg2)}
"""

JS = """
(function(){
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
  var panels = Array.prototype.slice.call(document.querySelectorAll('.panel'));
  function show(key){
    tabs.forEach(function(t){ t.setAttribute('aria-selected', String(t.dataset.key===key)); });
    panels.forEach(function(p){ p.classList.toggle('on', p.dataset.key===key); });
    if (history.replaceState) history.replaceState(null,'','#'+key);
  }
  tabs.forEach(function(t){ t.addEventListener('click', function(){ show(t.dataset.key); }); });
  var initial = (location.hash||'').replace('#','');
  var known = tabs.map(function(t){ return t.dataset.key; });
  show(known.indexOf(initial) >= 0 ? initial : (tabs[0] && tabs[0].dataset.key));
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
    return '<span class="mdash">&mdash;</span>' if v is None else f"{v:.1f}"


def fmt_frac(v) -> str:
    return '<span class="mdash">&mdash;</span>' if v is None else f"{v * 100:.1f}"


def bar(pct: float, color: str = "var(--accent)") -> str:
    pct = max(0.0, min(100.0, pct))
    return f'<span class="bar"><i style="width:{pct:.0f}%;background:{color}"></i></span>'


def _chart(models: list[dict], value_key: str, label_key: str = "name", top: int = 24) -> str:
    rows = [m for m in models if m.get(value_key) is not None][:top]
    if not rows:
        return '<p class="lede">No data.</p>'
    vals = [m[value_key] for m in rows]
    vmax = max(vals)
    lo = min(vals)
    span = (vmax - lo) or max(abs(vmax) * 0.2, 1)
    floor = max(0.0, lo - span * 0.28)
    rng = (vmax - floor) or 1

    bars, labs = [], []
    for m in rows:
        v = m[value_key]
        h = max(2.5, min(93.0, (v - floor) / rng * 93.0))
        name = m[label_key]
        short = name if len(name) <= 26 else name[:25] + "…"
        bars.append(
            f'<div class="col" title="{esc(name)} — {v:.1f}">'
            f'<span class="bv">{v:.1f}</span>'
            f'<div class="bx" style="height:{h:.1f}%"></div></div>'
        )
        labs.append(f'<div class="c"><span>{esc(short)}</span></div>')
    return f'<div class="plot">{"".join(bars)}</div><div class="xlab">{"".join(labs)}</div>'


def _row(rank: int, m: dict, preset: Preset, max_score: float) -> str:
    name = esc(m["name"])
    if m.get("available_locally"):
        name += '<span class="pill local">local</span>'
    if m["sources"]:
        name += f'<span class="pill">{esc("·".join(m["sources"]))}</span>'

    score = m["scores"].get(preset.key)
    eff = m["efficiency"].get(preset.key)
    price = m["pricing"].get("blended")
    cov = m["coverage"].get(preset.key, 0)
    pct = (score / max_score * 100) if (score is not None and max_score) else 0

    return (
        "<tr>"
        f'<td class="rk">{rank}</td>'
        f'<td><span class="nm">{name}</span></td>'
        f'<td class="fam">{esc(m["family"])}</td>'
        f'<td class="num">{bar(pct)}{fmt_score(score)}</td>'
        f'<td class="num">{fmt_price(price)}</td>'
        f'<td class="num">{fmt_eff(eff)}</td>'
        f'<td class="num">{cov:.2f}</td>'
        "</tr>"
    )


def _table(models: list[dict], preset: Preset, limit: int = 40) -> str:
    rows = models[:limit]
    if not rows:
        return '<p class="lede">No models matched this preset.</p>'
    max_score = max((m["scores"].get(preset.key) or 0) for m in rows) or 1
    body = "".join(_row(i, m, preset, max_score) for i, m in enumerate(rows, 1))
    which = "ability per dollar" if preset.rank_by == "efficiency" else "score"
    return (
        "<table><thead><tr>"
        '<th class="rk">#</th><th>Model</th><th>Family</th>'
        f'<th class="num">Score</th><th class="num">$/1M</th>'
        f'<th class="num">Eff.</th><th class="num">Cov.</th>'
        "</tr></thead><tbody>"
        f"{body}</tbody></table>"
        f'<p class="lede">Sorted by {which}. '
        f'"Cov." is the fraction of this preset\'s weight that had data.</p>'
    )


def _eligible(model: dict, preset: Preset) -> bool:
    """Whether a model has enough data to be ranked under this preset.

    A coverage floor, not just a non-null score: renormalisation alone would let
    a model with one of five metrics top the chart (see ``Preset.min_coverage``).
    """
    if model["scores"].get(preset.key) is None:
        return False
    if model["coverage"].get(preset.key, 0.0) < preset.min_coverage:
        return False
    if preset.rank_by == "efficiency" and model["efficiency"].get(preset.key) is None:
        return False
    return True


def _panel(models: list[dict], preset: Preset, first: bool) -> str:
    ranked = [m for m in models if _eligible(m, preset)]
    if preset.rank_by == "efficiency":
        ranked.sort(key=lambda m: -(m["efficiency"].get(preset.key) or 0))
    else:
        ranked.sort(key=lambda m: -(m["scores"].get(preset.key) or 0))

    # Models that have a score but not enough coverage to be ranked. Reported
    # rather than hidden, so a low-coverage model is visibly "insufficient data"
    # instead of silently absent or misleadingly placed.
    excluded = [
        m for m in models
        if m["scores"].get(preset.key) is not None and not _eligible(m, preset)
    ]

    best = ranked[0] if ranked else None

    # Value leader is worth surfacing in every view, not just the value preset:
    # "cheapest model that is still good" is a different question from "best".
    by_value = sorted(
        (m for m in ranked if m["efficiency"].get(preset.key) is not None),
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
        ("Models ranked", str(len(ranked)),
         f"coverage ≥ {preset.min_coverage:.0%}"),
        (
            "Best score",
            esc(best["name"]) if best else "&mdash;",
            f'{best["scores"][preset.key]:.1f} pts' if best else "no data",
        ),
        (
            "Best value",
            esc(best_value["name"]) if best_value else "&mdash;",
            f'{best_value["efficiency"][preset.key]:.1f} pts/\$' if best_value else "no published price",
        ),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="k">{k}</div>'
        f'<div class="v{" sm" if len(v) > 14 else ""}">{v}</div>'
        f'<div class="n">{n}</div></div>'
        for k, v, n in cards
    )

    excluded_note = ""
    if excluded:
        excluded_note = (
            f'<div class="note">{len(excluded)} further model(s) have a partial score '
            f'for this preset but fall below the {preset.min_coverage:.0%} coverage floor '
            f'and are not ranked. Their data covers too few of the weighted metrics to '
            f'place them meaningfully against the rest.</div>'
        )

    return (
        f'<section class="panel{" on" if first else ""}" data-key="{esc(preset.key)}">'
        f'<p class="desc">{esc(preset.description)}</p>'
        f'<div class="cards">{cards_html}</div>'
        + excluded_note
        + f'<h2>Top {len(chart_rows)}</h2>'
        + _chart(chart_rows, "_chart")
        + f'<h2>Full ranking</h2>'
        + _table(ranked, preset)
        + "</section>"
    )


def render(
    models: list[dict],
    presets: dict[str, Preset],
    meta: dict | None = None,
    generated: str | None = None,
    source_labels: dict[str, str] | None = None,
) -> str:
    """Render the full self-contained HTML page."""
    meta = meta or {}
    generated = generated or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    keys = list(presets.keys())
    tabs = "".join(
        f'<button class="tab" data-key="{esc(k)}" role="tab" aria-selected="false">'
        f'{esc(presets[k].label)}<span class="k">{esc(k)}</span></button>'
        for k in keys
    )
    panels = "".join(_panel(models, presets[k], first=(i == 0)) for i, k in enumerate(keys))

    # Weight table so the methodology is inspectable without reading source.
    weight_rows = "".join(
        "<tr><td><code>" + esc(k) + "</code></td><td>"
        + " · ".join(
            f'{esc(METRIC_LABELS.get(mk, mk))} {w:.2f}' for mk, w in p.weights.items()
        )
        + "</td><td>" + esc(p.rank_by) + "</td></tr>"
        for k, p in presets.items()
    )

    src_note = ""
    if source_labels:
        src_note = (
            '<div class="note"><b>Local gateway sources:</b> '
            + esc(", ".join(f"{k} → {v}" for k, v in sorted(source_labels.items())))
            + "</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>scipick — LLM selection leaderboard</title>
<meta name="description" content="Weighted LLM leaderboard for research, coding and value, built on Artificial Analysis benchmark data.">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
<h1>scipick</h1>
<p class="lede">A weighted LLM leaderboard for research and engineering work.
Benchmark data from Artificial Analysis; the weighting is ours and adjustable.
Generated {esc(generated)}.</p>
</header>

<div class="tabs" role="tablist">{tabs}</div>
{panels}

<h2>Weighting</h2>
<p class="lede">Every view is the same metric set under different weights.
Edit <code>config/presets.yaml</code> to define your own.</p>
<table><thead><tr><th>Preset</th><th>Weights</th><th>Rank by</th></tr></thead>
<tbody>{weight_rows}</tbody></table>

{src_note}

<div class="note">
<b>How to read this.</b> Scores are weighted benchmarks rescaled to 0–100, not an
official ranking. A missing benchmark is skipped and the remaining weights are
renormalised, so <b>Cov.</b> tells you how much of the weighting actually had
data — a score at 0.4 coverage rests on fewer benchmarks. Value is score per
blended dollar (3:1 input:output); models without a published price have no
value score.
</div>

<footer>
Data: <a href="https://artificialanalysis.ai">Artificial Analysis</a> data API
({meta.get("aa_total", 0)} models fetched, {meta.get("board_size", 0)} rankable).
Scoring and presentation by scipick.
</footer>
</div>
<script>{JS}</script>
</body>
</html>
"""


def render_json(models: list[dict], presets: dict[str, Preset], meta: dict, generated: str) -> str:
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
