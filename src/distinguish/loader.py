"""Helpers for retrieving case silhouettes for distinction exercises."""

from __future__ import annotations

import json
from pathlib import Path

from .engine import CaseSilhouette, extract_case_silhouette

# Base directory of examples used in tests.  In a fuller system this would be
# replaced by a database or ingestion pipeline.
_EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "distinguish_glj"

# Mapping of neutral citations (case-insensitive) to silhouette files.
_CITATION_MAP = {
    "glj": _EXAMPLE_DIR / "glj_silhouette.json",
}


def load_case_silhouette(citation: str) -> CaseSilhouette:
    """Return the :class:`CaseSilhouette` for ``citation``.

    The current implementation is intentionally simple and only looks up a
    small set of example data shipped with the repository.  A ``KeyError`` is
    raised if the citation is unknown.
    """

    path = _CITATION_MAP.get(citation.lower())
    if path is None or not path.exists():
        raise KeyError(f"Unknown case citation: {citation}")

    data = json.loads(path.read_text())
    paragraphs = data.get("paragraphs", [])
    silhouette = extract_case_silhouette(paragraphs)
    # Allow explicit fact/holding tags from the JSON to override heuristics
    silhouette.fact_tags = data.get("fact_tags", silhouette.fact_tags)
    silhouette.holding_hints = data.get("holding_hints", silhouette.holding_hints)
    return silhouette
