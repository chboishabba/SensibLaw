"""REST API route definitions using FastAPI."""

from __future__ import annotations

import subprocess
from dataclasses import asdict
from datetime import date
from math import exp
from typing import Any, Dict, List, Optional, Tuple

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

from ..graph.models import EdgeType, LegalGraph, GraphEdge, GraphNode, NodeType
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
# Ranking configuration -----------------------------------------------------

COURT_RANK: Dict[str, float] = {
    "HCA": 5.0,
    "FCAFC": 4.0,
    "FCA": 3.0,
    "FCCA": 3.0,
    "FCC": 3.0,
    "FEDCRTS": 3.0,
    "FAMILY COURT": 4.0,
    "FAMCA": 4.0,
    "FAMCAFC": 4.0,
    "FAMCT": 4.0,
    "SINGLE-JUDGE": 3.0,
    "TRIAL": 3.0,
    "MAG": 2.0,
}

RELATION_WEIGHT: Dict[str, float] = {
    "FOLLOWS": 3.0,
    "APPLIES": 2.0,
    "CONSIDERS": 1.0,
    "DISTINGUISHES": -1.0,
    "OVERRULES": -3.0,
}

# Backwards compatible aliases retained for tests importing the legacy names.
RANK = COURT_RANK
WEIGHT = RELATION_WEIGHT

_COURT_FAMILY: Dict[str, str] = {
    "HCA": "HCA",
    "FCA": "Federal",
    "FCAFC": "Federal",
    "FCC": "Federal",
    "FCCA": "Federal",
    "FEDCRTS": "Federal",
    "FAMILY COURT": "Family",
    "FAMCA": "Family",
    "FAMCAFC": "Family",
    "FAMCT": "Family",
    "SINGLE-JUDGE": "Trial",
    "TRIAL": "Trial",
    "MAG": "Magistrates",
}

_ADJACENT_FAMILIES: Dict[str, Tuple[str, ...]] = {
    "HCA": ("Federal", "Family"),
    "Federal": ("HCA", "Family", "Trial"),
    "Family": ("HCA", "Federal"),
    "Trial": ("Federal", "Magistrates"),
    "Magistrates": ("Trial",),
}

POSTURE_MATCH_BOOST = 1.2
POSTURE_MISMATCH_FACTOR = 0.8

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


