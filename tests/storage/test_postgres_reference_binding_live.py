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
            first_candidate_build_count = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM execution.document_compilation_build
                WHERE document_ref = ANY(%s)
                  AND compiler_contract_ref = 'postgres-semantic-compiler:v0_7'
                """,
                (list(first.document_refs),),
            )
            first_document_build_count = int(cursor.fetchone()[0])
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
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM resolution.demand_candidate_set AS link
                JOIN resolution.binding_candidate_set AS candidate_set
                  ON candidate_set.candidate_set_ref = link.candidate_set_ref
                WHERE candidate_set.document_ref = ANY(%s)
                """,
                (list(first.document_refs),),
            )
            demand_set_links = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT DISTINCT demand.budget_class_ref
                FROM resolution.demand AS demand
                JOIN resolution.demand_candidate_set AS link
                  ON link.demand_ref = demand.demand_ref
                JOIN resolution.binding_candidate_set AS candidate_set
                  ON candidate_set.candidate_set_ref = link.candidate_set_ref
                WHERE candidate_set.document_ref = ANY(%s)
                """,
                (list(first.document_refs),),
            )
            linked_budget_classes = {str(row[0]) for row in cursor.fetchall()}

        assert first.failure_refs == ()
        assert len(first.document_refs) == 5
        assert first_counts["entity_reference"][1] > 0
        assert first_counts["eventuality_reference"][1] > 0
        assert first_counts["proposition_reference"][1] > 0
        assert zero_member_sets > 0
        assert first_candidate_build_count == sum(
            value[0] for value in first_counts.values()
        )
        assert first_document_build_count == 5
        assert pairwise_rows == 0
        assert demand_set_links > 0
        assert "bounded_document_local_evidence" in linked_budget_classes

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
            second_candidate_build_count = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM execution.document_compilation_build
                WHERE document_ref = ANY(%s)
                  AND compiler_contract_ref = 'postgres-semantic-compiler:v0_7'
                """,
                (list(first.document_refs),),
            )
            second_document_build_count = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM corpus.document_occurrence
                WHERE corpus_ref = %s AND occurrence_state_ref = 'reused_compilation'
                """,
                (first.corpus_ref,),
            )
            reused_occurrences = int(cursor.fetchone()[0])

        assert second.corpus_ref == first.corpus_ref
        assert second.document_refs == first.document_refs
        assert second.demand_refs == first.demand_refs
        assert second.failure_refs == ()
        assert second_candidate_build_count == first_candidate_build_count
        assert second_document_build_count == first_document_build_count
        assert reused_occurrences == 5
    finally:
        store.close()
