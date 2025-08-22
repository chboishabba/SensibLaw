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
from pathlib import Path
from typing import Dict, List

try:  # pragma: no cover - handled in tests via monkeypatching
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

# ``DATA_DIR`` points to the default location where concept seed files
# should be written.  Tests can monkeypatch this path to redirect output
# to a temporary directory.
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "concepts"

POLIS_API = "https://pol.is/api/v3/conversations"


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


def fetch_conversation(convo_id: str) -> List[Dict]:
    """Fetch a Pol.is conversation and write concept seeds.

    Parameters
    ----------
    convo_id:
        The Pol.is conversation identifier.

    Returns
    -------
    List[Dict]
        A list of concept seed mappings with ``id``, ``label`` and
        ``cluster`` keys.
    """

    url = f"{POLIS_API}/{convo_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    statements = data.get("statements", [])
    clusters = {c.get("id"): c for c in data.get("clusters", [])}

    # Order statements from highest to lowest score so that callers can
    # easily pick the top ranked item.
    ordered = sorted(statements, key=_statement_score, reverse=True)

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
