"""REST API route definitions using FastAPI.

This module exposes endpoints that mirror selected CLI commands. Each
endpoint returns JSON data and, when requested via the ``dot`` query
parameter, includes a Graphviz DOT representation of the result.
"""

from __future__ import annotations

import json
import subprocess
from typing import Dict

from fastapi import APIRouter, Query

from ..ontology.tagger import tag_text
from ..pipeline import build_cloud, match_concepts, normalise
from ..rules.extractor import extract_rules

router = APIRouter()


def _cloud_to_dot(cloud: Dict[str, int]) -> str:
    lines = ["digraph G {"]
    for node, count in cloud.items():
        lines.append(f'  "{node}" [label="{node} ({count})"]')
    lines.append("}")
    return "\n".join(lines)


def _rules_to_dot(rules: list[Dict[str, str]]) -> str:
    lines = ["digraph G {"]
    for i, rule in enumerate(rules):
        label = f"{rule['actor']} {rule['modality']} {rule['action']}"
        lines.append(f'  r{i} [label="{label}"]')
    lines.append("}")
    return "\n".join(lines)


def _provision_to_dot(provision: Dict[str, object]) -> str:
    lines = ["digraph G {", '  prov [label="Provision"]']
    for p in provision.get("principles", []):
        lines.append(f'  "{p}" [shape=box]')
        lines.append(f'  prov -> "{p}" [label="principle"]')
    for c in provision.get("customs", []):
        lines.append(f'  "{c}" [shape=ellipse]')
        lines.append(f'  prov -> "{c}" [label="custom"]')
    lines.append("}")
    return "\n".join(lines)


@router.get("/subgraph")
def get_subgraph(text: str = Query(..., description="Query text"), *, dot: bool = False) -> Dict[str, object]:
    """Return a simple concept cloud for ``text``.

    Parameters
    ----------
    text:
        Free-form query text.
    dot:
        When ``True`` include a Graphviz DOT representation.
    """
    normalised = normalise(text)
    concepts = match_concepts(normalised)
    cloud = build_cloud(concepts)
    result: Dict[str, object] = {"cloud": cloud}
    if dot:
        result["dot"] = _cloud_to_dot(cloud)
    return result


@router.get("/treatment")
def get_treatment(text: str = Query(..., description="Provision text"), *, dot: bool = False) -> Dict[str, object]:
    """Extract rules from provision ``text``."""
    rules = [r.__dict__ for r in extract_rules(text)]
    result: Dict[str, object] = {"rules": rules}
    if dot:
        result["dot"] = _rules_to_dot(rules)
    return result


@router.get("/provision")
def get_provision(text: str = Query(..., description="Provision text"), *, dot: bool = False) -> Dict[str, object]:
    """Tag a provision of law and return structured data."""
    provision = tag_text(text).to_dict()
    result: Dict[str, object] = {"provision": provision}
    if dot:
        result["dot"] = _provision_to_dot(provision)
    return result


@router.post("/tests/run")
def run_tests() -> Dict[str, object]:
    """Execute the pytest suite and return the result."""
    completed = subprocess.run(["pytest", "-q"], capture_output=True, text=True)
    output = completed.stdout + completed.stderr
    return {"exit_code": completed.returncode, "output": output}


__all__ = ["router"]
