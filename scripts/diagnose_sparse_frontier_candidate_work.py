from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-candidate-work-diagnostic.v0_1"

_PARENT_DEMAND = """
SELECT demand.demand_id,
       demand.expected_target_kind,
       demand.expected_factor_type_symbol_id,
       demand.expected_object_kind_symbol_id,
       demand.role_symbol_id,
       demand.lexical_symbol_id,
       demand.recency_class,
       demand.max_candidates,
       COALESCE(demand.source_start_char, source_region.end_char) AS demand_position,
       source_region.start_char AS source_region_start,
       source_region.end_char AS source_region_end
  FROM execution.semantic_pnf_interface_export AS demand_export
  JOIN execution.semantic_pnf_demand AS demand
    ON demand.demand_id = demand_export.target_id
  JOIN execution.semantic_pnf_region AS source_region
    ON source_region.region_id = demand.source_region_id
 WHERE demand_export.interface_id = %s
   AND demand_export.target_kind = 3
   AND demand.state IN (1, 3)
"""

_OBJECT_DEMAND = f"""
SELECT * FROM ({_PARENT_DEMAND}) AS demand
 WHERE demand.expected_target_kind = 1
"""

_PROFILE_BASE = """
SELECT profile.object_id,
       profile.object_kind_symbol_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id,
       profile.occurrence_count,
       profile.first_start_char,
       profile.last_end_char,
       profile.promotion_score,
       object.head_symbol_id
  FROM execution.semantic_pnf_actor_profile AS profile
  JOIN execution.semantic_pnf_object AS object
    ON object.object_id = profile.object_id
 WHERE profile.interface_id = %s
"""

_REQUIRED_KEY = f"""
WITH object_demand AS MATERIALIZED ({_OBJECT_DEMAND})
SELECT demand.demand_id, key.key_kind, key.key_a, 0::BIGINT AS key_b
  FROM object_demand AS demand
  CROSS JOIN LATERAL (
      VALUES
          (1::SMALLINT, demand.expected_factor_type_symbol_id),
          (2::SMALLINT, demand.expected_object_kind_symbol_id),
          (3::SMALLINT, demand.lexical_symbol_id),
          (4::SMALLINT, demand.role_symbol_id)
  ) AS key(key_kind, key_a)
 WHERE key.key_a IS NOT NULL
"""

_PROFILE_KEY = f"""
WITH profile_base AS MATERIALIZED ({_PROFILE_BASE})
SELECT DISTINCT profile.object_id,
       profile.object_kind_symbol_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id,
       profile.occurrence_count,
       profile.first_start_char,
       profile.last_end_char,
       profile.promotion_score,
       key.key_kind,
       key.key_a,
       0::BIGINT AS key_b
  FROM profile_base AS profile
  CROSS JOIN LATERAL (
      VALUES
          (1::SMALLINT, profile.factor_type_symbol_id),
          (2::SMALLINT, profile.object_kind_symbol_id),
          (3::SMALLINT, profile.predicate_symbol_id),
          (3::SMALLINT, profile.head_symbol_id),
          (4::SMALLINT, profile.role_symbol_id)
  ) AS key(key_kind, key_a)
 WHERE key.key_a IS NOT NULL
"""

_UNARY_MATCH = f"""
WITH required_key AS MATERIALIZED ({_REQUIRED_KEY}),
profile_key AS MATERIALIZED ({_PROFILE_KEY})
SELECT required_key.demand_id,
       profile.object_id,
       profile.object_kind_symbol_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id,
       profile.occurrence_count,
       profile.first_start_char,
       profile.last_end_char,
       profile.promotion_score,
       required_key.key_kind
  FROM required_key
  JOIN profile_key AS profile
    ON profile.key_kind = required_key.key_kind
   AND profile.key_a = required_key.key_a
   AND profile.key_b = required_key.key_b
"""

_PARTIAL_PROFILE = f"""
SELECT matched.demand_id,
       matched.object_id,
       matched.object_kind_symbol_id,
       matched.role_symbol_id,
       matched.factor_type_symbol_id,
       matched.predicate_symbol_id,
       matched.occurrence_count,
       matched.first_start_char,
       matched.last_end_char,
       matched.promotion_score,
       count(*)::BIGINT AS matched_count
  FROM ({_UNARY_MATCH}) AS matched
 GROUP BY matched.demand_id,
          matched.object_id,
          matched.object_kind_symbol_id,
          matched.role_symbol_id,
          matched.factor_type_symbol_id,
          matched.predicate_symbol_id,
          matched.occurrence_count,
          matched.first_start_char,
          matched.last_end_char,
          matched.promotion_score
"""

