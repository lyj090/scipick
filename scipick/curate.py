"""Curation: decide which models belong on the board at all.

Two rules, both aimed at the same problem — a leaderboard that ranks *every*
model ever released is dominated by tiny, cheap, superseded entries that are
irrelevant to someone choosing a model for real work.

**Latest generation only.** "Claude Opus 4.5" through "Opus 5.5" are all present
in the catalogue. If you want the state of the art, six rows for one product line
is noise. Grouping keeps the newest version of each line.

**Frontier gate.** A model must reach a fraction of the best score in a view to
be ranked in it. This is what stops the value board from being topped by 4B
models: something can be 400 points-per-dollar and still be the wrong tool, and a
pure ratio ranking has no way to say so. The gate makes "best value" mean *best
value among models worth using*, which is the actual question.

Both rules are configurable and both are reported, not silent: excluded models
are counted so the page can say how many were filtered and why.
"""

from __future__ import annotations

import re

from .config import Preset

# --------------------------------------------------------------------------- #
# Product lines
# --------------------------------------------------------------------------- #

#: Trailing release-date stamps: "DeepSeek V4 Pro 0813" -> "DeepSeek V4 Pro".
#: Four digits alone at the end is a date, not a version.
_DATE_SUFFIX = re.compile(r"[\s\-]+\d{4}$")

#: Trailing single version number/word: "Claude Opus 5.5" -> "Claude Opus".
_VERSION_SUFFIX = re.compile(r"[\s\-]+v?\d+(?:\.\d+)*$", re.I)

_PARENTHETICAL = re.compile(r"\s*\([^)]*\)\s*")


def base_name(name: str) -> str:
    """Model name with tier qualifiers removed.

    "Claude Opus 5.5 (Max, Default Fallback)" -> "Claude Opus 5.5"
    """
    return _PARENTHETICAL.sub(" ", name or "").strip()


def version_of(name: str) -> tuple[float, ...]:
    """Comparable version tuple from a model name.

    Returns the dotted numbers in the name as a tuple, so "Claude Opus 5.5"
    sorts above "Claude Opus 4.8". Names with no number sort lowest.
    """
    nums = re.findall(r"\d+(?:\.\d+)?", base_name(name))
    if not nums:
        return (0.0,)
    return tuple(float(n) for n in nums[:3])


def product_line(name: str) -> str:
    """Grouping key: the model family without its version.

    "Claude Opus 5.5 (Max)" and "Claude Opus 4.5 (Reasoning)" share the line
    "claude opus", so only the newest survives ``latest_only``.
    """
    b = base_name(name).lower()
    b = _DATE_SUFFIX.sub("", b)
    b = _VERSION_SUFFIX.sub("", b)
    return re.sub(r"[\s_]+", " ", b).strip()


def latest_only(models: list[dict]) -> tuple[list[dict], int]:
    """Keep only the newest generation of each product line.

    Within a line the version number decides; ties break on release date, then
    on capability score so a higher tier of the same version wins.

    Returns ``(kept, dropped_count)``.
    """
    best: dict[str, dict] = {}
    for m in models:
        line = product_line(m["name"])
        cur = best.get(line)
        if cur is None:
            best[line] = m
            continue
        key_new = (
            version_of(m["name"]),
            m.get("release_date") or "",
            m.get("science_fit_score") or 0,
        )
        key_cur = (
            version_of(cur["name"]),
            cur.get("release_date") or "",
            cur.get("science_fit_score") or 0,
        )
        if key_new > key_cur:
            best[line] = m
    kept = list(best.values())
    return kept, len(models) - len(kept)


# --------------------------------------------------------------------------- #
# Frontier gate
# --------------------------------------------------------------------------- #

def frontier_threshold(models: list[dict], preset: Preset) -> float | None:
    """The score a model must reach to be ranked under ``preset``.

    Based on the best score *in that view*, so the bar moves with the field
    rather than being a hardcoded number that ages badly.
    """
    if preset.min_relative_score <= 0:
        return None
    scores = [m["scores"].get(preset.key) for m in models]
    scores = [s for s in scores if s is not None]
    if not scores:
        return None
    return max(scores) * preset.min_relative_score


