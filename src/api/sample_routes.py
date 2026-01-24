"""Sample FastAPI routes for text analysis endpoints."""

from __future__ import annotations

import sqlite3
from pathlib import Path
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

try:
    from src import logic_tree
except Exception:
    import logic_tree  # type: ignore

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


def _logic_tree_search(
    query: str,
    *,
    limit: int = 20,
    use_offsets: bool = True,
    sqlite_path: str | Path | None = None,
) -> List[Dict[str, Any]]:
    path = Path(sqlite_path) if sqlite_path is not None else Path("artifacts/logic_tree.sqlite")
    if not path.exists():
        raise HTTPException(status_code=404, detail="logic tree SQLite database not found")
    try:
        conn = sqlite3.connect(path)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        return logic_tree.search_fts_over_logic_tree(conn, query, limit=limit, use_offsets=use_offsets)
    finally:
        conn.close()


@router.get("/logic-tree/search")
def api_logic_tree_search(
    query: str = Query(..., description="Search expression"),
    limit: int = 20,
    use_offsets: bool = True,
    sqlite_path: str | None = None,
) -> Dict[str, Any]:
    """Search logic tree FTS index and return doc/node hits."""

    results = _logic_tree_search(query, limit=limit, use_offsets=use_offsets, sqlite_path=sqlite_path)
    return {"results": results}


__all__ = [
    "router",
    "api_subgraph",
    "api_treatment",
    "api_provision",
    "api_logic_tree_search",
    "_logic_tree_search",
]
