"""Thin presentation compatibility for AU/GWB follow surfaces.

These functions consume a relational query result and produce detached response
payloads. They do not construct semantic edges, choose admissibility, or accept a
prior JSON graph as input.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.storage.postgres.follow_projection_store import FollowProjectionQueryResult


def _summary(result: FollowProjectionQueryResult) -> dict[str, Any]:
    states: dict[str, int] = {}
    kinds: dict[str, int] = {}
    for row in result.edges:
        state = str(row.get("admissibility_state") or "undetermined")
        relation = str(row.get("relation_kind") or "unknown")
        states[state] = states.get(state, 0) + 1
        kinds[relation] = kinds.get(relation, 0) + 1
    return {
        "node_count": len(result.nodes),
        "edge_count": len(result.edges),
        "edge_admissibility_counts": dict(sorted(states.items())),
        "edge_kind_counts": dict(sorted(kinds.items())),
        "derived_only": True,
        "challengeable": True,
    }


def project_au_follow_surface(result: FollowProjectionQueryResult) -> dict[str, Any]:
    payload = result.presentation_payload()
    payload.update(
        {
            "version": "au.follow.presentation.v2",
            "profile": "au",
            "summary": _summary(result),
            "queue": [
                {
                    "item_id": str(row.get("edge_ref") or ""),
                    "title": f"{row.get('source_label')} → {row.get('target_label')}",
                    "relation_kind": row.get("relation_kind"),
                    "resolution_status": row.get("admissibility_state"),
                    "route_target": "au_follow_review",
                }
                for row in result.edges
                if str(row.get("admissibility_state") or "")
                in {"blocked", "undetermined"}
            ],
        }
    )
    return payload


def project_gwb_follow_surface(result: FollowProjectionQueryResult) -> dict[str, Any]:
    payload = result.presentation_payload()
    payload.update(
        {
            "version": "gwb.follow.presentation.v2",
            "profile": "gwb",
            "summary": _summary(result),
            "binding_edges": [
                dict(row)
                for row in result.edges
                if str(row.get("relation_kind") or "") in {"binds", "references"}
            ],
        }
    )
    return payload


def reject_nested_follow_graph_semantic_input(value: Mapping[str, Any]) -> None:
    if any(key in value for key in ("nodes", "edges", "legal_follow_graph")):
        raise ValueError(
            "nested follow graphs are presentation-only and cannot be semantic input"
        )


__all__ = [
    "project_au_follow_surface",
    "project_gwb_follow_surface",
    "reject_nested_follow_graph_semantic_input",
]
