"""Pol.is conversation importer.

This module provides helpers for fetching a conversation from the
`pol.is <https://pol.is/>`_ API and turning the top rated statements
into concept seeds.  The seeds can then be loaded into the knowledge
base or used to generate proof packs.

The public function :func:`fetch_conversation` performs the network
request, extracts the relevant fields and writes a seed file to
``DATA_DIR``.  It returns the list of seed mappings to allow callers to
further process the statements (for example, generating proof packs).

The format of the generated JSON file mirrors the structure used by the
rest of the project for concept seeds – a mapping containing a
``concepts`` list and an empty ``relations`` list.
"""

from __future__ import annotations

import json
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:  # pragma: no cover - handled in tests via monkeypatching
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

# ``DATA_DIR`` points to the default location where concept seed files
# should be written.  Tests can monkeypatch this path to redirect output
# to a temporary directory.
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "concepts"

POLIS_API = "https://pol.is/api/v3/conversations"

DEFAULT_MAX_RETRIES = int(os.environ.get("SENSIBLAW_MAX_RETRIES", 3))
DEFAULT_SLEEP_BETWEEN_RETRIES = float(os.environ.get("SENSIBLAW_SLEEP_BETWEEN_RETRIES", 1.0))

_REQUEST_CACHE: "OrderedDict[Tuple[str, str, Optional[int]], Dict]" = OrderedDict()
_MAX_CACHE_SIZE = 128


def _resolve_retry_config(
    max_retries: Optional[int], sleep_between_retries: Optional[float]
) -> Tuple[int, float]:
    resolved_max = (
        DEFAULT_MAX_RETRIES if max_retries is None else max(0, int(max_retries))
    )
    resolved_sleep = (
        DEFAULT_SLEEP_BETWEEN_RETRIES
        if sleep_between_retries is None
        else max(0.0, float(sleep_between_retries))
    )
    return resolved_max, resolved_sleep


def _cache_key(provider: str, term: str, limit: Optional[int]) -> Tuple[str, str, Optional[int]]:
    return provider, term, limit


def _get_cached_response(provider: str, term: str, limit: Optional[int]) -> Optional[Dict]:
    key = _cache_key(provider, term, limit)
    cached = _REQUEST_CACHE.get(key)
    if cached is not None:
        _REQUEST_CACHE.move_to_end(key)
    return cached


def _store_cached_response(provider: str, term: str, limit: Optional[int], data: Dict) -> None:
    key = _cache_key(provider, term, limit)
    _REQUEST_CACHE[key] = data
    _REQUEST_CACHE.move_to_end(key)
    while len(_REQUEST_CACHE) > _MAX_CACHE_SIZE:
        _REQUEST_CACHE.popitem(last=False)


def _get_with_retry(
    url: str,
    *,
    max_retries: Optional[int] = None,
    sleep_between_retries: Optional[float] = None,
) -> Dict:
    """Perform a GET request with retry/backoff and return JSON content."""

    if requests is None:  # pragma: no cover - optional dependency guard
        raise RuntimeError("requests library required for network operations")

    retries, sleep_between = _resolve_retry_config(max_retries, sleep_between_retries)
    attempt = 0

    while True:
        response = requests.get(url, timeout=30)
        status = getattr(response, "status_code", None)
        if status is None:
            response.raise_for_status()
        if status == 429 or (500 <= status < 600):
            attempt += 1
            if attempt > retries:
                response.raise_for_status()
            time.sleep(sleep_between * attempt)
            continue
        response.raise_for_status()
        return response.json()


def _statement_score(stmt: Dict) -> float:
    """Return a ranking score for a statement.

    The Pol.is API can expose a ``score`` field directly.  If it is not
    present we fall back to a simple agree/disagree differential which
    mimics the behaviour of the official analysis tools.
    """

    if "score" in stmt and isinstance(stmt["score"], (int, float)):
        return float(stmt["score"])
    agrees = stmt.get("agrees", 0)
    disagrees = stmt.get("disagrees", 0)
    return float(agrees) - float(disagrees)


def fetch_conversation(
    convo_id: str,
    *,
    limit: Optional[int] = None,
    max_retries: Optional[int] = None,
    sleep_between_retries: Optional[float] = None,
) -> List[Dict]:
    """Fetch a Pol.is conversation and write concept seeds.

    Parameters
    ----------
    convo_id:
        The Pol.is conversation identifier.

    limit:
        Optional maximum number of statements to include, ordered by score.
    max_retries:
        Override the maximum number of retries for HTTP 429/5xx responses.
        Falls back to the ``SENSIBLAW_MAX_RETRIES`` environment variable when
        omitted.
    sleep_between_retries:
        Base sleep interval between retries. Backoff increases linearly per
        attempt and defaults to ``SENSIBLAW_SLEEP_BETWEEN_RETRIES``.

    Returns
    -------
    List[Dict]
        A list of concept seed mappings with ``id``, ``label`` and
        ``cluster`` keys.
    """

    provider = "polis"
    url = f"{POLIS_API}/{convo_id}"
    cached = _get_cached_response(provider, convo_id, limit)
    if cached is None:
        data = _get_with_retry(
            url,
            max_retries=max_retries,
            sleep_between_retries=sleep_between_retries,
        )
        if limit is not None:
            trimmed = dict(data)
            trimmed["statements"] = data.get("statements", [])[:limit]
            data = trimmed
        _store_cached_response(provider, convo_id, limit, data)
    else:
        data = cached

    statements = data.get("statements", [])
    clusters = {c.get("id"): c for c in data.get("clusters", [])}

    # Order statements from highest to lowest score so that callers can
    # easily pick the top ranked item.
    ordered = sorted(statements, key=_statement_score, reverse=True)
    if limit is not None:
        ordered = ordered[:limit]

    seeds: List[Dict] = []
    for stmt in ordered:
        sid = str(stmt.get("id"))
        text = stmt.get("txt") or stmt.get("text") or ""
        cluster_id = stmt.get("cluster")
        cluster_label = None
        if cluster_id in clusters:
            cluster_label = clusters[cluster_id].get("name") or clusters[cluster_id].get(
                "label"
            )
        seed = {
            "id": f"polis_{convo_id}_{sid}",
            "label": text,
            "cluster": cluster_label,
        }
        seeds.append(seed)

    # Write the seeds to disk.  The structure mirrors the existing
    # ``concepts/seeds.json`` file used elsewhere in the project.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"polis_{convo_id}.json"
    payload = {"concepts": seeds, "relations": []}
    with out_file.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    return seeds


__all__ = ["fetch_conversation", "DATA_DIR"]
