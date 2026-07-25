from __future__ import annotations

import os

import pytest

from src.policy.follow_projection import build_follow_projection
from src.storage.postgres.follow_projection_store import (
    persist_follow_projection,
    query_follow_projection,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="PostgreSQL DATABASE_URL required"
)


def _connect():
    import psycopg

    return psycopg.connect(os.environ["DATABASE_URL"])


def test_follow_projection_persists_parent_first_and_queries_relational_rows() -> None:
    projection = build_follow_projection(
        document_ref="document:follow-store",
        profile_ref="profile:test",
        scope_ref="document:follow-store",
        projection_kind="legal",
        node_rows=(
            {
                "node_ref": "node:source",
                "node_kind": "semantic.claim",
                "label": "Source",
                "factor_ref": "factor:source",
                "ordinal": 0,
            },
            {
                "node_ref": "node:target",
                "node_kind": "semantic.authority",
                "label": "Target",
                "factor_ref": "factor:target",
                "ordinal": 1,
            },
        ),
        edge_rows=(
            {
                "edge_ref": "edge:source-target",
                "source_node_ref": "node:source",
                "target_node_ref": "node:target",
                "relation_kind": "cites",
                "admissibility_state": "blocked",
                "evidence_refs": ["evidence:1"],
                "provenance_refs": ["span:1"],
                "admissibility_ground_refs": ["coverage:open"],
                "ordinal": 0,
            },
        ),
    )
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO algebra.factor(factor_ref, document_ref, factor_type_ref)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
                """,
                [
                    ("factor:source", "document:follow-store", "semantic.claim"),
                    ("factor:target", "document:follow-store", "semantic.authority"),
                ],
            )
            projection_ref = persist_follow_projection(cursor, projection)
        connection.commit()
        with connection.cursor() as cursor:
            queried = query_follow_projection(cursor, projection_ref)
    assert len(queried.nodes) == 2
    assert len(queried.edges) == 1
    assert queried.edges[0]["derived_only"] is True
    assert queried.edges[0]["promotes_truth"] is False
    assert queried.presentation_payload()["semantic_input_allowed"] is False


def test_follow_projection_rejects_non_durable_factor_parent() -> None:
    projection = build_follow_projection(
        document_ref="document:follow-store-missing",
        profile_ref="profile:test",
        scope_ref="document:follow-store-missing",
        projection_kind="nonlegal",
        node_rows=(
            {
                "node_ref": "node:missing",
                "node_kind": "semantic.claim",
                "label": "Missing",
                "factor_ref": "factor:not-persisted",
                "ordinal": 0,
            },
        ),
        edge_rows=(),
    )
    with _connect() as connection:
        with connection.cursor() as cursor:
            with pytest.raises(ValueError, match="non-durable factor refs"):
                persist_follow_projection(cursor, projection)
        connection.rollback()
