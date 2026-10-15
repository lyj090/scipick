# scipick

**A weighted LLM leaderboard for research and engineering work.**

Public leaderboards optimise for general chat quality. If you are picking a model
to write code, read a repository, or work through a paper, that ranking is the
wrong objective. `scipick` takes benchmark data from
[Artificial Analysis](https://artificialanalysis.ai) and lets you rank models by
*what you actually care about* — with the weighting written down and editable,
not hidden behind a leaderboard you have to trust.

**Live leaderboard:** <https://lyj090.github.io/scipick/>

---

## Why

Every "which model should I use" question has the same shape and three different
answers:

| Question | Objective | Wrong answer looks like |
|---|---|---|
| Which model is *best*? | raw ability | picking the one with the best chat vibes |
| Which is *worth it*? | ability per dollar | paying 5× for a 4% gain |
| Which is best *for code*? | code + terminal ability | a model tuned for prose |

`scipick` treats these as **three views over one metric set** rather than three
independent rankings, so the numbers stay comparable. You can add your own view
by editing a YAML file — no code changes.

Each view is self-contained: it states its own top three, the efficient frontier
for its own scoring, and the full ranking. Switching views changes all of it, so
what is on screen always describes the view you selected.

## Reading the page

**Top three, per view.** The podium leads with the view's own ranking criterion,
then names the leader on the other axis — so "who is strongest" and "who is best
value" are both answerable without leaving the view.

**Absolute ability.** The bar chart ranks the leading models by weighted score
with price ignored, and its y-axis starts near the top of the field rather than
at zero — the gap between first and tenth is a few points, so a zero-based axis
would draw twenty identical bars. That truncation is a real distortion, so the
floor value is printed under the chart rather than left to be guessed.

It is the one place a strong model with no published price is visible, because
the scatter can only plot priced models and an efficiency board cannot rank
them at all.

**Score vs price.** The scatter plots every priced model in the view against a
log-scaled blended price. The blue staircase is the *efficient frontier*: the
best score available at or below each price. A model on the line is not
dominated — nothing is both cheaper and better. Everything below it is. This is
the view that makes the trade-off legible in a way a ranked list cannot, and it
is why the value gate is a rule rather than a sort order.

Dots are coloured by vendor for the vendors that actually reach the frontier or
the top three in that view — five to nine of the thirty-three on the board.
Colouring the rest would need a palette nobody can tell apart; leaving them grey
is also the truthful reading, because a grey dot is not in contention.

**Compare.** Click a bar, a scatter point, or a table row to pin a model. Pinned
models are highlighted across *every* view and collected in the tray at the top,
so the model you are considering stays lit while you move between weightings.
Up to five at a time; the selection survives a reload. There is also an
add-by-name box, which is the practical way to find a model among 290 when you
already know which one you want.

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

Three design decisions worth stating, because they change the numbers:

**A missing benchmark is skipped, not scored as zero.** If a model was never
evaluated on SciCode, counting that as 0 would rank it below a model that scored
badly on it. Instead the remaining weights are renormalised — and the row reports
**coverage**, the share of the weighting that had data. A score at `0.40`
coverage rests on four-tenths of the intended evidence.

**Only the latest generation of each product line.** The catalogue contains
Claude Opus 4.5 through 5.5, GPT-4 through 5.5, and so on. Six rows for one
product line is noise when you want the state of the art, so the newest version
of each line is kept and the rest are counted as superseded.

**A minimum coverage floor keeps rankings honest.** Renormalisation alone has a
trap: SciCode and Terminal-Bench cover only about a third of the catalogue, so a
"coding" preset would happily rank a model on the one metric it happened to have
— producing a *coding* leaderboard sorted by *long-context reasoning*. Each
preset therefore declares a `min_coverage`; models below it are listed as
insufficient data rather than ranked. (This was a real bug found while building
the tool, and the reason the floor exists at all.)

**The value board has a frontier gate.** This is the rule that makes "best
value" mean something. Ranking purely on points-per-dollar put Gemma 4 E4B
(score 15.5 at $0.04/1M) above Claude Haiku 5.5 (score 51.1 at $0.20) — 388
points-per-dollar against 256. Technically correct, practically useless: a model
scoring 15/100 is not a cheaper way to do your work, it is a model that cannot
do your work. Each view therefore declares `min_relative_score`: a model must
reach that fraction of the *best score in that same view* to be ranked. The gate
is relative, so the bar moves with the field instead of aging into a hardcoded
threshold.

**"Price not published" is not "free".** The API reports `0` for unpriced
models. Treating that as `$0` would put them at the top of every value ranking,
so they get no value score at all.

**The leaderboard ranks models, not endpoints.** The same model reached through
different gateways or reasoning-effort suffixes collapses to one row, with the
routing detail kept alongside.

## Quick start

No dependencies — standard library only, Python 3.9+.

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
live for you. This is entirely optional — the leaderboard is complete without it.

```bash
export SCIPICK_LOCAL_BASE=http://127.0.0.1:8000
export SCIPICK_LOCAL_KEY=...
python -m scipick --sources-file config/sources.yaml
```

`config/sources.example.yaml` maps route prefixes to display names. It ships
empty on purpose: which providers you use is your business, not this project's.

## How models are selected

Three filters stack, and all three are reported on the page rather than applied
silently:

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
`model_creator` field, not against the model name — Meta ships its current
flagship as "Muse", with the vendor appearing nowhere in the name, so name
matching alone would file it under "Other".

`--all-vendors` and `--all-generations` disable the two global filters if you
want the complete field.

The frontier gate is the filter that needs judgement. Set it too low and a value board
fills with small models nobody would choose; too high and it becomes a
capability board with extra steps. `0.65` on value keeps genuinely cheap
frontier-class models (Claude Haiku, MiMo Flash) in play while excluding the
sub-4B tier. Raise or lower it in `config/presets.yaml` to match your own
willingness to trade capability for cost.

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

Available metrics, and `rank_by` semantics, are documented at the top of that
file. Weights are renormalised, so they need not sum to 1.

## Languages

The page ships English and Chinese and switches client-side, so one static file
serves either audience. Interface strings live in `scipick/i18n.py`; model names
and benchmark names come from the data and are not translated. Adding a language
means adding one dict to `STRINGS`.

## Deploying your own

`.github/workflows/build.yml` rebuilds daily and publishes to GitHub Pages.
Add `AA_API_KEY` under **Settings → Secrets and variables → Actions**, enable
Pages with source "GitHub Actions", and it runs itself.

## Tests

```bash
python -m pytest tests/ -q
```

The suite covers the decisions that are easy to regress: renormalisation,
coverage, the no-price rule, name matching and de-duplication. It also covers the
page itself — that each view's podium matches its own table, that no two frontier
labels overprint, and that a collapsed ranking still contains every row.

## Limitations

- **Benchmarks are proxies.** A weighted average of SciCode and HLE is still a
  weighted average of benchmarks, not a measurement of your task. It narrows the
  field; it does not pick for you.
- **Coverage varies.** Newly released models often have partial data. The
  coverage column exists so you can discount them yourself.
- **The weights are opinions.** The defaults are *our* opinion about research
  work. They are visible, and editable, precisely so you can disagree.
- **Data is Artificial Analysis's.** scipick does not benchmark anything; it
  re-weights someone else's measurements. Please respect their terms.
- **The frontier is in-sample.** The efficient frontier is computed from the same
  models being ranked, so it describes the current field, not a permanent bar. A
  quiet release week moves it.

## Design notes

The visual language, the borrowing from Artificial Analysis's frontier chart, and
the four layout defects that were measured and fixed are written up in
[DESIGN.md](DESIGN.md).

## License

MIT — see [LICENSE](LICENSE).
