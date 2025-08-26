"""REST API route definitions using FastAPI."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from dataclasses import asdict
from typing import Any, Dict, List

try:  # pragma: no cover - FastAPI is optional for CLI tests
    from fastapi import APIRouter, HTTPException
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

        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

try:  # pragma: no cover
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover
    class BaseModel:  # minimal stub when pydantic is absent
        pass

    def Field(*args, **kwargs):  # type: ignore[misc]
        return None

from ..graph.models import LegalGraph, GraphEdge
from ..tests.templates import TEMPLATE_REGISTRY
from ..policy.engine import PolicyEngine

router = APIRouter()


@router.post("/tests/run")
def run_tests() -> Dict[str, Any]:
    """Execute the pytest suite and return the result."""
    completed = subprocess.run(["pytest", "-q"], capture_output=True, text=True)
    output = completed.stdout + completed.stderr
    return {"exit_code": completed.returncode, "output": output}


# Additional utility functions used by the CLI and tests
RANK: Dict[str, float] = {
    "HCA": 3.0,
    "FCA": 2.0,
    "NSWCA": 1.0,
}

WEIGHT: Dict[str, float] = {
    "followed": 2.0,
    "distinguished": 1.0,
    "overruled": 3.0,
}

_graph = LegalGraph()
_policy = PolicyEngine({"if": "SACRED_DATA", "then": "require", "else": "allow"})


def generate_subgraph(seed: str, hops: int, consent: bool = False) -> Dict[str, Any]:
    """Return a subgraph around ``seed`` up to ``hops`` hops."""
    if seed not in _graph.nodes:
        raise HTTPException(status_code=404, detail="Seed node not found")
    visited = {seed}
    nodes = {seed: _graph.nodes[seed]}
    edges: List[GraphEdge] = []
    frontier = [(seed, 0)]
    while frontier:
        current, depth = frontier.pop(0)
        if depth >= hops:
            continue
        for edge in _graph.find_edges(source=current):
            edges.append(edge)
            tgt = edge.target
            if tgt not in visited:
                visited.add(tgt)
                nodes[tgt] = _graph.nodes[tgt]
                frontier.append((tgt, depth + 1))
    result_nodes = []
    for n in nodes.values():
        enforced = _policy.enforce(n, consent=consent)
        if enforced:
            result_nodes.append(asdict(enforced))
    return {"nodes": result_nodes, "edges": [asdict(e) for e in edges]}


class TestRunRequest(BaseModel):
    ids: List[str] = Field(..., description="List of test IDs to run")
    story: Dict[str, Any] = Field(..., description="Story data for evaluation")


def execute_tests(ids: List[str], story: Dict[str, Any]) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    for test_id in ids:
        template = TEMPLATE_REGISTRY.get(test_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Unknown test '{test_id}'")
        factors = {f.id: bool(story.get(f.id)) for f in template.factors}
        results[test_id] = {
            "name": template.name,
            "factors": factors,
            "passed": all(factors.values()),
        }
    return {"results": results}


def fetch_case_treatment(case_id: str) -> Dict[str, Any]:
    """Aggregate treatments for ``case_id`` from incoming citations."""
    if case_id not in _graph.nodes:
        raise HTTPException(status_code=404, detail="Case not found")

    totals: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)
    for edge in _graph.find_edges(target=case_id):
        relation = edge.metadata.get("relation")
        court = edge.metadata.get("court")
        if relation is None or court is None:
            continue
        weight = WEIGHT.get(relation, 0.0)
        rank = RANK.get(court, 0.0)
        contribution = weight * rank
        totals[relation] += contribution
        counts[relation] += 1

    records: List[Dict[str, Any]] = [
        {
            "treatment": relation,
            "count": counts[relation],
            "total": total,
        }
        for relation, total in totals.items()
    ]

    if not records:
        raise HTTPException(status_code=404, detail="Case not found")

    # Sort by total descending and treatment name for deterministic order
    records.sort(key=lambda r: (-r["total"], r["treatment"]))
    return {"case_id": case_id, "treatments": records}


@router.get("/cases/{case_id}/treatment")
def case_treatment_endpoint(case_id: str) -> Dict[str, Any]:
    return fetch_case_treatment(case_id)


__all__ = [
    "router",
    "generate_subgraph",
    "execute_tests",
    "fetch_case_treatment",
    "_graph",
    "WEIGHT",
    "RANK",
]

