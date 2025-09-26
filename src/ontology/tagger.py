"""Utilities for tagging text with ontology-based labels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from ..models.provision import Atom, Provision

# Directory where ontology JSON files are stored.
ONTOLOGY_DIR = Path(__file__).resolve().parents[2] / "data" / "ontology"


def _load_ontology(path: Path) -> Dict[str, List[str]]:
    """Load and normalise an ontology definition.

    Each ontology file is a JSON mapping of ontology names to a mapping of tag
    names and their associated keywords. The file may wrap the mapping in a
    single top-level key which is unwrapped for convenience.
    """
    with path.open() as f:
        data = json.load(f)
    # Unwrap a single top-level key if present
    if isinstance(data, dict) and len(data) == 1:
        data = next(iter(data.values()))
    return data


# Load all ontology definitions at import time.
ONTOLOGIES: Dict[str, Dict[str, List[str]]] = {}
for file in ONTOLOGY_DIR.glob("*.json"):
    try:
        ONTOLOGIES[file.stem] = _load_ontology(file)
    except Exception:
        ONTOLOGIES[file.stem] = {}


def _match_terms(text: str, mapping: Dict[str, List[str]]) -> List[str]:
    """Return tags whose associated keywords appear in the text."""
    lower = text.lower()
    return [tag for tag, kws in mapping.items() if any(kw.lower() in lower for kw in kws)]


def tag_provision(provision: Provision) -> Dict[str, List[str]]:
    """Populate ontology tags on an existing :class:`Provision`.

    The provision's ``principles`` and ``customs`` lists are updated in place
    based on matches from the loaded ontologies.  A mapping of ontology name to
    matching tags is returned for external use (e.g., document metadata).
    """

    tags: Dict[str, List[str]] = {}
    for name, mapping in ONTOLOGIES.items():
        matched = _match_terms(provision.text, mapping)
        if not matched:
            continue
        tags[name] = matched
        if name == "lpo":
            provision.principles = matched
            provision.atoms = [
                atom
                for atom in provision.atoms
                if not (atom.role == "principle" and atom.type == "ontology")
            ]
            provision.atoms.extend(
                Atom(type="ontology", role="principle", text=tag)
                for tag in matched
            )
        elif name == "cco":
            provision.customs = matched
    return tags


def tag_text(text: str) -> Provision:
    """Create and tag a :class:`Provision` from raw text."""

    provision = Provision(text=text)
    tag_provision(provision)
    return provision
