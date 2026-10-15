"""Collect: join Artificial Analysis data with (optional) local availability
into one list of comparable model records.

Output shape — one record per *model*, not per route:

    {
      "name": "Claude Opus 4.5",
      "canonical": "claude-opus-4-5",
      "family": "Claude",
      "presets": {"capability": 64.99, "value": 63.62, "coding": 71.4},
      "coverage": {"capability": 1.0, ...},
      "metrics": {"scicode": 0.53, ...},
      "pricing": {"input": 5.0, "output": 25.0, "blended": 10.0},
      "efficiency": {"capability": 6.5, ...},
      "speed": {...},
      "sources": ["gateway-a"],        # empty when not locally reachable
      "available_locally": False,
    }

Merging note: the same model can appear under several gateway routes and several
effort variants. Those collapse into one row keyed by the AA name, so the
leaderboard ranks *models*, while ``sources`` keeps the routing detail.
"""

from __future__ import annotations

import re

from . import config, fetch
from .config import Preset
from .curate import filter_vendors, latest_only
from .score import blended_price, efficiency, science_score

#: Families used to pick cross-vendor reference models. Matching is substring
#: based on the lowercased AA name, so these must stay lowercase.
FAMILIES: dict[str, str] = {
    "Claude": r"claude",
    "GPT": r"\bgpt",
    "Gemini": r"gemini",
    "DeepSeek": r"deepseek",
    "GLM": r"glm",
    "Kimi": r"kimi",
    "Grok": r"grok",
    "Qwen": r"qwen",
    "Llama": r"llama",
    "Mistral": r"mistral",
    "MiMo": r"mimo",
}

#: AA marks high reasoning tiers with a parenthetical, e.g. "GPT-5 (High)".
TOP_TIER = re.compile(r"\((?:max|xhigh|high|thinking|reasoning)[^)]*\)", re.I)


#: Creator name -> display family. More reliable than parsing the model name,
#: which often carries no vendor at all (Meta ships its flagship as "Muse").
CREATOR_FAMILY: dict[str, str] = {
    "OpenAI": "OpenAI",
    "Google": "Google",
    "Anthropic": "Anthropic",
    "Meta": "Meta",
    "Mistral": "Mistral",
    "SpaceXAI": "xAI",
    "xAI": "xAI",
    "Cohere": "Cohere",
    "Amazon": "Amazon",
    "Microsoft": "Microsoft",
    "NVIDIA": "NVIDIA",
    "Perplexity": "Perplexity",
    "AI21 Labs": "AI21",
    "Alibaba": "Alibaba",
    "DeepSeek": "DeepSeek",
    "Z AI": "Z AI",
    "Moonshot": "Moonshot",
    "Kimi": "Moonshot",
    "MiniMax": "MiniMax",
    "Xiaomi": "Xiaomi",
    "Tencent": "Tencent",
    "ByteDance Seed": "ByteDance",
    "Baidu": "Baidu",
    "StepFun": "StepFun",
    "OpenBMB": "OpenBMB",
    "InclusionAI": "InclusionAI",
    "LongCat": "LongCat",
    "China Mobile": "China Mobile",
    "IBM": "IBM",
    "Allen Institute for AI": "AI2",
    "Nous Research": "Nous",
    "Liquid AI": "Liquid AI",
    "Institute of Foundation Models": "IFM",
    "LG AI Research": "LG",
    "Upstage": "Upstage",
}


def family_of(name: str, slug: str = "", creator: str = "") -> str:
    """Display family for a model.

    Prefers the authoritative creator field; falls back to name matching for
    records that lack it. The name heuristic alone would place Meta's "Muse"
    line outside its family, since the vendor appears nowhere in the name.
    """
    if creator:
        fam = CREATOR_FAMILY.get(creator.strip())
        if fam:
            return fam
    text = f"{name} {slug}".lower()
    for fam, pat in FAMILIES.items():
        if re.search(pat, text):
            return fam
    if creator:
        return creator.strip()
    return "Other"


def canonical_key(name: str) -> str:
    """Stable identity for a model row."""
    base = fetch.strip_variant(name).lower().strip()
    return re.sub(r"[\s_]+", "-", base).strip("-")


