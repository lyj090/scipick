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

**A minimum coverage floor keeps rankings honest.** Renormalisation alone has a
trap: SciCode and Terminal-Bench cover only about a third of the catalogue, so a
"coding" preset would happily rank a model on the one metric it happened to have
— producing a *coding* leaderboard sorted by *long-context reasoning*. Each
preset therefore declares a `min_coverage`; models below it are listed as
insufficient data rather than ranked. (This was a real bug found while building
the tool, and the reason the floor exists at all.)

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

## Deploying your own

`.github/workflows/build.yml` rebuilds daily and publishes to GitHub Pages.
Add `AA_API_KEY` under **Settings → Secrets and variables → Actions**, enable
Pages with source "GitHub Actions", and it runs itself.

## Tests

```bash
python -m pytest tests/ -q
```

The suite covers the decisions that are easy to regress: renormalisation,
coverage, the no-price rule, name matching and de-duplication.

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

## License

MIT — see [LICENSE](LICENSE).
