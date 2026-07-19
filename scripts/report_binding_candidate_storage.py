"""Report semantic cardinality and physical PostgreSQL binding storage."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


_RELATIONS = (
    "pnf.factor_anchor",
    "pnf.factor_morphology",
    "resolution.binding_candidate_set",
    "resolution.binding_compatibility_assessment",
    "resolution.binding_candidate_member",
    "resolution.binding_exclusion_summary",
    "resolution.refinement_candidate_set",
    "resolution.meet_candidate_set",
    "resolution.demand_candidate_set",
    "execution.binding_candidate_set_build",
    "execution.document_compilation_build",
)

_CARDINALITY_BUCKET_SQL = """
CASE
    WHEN candidate_set.member_count = 0 THEN 'zero'
    WHEN candidate_set.member_count = 1 THEN 'singleton'
    WHEN candidate_set.member_count BETWEEN 2 AND 5 THEN '2_to_5'
    WHEN candidate_set.member_count BETWEEN 6 AND 20 THEN '6_to_20'
    ELSE 'over_20'
END
"""

_ROLE_SQL = """
CASE
    WHEN anchor.pnf_kind_ref LIKE 'semantic.argument.%'
        THEN split_part(anchor.pnf_kind_ref, '.', 3)
    WHEN anchor.parser_dependency_ref IN
         ('nsubj', 'nsubjpass', 'csubj', 'csubjpass')
        THEN 'subject'
    WHEN anchor.parser_dependency_ref IN
         ('obj', 'dobj', 'iobj', 'attr', 'acomp')
        THEN 'object'
    WHEN anchor.parser_dependency_ref IN
         ('obl', 'dative', 'prep', 'pobj', 'agent')
        THEN 'oblique'
    WHEN anchor.parser_dependency_ref IN ('ccomp', 'xcomp')
        THEN 'complement'
    ELSE 'other'
END
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL URL; defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--corpus-ref",
        help="Optional corpus restriction. Relation sizes remain database-wide.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path; stdout is always emitted.",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _relation_sizes(cursor: Any) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for relation in _RELATIONS:
        cursor.execute(
            """
            SELECT
                pg_relation_size(%s::regclass),
                pg_table_size(%s::regclass),
                pg_indexes_size(%s::regclass),
                pg_total_relation_size(%s::regclass)
            """,
            (relation, relation, relation, relation),
        )
        heap_bytes, table_bytes, index_bytes, total_bytes = cursor.fetchone()
        rows.append(
            {
                "relation": relation,
                "heap_bytes": int(heap_bytes),
                "table_bytes_including_toast": int(table_bytes),
                "toast_and_table_overhead_bytes": int(table_bytes) - int(heap_bytes),
                "index_bytes": int(index_bytes),
                "total_bytes": int(total_bytes),
            }
        )
    return rows


def _scope(corpus_ref: str | None, column: str) -> tuple[str, tuple[object, ...]]:
    if not corpus_ref:
        return "", ()
    return (
        f"""
        WHERE {column} IN (
            SELECT DISTINCT occurrence.document_ref
            FROM corpus.document_occurrence AS occurrence
            WHERE occurrence.corpus_ref = %s
        )
        """,
        (corpus_ref,),
    )


