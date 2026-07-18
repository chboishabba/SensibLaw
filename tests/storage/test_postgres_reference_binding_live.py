from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.policy.corpus_compilation import default_compiler_context
from src.policy.postgres_corpus_compilation import compile_directory_postgres
from src.storage.postgres import PostgresCompilerStore


pytestmark = pytest.mark.live


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "corpora"
    / "reference-binding-mini"
)


def test_reference_binding_mini_persists_nonempty_and_zero_member_sets() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for the PostgreSQL integration proof")
    if not FIXTURE.exists():
        pytest.skip("reference-binding-mini fixture is not present on this branch")

    store = PostgresCompilerStore.connect(database_url)
    try:
        first = compile_directory_postgres(
            FIXTURE,
            context=default_compiler_context(),
            store=store,
        )
        with store.transaction() as cursor:
            cursor.execute(
                """
                SELECT referential_type_ref,
                       COUNT(*) AS candidate_set_count,
                       COALESCE(SUM(member_count), 0) AS member_count
                FROM resolution.binding_candidate_set
                WHERE document_ref = ANY(%s)
                GROUP BY referential_type_ref
                """,
                (list(first.document_refs),),
            )
            first_counts = {
                str(row[0]): (int(row[1]), int(row[2])) for row in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM resolution.binding_candidate_set
                WHERE document_ref = ANY(%s) AND member_count = 0
                """,
                (list(first.document_refs),),
            )
            zero_member_sets = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM execution.binding_candidate_set_build AS build
                JOIN resolution.binding_candidate_set AS candidate_set
                  ON candidate_set.candidate_set_ref = build.candidate_set_ref
                WHERE candidate_set.document_ref = ANY(%s)
                """,
                (list(first.document_refs),),
            )
            first_build_count = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM evidence.local_evidence
                WHERE document_ref = ANY(%s)
                  AND evidence_type_ref = 'typed_binding_candidate'
                """,
                (list(first.document_refs),),
            )
            pairwise_rows = int(cursor.fetchone()[0])

        assert first.failure_refs == ()
        assert len(first.document_refs) == 5
        assert first_counts["entity_reference"][1] > 0
        assert first_counts["eventuality_reference"][1] > 0
        assert first_counts["proposition_reference"][1] > 0
        assert zero_member_sets > 0
        assert first_build_count == sum(value[0] for value in first_counts.values())
        assert pairwise_rows == 0

        second = compile_directory_postgres(
            FIXTURE,
            context=default_compiler_context(),
            store=store,
        )
        with store.transaction() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM execution.binding_candidate_set_build AS build
                JOIN resolution.binding_candidate_set AS candidate_set
                  ON candidate_set.candidate_set_ref = build.candidate_set_ref
                WHERE candidate_set.document_ref = ANY(%s)
                """,
                (list(first.document_refs),),
            )
            second_build_count = int(cursor.fetchone()[0])

        assert second.corpus_ref == first.corpus_ref
        assert second.document_refs == first.document_refs
        assert second.demand_refs == first.demand_refs
        assert second.failure_refs == ()
        assert second_build_count == first_build_count
    finally:
        store.close()
