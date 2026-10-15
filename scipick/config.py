"""scipick configuration: scoring presets, metric labels, source labels.

Everything user-specific lives in config files or environment variables —
nothing about any particular deployment is hardcoded here.

Design note: a preset is a *view* over the same underlying metrics. We keep one
scoring function and vary the weights, rather than forking the ranking logic per
use case, so any new preset stays comparable with the others.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

#: AA evaluation keys that scipick understands, mapped to human labels.
#: Keys match the field names in the Artificial Analysis data API.
METRIC_LABELS: dict[str, str] = {
    "scicode": "SciCode",
    "hle": "HLE",
    "artificial_analysis_intelligence_index": "AA Intelligence Index",
    "lcr": "Long-context reasoning",
    "terminalbench_v4_0": "Terminal-Bench 4.0",
}

#: Metrics stored on a collected model, keyed by scipick's short name.
#: ``aa_intelligence_index`` is the short alias for the long AA field name.
MODEL_METRIC_KEYS: tuple[str, ...] = (
    "scicode",
    "hle",
    "aa_intelligence_index",
    "long_context_reasoning",
    "terminalbench_v4_0",
)

#: AA stores the intelligence index as 0-100 while other benchmarks are 0-1.
#: ``science_score`` needs to know which keys to rescale.
FRACTION_METRICS = frozenset({"scicode", "hle", "lcr", "terminalbench_v4_0"})


@dataclass(frozen=True)
class Preset:
    """A named weighting over the same metric set.

    ``min_coverage`` guards against a real failure mode: benchmark data is
    unevenly available (SciCode covers roughly a third of the catalogue). Without
    a floor, a "coding" preset would happily rank a model on whichever single
    metric it happens to have, producing a coding leaderboard sorted by
    long-context reasoning. Renormalisation keeps the arithmetic valid, but only
    a coverage floor keeps the *ranking* meaningful.
    """

    key: str
    label: str
    description: str
    weights: dict[str, float]
    rank_by: str = "score"  # "score" | "efficiency"
    min_coverage: float = 0.6

    def normalised(self) -> dict[str, float]:
        total = sum(self.weights.values())
        if total <= 0:
            raise ValueError(f"preset {self.key!r} has non-positive total weight")
        return {k: v / total for k, v in self.weights.items()}


#: Default presets. Overridable via a config file — see :func:`load_presets`.
DEFAULT_PRESETS: dict[str, Preset] = {
    "capability": Preset(
        key="capability",
        label="Capability",
        description="Absolute ability, price ignored.",
        weights={
            "scicode": 0.40,
            "hle": 0.20,
            "artificial_analysis_intelligence_index": 0.20,
            "lcr": 0.10,
            "terminalbench_v4_0": 0.10,
        },
        rank_by="score",
        min_coverage=0.5,
    ),
    "value": Preset(
        key="value",
        label="Value",
        description="Ability per dollar, using a 3:1 input:output blended price.",
        weights={
            "scicode": 0.40,
            "hle": 0.20,
            "artificial_analysis_intelligence_index": 0.20,
            "lcr": 0.10,
            "terminalbench_v4_0": 0.10,
        },
        rank_by="efficiency",
        min_coverage=0.5,
    ),
    "coding": Preset(
        key="coding",
        label="Coding",
        description="Weighted toward code generation and terminal execution.",
        weights={
            "scicode": 0.60,
            "terminalbench_v4_0": 0.25,
            "lcr": 0.15,
        },
        rank_by="score",
        # SciCode + Terminal-Bench + LCR must mostly be present, otherwise this
        # degenerates into a long-context ranking (see Preset.min_coverage).
        min_coverage=0.85,
    ),
}

DEFAULT_PRESET = "capability"


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

AA_API = os.environ.get(
    "AA_API", "https://artificialanalysis.ai/api/v2/data/llms/models"
)

#: Optional. When set, scipick also reports which models you can actually reach
#: from a local OpenAI-compatible gateway. Unset by default: the leaderboard is
#: fully useful without it, and no personal endpoint should be baked in.
LOCAL_BASE = os.environ.get("SCIPICK_LOCAL_BASE", "")
LOCAL_KEY = os.environ.get("SCIPICK_LOCAL_KEY", "")


# --------------------------------------------------------------------------- #
# Source labels
# --------------------------------------------------------------------------- #

def load_source_labels(path: str | os.PathLike | None = None) -> dict[str, str]:
    """Map route prefixes to display names.

    Deliberately empty by default. Providers are a private detail; anyone who
    wants them labelled supplies their own mapping instead of inheriting
    someone else's vendor list.

    Accepts a YAML file of the form::

        sources:
          my-gateway: "My Gateway"
    """
    if path is None:
        path = os.environ.get("SCIPICK_SOURCES", "")
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"source labels file not found: {p}")
    try:
        import yaml  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "PyYAML is required to read a source labels file"
        ) from e
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw = data.get("sources") or {}
    return {str(k): str(v) for k, v in raw.items()}


def load_presets(path: str | os.PathLike | None = None) -> dict[str, Preset]:
    """Load presets from YAML, falling back to :data:`DEFAULT_PRESETS`.

    A file may define a subset; missing presets are filled in from the defaults
    so a user config never accidentally removes a view.
    """
    if path is None:
        path = os.environ.get("SCIPICK_PRESETS", "")
    if not path:
        return dict(DEFAULT_PRESETS)
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"presets file not found: {p}")
    try:
        import yaml  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("PyYAML is required to read a presets file") from e

    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out = dict(DEFAULT_PRESETS)
    for key, body in (data.get("presets") or {}).items():
        body = body or {}
        weights = {str(k): float(v) for k, v in (body.get("weights") or {}).items()}
        if not weights:
            continue
        out[str(key)] = Preset(
            key=str(key),
            label=str(body.get("label") or key),
            description=str(body.get("description") or ""),
            weights=weights,
            rank_by=str(body.get("rank_by") or "score"),
            min_coverage=float(body.get("min_coverage", 0.6)),
        )
    return out