def _candidate_metrics(cursor: Any, corpus_ref: str | None) -> dict[str, object]:
    where, params = _scope(corpus_ref, "candidate_set.document_ref")
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS candidate_set_count,
            COALESCE(SUM(candidate_set.member_count), 0) AS candidate_member_count,
            COUNT(*) FILTER (WHERE candidate_set.member_count = 0),
            COUNT(*) FILTER (WHERE candidate_set.member_count = 1),
            COUNT(*) FILTER (WHERE candidate_set.member_count > 1),
            COUNT(DISTINCT candidate_set.reference_factor_ref),
            COUNT(DISTINCT candidate_set.generator_build_ref)
        FROM resolution.binding_candidate_set AS candidate_set
        {where}
        """,
        params,
    )
    (
        candidate_set_count,
        candidate_member_count,
        zero_member_sets,
        one_member_sets,
        many_member_sets,
        reference_factor_count,
        build_count,
    ) = cursor.fetchone()

    cursor.execute(
        f"""
        SELECT
            candidate_set.referential_type_ref,
            {_CARDINALITY_BUCKET_SQL} AS cardinality_bucket,
            COUNT(*),
            COALESCE(SUM(candidate_set.member_count), 0)
        FROM resolution.binding_candidate_set AS candidate_set
        {where}
        GROUP BY candidate_set.referential_type_ref, cardinality_bucket
        ORDER BY candidate_set.referential_type_ref, cardinality_bucket
        """,
        params,
    )
    by_type: dict[str, dict[str, object]] = {}
    for referential_type, bucket, set_count, member_count in cursor.fetchall():
        type_row = by_type.setdefault(
            str(referential_type),
            {
                "candidate_sets": 0,
                "candidate_members": 0,
                "cardinality_buckets": {},
            },
        )
        type_row["candidate_sets"] = int(type_row["candidate_sets"]) + int(set_count)
        type_row["candidate_members"] = int(type_row["candidate_members"]) + int(
            member_count
        )
        type_row["cardinality_buckets"][str(bucket)] = {
            "candidate_sets": int(set_count),
            "candidate_members": int(member_count),
        }

    cursor.execute(
        f"""
        SELECT
            candidate_set.referential_type_ref,
            {_ROLE_SQL} AS syntactic_role,
            COUNT(*),
            COALESCE(SUM(candidate_set.member_count), 0)
        FROM resolution.binding_candidate_set AS candidate_set
        LEFT JOIN pnf.factor_anchor AS anchor
          ON anchor.factor_revision_ref =
             candidate_set.reference_factor_revision_ref
        {where}
        GROUP BY candidate_set.referential_type_ref, syntactic_role
        ORDER BY candidate_set.referential_type_ref, syntactic_role
        """,
        params,
    )
    by_type_and_role: dict[str, dict[str, dict[str, int]]] = {}
    for referential_type, role, set_count, member_count in cursor.fetchall():
        by_type_and_role.setdefault(str(referential_type), {})[str(role)] = {
            "candidate_sets": int(set_count),
            "candidate_members": int(member_count),
        }

    cursor.execute(
        f"""
        SELECT
            exclusion.reason_ref,
            COUNT(*) AS summary_rows,
            COALESCE(SUM(exclusion.excluded_count), 0) AS excluded_candidates
        FROM resolution.binding_exclusion_summary AS exclusion
        JOIN resolution.binding_candidate_set AS candidate_set
          ON candidate_set.candidate_set_ref = exclusion.candidate_set_ref
        {where}
        GROUP BY exclusion.reason_ref
        ORDER BY exclusion.reason_ref
        """,
        params,
    )
    exclusion_rows = {
        str(reason): {
            "summary_rows": int(summary_rows),
            "excluded_candidates": int(excluded_candidates),
        }
        for reason, summary_rows, excluded_candidates in cursor.fetchall()
    }
    excluded_total = sum(
        int(row["excluded_candidates"]) for row in exclusion_rows.values()
    )
    accessible_total = int(candidate_member_count) + excluded_total
    return {
        "reference_factors": int(reference_factor_count),
        "candidate_sets": int(candidate_set_count),
        "candidate_members": int(candidate_member_count),
        "zero_member_sets": int(zero_member_sets),
        "one_member_sets": int(one_member_sets),
        "many_member_sets": int(many_member_sets),
        "candidate_set_builds": int(build_count),
        "candidate_sets_by_referential_type": by_type,
        "candidate_sets_by_referential_type_and_role": by_type_and_role,
        "excluded_candidates_by_reason": exclusion_rows,
        "excluded_candidates": excluded_total,
        "accessible_candidates": accessible_total,
        "compatibility_retention_rate": (
            round(int(candidate_member_count) / accessible_total, 6)
            if accessible_total
            else None
        ),
    }


def _factor_metrics(cursor: Any, corpus_ref: str | None) -> dict[str, object]:
    where, params = _scope(corpus_ref, "factor.document_ref")
    cursor.execute(
        f"""
        SELECT
            COUNT(DISTINCT factor.factor_ref),
            COUNT(DISTINCT revision.factor_revision_ref),
            COUNT(DISTINCT refinement.refinement_ref),
            COUNT(DISTINCT refinement.factor_ref)
        FROM algebra.factor AS factor
        LEFT JOIN algebra.factor_revision AS revision
          ON revision.factor_ref = factor.factor_ref
        LEFT JOIN resolution.refinement AS refinement
          ON refinement.factor_ref = factor.factor_ref
        {where}
        """,
        params,
    )
    factor_count, revision_count, refinement_count, refined_factor_count = (
        cursor.fetchone()
    )
    factor_count = int(factor_count)
    refined_factor_count = int(refined_factor_count)
    return {
        "factors": factor_count,
        "factor_revisions": int(revision_count),
        "refinements": int(refinement_count),
        "refined_factors": refined_factor_count,
        "revision_locality": (
            round(refined_factor_count / factor_count, 6) if factor_count else None
        ),
    }


def _demand_metrics(cursor: Any, corpus_ref: str | None) -> dict[str, object]:
    where, params = _scope(corpus_ref, "factor.document_ref")
    cursor.execute(
        f"""
        SELECT
            COUNT(DISTINCT demand.demand_ref),
            COUNT(DISTINCT demand.demand_ref) FILTER (
                WHERE demand.demand_state_ref IN
                    ('open', 'not_evaluated', 'budget_exhausted')
            ),
            COUNT(DISTINCT demand.demand_ref) FILTER (
                WHERE demand.factor_revision_ref IS NULL
            ),
            COUNT(DISTINCT link.demand_ref)
        FROM resolution.demand AS demand
        JOIN algebra.factor AS factor
          ON factor.factor_ref = demand.factor_ref
        LEFT JOIN resolution.demand_candidate_set AS link
          ON link.demand_ref = demand.demand_ref
        {where}
        """,
        params,
    )
    total, open_count, missing_revision, linked = cursor.fetchone()

    def grouped(column: str) -> dict[str, int]:
        cursor.execute(
            f"""
            SELECT COALESCE({column}, '<none>'), COUNT(DISTINCT demand.demand_ref)
            FROM resolution.demand AS demand
            JOIN algebra.factor AS factor
              ON factor.factor_ref = demand.factor_ref
            {where}
            GROUP BY COALESCE({column}, '<none>')
            ORDER BY COALESCE({column}, '<none>')
            """,
            params,
        )
        return {str(key): int(value) for key, value in cursor.fetchall()}

    total = int(total)
    linked = int(linked)
    return {
        "demands": total,
        "open_demands": int(open_count),
        "demands_missing_factor_revision": int(missing_revision),
        "candidate_set_linked_demands": linked,
        "candidate_set_linked_share": round(linked / total, 6) if total else None,
        "by_budget_class": grouped("demand.budget_class_ref"),
        "by_scope": grouped("demand.scope_ref"),
        "by_subject_kind": grouped("demand.subject_kind_ref"),
        "by_formal_role": grouped("demand.formal_role_ref"),
    }


def _execution_metrics(cursor: Any, corpus_ref: str | None) -> dict[str, object]:
    if not corpus_ref:
        return {
            "occurrence_states": {},
            "document_compilation_builds": None,
            "pairwise_binding_evidence_rows": None,
        }
    cursor.execute(
        """
        SELECT occurrence_state, COUNT(*)
        FROM corpus.document_occurrence
        WHERE corpus_ref = %s
        GROUP BY occurrence_state
        ORDER BY occurrence_state
        """,
        (corpus_ref,),
    )
    occurrence_states = {str(state): int(count) for state, count in cursor.fetchall()}
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM execution.document_compilation_build AS build
        WHERE build.document_ref IN (
            SELECT DISTINCT occurrence.document_ref
            FROM corpus.document_occurrence AS occurrence
            WHERE occurrence.corpus_ref = %s
        )
        """,
        (corpus_ref,),
    )
    document_builds = int(cursor.fetchone()[0])
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM evidence.local_evidence AS evidence
        WHERE evidence.document_ref IN (
            SELECT DISTINCT occurrence.document_ref
            FROM corpus.document_occurrence AS occurrence
            WHERE occurrence.corpus_ref = %s
        )
          AND evidence.evidence_type_ref = 'typed_binding_candidate'
        """,
        (corpus_ref,),
    )
    pairwise_rows = int(cursor.fetchone()[0])
    return {
        "occurrence_states": occurrence_states,
        "document_compilation_builds": document_builds,
        "pairwise_binding_evidence_rows": pairwise_rows,
    }


def _document_metrics(cursor: Any, corpus_ref: str | None) -> dict[str, object]:
    if not corpus_ref:
        cursor.execute("SELECT COUNT(*) FROM corpus.document")
        return {"documents": int(cursor.fetchone()[0])}
    cursor.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT document_ref)
        FROM corpus.document_occurrence
        WHERE corpus_ref = %s
        """,
        (corpus_ref,),
    )
    occurrences, documents = cursor.fetchone()
    return {
        "document_occurrences": int(occurrences),
        "documents": int(documents),
    }


