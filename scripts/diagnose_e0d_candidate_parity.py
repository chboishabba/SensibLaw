#!/usr/bin/env python3
"""Diagnose E0d candidate parity without weakening the semantic gate.

This probe compares a migration-179 fixture and migration-180 fixture at the
candidate reducer boundary.  It deliberately separates four questions:

1. Is the portable candidate target/evidence relation the same?
2. Are persisted ordinals different only because migration 062 breaks ties by
   database-local target_id?
3. Do portable actor profiles disagree on occurrence_count / span / promotion?
4. If actor profiles disagree, is the disagreement already present in their
   child-profile/direct-factor source contributions?

No mutation is performed.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.e0d-candidate-parity-diagnosis.v0_1"


def _rows(cursor: Any, query: str, params: tuple[Any, ...]) -> tuple[tuple[Any, ...], ...]:
    cursor.execute(query, params)
    return tuple(tuple(row) for row in cursor.fetchall())


def _scope(run_ref: str, document_ref: str | None) -> tuple[Any, ...]:
    return (run_ref, document_ref, document_ref)


def _object_key_sql(prefix: str) -> str:
    return f"""
    concat_ws(':',
        'object',
        {prefix}_region.region_kind::TEXT,
        {prefix}_region.start_char::TEXT,
        {prefix}_region.end_char::TEXT,
        encode({prefix}_kind.symbol_digest,'hex'),
        encode({prefix}_head.symbol_digest,'hex'),
        COALESCE((
            SELECT string_agg(
                concat_ws('-',
                    support_token.start_char::TEXT,
                    support_token.end_char::TEXT,
                    support_token.local_token_ordinal::TEXT
                ),
                ',' ORDER BY support.ordinal, support_token.local_token_ordinal
            )
              FROM execution.semantic_pnf_object_token_support AS support
              JOIN execution.semantic_parser_token AS support_token
                ON support_token.token_id=support.token_id
             WHERE support.object_id={prefix}.object_id
        ), '')
    )
    """


def _demand_key_sql() -> str:
    return """
    concat_ws(':',
        'demand',
        source_region.region_kind::TEXT,
        source_region.start_char::TEXT,
        source_region.end_char::TEXT,
        source_token.start_char::TEXT,
        source_token.end_char::TEXT,
        source_token.local_token_ordinal::TEXT,
        encode(surface.symbol_digest,'hex'),
        encode(residual.symbol_digest,'hex')
    )
    """


def _snapshot(database_url: str, *, run_ref: str, document_ref: str | None) -> dict[str, Any]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                scope = _scope(run_ref, document_ref)
                object_key = _object_key_sql("target_object")
                demand_key = _demand_key_sql()

                candidates = _rows(
                    cursor,
                    f"""
                    SELECT {demand_key} AS demand_key,
                           candidate.ordinal,
                           candidate.target_kind,
                           {object_key} AS target_key,
                           source_interface_region.region_kind,
                           source_interface_region.start_char,
                           source_interface_region.end_char,
                           candidate.ancestor_distance,
                           candidate.index_rank,
                           candidate.candidate_score,
                           common_scope_region.region_kind,
                           common_scope_region.start_char,
                           common_scope_region.end_char,
                           candidate.validation_state,
                           candidate.target_id
                      FROM execution.semantic_pnf_demand AS demand
                      JOIN execution.semantic_symbol AS residual
                        ON residual.symbol_id=demand.residual_type_symbol_id
                       AND residual.kind_id=13
                       AND residual.symbol_text='anaphor_unresolved'
                      JOIN execution.semantic_pnf_region AS source_region
                        ON source_region.region_id=demand.source_region_id
                      LEFT JOIN execution.semantic_symbol AS surface
                        ON surface.symbol_id=demand.surface_lexical_symbol_id
                      LEFT JOIN execution.semantic_pnf_object_token_support AS source_support
                        ON source_support.object_id=demand.source_object_id
                       AND source_support.ordinal=0
                      LEFT JOIN execution.semantic_parser_token AS source_token
                        ON source_token.token_id=source_support.token_id
                      JOIN execution.semantic_pnf_demand_candidate AS candidate
                        ON candidate.demand_id=demand.demand_id
                      JOIN execution.semantic_pnf_object AS target_object
                        ON candidate.target_kind=1
                       AND target_object.object_id=candidate.target_id
                      JOIN execution.semantic_pnf_region AS target_object_region
                        ON target_object_region.region_id=target_object.region_id
                      LEFT JOIN execution.semantic_symbol AS target_object_kind
                        ON target_object_kind.symbol_id=target_object.object_kind_symbol_id
                      LEFT JOIN execution.semantic_symbol AS target_object_head
                        ON target_object_head.symbol_id=target_object.head_symbol_id
                      JOIN execution.semantic_pnf_interface AS source_interface
                        ON source_interface.interface_id=candidate.source_interface_id
                      JOIN execution.semantic_pnf_region AS source_interface_region
                        ON source_interface_region.region_id=source_interface.region_id
                      JOIN execution.semantic_pnf_interface AS common_scope
                        ON common_scope.interface_id=candidate.common_scope_interface_id
                      JOIN execution.semantic_pnf_region AS common_scope_region
                        ON common_scope_region.region_id=common_scope.region_id
                     WHERE source_region.run_ref=%s
                       AND (%s::TEXT IS NULL OR source_region.document_ref=%s::TEXT)
                     ORDER BY source_region.start_char,source_token.start_char,
                              candidate.ordinal,candidate.target_id
                    """,
                    scope,
                )

                profiles = _rows(
                    cursor,
                    f"""
                    WITH selected_interface AS MATERIALIZED (
                        SELECT DISTINCT candidate.source_interface_id AS interface_id
                          FROM execution.semantic_pnf_demand AS demand
                          JOIN execution.semantic_symbol AS residual
                            ON residual.symbol_id=demand.residual_type_symbol_id
                           AND residual.kind_id=13
                           AND residual.symbol_text='anaphor_unresolved'
                          JOIN execution.semantic_pnf_region AS source_region
                            ON source_region.region_id=demand.source_region_id
                          JOIN execution.semantic_pnf_demand_candidate AS candidate
                            ON candidate.demand_id=demand.demand_id
                         WHERE source_region.run_ref=%s
                           AND (%s::TEXT IS NULL OR source_region.document_ref=%s::TEXT)
                    )
                    SELECT interface_region.region_kind,
                           interface_region.start_char,
                           interface_region.end_char,
                           {_object_key_sql("object")} AS object_key,
                           encode(role.symbol_digest,'hex'),
                           encode(factor_type.symbol_digest,'hex'),
                           encode(predicate.symbol_digest,'hex'),
                           profile.occurrence_count,
                           profile.first_start_char,
                           profile.last_end_char,
                           profile.promotion_score,
                           profile.object_id
                      FROM selected_interface AS selected
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.interface_id=selected.interface_id
                      JOIN execution.semantic_pnf_region AS interface_region
                        ON interface_region.region_id=interface.region_id
                      JOIN execution.semantic_pnf_actor_profile AS profile
                        ON profile.interface_id=interface.interface_id
                      JOIN execution.semantic_pnf_object AS object
                        ON object.object_id=profile.object_id
                      JOIN execution.semantic_pnf_region AS object_region
                        ON object_region.region_id=object.region_id
                      LEFT JOIN execution.semantic_symbol AS object_kind
                        ON object_kind.symbol_id=object.object_kind_symbol_id
                      LEFT JOIN execution.semantic_symbol AS object_head
                        ON object_head.symbol_id=object.head_symbol_id
                      LEFT JOIN execution.semantic_symbol AS role
                        ON role.symbol_id=profile.role_symbol_id
                      LEFT JOIN execution.semantic_symbol AS factor_type
                        ON factor_type.symbol_id=profile.factor_type_symbol_id
                      LEFT JOIN execution.semantic_symbol AS predicate
                        ON predicate.symbol_id=profile.predicate_symbol_id
                     ORDER BY interface_region.start_char,object_region.start_char,
                              object_key,profile.object_id
                    """,
                    scope,
                )

                contributions = _rows(
                    cursor,
                    f"""
                    WITH selected_parent AS MATERIALIZED (
                        SELECT DISTINCT source_interface.region_id AS parent_region_id
                          FROM execution.semantic_pnf_demand AS demand
                          JOIN execution.semantic_symbol AS residual
                            ON residual.symbol_id=demand.residual_type_symbol_id
                           AND residual.kind_id=13
                           AND residual.symbol_text='anaphor_unresolved'
                          JOIN execution.semantic_pnf_region AS source_region
                            ON source_region.region_id=demand.source_region_id
                          JOIN execution.semantic_pnf_demand_candidate AS candidate
                            ON candidate.demand_id=demand.demand_id
                          JOIN execution.semantic_pnf_interface AS source_interface
                            ON source_interface.interface_id=candidate.source_interface_id
                         WHERE source_region.run_ref=%s
                           AND (%s::TEXT IS NULL OR source_region.document_ref=%s::TEXT)
                    ),
                    child_interface AS MATERIALIZED (
                        SELECT parent.parent_region_id,
                               child_region.region_id,
                               child_interface.interface_id
                          FROM selected_parent AS parent
                          JOIN execution.semantic_pnf_region AS child_region
                            ON child_region.parent_region_id=parent.parent_region_id
                           AND child_region.region_kind<>9
                          JOIN execution.semantic_pnf_interface AS child_interface
                            ON child_interface.region_id=child_region.region_id
                    ),
                    source_row AS (
                        SELECT parent_region.region_kind AS parent_kind,
                               parent_region.start_char AS parent_start,
                               parent_region.end_char AS parent_end,
                               'child_profile'::TEXT AS source_kind,
                               {_object_key_sql("object")} AS object_key,
                               encode(role.symbol_digest,'hex') AS role_digest,
                               encode(factor_type.symbol_digest,'hex') AS factor_digest,
                               encode(predicate.symbol_digest,'hex') AS predicate_digest,
                               profile.occurrence_count,
                               profile.first_start_char,
                               profile.last_end_char,
                               profile.promotion_score
                          FROM child_interface AS child
                          JOIN execution.semantic_pnf_region AS parent_region
                            ON parent_region.region_id=child.parent_region_id
                          JOIN execution.semantic_pnf_actor_profile AS profile
                            ON profile.interface_id=child.interface_id
                          JOIN execution.semantic_pnf_object AS object
                            ON object.object_id=profile.object_id
                          JOIN execution.semantic_pnf_region AS object_region
                            ON object_region.region_id=object.region_id
                          LEFT JOIN execution.semantic_symbol AS object_kind
                            ON object_kind.symbol_id=object.object_kind_symbol_id
                          LEFT JOIN execution.semantic_symbol AS object_head
                            ON object_head.symbol_id=object.head_symbol_id
                          LEFT JOIN execution.semantic_symbol AS role
                            ON role.symbol_id=profile.role_symbol_id
                          LEFT JOIN execution.semantic_symbol AS factor_type
                            ON factor_type.symbol_id=profile.factor_type_symbol_id
                          LEFT JOIN execution.semantic_symbol AS predicate
                            ON predicate.symbol_id=profile.predicate_symbol_id
                        UNION ALL
                        SELECT parent_region.region_kind,
                               parent_region.start_char,
                               parent_region.end_char,
                               'direct_factor',
                               {_object_key_sql("object")},
                               encode(role.symbol_digest,'hex'),
                               encode(factor_type.symbol_digest,'hex'),
                               encode(predicate.symbol_digest,'hex'),
                               1::BIGINT,
                               factor_region.start_char,
                               factor_region.end_char,
                               object.promotion_score
                          FROM child_interface AS child
                          JOIN execution.semantic_pnf_region AS parent_region
                            ON parent_region.region_id=child.parent_region_id
                          JOIN execution.semantic_pnf_interface_export AS factor_export
                            ON factor_export.interface_id=child.interface_id
                           AND factor_export.target_kind=2
                          JOIN execution.semantic_pnf_factor AS factor
                            ON factor.factor_id=factor_export.target_id
                          JOIN execution.semantic_pnf_region AS factor_region
                            ON factor_region.region_id=factor.region_id
                          JOIN execution.semantic_pnf_hyperedge AS edge
                            ON edge.factor_id=factor.factor_id
                          JOIN execution.semantic_pnf_object AS object
                            ON object.object_id=edge.object_id
                          JOIN execution.semantic_pnf_region AS object_region
                            ON object_region.region_id=object.region_id
                          LEFT JOIN execution.semantic_symbol AS object_kind
                            ON object_kind.symbol_id=object.object_kind_symbol_id
                          LEFT JOIN execution.semantic_symbol AS object_head
                            ON object_head.symbol_id=object.head_symbol_id
                          LEFT JOIN execution.semantic_symbol AS role
                            ON role.symbol_id=edge.role_symbol_id
                          LEFT JOIN execution.semantic_symbol AS factor_type
                            ON factor_type.symbol_id=factor.factor_type_symbol_id
                          LEFT JOIN execution.semantic_symbol AS predicate
                            ON predicate.symbol_id=factor.predicate_symbol_id
                    )
                    SELECT * FROM source_row
                    ORDER BY parent_start,object_key,source_kind,first_start_char,last_end_char
                    """,
                    scope,
                )

                return {
                    "candidates": candidates,
                    "profiles": profiles,
                    "contributions": contributions,
                }
    finally:
        connection.close()


def _counter(rows: Iterable[Iterable[Any]], *, drop: set[int] | None = None) -> Counter[tuple[Any, ...]]:
    removed = drop or set()
    return Counter(
        tuple(value for index, value in enumerate(row) if index not in removed)
        for row in rows
    )


def _diff(left: Counter[tuple[Any, ...]], right: Counter[tuple[Any, ...]], limit: int = 20) -> dict[str, Any]:
    missing = left - right
    extra = right - left
    return {
        "equal": not missing and not extra,
        "missing_count": sum(missing.values()),
        "extra_count": sum(extra.values()),
        "missing": [
            {"row": list(row), "multiplicity": count}
            for row, count in list(sorted(missing.items(), key=lambda item: repr(item[0])))[:limit]
        ],
        "extra": [
            {"row": list(row), "multiplicity": count}
            for row, count in list(sorted(extra.items(), key=lambda item: repr(item[0])))[:limit]
        ],
    }


def _profile_key(row: tuple[Any, ...]) -> tuple[Any, ...]:
    # Exclude occurrence_count/span/promotion and database-local object_id.
    return row[:7]


def _profile_state(row: tuple[Any, ...]) -> tuple[Any, ...]:
    return row[7:11]


def _profile_mismatches(
    legacy: tuple[tuple[Any, ...], ...],
    e0d: tuple[tuple[Any, ...], ...],
) -> list[dict[str, Any]]:
    left: dict[tuple[Any, ...], list[tuple[Any, ...]]] = defaultdict(list)
    right: dict[tuple[Any, ...], list[tuple[Any, ...]]] = defaultdict(list)
    for row in legacy:
        left[_profile_key(row)].append(_profile_state(row))
    for row in e0d:
        right[_profile_key(row)].append(_profile_state(row))
    output: list[dict[str, Any]] = []
    for key in sorted(set(left) | set(right), key=repr):
        if Counter(left[key]) == Counter(right[key]):
            continue
        output.append({
            "profile_key": list(key),
            "legacy_states": [list(value) for value in left[key]],
            "e0d_states": [list(value) for value in right[key]],
        })
    return output


def _score_formula_candidates(score: float, promotion: float, *, max_occurrences: int = 100) -> list[int]:
    return [
        count
        for count in range(1, max_occurrences + 1)
        if math.isclose(
            promotion + math.log(1 + count),
            score,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
    ]


def diagnose(
    *,
    legacy_database_url: str,
    e0d_database_url: str,
    run_ref: str,
    document_ref: str | None,
) -> dict[str, Any]:
    legacy = _snapshot(
        legacy_database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )
    e0d = _snapshot(
        e0d_database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )

    # Candidate columns:
    # 0 demand key, 1 ordinal, 2 target kind, 3 portable target,
    # 4:6 source-interface geometry, 7 distance, 8 index rank, 9 score,
    # 10:12 common-scope geometry, 13 validation, 14 local target_id.
    exact_portable = _diff(
        _counter(legacy["candidates"], drop={14}),
        _counter(e0d["candidates"], drop={14}),
    )
    without_ordinal = _diff(
        _counter(legacy["candidates"], drop={1, 14}),
        _counter(e0d["candidates"], drop={1, 14}),
    )
    without_ordinal_score = _diff(
        _counter(legacy["candidates"], drop={1, 9, 14}),
        _counter(e0d["candidates"], drop={1, 9, 14}),
    )

    profile_exact = _diff(
        _counter(legacy["profiles"], drop={11}),
        _counter(e0d["profiles"], drop={11}),
    )
    contribution_exact = _diff(
        _counter(legacy["contributions"]),
        _counter(e0d["contributions"]),
    )
    profile_mismatch = _profile_mismatches(
        legacy["profiles"],
        e0d["profiles"],
    )

    # For score-mismatched profiles, show which integral occurrence counts
    # reproduce candidate scores under the stored promotion score.
    score_explanations: list[dict[str, Any]] = []
    candidate_scores: dict[str, set[float]] = defaultdict(set)
    for side in (legacy, e0d):
        for row in side["candidates"]:
            candidate_scores[str(row[3])].add(float(row[9]))
    for mismatch in profile_mismatch:
        key = mismatch["profile_key"]
        object_key = str(key[3])
        observed = sorted(candidate_scores.get(object_key, set()))
        if not observed:
            continue
        states = mismatch["legacy_states"] + mismatch["e0d_states"]
        promotions = sorted({float(state[3]) for state in states})
        score_explanations.append({
            "object_key": object_key,
            "observed_candidate_scores": observed,
            "promotion_scores": promotions,
            "integral_occurrence_count_explanations": {
                str(promotion): {
                    str(score): _score_formula_candidates(score, promotion)
                    for score in observed
                }
                for promotion in promotions
            },
        })

    ordinal_allocator_dependency = (
        without_ordinal["equal"] and not exact_portable["equal"]
    )
    score_is_only_remaining_candidate_difference = (
        without_ordinal_score["equal"] and not without_ordinal["equal"]
    )

    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "candidate_decomposition": {
            "exact_portable_candidate_rows": exact_portable,
            "ignoring_persisted_ordinal": without_ordinal,
            "ignoring_persisted_ordinal_and_score": without_ordinal_score,
            "ordinal_allocator_dependency_consistent": ordinal_allocator_dependency,
            "score_is_only_remaining_candidate_difference":
                score_is_only_remaining_candidate_difference,
            "migration_062_rank_tail": [
                "structural_distance",
                "candidate_score DESC",
                "index_rank",
                "target_id (database-local)",
            ],
        },
        "actor_profile": {
            "exact_portable_state": profile_exact,
            "mismatches": profile_mismatch,
            "score_formula_explanations": score_explanations,
        },
        "profile_source_contributions": {
            "exact_portable_relation": contribution_exact,
            "interpretation": (
                "If contributions differ, drift exists below parent aggregation. "
                "If contributions agree but profiles differ, parent aggregation/rebuild "
                "is non-deterministic or non-idempotent."
            ),
        },
        "diagnosis_gate": {
            "candidate_target_evidence_equal_ignoring_rank_score":
                without_ordinal_score["equal"],
            "candidate_score_equal_ignoring_ordinal": without_ordinal["equal"],
            "actor_profile_equal": profile_exact["equal"],
            "profile_source_contributions_equal": contribution_exact["equal"],
            "safe_to_reclassify_as_ordinal_only": (
                without_ordinal["equal"] and profile_exact["equal"]
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-database-url", required=True)
    parser.add_argument("--e0d-database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    receipt = diagnose(
        legacy_database_url=args.legacy_database_url,
        e0d_database_url=args.e0d_database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    gate = receipt["diagnosis_gate"]
    if gate["safe_to_reclassify_as_ordinal_only"]:
        return 0
    if not gate["candidate_target_evidence_equal_ignoring_rank_score"]:
        return 4
    if not gate["actor_profile_equal"]:
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