def _record(aa_model: dict, presets: dict[str, Preset]) -> dict:
    """Build one model record from an AA entry."""
    ev = aa_model.get("evaluations") or {}
    pricing = aa_model.get("pricing") or {}
    scores: dict[str, float | None] = {}
    coverages: dict[str, float] = {}
    for key, preset in presets.items():
        s = science_score(ev, preset)
        scores[key] = s.value
        coverages[key] = s.coverage

    price = blended_price(pricing)
    creator = ((aa_model.get("model_creator") or {}).get("name") or "").strip()
    return {
        "name": aa_model.get("name") or aa_model.get("slug") or "unknown",
        "canonical": canonical_key(aa_model.get("name") or ""),
        "creator": creator,
        "family": family_of(aa_model.get("name", ""), aa_model.get("slug", ""), creator),
        "release_date": aa_model.get("release_date"),
        "science_fit_score": scores.get("capability"),  # back-compat alias
        "scores": scores,
        "coverage": coverages,
        "metrics": {
            "scicode": ev.get("scicode"),
            "hle": ev.get("hle"),
            "aa_intelligence_index": ev.get("artificial_analysis_intelligence_index"),
            "long_context_reasoning": ev.get("lcr"),
            "terminalbench_v4_0": ev.get("terminalbench_v4_0"),
        },
        "pricing": {
            "input": pricing.get("price_1m_input_tokens"),
            "output": pricing.get("price_1m_output_tokens"),
            "blended": price,
        },
        "efficiency": {
            k: efficiency(v, price) for k, v in scores.items()
        },
        "speed": {
            "output_tokens_per_second": aa_model.get("median_output_tokens_per_second"),
            "ttft_seconds": aa_model.get("median_time_to_first_token_seconds"),
        },
        "sources": [],
        "variants": [],
        "available_locally": False,
    }


def collect(
    aa_models: list[dict],
    local_models: dict[str, list[str]] | None = None,
    presets: dict[str, Preset] | None = None,
    latest: bool = True,
    mainstream_only: bool = True,
) -> tuple[list[dict], list[dict], dict]:
    """Join AA data with local availability.

    Returns ``(board, unmatched, meta)`` where ``board`` is the merged, de-duped
    leaderboard, ``unmatched`` lists gateway routes with no AA entry, and ``meta``
    carries counts for the header.
    """
    presets = presets or dict(config.DEFAULT_PRESETS)
    local_models = local_models or {}

    # Every AA model is a candidate row; local availability is an annotation.
    # Two stages drop rows here without being named in the filter table the page
    # prints, so both are counted: an entry with neither SciCode nor the
    # intelligence index has nothing to rank on, and several API entries collapse
    # to one canonical model (the same model at different reasoning efforts).
    # Without these counts the page's "selected from N" arithmetic does not add
    # up, which on a page whose selling point is stated rules is worse than not
    # stating them.
    board: dict[str, dict] = {}
    unrankable = 0
    duplicates = 0
    for m in aa_models:
        ev = m.get("evaluations") or {}
        if ev.get("scicode") is None and ev.get("artificial_analysis_intelligence_index") is None:
            unrankable += 1
            continue
        rec = _record(m, presets)
        key = rec["canonical"] or rec["name"].lower()
        if key in board:
            duplicates += 1
            continue
        board[key] = rec

    aa_idx = fetch.build_aa_index(aa_models)
    unmatched: list[dict] = []
    for source, names in sorted(local_models.items()):
        for name in sorted(names):
            m = fetch.match_model(name, aa_idx)
            route = f"{source}/{name}"
            if not m:
                unmatched.append({"route": route, "source": source, "name": name})
                continue
            key = canonical_key(m.get("name") or "")
            rec = board.get(key)
            if rec is None:
                continue
            if source not in rec["sources"]:
                rec["sources"].append(source)
            if name not in rec["variants"]:
                rec["variants"].append(name)
            rec["available_locally"] = True

    rows = list(board.values())
    superseded = 0
    if latest:
        rows, superseded = latest_only(rows)

    vendors_removed = 0
    if mainstream_only:
        rows, vendors_removed = filter_vendors(rows)

    out = sorted(rows, key=lambda r: -(r.get("science_fit_score") or 0))
    for rec in out:
        rec["sources"].sort()
        rec["variants"].sort()

    meta = {
        "aa_total": len(aa_models),
        "board_size": len(out),
        "superseded_removed": superseded,
        "vendors_removed": vendors_removed,
        "unrankable_removed": unrankable,
        "duplicate_removed": duplicates,
        "vendors_filtered": mainstream_only,
        "latest_only": latest,
        "local_sources": sorted(local_models.keys()),
        "unmatched_count": len(unmatched),
    }
    return out, unmatched, meta
