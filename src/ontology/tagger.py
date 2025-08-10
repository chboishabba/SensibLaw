"""Utilities for tagging provisions with ontology-based labels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from ..models.provision import Provision

# Directory where ontology JSON files are stored.
ONTOLOGY_DIR = Path(__file__).resolve().parents[2] / "data" / "ontology"


def _load_ontology(filename: str) -> Dict[str, Dict[str, List[str]]]:
    """Load an ontology definition from a JSON file.

    The JSON file is expected to map tag names to a list of keywords.  The
    function returns the parsed dictionary or an empty mapping if the file is
    missing.
    """
    path = ONTOLOGY_DIR / filename
    if not path.exists():
        return {}
    with path.open() as f:
        return json.load(f)


# Load ontologies at module import time.  These serve as simple rule bases
# for the tagging process.  A real implementation could replace this with an
# ML model or more sophisticated pipeline.
LPO = _load_ontology("lpo.json").get("principles", {})
CCO = _load_ontology("cco.json").get("customs", {})


def _match_terms(text: str, mapping: Dict[str, List[str]]) -> List[str]:
    """Return tags whose associated keywords appear in the text."""
    lower = text.lower()
    return [tag for tag, kws in mapping.items() if any(kw.lower() in lower for kw in kws)]


def tag_provision(provision: Provision) -> Provision:
    """Assign principle and custom tags to a provision.

    The function mutates the provided :class:`Provision` instance and also
    returns it for convenience.
    """
    provision.principles = _match_terms(provision.text, LPO)
    provision.customs = _match_terms(provision.text, CCO)
    return provision


def tag_text(text: str) -> Provision:
    """Create and tag a provision directly from raw text."""
    return tag_provision(Provision(text=text))
