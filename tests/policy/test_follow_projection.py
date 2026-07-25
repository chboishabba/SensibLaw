from __future__ import annotations

import pytest

from src.policy.follow_projection import build_follow_projection
from src.policy.follow_projection_compat import reject_nested_follow_graph_semantic_input


def test_follow_projection_is_deterministic_derived_and_closed() -> None:
    projection = build_follow_projection(
        document_ref="document:1",
        profile_ref="profile:test",
        scope_ref="document:1",
        projection_kind="legal",
        node_rows=(
            {
                "node_ref": "node:a",
                "node_kind": "semantic.claim",
                "label": "A",
                "factor_ref": "factor:a",
                "ordinal": 0,
            },
            {
                "node_ref": "node:b",
                "node_kind": "semantic.authority",
                "label": "B",
                "factor_ref": "factor:b",
                "ordinal": 1,
            },
        ),
        edge_rows=(
            {
                "edge_ref": "edge:a-b",
                "source_node_ref": "node:a",
                "target_node_ref": "node:b",
                "relation_kind": "cites",
                "admissibility_state": "blocked",
                "evidence_refs": ["evidence:2", "evidence:1", "evidence:1"],
                "provenance_refs": ["span:1"],
                "admissibility_ground_refs": ["ground:coverage"],
                "ordinal": 0,
            },
        ),
    )
    payload = projection.to_dict()
    assert payload["derived_only"] is True
    assert payload["challengeable"] is True
    assert payload["promotes_truth"] is False
    assert payload["execution_authority"] is False
    assert payload["edges"][0]["evidence_refs"] == ["evidence:1", "evidence:2"]
    assert projection.projection_ref == build_follow_projection(
        document_ref="document:1",
        profile_ref="profile:test",
        scope_ref="document:1",
        projection_kind="legal",
        node_rows=tuple(row.to_dict() for row in projection.nodes),
        edge_rows=tuple(row.to_dict() for row in projection.edges),
    ).projection_ref


def test_follow_projection_rejects_missing_endpoint() -> None:
    with pytest.raises(ValueError, match="endpoint"):
        build_follow_projection(
            document_ref="document:1",
            profile_ref="profile:test",
            scope_ref="document:1",
            projection_kind="legal",
            node_rows=(
                {
                    "node_ref": "node:a",
                    "node_kind": "semantic.claim",
                    "label": "A",
                    "ordinal": 0,
                },
            ),
            edge_rows=(
                {
                    "edge_ref": "edge:a-b",
                    "source_node_ref": "node:a",
                    "target_node_ref": "node:missing",
                    "relation_kind": "cites",
                    "admissibility_state": "blocked",
                    "ordinal": 0,
                },
            ),
        )


def test_nested_follow_graph_cannot_be_semantic_input() -> None:
    with pytest.raises(ValueError, match="presentation-only"):
        reject_nested_follow_graph_semantic_input({"nodes": [], "edges": []})
