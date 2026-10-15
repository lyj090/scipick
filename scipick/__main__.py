"""Command-line entry point.

    python -m scipick                      # build the default leaderboard
    python -m scipick --preset value       # rank by ability per dollar
    python -m scipick --list-presets       # show available views
    python -m scipick --json out.json      # also dump machine-readable data

AA_API_KEY is required. SCIPICK_LOCAL_BASE is optional — set it to also mark
which models a local OpenAI-compatible gateway can reach.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone

from . import __version__
from .collect import collect
from .config import DEFAULT_PRESETS, load_presets, load_source_labels
from .fetch import fetch_aa_models, fetch_local_models
from .render import render, render_json


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scipick",
        description="Weighted LLM leaderboard for research and engineering work.",
    )
    p.add_argument("-o", "--output", default="docs/index.html",
                   help="output HTML path (default: docs/index.html)")
    p.add_argument("-p", "--preset", action="append", default=None,
                   help="preset to include; repeatable (default: all)")
    p.add_argument("--presets-file", default=None,
                   help="YAML file defining custom presets")
    p.add_argument("--sources-file", default=None,
                   help="YAML file mapping gateway route prefixes to display names")
    p.add_argument("--json", dest="json_path", default=None,
                   help="also write a machine-readable JSON dump here")
    p.add_argument("--local-base", default=None,
                   help="base URL of a local OpenAI-compatible gateway "
                        "(overrides SCIPICK_LOCAL_BASE)")
    p.add_argument("--all-vendors", action="store_true",
                   help="include every model creator, not just the mainstream "
                        "allowlist in scipick/curate.py")
    p.add_argument("--all-generations", action="store_true",
                   help="include superseded generations, not just the latest "
                        "version of each product line")
    p.add_argument("--limit", type=int, default=60,
                   help="rows shown initially per view (default: 60; 0 = show "
                        "all at once). All rows are always rendered, so search "
                        "and sort cover the whole board either way.")
    p.add_argument("--list-presets", action="store_true",
                   help="list available presets and exit")
    p.add_argument("--open", action="store_true", dest="do_open",
                   help="open the result in a browser")
    p.add_argument("--version", action="version", version=f"scipick {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    presets = load_presets(args.presets_file)

    if args.list_presets:
        for key, preset in presets.items():
            weights = ", ".join(f"{k}={v}" for k, v in preset.weights.items())
            print(f"{key:12s} rank_by={preset.rank_by:10s} {weights}")
        return 0

    if args.preset:
        unknown = [k for k in args.preset if k not in presets]
        if unknown:
            print(f"error: unknown preset(s): {', '.join(unknown)}", file=sys.stderr)
            print(f"available: {', '.join(presets)}", file=sys.stderr)
            return 2
        presets = {k: presets[k] for k in args.preset}

    aa_key = os.environ.get("AA_API_KEY", "")
    if not aa_key:
        print(
            "error: AA_API_KEY is not set.\n"
            "       Get a key from https://artificialanalysis.ai and export it.",
            file=sys.stderr,
        )
        return 2

    local_base = args.local_base
    if local_base is None:
        local_base = os.environ.get("SCIPICK_LOCAL_BASE", "")

    print("fetching Artificial Analysis data...", file=sys.stderr)
    try:
        aa_models = fetch_aa_models(aa_key)
    except Exception as e:  # noqa: BLE001 - surface the real upstream error
        print(f"error: could not fetch AA data: {e}", file=sys.stderr)
        return 1

    local_models: dict[str, list[str]] = {}
    if local_base:
        print(f"probing local gateway at {local_base} ...", file=sys.stderr)
        try:
            local_models = fetch_local_models(local_base)
        except Exception as e:  # noqa: BLE001 - optional feature, do not fail the run
            print(f"warning: local gateway unreachable ({e}); continuing without it",
                  file=sys.stderr)

    models, unmatched, meta = collect(
        aa_models, local_models, presets,
        latest=not args.all_generations,
        mainstream_only=not args.all_vendors,
    )
    meta["local_base"] = local_base or None

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    source_labels = load_source_labels(args.sources_file)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    html_doc = render(models, presets, meta, generated, source_labels,
                      limit=(args.limit or None))
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_doc)

    rankable = sum(1 for m in models if m.get("science_fit_score") is not None)
    print(
        f"wrote {args.output} "
        f"({rankable} rankable models, {len(presets)} preset(s))",
        file=sys.stderr,
    )

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            f.write(render_json(models, presets, meta, generated))
        print(f"wrote {args.json_path}", file=sys.stderr)

    if args.do_open:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.run([opener, os.path.abspath(args.output)], check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
