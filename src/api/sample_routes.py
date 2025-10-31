"""Sample FastAPI routes for text analysis endpoints."""

from __future__ import annotations

from typing import Any, Dict, List

try:  # pragma: no cover - FastAPI is optional
    from fastapi import APIRouter, HTTPException, Query
except Exception:  # pragma: no cover
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            self.status_code = status_code
            self.detail = detail

    class APIRouter:  # minimal stub for testing without FastAPI
        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def Query(*args, **kwargs):  # type: ignore[misc]
        return None

from ontology.tagger import tag_text
from pipeline import build_cloud, match_concepts, normalise
from rules.extractor import extract_rules

router = APIRouter()


def _cloud_to_dot(cloud: Dict[str, int]) -> str:
    lines = ["digraph G {"]
    for node, count in cloud.items():
        lines.append(f'  "{node}" [label="{node} ({count})"]')
    lines.append("}")
    return "\n".join(lines)


def _rules_to_dot(rules: List[Dict[str, str]]) -> str:
    lines = ["digraph G {"]
    for i, rule in enumerate(rules):
        label = f"{rule['actor']} {rule['modality']} {rule['action']}"
        lines.append(f'  r{i} [label="{label}"]')
    lines.append("}")
    return "\n".join(lines)


def _provision_to_dot(provision: Dict[str, Any]) -> str:
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
def api_subgraph(
    text: str = Query(..., description="Query text"), *, dot: bool = False
) -> Dict[str, Any]:
    """Return a simple concept cloud for ``text``."""
    normalised = normalise(text)
    concepts = match_concepts(normalised)
    cloud = build_cloud(concepts)
    token_payload = [token.as_dict() for token in normalised.tokens]
    result: Dict[str, Any] = {"cloud": cloud, "tokens": token_payload}
    if dot:
        result["dot"] = _cloud_to_dot(cloud)
    return result


@router.get("/treatment")
def api_treatment(
    text: str = Query(..., description="Provision text"), *, dot: bool = False
) -> Dict[str, Any]:
    """Extract rules from provision ``text``."""
    rules = [r.__dict__ for r in extract_rules(text)]
    result: Dict[str, Any] = {"rules": rules}
    if dot:
        result["dot"] = _rules_to_dot(rules)
    return result


@router.get("/provision")
def api_provision(
    text: str = Query(..., description="Provision text"), *, dot: bool = False
) -> Dict[str, Any]:
    """Tag a provision of law and return structured data."""
    provision = tag_text(text).to_dict()
    result: Dict[str, Any] = {"provision": provision}
    if dot:
        result["dot"] = _provision_to_dot(provision)
    return result


__all__ = ["router", "api_subgraph", "api_treatment", "api_provision"]
