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


_PROVISION_ATOMS: Dict[str, Dict[str, Any]] = {
    "Provision#NTA:s223": {
        "provision_id": "Provision#NTA:s223",
        "title": "Native Title Act 1993 (Cth) s 223",
        "atoms": [
            {
                "id": "nta-s223-principle",
                "label": "Native title is recognised if laws and customs are acknowledged",
                "role": "principle",
                "proof": {"status": "proven", "confidence": 0.91, "evidenceCount": 3},
                "principle": {
                    "id": "nta-principle-1",
                    "title": "Continuity of traditional laws",
                    "summary": "Claimants must show continued acknowledgment of traditional laws and customs since sovereignty.",
                    "citation": "#/proof-tree/statute/Provision#NTA:s223",
                    "tags": ["continuity", "custom"],
                },
                "children": [
                    {
                        "id": "nta-s223-fact-1",
                        "label": "Elders gave testimony about ongoing ceremonies",
                        "role": "fact",
                        "proof": {"status": "proven", "confidence": 0.87},
                    },
                    {
                        "id": "nta-s223-fact-2",
                        "label": "Anthropological report contested on methodology",
                        "role": "fact",
                        "proof": {"status": "contested", "evidenceCount": 1},
                        "notes": "The opposing expert challenges the time depth of the survey interviews.",
                    },
                ],
            },
            {
                "id": "nta-s223-principle-2",
                "label": "The society must have a normative system",
                "role": "principle",
                "proof": {"status": "pending", "evidenceCount": 0},
                "principle": {
                    "id": "nta-principle-2",
                    "title": "Normative society",
                    "summary": "Proof requires demonstrating a body of rules that binds the claim group.",
                    "tags": ["society", "normative"],
                },
            },
        ],
    },
    "Provision#NTA:s225": {
        "provision_id": "Provision#NTA:s225",
        "title": "Native Title Act 1993 (Cth) s 225",
        "atoms": [
            {
                "id": "nta-s225-principle",
                "label": "Determinations must describe the nature and extent of native title rights",
                "role": "principle",
                "proof": {"status": "proven", "confidence": 0.78, "evidenceCount": 2},
                "principle": {
                    "id": "nta-principle-3",
                    "title": "Determination particulars",
                    "summary": "Orders identify rights, interests, and relationship to other interests in the determination area.",
                    "tags": ["determination", "interests"],
                },
            },
            {
                "id": "nta-s225-fact",
                "label": "Overlap with pastoral lease requires clarification",
                "role": "fact",
                "proof": {"status": "contested", "evidenceCount": 2},
                "notes": "Negotiations with the leaseholder are ongoing and unresolved.",
            },
        ],
    },
}


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


def fetch_provision_atoms(provision_id: str) -> Dict[str, Any]:
    """Return provision atoms ready for checklist rendering."""

    provision = _PROVISION_ATOMS.get(provision_id)
    if not provision:
        raise HTTPException(status_code=404, detail="Provision not found")
    return provision


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


@router.get("/provisions/{provision_id}/atoms")
def provision_atoms_endpoint(provision_id: str) -> Dict[str, Any]:
    return fetch_provision_atoms(provision_id)


__all__ = [
    "router",
    "generate_subgraph",
    "execute_tests",
    "fetch_case_treatment",
    "fetch_provision_atoms",
    "_graph",
    "WEIGHT",
    "RANK",
]