def collect_binding_report(
    cursor: Any, *, corpus_ref: str | None
) -> dict[str, object]:
    """Collect one explicit corpus-scoped semantic and execution ledger."""

    relation_sizes = _relation_sizes(cursor)
    candidate_metrics = _candidate_metrics(cursor, corpus_ref)
    factor_metrics = _factor_metrics(cursor, corpus_ref)
    demand_metrics = _demand_metrics(cursor, corpus_ref)
    execution_metrics = _execution_metrics(cursor, corpus_ref)
    document_metrics = _document_metrics(cursor, corpus_ref)
    member_count = int(candidate_metrics["candidate_members"])
    candidate_storage = sum(
        int(row["total_bytes"])
        for row in relation_sizes
        if str(row["relation"]).startswith("resolution.binding_")
    )
    return {
        "corpus_ref": corpus_ref,
        "documents": document_metrics,
        "semantic_metrics": {
            "factors": factor_metrics,
            "binding": candidate_metrics,
            "demands": demand_metrics,
        },
        "execution_metrics": execution_metrics,
        "physical_storage": {
            "relations": relation_sizes,
            "binding_relation_total_bytes": candidate_storage,
            "average_binding_relation_bytes_per_member": (
                round(candidate_storage / member_count, 3)
                if member_count
                else None
            ),
        },
        "measurement_boundary": {
            "relation_sizes_are_database_wide": True,
            "semantic_counts_are_corpus_scoped": bool(corpus_ref),
            "occurrence_and_reuse_counts_are_corpus_scoped": bool(corpus_ref),
            "legacy_json_size_included": False,
            "candidate_membership_does_not_imply_identity": True,
            "zero_member_set_does_not_imply_expletivity": True,
        },
    }


def main() -> int:
    args = _parse_args()
    try:
        import psycopg
    except ImportError as error:
        raise SystemExit("psycopg[binary]>=3.1 is required") from error

    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            output = collect_binding_report(cursor, corpus_ref=args.corpus_ref)
    encoded = json.dumps(output, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
