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
    "execution.binding_candidate_set_build",
)


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


def _semantic_metrics(cursor: Any, corpus_ref: str | None) -> dict[str, object]:
    where = ""
    params: tuple[object, ...] = ()
    if corpus_ref:
        where = """
        WHERE candidate_set.document_ref IN (
            SELECT occurrence.document_ref
            FROM corpus.document_occurrence AS occurrence
            WHERE occurrence.corpus_ref = %s
        )
        """
        params = (corpus_ref,)
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
            COUNT(*),
            COALESCE(SUM(candidate_set.member_count), 0)
        FROM resolution.binding_candidate_set AS candidate_set
        {where}
        GROUP BY candidate_set.referential_type_ref
        ORDER BY candidate_set.referential_type_ref
        """,
        params,
    )
    by_type = {
        str(row[0]): {
            "candidate_sets": int(row[1]),
            "candidate_members": int(row[2]),
        }
        for row in cursor.fetchall()
    }
    cursor.execute(
        f"""
        SELECT
            exclusion.reason_ref,
            COALESCE(SUM(exclusion.excluded_count), 0)
        FROM resolution.binding_exclusion_summary AS exclusion
        JOIN resolution.binding_candidate_set AS candidate_set
          ON candidate_set.candidate_set_ref = exclusion.candidate_set_ref
        {where}
        GROUP BY exclusion.reason_ref
        ORDER BY exclusion.reason_ref
        """,
        params,
    )
    exclusions = {str(row[0]): int(row[1]) for row in cursor.fetchall()}
    return {
        "reference_factors": int(reference_factor_count),
        "candidate_sets": int(candidate_set_count),
        "candidate_members": int(candidate_member_count),
        "zero_member_sets": int(zero_member_sets),
        "one_member_sets": int(one_member_sets),
        "many_member_sets": int(many_member_sets),
        "candidate_set_builds": int(build_count),
        "candidate_sets_by_referential_type": by_type,
        "excluded_candidates_by_reason": exclusions,
    }


def main() -> int:
    args = _parse_args()
    try:
        import psycopg
    except ImportError as error:
        raise SystemExit("psycopg[binary]>=3.1 is required") from error

    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            relation_sizes = _relation_sizes(cursor)
            semantic_metrics = _semantic_metrics(cursor, args.corpus_ref)
    member_count = int(semantic_metrics["candidate_members"])
    candidate_storage = sum(
        int(row["total_bytes"])
        for row in relation_sizes
        if str(row["relation"]).startswith("resolution.binding_")
    )
    output = {
        "corpus_ref": args.corpus_ref,
        "semantic_metrics": semantic_metrics,
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
            "semantic_counts_are_corpus_scoped": bool(args.corpus_ref),
            "legacy_json_size_included": False,
        },
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