def _normalise_court(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip().upper()


def _court_rank(court: Optional[str]) -> float:
    if court is None:
        return 0.0
    return COURT_RANK.get(court, COURT_RANK.get(court.replace(" ", ""), 0.0))


def _court_family_for(court: Optional[str]) -> Optional[str]:
    if court is None:
        return None
    key = court.replace(" ", "").upper()
    return _COURT_FAMILY.get(key, None)


def _jurisdiction_fit(source_court: Optional[str], target_court: Optional[str]) -> float:
    source_family = _court_family_for(source_court)
    target_family = _court_family_for(target_court)
    if source_family is None or target_family is None:
        return 0.4
    if source_family == target_family:
        return 1.0
    adjacent = _ADJACENT_FAMILIES.get(source_family, ())
    if target_family in adjacent:
        return 0.7
    return 0.4


def _posture_fit(source_posture: Optional[str], target_posture: Optional[str]) -> float:
    if not source_posture or not target_posture:
        return 1.0
    if source_posture.lower() == target_posture.lower():
        return POSTURE_MATCH_BOOST
    return POSTURE_MISMATCH_FACTOR


def _relation_value(relation: Optional[str]) -> float:
    if relation is None:
        return 0.0
    return RELATION_WEIGHT.get(relation.upper(), 0.0)


def _recency_decay(
    source_date: Optional[date], target_date: Optional[date]
) -> Tuple[float, float]:
    if not source_date or not target_date:
        return 1.0, 0.0
    days = (source_date - target_date).days
    years = max(0.0, days / 365.25)
    return exp(-years / 6.0), years


def _pinpoint_from_metadata(meta: Dict[str, Any]) -> Optional[str]:
    for key in ("pinpoint", "pin_cite", "pin", "paragraph", "paragraphs"):
        if key in meta:
            value = meta[key]
            if isinstance(value, (list, tuple)):
                return ", ".join(str(v) for v in value)
            return str(value)
    return None


def _factor_alignment(meta: Dict[str, Any]) -> Optional[str]:
    for key in ("factor_alignment", "factor", "s60cc"):
        if key in meta and meta[key]:
            return str(meta[key])
    return None


def fetch_case_treatment(case_id: str) -> Dict[str, Any]:
    """Aggregate treatments for ``case_id`` from incoming citations."""
    if case_id not in _graph.nodes:
        raise HTTPException(status_code=404, detail="Case not found")

    target_node = _graph.get_node(case_id)
    target_court = None
    target_posture = None
    target_date = None
    if target_node:
        target_court = _normalise_court(target_node.metadata.get("court"))
        target_posture = target_node.metadata.get("posture")
        target_date = target_node.date

    authorities: List[Dict[str, Any]] = []
    for edge in _graph.find_edges(target=case_id):
        relation = edge.metadata.get("relation")
        court = _normalise_court(edge.metadata.get("court") or edge.metadata.get("jurisdiction"))
        if relation is None or court is None:
            continue

        source_node = _graph.get_node(edge.source)
        source_date = source_node.date if source_node else None
        recency, years = _recency_decay(source_date, target_date)
        relation_weight = _relation_value(relation)
        court_rank = _court_rank(court)
        jurisdiction_fit = _jurisdiction_fit(court, target_court)
        posture_fit = _posture_fit(
            edge.metadata.get("posture") or (source_node.metadata.get("posture") if source_node else None),
            target_posture,
        )

        score = court_rank * relation_weight * recency * jurisdiction_fit * posture_fit

        if source_node is not None:
            citation = source_node.metadata.get("citation")
            title = source_node.metadata.get("title")
        else:
            citation = None
            title = None
        pinpoint = _pinpoint_from_metadata(edge.metadata)
        factor = _factor_alignment(edge.metadata)
        components = {
            "court_rank": court_rank,
            "relation_weight": relation_weight,
            "recency_decay": recency,
            "jurisdiction_fit": jurisdiction_fit,
            "posture_fit": posture_fit,
        }

        authorities.append(
            {
                "authority_id": edge.source,
                "neutral_citation": citation,
                "title": title,
                "relationship": relation.upper(),
                "score": score,
                "components": components,
                "pinpoint": pinpoint,
                "factor_alignment": factor,
                "years_since": years,
                "flag_inapposite": jurisdiction_fit <= 0.4 or posture_fit < 1.0,
                "court": court,
                "posture": edge.metadata.get("posture")
                or (source_node.metadata.get("posture") if source_node else None),
            }
        )

    if not authorities:
        raise HTTPException(status_code=404, detail="Case not found")

    authorities.sort(
        key=lambda record: (
            -record["score"],
            -record["components"]["court_rank"],
            -record["components"]["relation_weight"],
            record.get("neutral_citation") or record["authority_id"],
        )
    )

    supportive = [rec for rec in authorities if rec["score"] > 0]
    if supportive:
        lines = ["Consider emphasising:"]
        for rec in supportive[:3]:
            cite = rec.get("neutral_citation") or rec["authority_id"]
            factor = rec.get("factor_alignment") or "overall discretion"
            lines.append(
                f"- {cite} ({rec['relationship'].lower()} – supports {factor}, score {rec['score']:.2f})"
            )
        what_to_cite_next = "\n".join(lines)
    else:
        what_to_cite_next = "No supportive authorities met the ranking criteria."

    return {
        "case_id": case_id,
        "authorities": authorities,
        "what_to_cite_next": what_to_cite_next,
    }


def ensure_sample_treatment_graph() -> None:
    """Populate the in-memory graph with sample treatment data if empty."""

    if _graph.nodes:
        return

    target_id = "case123"
    _graph.add_node(
        GraphNode(
            type=NodeType.DOCUMENT,
            identifier=target_id,
            metadata={
                "citation": "[2014] FamCA 1",
                "title": "Sample Parenting Matter",
                "court": "FamCA",
                "posture": "final",
            },
            date=date(2014, 1, 1),
        )
    )

    citing_cases = [
        (
            "caseA",
            {
                "citation": "[2015] HCA 10",
                "title": "High Court guidance",
                "court": "HCA",
                "posture": "final",
            },
            {
                "relation": "FOLLOWS",
                "court": "HCA",
                "pinpoint": "¶ 42",
                "factor": "s 60CC(2)(a)",
                "posture": "final",
            },
            date(2015, 6, 1),
        ),
        (
            "caseB",
            {
                "citation": "[2016] FamCAFC 50",
                "title": "Family Court of Appeal consideration",
                "court": "FAMCAFC",
                "posture": "final",
            },
            {
                "relation": "APPLIES",
                "court": "FAMCAFC",
                "pinpoint": "¶¶ 12-15",
                "factor": "s 60CC(2)(b)",
                "posture": "final",
            },
            date(2016, 3, 15),
        ),
    ]

    for identifier, node_meta, edge_meta, node_date in citing_cases:
        _graph.add_node(
            GraphNode(
                type=NodeType.DOCUMENT,
                identifier=identifier,
                metadata=node_meta,
                date=node_date,
            )
        )
        _graph.add_edge(
            GraphEdge(
                type=EdgeType.CITES,
                source=identifier,
                target=target_id,
                metadata=edge_meta,
            )
        )


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
    "ensure_sample_treatment_graph",
    "fetch_provision_atoms",
    "_graph",
    "WEIGHT",
    "RANK",
    "COURT_RANK",
    "RELATION_WEIGHT",
    "POSTURE_MATCH_BOOST",
    "POSTURE_MISMATCH_FACTOR",
]

