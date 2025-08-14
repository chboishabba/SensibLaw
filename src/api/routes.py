from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Any, List
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..graph.models import LegalGraph, GraphEdge
from ..tests.templates import TEMPLATE_REGISTRY

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


def fetch_case_treatment(case_id: str) -> Dict[str, Any]:
    """Aggregate treatments for ``case_id`` from incoming citations.

    Each incoming edge is expected to provide ``relation`` and ``court``
    metadata.  The contribution of an edge to its relation's total score is the
    product ``WEIGHT[relation] * RANK[court]``.  Relations are sorted in
    descending order of their accumulated totals and returned to the caller.
    """

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