_UNARY_CONJUNCTIVE = f"""
WITH required_count AS MATERIALIZED (
    SELECT required.demand_id, count(*)::BIGINT AS required_count
      FROM ({_REQUIRED_KEY}) AS required
     GROUP BY required.demand_id
),
partial AS MATERIALIZED ({_PARTIAL_PROFILE})
SELECT partial.*
  FROM partial
  JOIN required_count AS required
    ON required.demand_id = partial.demand_id
   AND required.required_count = partial.matched_count
"""

# Literal legacy static conjunction, before recency.  Its cardinality is the
# posting fibre a direct composite signature lookup must expose; the SQL itself
# is diagnostic only and is not claimed as the proposed physical implementation.
_DIRECT_STATIC_MATCH = f"""
WITH object_demand AS MATERIALIZED ({_OBJECT_DEMAND}),
profile_base AS MATERIALIZED ({_PROFILE_BASE})
SELECT demand.demand_id,
       profile.object_id,
       profile.occurrence_count,
       profile.first_start_char,
       profile.last_end_char,
       profile.promotion_score,
       demand.recency_class,
       demand.demand_position,
       demand.source_region_start,
       demand.source_region_end,
       demand.max_candidates
  FROM object_demand AS demand
  JOIN profile_base AS profile
    ON (demand.expected_object_kind_symbol_id IS NULL
        OR demand.expected_object_kind_symbol_id = profile.object_kind_symbol_id)
   AND (demand.role_symbol_id IS NULL
        OR demand.role_symbol_id = profile.role_symbol_id)
   AND (demand.expected_factor_type_symbol_id IS NULL
        OR demand.expected_factor_type_symbol_id = profile.factor_type_symbol_id)
   AND (demand.lexical_symbol_id IS NULL
        OR demand.lexical_symbol_id = profile.head_symbol_id
        OR demand.lexical_symbol_id = profile.predicate_symbol_id)
"""

_DIRECT_OBJECT_CANDIDATE = f"""
SELECT match.demand_id,
       1::SMALLINT AS target_kind,
       match.object_id AS target_id,
       abs(match.demand_position - match.last_end_char) AS structural_distance,
       0::BIGINT AS index_rank,
       match.promotion_score
           + ln(1 + match.occurrence_count)::DOUBLE PRECISION AS candidate_score,
       match.max_candidates
  FROM ({_DIRECT_STATIC_MATCH}) AS match
 WHERE CASE match.recency_class
     WHEN 1 THEN
         match.first_start_char >= match.source_region_start
         AND match.last_end_char <= match.source_region_end
     WHEN 2 THEN match.last_end_char <= match.demand_position
     WHEN 3 THEN match.last_end_char <= match.demand_position
     WHEN 4 THEN TRUE
     WHEN 5 THEN TRUE
     ELSE FALSE
 END
"""

_INDEXED_OBJECT_CANDIDATE = """
SELECT candidate.demand_id,
       candidate.target_kind,
       candidate.target_id,
       candidate.structural_distance,
       candidate.index_rank,
       candidate.candidate_score,
       demand.max_candidates
  FROM execution.indexed_numeric_pnf_object_candidate_rows(%s) AS candidate
  JOIN execution.semantic_pnf_demand AS demand
    ON demand.demand_id = candidate.demand_id
"""

_FACTOR_CANDIDATE = f"""
WITH parent_demand AS MATERIALIZED ({_PARENT_DEMAND})
SELECT demand.demand_id,
       2::SMALLINT AS target_kind,
       factor.factor_id AS target_id,
       abs(demand.demand_position - factor_region.end_char) AS structural_distance,
       factor_export.rank AS index_rank,
       factor.support_score AS candidate_score,
       demand.max_candidates
  FROM parent_demand AS demand
  JOIN execution.semantic_pnf_interface_export AS factor_export
    ON factor_export.interface_id = %s
   AND factor_export.target_kind = 2
  JOIN execution.semantic_pnf_factor AS factor
    ON factor.factor_id = factor_export.target_id
  JOIN execution.semantic_pnf_region AS factor_region
    ON factor_region.region_id = factor.region_id
 WHERE demand.expected_target_kind = 2
   AND (demand.expected_factor_type_symbol_id IS NULL
        OR demand.expected_factor_type_symbol_id = factor.factor_type_symbol_id)
   AND (demand.lexical_symbol_id IS NULL
        OR demand.lexical_symbol_id = factor.predicate_symbol_id)
   AND (demand.recency_class IN (4, 5)
        OR factor_region.end_char <= demand.demand_position)
"""

