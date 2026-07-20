from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.report_binding_candidate_storage import collect_binding_report
from src.policy.corpus_compilation import default_compiler_context
from src.policy.operational_corpus_compilation import OPERATIONAL_COMPILER_CONTRACT
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
                  AND compiler_contract_ref = %s
                """,
                (list(first.document_refs), OPERATIONAL_COMPILER_CONTRACT),
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
            first_report = collect_binding_report(
                cursor,
                corpus_ref=first.corpus_ref,
            )

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

        report_binding = first_report["semantic_metrics"]["binding"]
        report_demands = first_report["semantic_metrics"]["demands"]
        report_execution = first_report["execution_metrics"]
        assert first_report["documents"] == {
            "document_occurrences": 5,
            "documents": 5,
        }
        assert report_binding["candidate_sets"] == first_candidate_build_count
        assert report_binding["zero_member_sets"] == zero_member_sets
        assert report_binding["candidate_members"] == sum(
            value[1] for value in first_counts.values()
        )
        assert set(report_binding["candidate_sets_by_referential_type"]) == {
            "entity_reference",
            "eventuality_reference",
            "proposition_reference",
        }
        assert report_binding["accessible_candidates"] >= report_binding[
            "candidate_members"
        ]
        assert report_binding["compatibility_retention_rate"] is not None
        assert report_demands["demands"] == len(first.demand_refs)
        assert report_demands["open_demands"] == len(first.demand_refs)
        assert report_demands["demands_missing_factor_revision"] == 0
        assert report_demands["candidate_set_linked_demands"] > 0
        assert report_execution["pairwise_binding_evidence_rows"] == 0
        assert report_execution["occurrence_states"] == {"compiled": 5}
        assert first_report["measurement_boundary"] == {
            "relation_sizes_are_database_wide": True,
            "semantic_counts_are_corpus_scoped": True,
            "occurrence_and_reuse_counts_are_corpus_scoped": True,
            "legacy_json_size_included": False,
            "candidate_membership_does_not_imply_identity": True,
            "zero_member_set_does_not_imply_expletivity": True,
        }

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
                  AND compiler_contract_ref = %s
                """,
                (list(first.document_refs), OPERATIONAL_COMPILER_CONTRACT),
            )
            second_document_build_count = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM corpus.document_occurrence
                WHERE corpus_ref = %s AND occurrence_state = 'reused_compilation'
                """,
                (first.corpus_ref,),
            )
            reused_occurrences = int(cursor.fetchone()[0])
            second_report = collect_binding_report(
                cursor,
                corpus_ref=first.corpus_ref,
            )

        assert second.corpus_ref == first.corpus_ref
        assert second.document_refs == first.document_refs
        assert second.demand_refs == first.demand_refs
        assert second.failure_refs == ()
        assert second_candidate_build_count == first_candidate_build_count
        assert second_document_build_count == first_document_build_count
        assert reused_occurrences == 5
        assert second_report["semantic_metrics"] == first_report["semantic_metrics"]
        assert second_report["execution_metrics"]["occurrence_states"] == {
            "reused_compilation": 5
        }
        assert second_report["execution_metrics"][
            "document_compilation_builds"
        ] == first_report["execution_metrics"]["document_compilation_builds"]
    finally:
        store.close()
