from __future__ import annotations

from typing import Any, Dict, Optional

from .models import EdgeType, ExtrinsicNode, GraphEdge, LegalGraph, NodeType

# Basic weighting rules for roles and legislative stages.
ROLE_WEIGHTS: Dict[str, float] = {
    "minister": 2.0,
    "shadow minister": 1.5,
    "backbencher": 1.0,
}

STAGE_WEIGHTS: Dict[str, float] = {
    "1st reading": 1.0,
    "first reading": 1.0,
    "2nd reading": 1.5,
    "second reading": 1.5,
    "committee": 1.2,
    "3rd reading": 1.1,
    "third reading": 1.1,
}


def compute_weight(role: str, stage: str) -> float:
    """Return a numeric weight from the supplied role and stage."""
    role_weight = ROLE_WEIGHTS.get(role.lower(), 1.0)
    stage_weight = STAGE_WEIGHTS.get(stage.lower(), 1.0)
    return role_weight * stage_weight


def ingest_extrinsic(
    graph: LegalGraph,
    *,
    identifier: str,
    role: str,
    stage: str,
    target: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> ExtrinsicNode:
    """Create an ``ExtrinsicNode`` and connect it to a target with weighted edge."""
    node = ExtrinsicNode(
        type=NodeType.EXTRINSIC,
        identifier=identifier,
        role=role,
        stage=stage,
        metadata=metadata or {},
    )
    graph.add_node(node)
    weight = compute_weight(role, stage)
    edge = GraphEdge(
        type=EdgeType.RELATED_TO,
        source=identifier,
        target=target,
        weight=weight,
    )
    graph.add_edge(edge)
    return node


__all__ = ["ingest_extrinsic", "compute_weight", "ROLE_WEIGHTS", "STAGE_WEIGHTS"]