_RANKED = f"""
WITH raw_candidate AS MATERIALIZED (
    SELECT * FROM ({_INDEXED_OBJECT_CANDIDATE}) AS object_candidate
    UNION ALL
    SELECT * FROM ({_FACTOR_CANDIDATE}) AS factor_candidate
),
deduplicated AS MATERIALIZED (
    SELECT candidate.*,
           row_number() OVER (
               PARTITION BY candidate.demand_id,
                            candidate.target_kind,
                            candidate.target_id
               ORDER BY candidate.structural_distance,
                        candidate.index_rank,
                        candidate.target_id
           ) AS target_occurrence
      FROM raw_candidate AS candidate
),
ranked AS MATERIALIZED (
    SELECT candidate.*,
           row_number() OVER (
               PARTITION BY candidate.demand_id
               ORDER BY candidate.structural_distance,
                        candidate.candidate_score DESC,
                        candidate.index_rank,
                        candidate.target_id
           ) - 1 AS candidate_ordinal
      FROM deduplicated AS candidate
     WHERE candidate.target_occurrence = 1
)
SELECT * FROM ranked
"""

_SURVIVORS = f"""
SELECT ranked.demand_id,
       ranked.candidate_ordinal::SMALLINT AS ordinal,
       ranked.target_kind,
       ranked.target_id,
       ranked.structural_distance,
       ranked.index_rank,
       ranked.candidate_score
  FROM ({_RANKED}) AS ranked
 WHERE ranked.candidate_ordinal < ranked.max_candidates
"""


def _count(cursor: Any, sql: str, params: tuple[object, ...]) -> int:
    cursor.execute(f"SELECT count(*) FROM ({sql}) AS measured", params)
    return int(cursor.fetchone()[0])


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _histogram(cursor: Any, sql: str, params: tuple[object, ...]) -> dict[str, int]:
    cursor.execute(sql, params)
    return {str(key): int(value) for key, value in cursor.fetchall()}


def _json_plan(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, list):
        return dict(value[0])
    return dict(value)


def _plan(
    cursor: Any, sql: str, params: tuple[object, ...], *, analyze: bool
) -> dict[str, object]:
    options = "ANALYZE, BUFFERS, WAL, FORMAT JSON" if analyze else "FORMAT JSON"
    cursor.execute(f"EXPLAIN ({options}) {sql}", params)
    envelope = _json_plan(cursor.fetchone()[0])
    plan = dict(envelope["Plan"])
    receipt: dict[str, object] = {
        "node_type": plan.get("Node Type"),
        "plan_rows": plan.get("Plan Rows"),
        "plan_width": plan.get("Plan Width"),
        "total_cost": plan.get("Total Cost"),
    }
    if analyze:
        receipt.update(
            {
                "planning_ms": envelope.get("Planning Time"),
                "execution_ms": envelope.get("Execution Time"),
                "actual_rows": plan.get("Actual Rows"),
                "actual_loops": plan.get("Actual Loops"),
                "shared_hit_blocks": plan.get("Shared Hit Blocks", 0),
                "shared_read_blocks": plan.get("Shared Read Blocks", 0),
                "temp_read_blocks": plan.get("Temp Read Blocks", 0),
                "temp_written_blocks": plan.get("Temp Written Blocks", 0),
                "wal_records": plan.get("WAL Records", 0),
                "wal_bytes": plan.get("WAL Bytes", 0),
            }
        )
    return receipt


