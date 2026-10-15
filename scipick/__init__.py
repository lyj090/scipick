"""scipick — a weighted LLM leaderboard for research and engineering.

Data: Artificial Analysis benchmark API.
Opinion: the weights, which are yours to change.
"""

from .config import DEFAULT_PRESETS, METRIC_LABELS, Preset, load_presets, load_source_labels
from .collect import collect
from .fetch import fetch_aa_models, fetch_local_models
from .score import efficiency, rank, science_score
from .render import render, render_json

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_PRESETS",
    "METRIC_LABELS",
    "Preset",
    "collect",
    "efficiency",
    "fetch_aa_models",
    "fetch_local_models",
    "load_presets",
    "load_source_labels",
    "rank",
    "render",
    "render_json",
    "science_score",
    "__version__",
]
