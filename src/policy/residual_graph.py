"""Deterministic typed residual-graph construction.

This deliberately stops before clustering or spectral analysis.  Every edge is
explained as admissible similarity, incompatibility, masked analogy, or
coverage unknown so later global analysis cannot erase its evidence boundary.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping, Sequence

from .residual_profiles import TYPED_RESIDUAL_PROFILE_SCHEMA_VERSION


TYPED_RESIDUAL_GRAPH_SCHEMA_VERSION = "sl.typed_residual_graph.v0_1"
EDGE_KINDS = frozenset(
    {
        "positive_similarity",
        "negative_incompatibility",
        "masked_analogy",
        "unknown_due_to_coverage",
    }
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _states(profile: Mapping[str, Any]) -> dict[str, str]:
    return {
        _text(row.get("feature")): _text(row.get("state"))
        for row in profile.get("feature_vector", [])
        if isinstance(row, Mapping) and _text(row.get("feature"))
    }


def _edge(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_ref = _text(left.get("candidate_ref"))
    right_ref = _text(right.get("candidate_ref"))
    left_state = _text(left.get("comparison_state"))
    right_state = _text(right.get("comparison_state"))
    if "unknown" in {left_state, right_state}:
        kind, reason = "unknown_due_to_coverage", "coverage_or_context_unknown"
    elif "masked" in {left_state, right_state}:
        kind, reason = "masked_analogy", "context_admissibility_failed"
    else:
        left_features, right_features = _states(left), _states(right)
        shared = sorted(set(left_features) & set(right_features))
        contradictory = [
            feature
            for feature in shared
            if {left_features[feature], right_features[feature]}
            == {"exact", "contradictory"}
        ]
        if contradictory:
            kind, reason = "negative_incompatibility", "opposed_residual_states"
        else:
            kind, reason = "positive_similarity", "admissible_residual_comparison"
    return {
        "left_candidate_ref": left_ref,
        "right_candidate_ref": right_ref,
        "edge_kind": kind,
        "reason": reason,
        "shared_features": sorted(set(_states(left)) & set(_states(right))),
        "left_comparison_state": left_state,
        "right_comparison_state": right_state,
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
    }


def build_typed_residual_graph(
    profiles: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a bounded, deterministic graph from generic residual profiles."""

    nodes = [dict(profile) for profile in profiles if isinstance(profile, Mapping)]
    for node in nodes:
        if _text(node.get("schema_version")) != TYPED_RESIDUAL_PROFILE_SCHEMA_VERSION:
            raise ValueError("typed residual graph requires typed residual profiles")
        if not _text(node.get("candidate_ref")):
            raise ValueError("typed residual profile node requires candidate_ref")
    nodes.sort(key=lambda node: _text(node.get("candidate_ref")))
    if len({_text(node.get("candidate_ref")) for node in nodes}) != len(nodes):
        raise ValueError("typed residual graph requires unique candidate refs")
    edges = [_edge(left, right) for left, right in combinations(nodes, 2)]
    edges.sort(
        key=lambda edge: (edge["left_candidate_ref"], edge["right_candidate_ref"])
    )
    return {
        "schema_version": TYPED_RESIDUAL_GRAPH_SCHEMA_VERSION,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "counts_by_kind": {
                kind: sum(1 for edge in edges if edge["edge_kind"] == kind)
                for kind in sorted(EDGE_KINDS)
            },
        },
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }


__all__ = [
    "EDGE_KINDS",
    "TYPED_RESIDUAL_GRAPH_SCHEMA_VERSION",
    "build_typed_residual_graph",
]