def candidate_work_receipt(
    database_url: str,
    interface_id: int,
    *,
    plan_mode: str = "analyze",
    statement_timeout_ms: int = 0,
) -> dict[str, object]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                if statement_timeout_ms > 0:
                    cursor.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (str(statement_timeout_ms),),
                    )

                cursor.execute(
                    """
                    SELECT interface.region_id,
                           region.region_kind,
                           interface.interface_cardinality,
                           interface.unresolved_count,
                           interface.graph_revision
                      FROM execution.semantic_pnf_interface AS interface
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = interface.region_id
                     WHERE interface.interface_id = %s
                    """,
                    (interface_id,),
                )
                metadata = cursor.fetchone()
                if metadata is None:
                    raise RuntimeError(f"PNF interface does not exist: {interface_id}")
                region_id, region_kind, cardinality, unresolved, revision = (
                    int(value) for value in metadata
                )

                object_demands = _count(cursor, _OBJECT_DEMAND, (interface_id,))
                actor_profiles = _count(cursor, _PROFILE_BASE, (interface_id,))
                required_key_rows = _count(cursor, _REQUIRED_KEY, (interface_id,))
                profile_key_rows = _count(cursor, _PROFILE_KEY, (interface_id,))
                unary_match_rows = _count(
                    cursor, _UNARY_MATCH, (interface_id, interface_id)
                )
                partial_profile_rows = _count(
                    cursor, _PARTIAL_PROFILE, (interface_id, interface_id)
                )
                unary_conjunctive_rows = _count(
                    cursor,
                    _UNARY_CONJUNCTIVE,
                    (interface_id, interface_id, interface_id),
                )
                direct_static_rows = _count(
                    cursor, _DIRECT_STATIC_MATCH, (interface_id, interface_id)
                )
                direct_object_rows = _count(
                    cursor, _DIRECT_OBJECT_CANDIDATE, (interface_id, interface_id)
                )
                indexed_object_rows = _count(
                    cursor, _INDEXED_OBJECT_CANDIDATE, (interface_id,)
                )
                factor_rows = _count(
                    cursor, _FACTOR_CANDIDATE, (interface_id, interface_id)
                )
                raw_rows = indexed_object_rows + factor_rows
                ranked_rows = _count(
                    cursor, _RANKED, (interface_id, interface_id, interface_id)
                )
                survivors = _count(
                    cursor, _SURVIVORS, (interface_id, interface_id, interface_id)
                )

                mask_histogram = _histogram(
                    cursor,
                    f"""
                    SELECT mask, count(*)
                      FROM (
                          SELECT ((CASE WHEN expected_factor_type_symbol_id IS NOT NULL THEN 8 ELSE 0 END)
                                + (CASE WHEN expected_object_kind_symbol_id IS NOT NULL THEN 4 ELSE 0 END)
                                + (CASE WHEN role_symbol_id IS NOT NULL THEN 2 ELSE 0 END)
                                + (CASE WHEN lexical_symbol_id IS NOT NULL THEN 1 ELSE 0 END))::INTEGER AS mask
                            FROM ({_OBJECT_DEMAND}) AS demand
                      ) AS masks
                     GROUP BY mask ORDER BY mask
                    """,
                    (interface_id,),
                )
                wildcard_demands = int(mask_histogram.get("0", 0))
                wildcard_rows = wildcard_demands * actor_profiles

                required_count_histogram = _histogram(
                    cursor,
                    f"""
                    SELECT required_count, count(*)
                      FROM (
                          SELECT ((expected_factor_type_symbol_id IS NOT NULL)::INTEGER
                                + (expected_object_kind_symbol_id IS NOT NULL)::INTEGER
                                + (role_symbol_id IS NOT NULL)::INTEGER
                                + (lexical_symbol_id IS NOT NULL)::INTEGER) AS required_count
                            FROM ({_OBJECT_DEMAND}) AS demand
                      ) AS counts
                     GROUP BY required_count ORDER BY required_count
                    """,
                    (interface_id,),
                )
                recency_histogram = _histogram(
                    cursor,
                    f"""SELECT recency_class, count(*) FROM ({_OBJECT_DEMAND}) AS demand
                        GROUP BY recency_class ORDER BY recency_class""",
                    (interface_id,),
                )
                max_candidates_histogram = _histogram(
                    cursor,
                    f"""SELECT max_candidates, count(*) FROM ({_PARENT_DEMAND}) AS demand
                        GROUP BY max_candidates ORDER BY max_candidates""",
                    (interface_id,),
                )
                key_kind_fanout = _histogram(
                    cursor,
                    f"""SELECT key_kind, count(*) FROM ({_UNARY_MATCH}) AS matched
                        GROUP BY key_kind ORDER BY key_kind""",
                    (interface_id, interface_id),
                )

                cursor.execute(
                    f"""
                    SELECT profile.key_kind, profile.key_a, count(*) AS profile_rows
                      FROM ({_PROFILE_KEY}) AS profile
                     GROUP BY profile.key_kind, profile.key_a
                     ORDER BY profile_rows DESC, profile.key_kind, profile.key_a
                     LIMIT 25
                    """,
                    (interface_id,),
                )
                broadest_profile_postings = [
                    {
                        "key_kind": int(kind),
                        "key_a": int(key),
                        "profile_rows": int(rows),
                    }
                    for kind, key, rows in cursor.fetchall()
                ]

                cursor.execute(
                    f"""
                    SELECT required.key_kind, required.key_a, count(*) AS demand_rows
                      FROM ({_REQUIRED_KEY}) AS required
                     GROUP BY required.key_kind, required.key_a
                     ORDER BY demand_rows DESC, required.key_kind, required.key_a
                     LIMIT 25
                    """,
                    (interface_id,),
                )
                broadest_demand_postings = [
                    {"key_kind": int(kind), "key_a": int(key), "demand_rows": int(rows)}
                    for kind, key, rows in cursor.fetchall()
                ]

                # Persistent rewrite surface of the canonical delete-all/reinsert path.
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_demand_candidate AS candidate
                     WHERE EXISTS (
                         SELECT 1 FROM execution.semantic_pnf_interface_export AS export
                          WHERE export.interface_id = %s
                            AND export.target_kind = 3
                            AND export.target_id = candidate.demand_id
                     )
                    """,
                    (interface_id,),
                )
                existing_candidate_rows = int(cursor.fetchone()[0])

                existing = """
                SELECT candidate.demand_id,
                       candidate.ordinal,
                       candidate.target_kind,
                       candidate.target_id,
                       candidate.ancestor_distance,
                       candidate.index_rank,
                       candidate.candidate_score
                  FROM execution.semantic_pnf_demand_candidate AS candidate
                 WHERE EXISTS (
                     SELECT 1 FROM execution.semantic_pnf_interface_export AS export
                      WHERE export.interface_id = %s
                        AND export.target_kind = 3
                        AND export.target_id = candidate.demand_id
                 )
                """
                desired = f"""
                SELECT survivor.demand_id,
                       survivor.ordinal,
                       survivor.target_kind,
                       survivor.target_id,
                       survivor.structural_distance,
                       survivor.index_rank,
                       survivor.candidate_score
                  FROM ({_SURVIVORS}) AS survivor
                """
                cursor.execute(
                    f"""
                    SELECT count(*) FROM (
                        (({existing}) EXCEPT ALL ({desired}))
                        UNION ALL
                        (({desired}) EXCEPT ALL ({existing}))
                    ) AS delta
                    """,
                    (
                        interface_id,
                        interface_id,
                        interface_id,
                        interface_id,
                        interface_id,
                        interface_id,
                        interface_id,
                        interface_id,
                    ),
                )
                semantic_delta_rows = int(cursor.fetchone()[0])
                canonical_candidate_rewrites = existing_candidate_rows + survivors

                cursor.execute(
                    "SELECT count(*) FROM execution.semantic_pnf_frontier_resolution WHERE interface_id = %s",
                    (interface_id,),
                )
                existing_resolution_rows = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    SELECT count(*) FROM execution.semantic_pnf_interface_export
                     WHERE interface_id = %s AND target_kind = 3
                    """,
                    (interface_id,),
                )
                exported_demand_rows = int(cursor.fetchone()[0])

                plans: dict[str, object] = {}
                if plan_mode != "none":
                    analyze = plan_mode == "analyze"
                    specs = {
                        "candidate_unary_match": (
                            _UNARY_MATCH,
                            (interface_id, interface_id),
                        ),
                        "candidate_partial_profile": (
                            _PARTIAL_PROFILE,
                            (interface_id, interface_id),
                        ),
                        "candidate_unary_conjunctive": (
                            _UNARY_CONJUNCTIVE,
                            (interface_id, interface_id, interface_id),
                        ),
                        "candidate_direct_static_conjunction": (
                            _DIRECT_STATIC_MATCH,
                            (interface_id, interface_id),
                        ),
                        "candidate_current_helper": (
                            _INDEXED_OBJECT_CANDIDATE,
                            (interface_id,),
                        ),
                        "factor_candidate": (
                            _FACTOR_CANDIDATE,
                            (interface_id, interface_id),
                        ),
                        "candidate_ranked": (
                            _RANKED,
                            (interface_id, interface_id, interface_id),
                        ),
                        "candidate_survivors": (
                            _SURVIVORS,
                            (interface_id, interface_id, interface_id),
                        ),
                    }
                    for name, (sql, params) in specs.items():
                        plans[name] = _plan(cursor, sql, params, analyze=analyze)

        return {
            "contract_ref": CONTRACT_REF,
            "interface_id": interface_id,
            "region_id": region_id,
            "region_kind": region_kind,
            "graph_revision": revision,
            "interface_cardinality": cardinality,
            "unresolved_count": unresolved,
            "population": {
                "object_demands": object_demands,
                "actor_profiles": actor_profiles,
                "required_key_rows": required_key_rows,
                "profile_key_rows": profile_key_rows,
                "wildcard_demands": wildcard_demands,
                "wildcard_rows": wildcard_rows,
                "candidate_mask_histogram": mask_histogram,
                "required_key_count_histogram": required_count_histogram,
                "recency_histogram": recency_histogram,
                "max_candidates_histogram": max_candidates_histogram,
            },
            "exposure": {
                "unary_key_match_rows": unary_match_rows,
                "unary_match_rows_by_key_kind": key_kind_fanout,
                "partial_profile_rows": partial_profile_rows,
                "unary_conjunctive_rows": unary_conjunctive_rows,
                "direct_static_conjunctive_rows": direct_static_rows,
                "direct_recency_candidate_rows": direct_object_rows,
                "current_helper_candidate_rows": indexed_object_rows,
                "factor_candidate_rows": factor_rows,
                "broadest_profile_postings": broadest_profile_postings,
                "broadest_demand_postings": broadest_demand_postings,
                "direct_helper_cardinality_parity": direct_object_rows
                == indexed_object_rows,
            },
            "ranking": {
                "raw_candidate_rows": raw_rows,
                "deduplicated_rows": ranked_rows,
                "ranked_rows": ranked_rows,
                "max_candidate_survivors": survivors,
            },
            "rewrite": {
                "existing_candidate_rows": existing_candidate_rows,
                "desired_candidate_rows": survivors,
                "candidate_rows_rewritten_by_canonical": canonical_candidate_rewrites,
                "candidate_semantic_delta_rows": semantic_delta_rows,
                "existing_resolution_rows": existing_resolution_rows,
                "exported_demand_rows": exported_demand_rows,
                "resolution_rows_rewritten_by_canonical": existing_resolution_rows
                + exported_demand_rows,
                "resolution_semantic_delta_rows": None,
                "resolution_delta_reason": "requires a pre-rebuild snapshot because demand state transitions are canonical resolution semantics",
            },
            "ratios": {
                "beta_unary_partial_key_rows_per_final_object_candidate": _ratio(
                    unary_match_rows, indexed_object_rows
                ),
                "beta_partial_profiles_per_final_object_candidate": _ratio(
                    partial_profile_rows, indexed_object_rows
                ),
                "beta_rank_raw_rows_per_survivor": _ratio(raw_rows, survivors),
                "beta_write_candidate_rows_per_semantic_delta": _ratio(
                    canonical_candidate_rewrites, semantic_delta_rows
                ),
                "beta_write_is_unbounded_for_zero_delta": semantic_delta_rows == 0
                and canonical_candidate_rewrites > 0,
            },
            "plans": plans,
            "decision_surface": {
                "conjunctive_exposure_candidate": unary_match_rows > direct_static_rows,
                "top_k_candidate": raw_rows > survivors,
                "incremental_candidate_lifecycle_candidate": canonical_candidate_rewrites
                > semantic_delta_rows,
                "wildcard_dominant": direct_static_rows > 0
                and wildcard_rows >= direct_static_rows,
            },
            "plan_mode": plan_mode,
            "semantics": (
                "read-only diagnostic; direct conjunction is the exact legacy static relation cardinality, not a proposed SQL plan; "
                "missing constraints remain wildcard; candidate semantic delta uses EXCEPT ALL on complete ranked row identities"
            ),
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument(
        "--plan-mode", choices=("none", "estimate", "analyze"), default="analyze"
    )
    parser.add_argument("--statement-timeout-ms", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = candidate_work_receipt(
        args.database_url,
        args.interface_id,
        plan_mode=args.plan_mode,
        statement_timeout_ms=args.statement_timeout_ms,
    )
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
