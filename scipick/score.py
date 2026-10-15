"""Scoring: turn benchmark numbers into (a) a weighted ability score and
(b) a value score.

Both views come from one place so presets stay comparable.

Scoring rules that matter:

* Metrics arrive on two scales. The AA intelligence index is 0-100; the other
  benchmarks are fractions (0-1). ``FRACTION_METRICS`` marks the ones to rescale.
* A missing benchmark is *skipped and renormalised*, not treated as zero. A model
  that simply was not evaluated for SciCode should not be punished for it — but
  the returned coverage tells you how much of the weighting actually landed, so
  a score built from one metric is visibly weaker evidence than one from five.
* Value = score per blended dollar. Models with no published price get no value
  score rather than an infinite one; "price unknown" is not "free".
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import FRACTION_METRICS, Preset


@dataclass
class Score:
    """A weighted ability score plus how much of the weighting was available."""

    value: float | None
    coverage: float

    def __bool__(self) -> bool:
        return self.value is not None


def science_score(evaluations: dict, preset: Preset) -> Score:
    """Weighted ability score in 0-100, and the fraction of weight covered.

    ``coverage`` is the sum of the weights that had data, before
    renormalisation. 1.0 means every weighted metric was present.
    """
    total = 0.0
    weight = 0.0
    for key, w in preset.weights.items():
        raw = evaluations.get(key)
        if raw is None:
            continue
        # Rescale fraction-valued metrics to 0-100.
        scaled = raw * 100 if key in FRACTION_METRICS else raw
        total += scaled * w
        weight += w
    if weight <= 0:
        return Score(value=None, coverage=0.0)
    return Score(value=round(total / weight, 2), coverage=round(weight, 2))


def blended_price(pricing: dict | None) -> float | None:
    """Blended USD per 1M tokens (3:1 input:output), if published.

    AA reports 0 for "not published", which must not read as "free".
    """
    if not pricing:
        return None
    v = pricing.get("price_1m_blended_3_to_1")
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def efficiency(score: float | None, price: float | None) -> float | None:
    """Ability per dollar, i.e. score / blended USD per 1M tokens."""
    if score is None or price is None or price <= 0:
        return None
    return score / price


def rank_key(model: dict, preset: Preset) -> tuple:
    """Sort key implementing a preset's ``rank_by``.

    Missing values sort last via a leading 0/1 flag, so an unrankable model never
    outranks a scored one.
    """
    if preset.rank_by == "efficiency":
        v = (model.get("efficiency") or {}).get(preset.key)
    else:
        v = (model.get("scores") or {}).get(preset.key)
        if v is None:
            # Accept the flat alias used by older records.
            v = model.get("science_fit_score")
    return (0 if v is not None else 1, -(v or 0.0), model.get("name", ""))


def rank(models: list[dict], preset: Preset) -> list[dict]:
    """Rank models under a preset, best first."""
    rankable = [
        m for m in models
        if (m.get("scores") or {}).get(preset.key) is not None
    ]
    if preset.rank_by == "efficiency":
        rankable = [
            m for m in rankable
            if (m.get("efficiency") or {}).get(preset.key) is not None
        ]
    return sorted(rankable, key=lambda m: rank_key(m, preset))
