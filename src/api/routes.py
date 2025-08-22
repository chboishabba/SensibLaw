from __future__ import annotations

from typing import Dict, Any, List

from collections import defaultdict

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

from ..graph.models import LegalGraph, GraphEdge
from ..graph.api import serialize_graph
from ..tests.templates import TEMPLATE_REGISTRY
from ..policy.engine import PolicyEngine

# Ranking of courts and weighting of relations when computing treatment scores.
# Higher values indicate greater persuasive authority.
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

router = APIRouter()
_graph = LegalGraph()

_policy = PolicyEngine({"if": "SACRED_DATA", "then": "require", "else": "allow"})


def generate_subgraph(seed: str, hops: int, consent: bool = False) -> Dict[str, Any]:
    """Return a subgraph around ``seed`` up to ``hops`` hops."""

def generate_subgraph(seed: str, hops: int, reduced: bool = False) -> Dict[str, Any]:
    """Return a subgraph around ``seed`` up to ``hops`` hops.

    When ``reduced`` is ``True`` the returned edge set has undergone a
    transitive reduction to remove edges that are implied by transitivity.
    """
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
    result_nodes = []
    for n in nodes.values():
        enforced = _policy.enforce(n, consent=consent)
        if enforced:
            result_nodes.append(asdict(enforced))
    return {"nodes": result_nodes, "edges": [asdict(e) for e in edges]}


    subgraph = LegalGraph()
    for node in nodes.values():
        subgraph.add_node(node)
    for edge in edges:
        subgraph.add_edge(edge)

    return serialize_graph(subgraph, reduced=reduced)


@router.get("/subgraph")
def subgraph_endpoint(
    seed: str = Query(..., description="Identifier for the seed node"),
    hops: int = Query(1, ge=1, le=5, description="Number of hops from seed"),
    consent: bool = Query(
        False, description="Consent granted to view sacred data"
    ),
) -> Dict[str, Any]:
    return generate_subgraph(seed, hops, consent)

    reduced: bool = Query(
        False, description="Apply transitive reduction to edge set"
    ),
) -> Dict[str, Any]:
    return generate_subgraph(seed, hops, reduced)


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
    """Aggregate treatments for ``case_id`` from incoming citations.

    Each incoming edge is expected to provide ``relation`` and ``court``
    metadata.  The contribution of an edge to its relation's total score is the
    product ``WEIGHT[relation] * RANK[court]``.  Relations are sorted in
    descending order of their accumulated totals and returned to the caller.
    """

    if case_id not in _graph.nodes:
        raise HTTPException(status_code=404, detail="Case not found")
    # Sort treatments deterministically by citation for stable CLI output
    ordered = sorted(treatments, key=lambda t: t["citation"])
    return {"case_id": case_id, "treatments": ordered}


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

    if not totals:
        raise HTTPException(status_code=404, detail="Case not found")

    records: List[Dict[str, Any]] = []
    for relation, total in totals.items():
        records.append(
            {
                "treatment": relation,
                "count": counts[relation],
                "total": total,
            }
        )

    records.sort(key=lambda r: r["total"], reverse=True)
    return {"case_id": case_id, "treatments": records}


@router.get("/cases/{case_id}/treatment")
def case_treatment_endpoint(case_id: str) -> Dict[str, Any]:
    return fetch_case_treatment(case_id)
