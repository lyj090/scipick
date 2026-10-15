# scipick

**A weighted LLM leaderboard for research and engineering work.**

General-purpose leaderboards optimise for chat quality. If you are picking a
model to write code, read a repository, or work through a paper, that is the
wrong objective. `scipick` pulls benchmark data from
[Artificial Analysis](https://artificialanalysis.ai) and ranks models against a
weighting you can read and edit, rather than one you have to take on faith.

**Live leaderboard:** <https://lyj090.github.io/scipick/>

## Why

"Which model should I use" has three different answers depending on what you
are asking:

| Question | Objective | Wrong answer looks like |
|---|---|---|
| Which model is *best*? | raw ability | picking the one with the best chat vibes |
| Which is *worth it*? | ability per dollar | paying 5× for a 4% gain |
| Which is best *for code*? | code + terminal ability | a model tuned for prose |

These are three views over one metric set, not three independent rankings, so
the numbers stay comparable across them. Adding a view means editing a YAML
file, not changing code.

Each view is self-contained. It states its own top three, the efficient frontier
for its own scoring, and its own full ranking, so what is on screen always
describes the view you selected.

## Reading the page

**Top three, per view.** The podium leads with the view's own ranking criterion,
then names the leader on the other axis. Both "who is strongest" and "who is
best value" are answerable without leaving the view.

**Absolute ability.** The bar chart ranks the leading models by weighted score
with price ignored. Its y-axis starts near the top of the field rather than at
zero, because the gap between first and tenth is a few points and a zero-based
axis would draw twenty identical bars. That truncation is a real distortion, so
the floor value is printed under the chart.

This is the one place a strong model with no published price is visible: the
scatter can only plot priced models, and an efficiency board cannot rank them at
all.

**Score vs price.** The scatter plots every priced model in the view against a
log-scaled blended price. The blue staircase is the *efficient frontier*: the
best score available at or below each price. A model on the line is not
dominated, meaning nothing is both cheaper and better. Everything below it is.
This is what makes the trade-off visible in a way a ranked list cannot, and it
is why the value gate is a rule rather than a sort order.

Dots are coloured by vendor, but only for the vendors that reach the frontier or
the top three in that view, which is five to nine of the thirty-three on the
board. Colouring the rest would need a palette nobody can tell apart. Grey is
also the accurate reading, since a grey dot is not in contention.

**Filtering and ordering.** Each ranking has its own family filter and a search
box. Order is switchable: rank in this view, name A–Z, or newest first within
family. That last one groups by vendor and then by release date, because
comparing a vendor's own line against itself is what you do when deciding
whether to upgrade. A straight date sort would interleave every vendor by
recency instead. Every row carries its release date, and the column is sortable.

**Compare.** Search for a model to pin it. Pinned models are highlighted across
every view (bar chart, scatter, and table) and collected in the tray at the top,
so the model you are considering stays lit while you move between weightings.
Up to five at a time, and the selection survives a reload.

If a pinned model is not in the bar chart's top twenty, it is added as a dashed
bar with a note explaining that it is not part of the ranking. That matters
because the picker offers all 374 board models while a view's table may hold
fewer. A model can be below the coverage floor in one view and perfectly
rankable in another, and pinning it is how you see that.

**Full ranking.** Sortable by any column, and collapsed to the first screen by
default. Every row ships in the file, so search and sort cover the whole set and
"Show all" reveals the rest in place. Sorting reads structured keys rather than
cell text, so "price not published" sorts as missing rather than as free.

## How it works

```
Artificial Analysis data API          (benchmarks, pricing, speed)
              │
              ▼
        collect  ──►  one row per model, de-duplicated across route and variant names
              │
              ▼
         score   ──►  weighted ability (0-100)  +  coverage
              │      ability per blended dollar
              ▼
        render   ──►  one self-contained HTML file (no build step, no JS deps)
```

Four decisions change the numbers, so they are worth stating.

**A missing benchmark is skipped, not scored as zero.** If a model was never
evaluated on SciCode, counting that as 0 would rank it below a model that scored
badly on it. The remaining weights are renormalised instead, and the row reports
**coverage**, meaning the share of the weighting that had data. A score at `0.40`
coverage rests on four-tenths of the intended evidence.

**Only the latest generation of each product line.** The catalogue carries
Claude Opus 4.5 through 5.5, GPT-4 through 5.5, and so on. Six rows for one
product line is noise when you want the state of the art, so the newest version
of each line is kept and the rest are counted as superseded.

**A minimum coverage floor keeps rankings honest.** Renormalisation alone has a
trap. SciCode and Terminal-Bench cover about a third of the catalogue, so a
"coding" preset would happily rank a model on the one metric it happened to have,
producing a *coding* leaderboard sorted by *long-context reasoning*. Each preset
declares a `min_coverage`, and models below it are listed as insufficient data
rather than ranked. This was a real bug found while building the tool, and it is
the reason the floor exists.

**The value board has a frontier gate.** Ranking purely on points-per-dollar put
Gemma 4 E4B (score 15.5 at $0.04/1M) above Claude Haiku 5.5 (score 51.1 at
$0.20): 388 points-per-dollar against 256. Technically correct and practically
useless, because a model scoring 15/100 is not a cheaper way to do your work, it
is a model that cannot do your work. Each view therefore declares
`min_relative_score`, the fraction of the best score in that same view a model
must reach to be ranked. The gate is relative, so the bar moves with the field
instead of aging into a hardcoded threshold.

**"Price not published" is not "free".** The API reports `0` for unpriced
models. Treating that as `$0` would put them at the top of every value ranking,
so they get no value score at all.

**The leaderboard ranks models, not endpoints.** The same model reached through
different gateways or reasoning-effort suffixes collapses to one row, with the
routing detail kept alongside.

## Quick start

No dependencies. Standard library only, Python 3.9+.

```bash
git clone https://github.com/lyj090/scipick.git
cd scipick

export AA_API_KEY=...        # https://artificialanalysis.ai (data API)
python -m scipick --open
```

That writes `docs/index.html` and opens it. No gateway, no config, no account
beyond the AA key.

### Useful flags

```bash
python -m scipick --list-presets                    # what views exist
python -m scipick --preset value --preset coding    # only these two
python -m scipick --presets-file config/presets.yaml
python -m scipick --json docs/data.json             # machine-readable dump
```

### Optional: mark what you can actually reach

If you run an OpenAI-compatible gateway, `scipick` can annotate which models are
live for you. This is optional, and the leaderboard is complete without it.

```bash
export SCIPICK_LOCAL_BASE=http://127.0.0.1:8000
export SCIPICK_LOCAL_KEY=...
python -m scipick --sources-file config/sources.yaml
```

`config/sources.example.yaml` maps route prefixes to display names. It ships
empty on purpose, since which providers you use is your business rather than this
project's.

## How models are selected

Three filters stack, and all of them are reported on the page rather than
applied silently:

| Filter | Scope | What it removes |
|---|---|---|
| Mainstream vendors | global | Models from creators outside the allowlist |
| Latest generation | global | Superseded versions of a product line |
| `min_coverage` | per view | Models missing too many of that view's benchmarks |
| `min_relative_score` | per view | Models too far below that view's frontier |

**Vendors.** The catalogue carries around sixty creators, most contributing a
single entry. Ranking all of them buries the models you would actually consider
and makes the "Other" family larger than any named one. The allowlist lives in
`scipick/curate.py` and covers the frontier labs plus the significant Chinese and
open-weight vendors. It is matched against the API's authoritative
`model_creator` field rather than the model name, because Meta ships its current
flagship as "Muse" with the vendor appearing nowhere in the name. Name matching
alone would file it under "Other".

`--all-vendors` and `--all-generations` disable the two global filters if you
want the complete field.

The frontier gate is the filter that needs judgement. Set it too low and a value
board fills with small models nobody would choose; too high and it becomes a
capability board with extra steps. `0.65` on value keeps cheap frontier-class
models (Claude Haiku, MiMo Flash) in play while excluding the sub-4B tier. Raise
or lower it in `config/presets.yaml` to match your own willingness to trade
capability for cost.

## Customising the ranking

This is the point of the tool. Copy `config/presets.yaml` and edit:

```yaml
presets:
  longcontext:
    label: Long context
    description: For whole-repository or long-document reasoning.
    rank_by: score        # or: efficiency
    weights:
      lcr: 0.50           # long-context reasoning
      scicode: 0.25
      artificial_analysis_intelligence_index: 0.25
```

Available metrics and the meaning of `rank_by` are documented at the top of that
file. Weights are renormalised, so they need not sum to 1.

## Languages

The page ships English and Chinese and switches client-side, so one static file
serves either audience. Interface strings live in `scipick/i18n.py`; model names
and benchmark names come from the data and are not translated. Adding a language
means adding one dict to `STRINGS`.

## Deploying your own

`.github/workflows/build.yml` rebuilds daily and publishes to GitHub Pages. Add
`AA_API_KEY` under **Settings → Secrets and variables → Actions**, enable Pages
with source "GitHub Actions", and it runs itself.

## Tests

```bash
python -m pytest tests/ -q
```

The suite covers the decisions that are easy to regress: renormalisation,
coverage, the no-price rule, name matching, and de-duplication. It also covers
the page itself, including that each view's podium matches its own table, that no
two frontier labels overprint, and that a collapsed ranking still contains every
row.

## Limitations

- **Benchmarks are proxies.** A weighted average of SciCode and HLE is still a
  weighted average of benchmarks, not a measurement of your task. It narrows the
  field, it does not pick for you.
- **Coverage varies.** Newly released models often have partial data. The
  coverage column exists so you can discount them yourself.
- **The weights are opinions.** The defaults are this project's opinion about
  research work. They are visible and editable so you can disagree.
- **Data is Artificial Analysis's.** scipick does not benchmark anything; it
  re-weights someone else's measurements. Please respect their terms.
- **The frontier is in-sample.** It is computed from the same models being
  ranked, so it describes the current field rather than a permanent bar. A quiet
  release week moves it.

## Design notes

The visual language, the borrowing from Artificial Analysis's frontier chart,
and the layout defects that were measured and fixed are written up in
[DESIGN.md](DESIGN.md).

## License

MIT, see [LICENSE](LICENSE).