def passes_frontier(model: dict, preset: Preset, threshold: float | None) -> bool:
    """Whether a model clears the frontier gate for this view."""
    if threshold is None:
        return True
    score = model["scores"].get(preset.key)
    return score is not None and score >= threshold


def gate(models: list[dict], preset: Preset) -> tuple[list[dict], list[dict], float | None]:
    """Split models into (rankable, below-frontier, threshold) for a view.

    Applies the frontier gate only; the coverage floor is a separate check
    applied at render time.
    """
    threshold = frontier_threshold(models, preset)
    if threshold is None:
        return list(models), [], None
    kept, below = [], []
    for m in models:
        score = m["scores"].get(preset.key)
        if score is None:
            continue
        (kept if score >= threshold else below).append(m)
    return kept, below, threshold

# --------------------------------------------------------------------------- #
# Vendor allowlist
# --------------------------------------------------------------------------- #

#: Creators kept on the board. Names match the ``model_creator.name`` field from
#: the Artificial Analysis API, which is authoritative — far more reliable than
#: guessing a vendor from the model name (Meta's "Muse" line, for instance, has
#: no vendor in the name at all).
#:
#: The list is deliberately limited to companies whose models someone would
#: actually consider for research or engineering work: the frontier labs plus the
#: significant Chinese and open-weight vendors. Without it the board carries ~60
#: creators, most contributing a single entry, and the "Other" bucket swallows
#: more rows than any named family.
MAINSTREAM_CREATORS: tuple[str, ...] = (
    # Frontier labs, US/EU
    "OpenAI", "Google", "Anthropic", "Meta", "Mistral", "SpaceXAI", "xAI",
    "Cohere", "Amazon", "Microsoft", "NVIDIA", "Perplexity", "AI21 Labs",
    # Significant Chinese vendors
    "Alibaba", "DeepSeek", "Z AI", "Moonshot", "Kimi", "MiniMax", "Xiaomi",
    "Tencent", "ByteDance Seed", "Baidu", "StepFun", "OpenBMB", "InclusionAI",
    "LongCat", "China Mobile",
    # Notable research labs and open-weight vendors
    "IBM", "Allen Institute for AI", "Nous Research", "Liquid AI",
    "Institute of Foundation Models", "LG AI Research", "Upstage",
)

#: Creators whose models are kept even though the vendor is not on the list
#: above. Meta's "Muse" line occasionally arrives under a different creator
#: string; listing it explicitly keeps that line on the board.
CREATOR_ALIASES: dict[str, str] = {
    "muse": "Meta",
    "xai": "xAI",
}


def is_mainstream(creator: str, allow: tuple[str, ...] | None = None,
                  aliases: dict[str, str] | None = None) -> bool:
    """Whether a model creator is on the board's allowlist.

    Matching is case-insensitive and falls back to the alias table, so a vendor
    is not lost to a capitalisation or naming change upstream.
    """
    if not creator:
        return False
    allow = MAINSTREAM_CREATORS if allow is None else allow
    aliases = CREATOR_ALIASES if aliases is None else aliases
    # An empty allowlist means "no filtering", not "filter everything out".
    # An unset config field should not silently empty the board.
    if not allow:
        return True
    c = creator.strip()
    folded = {a.lower() for a in allow}
    if c.lower() in folded:
        return True
    mapped = aliases.get(c.lower())
    return bool(mapped and mapped.lower() in folded)


def filter_vendors(models: list[dict],
                   allow: tuple[str, ...] | None = None) -> tuple[list[dict], int]:
    """Keep only models from allowlisted creators.

    Returns ``(kept, dropped_count)``. Models with no creator recorded are kept:
    the field is usually present, and dropping rows for a missing field would
    hide real models rather than filter vendors.
    """
    kept, dropped = [], 0
    for m in models:
        creator = m.get("creator") or ""
        if not creator or is_mainstream(creator, allow):
            kept.append(m)
        else:
            dropped += 1
    return kept, dropped
