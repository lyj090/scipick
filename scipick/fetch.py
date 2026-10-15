"""Data acquisition: Artificial Analysis benchmarks, plus an optional local probe.

Two independent sources:

* :func:`fetch_aa_models` — always used. Benchmark scores, pricing and speed
  straight from the Artificial Analysis data API.
* :func:`fetch_local_models` — optional. Probes an OpenAI-compatible gateway
  (``/v1/models``) so the report can mark which models you can actually reach.
  Without it, scipick still produces a complete leaderboard.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from . import config


def http_get(url: str, headers: dict, timeout: int = 40, retries: int = 3):
    """GET + JSON decode, with backoff on transient upstream failures.

    Retries network errors and 5xx/429. Auth failures (401/403) are retried
    once then raised, since a bad key is worth reporting rather than hiding
    behind a timeout.
    """
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 404):
                raise
            if e.code in (401, 403) and attempt == retries - 1:
                raise
        except Exception as e:  # noqa: BLE001 - network jitter, timeouts
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise last if last is not None else RuntimeError("http_get failed")


def fetch_aa_models(api_key: str) -> list[dict]:
    """Full Artificial Analysis model list (benchmarks, pricing, speed)."""
    if not api_key:
        raise RuntimeError(
            "AA_API_KEY is not set. Get a key from artificialanalysis.ai and export it."
        )
    payload = http_get(config.AA_API, {"x-api-key": api_key})
    return payload.get("data", []) or []


def fetch_local_models(base: str | None = None, key: str | None = None) -> dict[str, list[str]]:
    """Probe a local OpenAI-compatible gateway, grouped by route prefix.

    Models whose ids contain ``/`` are treated as ``prefix/model``, so a gateway
    fronting several upstreams yields one bucket per upstream. Returns an empty
    mapping when no gateway is configured — that is a supported mode, not an
    error.
    """
    base = (base if base is not None else config.LOCAL_BASE).rstrip("/")
    if not base:
        return {}
    key = key if key is not None else config.LOCAL_KEY

    payload = http_get(f"{base}/v1/models", {"Authorization": f"Bearer {key}"})
    by_source: dict[str, list[str]] = {}
    for m in payload.get("data", []) or []:
        mid = str(m.get("id", ""))
        if not mid:
            continue
        if "/" in mid:
            source, name = mid.split("/", 1)
        else:
            source, name = "local", mid
        by_source.setdefault(source, []).append(name)
    return by_source


# --------------------------------------------------------------------------- #
# Name matching against the AA catalogue
# --------------------------------------------------------------------------- #

#: Reasoning-effort / speed suffixes that AA and gateways append to a base model
#: name. Stripped before matching so ``gpt-5-high`` finds ``GPT-5``.
_VARIANT_SUFFIX = re.compile(
    r"-(?:ultraspeed|openai-compact|compact|high|low|medium|max|xhigh"
    r"|thinking|reasoning|non-reasoning)$",
    re.I,
)


def norm(name: str) -> str:
    """Normalise a model name for comparison."""
    s = (name or "").lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("_", "-").replace(".", "-").replace(" ", "-")
    return re.sub(r"-+", "-", s).strip("-")


def strip_variant(name: str) -> str:
    """Drop parenthetical qualifiers and trailing effort/speed suffixes."""
    s = re.sub(r"\s*\([^)]*\)\s*$", "", (name or "").strip())
    return _VARIANT_SUFFIX.sub("", s)


def build_aa_index(aa_models: list[dict]) -> dict[str, list[dict]]:
    """Index AA models by both normalised slug and normalised name."""
    idx: dict[str, list[dict]] = {}
    for m in aa_models:
        for v in {norm(m.get("slug", "")), norm(m.get("name", ""))}:
            if v:
                idx.setdefault(v, []).append(m)
    return idx


def match_model(name: str, aa_idx: dict[str, list[dict]]) -> dict | None:
    """Find the AA entry for a gateway route name.

    Exact normalised match first, then a prefix match. When several AA entries
    collide (the same model at different reasoning efforts), prefer the one with
    the most populated benchmarks — that is the representative row.
    """
    n = strip_variant(norm(name))
    n = _VARIANT_SUFFIX.sub("", n)
    cands = aa_idx.get(n)
    if not cands:
        for k, v in aa_idx.items():
            if k.startswith(n) or n.startswith(k):
                cands = v
                break
    if not cands:
        return None
    return sorted(
        cands,
        key=lambda x: -sum(
            1 for v in (x.get("evaluations") or {}).values() if v is not None
        ),
    )[0]
