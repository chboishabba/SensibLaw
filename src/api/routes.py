from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Any, List
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..graph.models import LegalGraph, GraphEdge
from ..tests.templates import TEMPLATE_REGISTRY
from ..policy.engine import PolicyEngine

router = APIRouter()
_graph = LegalGraph()

_policy = PolicyEngine({"if": "SACRED_DATA", "then": "require", "else": "allow"})


def generate_subgraph(seed: str, hops: int, consent: bool = False) -> Dict[str, Any]:
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
    result_nodes = []
    for n in nodes.values():
        enforced = _policy.enforce(n, consent=consent)
        if enforced:
            result_nodes.append(asdict(enforced))
    return {"nodes": result_nodes, "edges": [asdict(e) for e in edges]}


@router.get("/subgraph")
def subgraph_endpoint(
    seed: str = Query(..., description="Identifier for the seed node"),
    hops: int = Query(1, ge=1, le=5, description="Number of hops from seed"),
    consent: bool = Query(
        False, description="Consent granted to view sacred data"
    ),
) -> Dict[str, Any]:
    return generate_subgraph(seed, hops, consent)


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


def fetch_case_treatment(case_id: str) -> Dict[str, Any]:
    """Aggregate treatments for ``case_id`` from the global graph.

    The function scans all edges in :data:`_graph` that involve the target case
    either as a source or a target.  Edges are expected to carry ``treatment``
    and ``citation`` metadata along with an optional ``weight`` attribute.

    For each treatment category the number of citations is counted and the
    citation with the highest weight is selected.  The resulting categories are
    sorted in descending order of that weight.
    """

    if case_id not in _graph.nodes:
        raise HTTPException(status_code=404, detail="Case not found")

    grouped: Dict[str, List[GraphEdge]] = defaultdict(list)
    for edge in _graph.edges:
        if case_id not in (edge.source, edge.target):
            continue
        treatment = edge.metadata.get("treatment")
        citation = edge.metadata.get("citation")
        if not treatment or not citation:
            continue
        grouped[treatment].append(edge)

    if not grouped:
        raise HTTPException(status_code=404, detail="Case not found")

    records: List[Dict[str, Any]] = []
    for treatment, edges in grouped.items():
        count = len(edges)
        best = max(edges, key=lambda e: e.weight)
        records.append(
            {
                "treatment": treatment,
                "count": count,
                "citation": best.metadata.get("citation"),
                "weight": best.weight,
            }
        )

    records.sort(key=lambda r: r["weight"], reverse=True)
    return {"case_id": case_id, "treatments": records}


@router.get("/cases/{case_id}/treatment")
def case_treatment_endpoint(case_id: str) -> Dict[str, Any]:
    return fetch_case_treatment(case_id)
