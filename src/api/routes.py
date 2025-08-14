from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Any, List

try:  # pragma: no cover - FastAPI is optional for CLI tests
    from fastapi import APIRouter, HTTPException, Query
except ImportError:  # pragma: no cover
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
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

    def Query(*args, **kwargs):
        return None

try:  # pragma: no cover
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    class BaseModel:  # minimal stub when pydantic is absent
        pass

    def Field(*args, **kwargs):
        return None

from ..graph.models import LegalGraph
from ..tests.templates import TEMPLATE_REGISTRY

router = APIRouter()
_graph = LegalGraph()


def generate_subgraph(seed: str, hops: int) -> Dict[str, Any]:
    """Return a subgraph around ``seed`` up to ``hops`` hops."""
    if seed not in _graph.nodes:
        raise HTTPException(status_code=404, detail="Seed node not found")
    visited = {seed}
    nodes = {seed: _graph.nodes[seed]}
    edges = []
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
    return {
        "nodes": [asdict(n) for n in nodes.values()],
        "edges": [asdict(e) for e in edges],
    }


@router.get("/subgraph")
def subgraph_endpoint(
    seed: str = Query(..., description="Identifier for the seed node"),
    hops: int = Query(1, ge=1, le=5, description="Number of hops from seed"),
) -> Dict[str, Any]:
    return generate_subgraph(seed, hops)


class TestRunRequest(BaseModel):
    ids: List[str] = Field(..., description="List of test IDs to run")
    story: Dict[str, Any] = Field(..., description="Story data for evaluation")


def execute_tests(ids: List[str], story: Dict[str, Any]) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    for test_id in ids:
        template = TEMPLATE_REGISTRY.get(test_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Unknown test '{test_id}'")
        factors = {
            f.id: bool(story.get(f.id))
            for f in template.factors
        }
        results[test_id] = {
            "name": template.name,
            "factors": factors,
            "passed": all(factors.values()),
        }
    return {"results": results}


@router.post("/tests/run")
def tests_run_endpoint(payload: TestRunRequest) -> Dict[str, Any]:
    return execute_tests(payload.ids, payload.story)


_FAKE_TREATMENTS: Dict[str, List[Dict[str, Any]]] = {
    "case123": [
        # Intentionally out of order to exercise sorting logic
        {"citation": "2 CLR 50", "treatment": "distinguished"},
        {"citation": "1 CLR 1", "treatment": "followed"},
    ]
}


def fetch_case_treatment(case_id: str) -> Dict[str, Any]:
    treatments = _FAKE_TREATMENTS.get(case_id)
    if treatments is None:
        raise HTTPException(status_code=404, detail="Case not found")
    # Sort treatments deterministically by citation for stable CLI output
    ordered = sorted(treatments, key=lambda t: t["citation"])
    return {"case_id": case_id, "treatments": ordered}


@router.get("/cases/{case_id}/treatment")
def case_treatment_endpoint(case_id: str) -> Dict[str, Any]:
    return fetch_case_treatment(case_id)
