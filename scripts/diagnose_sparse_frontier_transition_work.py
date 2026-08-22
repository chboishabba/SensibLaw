from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-transition-work-diagnostic.v0_1"

# This probe is intentionally read-only.  It does not install another migration
# or mutate sparse-frontier authority.  Its job is to make the next optimisation
# choice empirical by measuring the complete transition-work funnel:
#
#   demand/profile population
#   -> unary key expansion
#   -> partial-key fanout
#   -> post-hoc conjunctive recovery
#   -> finite-mask composite-signature alternative
#   -> recency-qualified object/factor candidates
#   -> dedup/ranking/maxCandidates
#   -> current persistent candidate/resolution rewrite surface
#
# The finite mask encoding matches the Agda reference:
#   bit 3 = factor, bit 2 = object kind, bit 1 = role, bit 0 = lexical.
# Actor retention deliberately omits lexical identity and therefore uses only
# the upper three semantic axes (eight masks).

_PARENT_DEMAND = """
SELECT demand.demand_id,
       demand.expected_target_kind,
       demand.expected_factor_type_symbol_id,
       demand.expected_object_kind_symbol_id,
       demand.role_symbol_id,
       demand.lexical_symbol_id,
       demand.recency_class,
       demand.max_candidates,
       COALESCE(demand.source_start_char, source_region.end_char)
           AS demand_position,
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
SELECT *
  FROM ({_PARENT_DEMAND}) AS demand
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
SELECT demand.demand_id,
       key.key_kind,
       key.key_a,
       0::BIGINT AS key_b
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
SELECT DISTINCT
       profile.object_id,
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

_UNARY_KEY_MATCH = f"""
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

_PARTIAL_MATCHED_PROFILE = f"""
SELECT match.demand_id,
       match.object_id,
       match.object_kind_symbol_id,
       match.role_symbol_id,
       match.factor_type_symbol_id,
       match.predicate_symbol_id,
       match.occurrence_count,
       match.first_start_char,
       match.last_end_char,
       match.promotion_score,
       count(*)::BIGINT AS matched_count
  FROM ({_UNARY_KEY_MATCH}) AS match
 GROUP BY match.demand_id,
          match.object_id,
          match.object_kind_symbol_id,
          match.role_symbol_id,
          match.factor_type_symbol_id,
          match.predicate_symbol_id,
          match.occurrence_count,
          match.first_start_char,
          match.last_end_char,
          match.promotion_score
"""

_UNARY_CONJUNCTIVE_PROFILE = f"""
WITH required_count AS MATERIALIZED (
    SELECT required_key.demand_id,
           count(*)::BIGINT AS required_count
      FROM ({_REQUIRED_KEY}) AS required_key
     GROUP BY required_key.demand_id
),
matched_profile AS MATERIALIZED ({_PARTIAL_MATCHED_PROFILE})
SELECT matched.*
  FROM matched_profile AS matched
  JOIN required_count AS required
    ON required.demand_id = matched.demand_id
   AND required.required_count = matched.matched_count
"""

# A profile is projected to each applicable constraint mask.  This is a
# diagnostic realization of the proposed finite-mask geometry, not production
# authority.  Non-lexical masks contribute at most 8 rows/profile; lexical masks
# contribute at most 16 rows/profile because head and predicate are the legacy
# lexical disjunction.  DISTINCT collapses head=predicate duplicates.
_PROFILE_SIGNATURE = f"""
WITH profile_base AS MATERIALIZED ({_PROFILE_BASE}),
nonlexical AS (
    SELECT profile.object_id,
           profile.occurrence_count,
           profile.first_start_char,
           profile.last_end_char,
           profile.promotion_score,
           mask.mask,
           CASE WHEN (mask.mask & 8) <> 0 THEN profile.factor_type_symbol_id END
               AS factor_key,
           CASE WHEN (mask.mask & 4) <> 0 THEN profile.object_kind_symbol_id END
               AS kind_key,
           CASE WHEN (mask.mask & 2) <> 0 THEN profile.role_symbol_id END
               AS role_key,
           NULL::BIGINT AS lexical_key
      FROM profile_base AS profile
      CROSS JOIN (VALUES (0),(2),(4),(6),(8),(10),(12),(14)) AS mask(mask)
     WHERE ((mask.mask & 8) = 0 OR profile.factor_type_symbol_id IS NOT NULL)
       AND ((mask.mask & 4) = 0 OR profile.object_kind_symbol_id IS NOT NULL)
       AND ((mask.mask & 2) = 0 OR profile.role_symbol_id IS NOT NULL)
),
profile_lexical AS (
    SELECT DISTINCT profile.object_id,
           profile.occurrence_count,
           profile.first_start_char,
           profile.last_end_char,
           profile.promotion_score,
           profile.object_kind_symbol_id,
           profile.role_symbol_id,
           profile.factor_type_symbol_id,
           lexical.lexical_key
      FROM profile_base AS profile
      CROSS JOIN LATERAL (
          VALUES (profile.predicate_symbol_id), (profile.head_symbol_id)
      ) AS lexical(lexical_key)
     WHERE lexical.lexical_key IS NOT NULL
),
lexical AS (
    SELECT profile.object_id,
           profile.occurrence_count,
           profile.first_start_char,
           profile.last_end_char,
           profile.promotion_score,
           mask.mask,
           CASE WHEN (mask.mask & 8) <> 0 THEN profile.factor_type_symbol_id END
               AS factor_key,
           CASE WHEN (mask.mask & 4) <> 0 THEN profile.object_kind_symbol_id END
               AS kind_key,
           CASE WHEN (mask.mask & 2) <> 0 THEN profile.role_symbol_id END
               AS role_key,
           profile.lexical_key
      FROM profile_lexical AS profile
      CROSS JOIN (VALUES (1),(3),(5),(7),(9),(11),(13),(15)) AS mask(mask)
     WHERE ((mask.mask & 8) = 0 OR profile.factor_type_symbol_id IS NOT NULL)
       AND ((mask.mask & 4) = 0 OR profile.object_kind_symbol_id IS NOT NULL)
       AND ((mask.mask & 2) = 0 OR profile.role_symbol_id IS NOT NULL)
)
SELECT * FROM nonlexical
UNION ALL
SELECT * FROM lexical
"""

_DEMAND_SIGNATURE = f"""
SELECT demand.*,
       ((CASE WHEN demand.expected_factor_type_symbol_id IS NOT NULL THEN 8 ELSE 0 END)
        + (CASE WHEN demand.expected_object_kind_symbol_id IS NOT NULL THEN 4 ELSE 0 END)
        + (CASE WHEN demand.role_symbol_id IS NOT NULL THEN 2 ELSE 0 END)
        + (CASE WHEN demand.lexical_symbol_id IS NOT NULL THEN 1 ELSE 0 END))::INTEGER
           AS mask,
       demand.expected_factor_type_symbol_id AS factor_key,
       demand.expected_object_kind_symbol_id AS kind_key,
       demand.role_symbol_id AS role_key,
       demand.lexical_symbol_id AS lexical_key
  FROM ({_OBJECT_DEMAND}) AS demand
"""

_COMPOSITE_SIGNATURE_MATCH = f"""
WITH demand_signature AS MATERIALIZED ({_DEMAND_SIGNATURE}),
profile_signature AS MATERIALIZED ({_PROFILE_SIGNATURE})
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
  FROM demand_signature AS demand
  JOIN profile_signature AS profile
    ON profile.mask = demand.mask
   AND profile.factor_key IS NOT DISTINCT FROM demand.factor_key
   AND profile.kind_key IS NOT DISTINCT FROM demand.kind_key
   AND profile.role_key IS NOT DISTINCT FROM demand.role_key
   AND profile.lexical_key IS NOT DISTINCT FROM demand.lexical_key
"""

_COMPOSITE_OBJECT_CANDIDATE = f"""
SELECT match.demand_id,
       1::SMALLINT AS target_kind,
       match.object_id AS target_id,
       abs(match.demand_position - match.last_end_char) AS structural_distance,
       0::BIGINT AS index_rank,
       match.promotion_score
           + ln(1 + match.occurrence_count)::DOUBLE PRECISION AS candidate_score,
       match.max_candidates
  FROM ({_COMPOSITE_SIGNATURE_MATCH}) AS match
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
       abs(demand.demand_position - factor_region.end_char)
           AS structural_distance,
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
   AND (
       demand.expected_factor_type_symbol_id IS NULL
       OR demand.expected_factor_type_symbol_id = factor.factor_type_symbol_id
   )
   AND (
       demand.lexical_symbol_id IS NULL
       OR demand.lexical_symbol_id = factor.predicate_symbol_id
   )
   AND (
       demand.recency_class IN (4, 5)
       OR factor_region.end_char <= demand.demand_position
   )
"""

_DOWNSTREAM = f"""
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
  FROM ({_DOWNSTREAM}) AS ranked
 WHERE ranked.candidate_ordinal < ranked.max_candidates
"""


def _count(cursor: Any, sql: str, params: tuple[object, ...]) -> int:
    cursor.execute(f"SELECT count(*) FROM ({sql}) AS measured", params)
    return int(cursor.fetchone()[0])


def _rows(cursor: Any, sql: str, params: tuple[object, ...]) -> list[tuple[Any, ...]]:
    cursor.execute(sql, params)
    return list(cursor.fetchall())


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _json_plan(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, list):
        return dict(value[0])
    return dict(value)


def _plan_receipt(
    cursor: Any,
    *,
    sql: str,
    params: tuple[object, ...],
    analyze: bool,
) -> dict[str, object]:
    options = "ANALYZE, BUFFERS, WAL, FORMAT JSON" if analyze else "FORMAT JSON"
    cursor.execute(f"EXPLAIN ({options}) {sql}", params)
    envelope = _json_plan(cursor.fetchone()[0])
    plan = dict(envelope["Plan"])
    result: dict[str, object] = {
        "node_type": plan.get("Node Type"),
        "plan_rows": plan.get("Plan Rows"),
        "plan_width": plan.get("Plan Width"),
        "total_cost": plan.get("Total Cost"),
    }
    if analyze:
        result.update(
            {
                "planning_ms": envelope.get("Planning Time"),
                "execution_ms": envelope.get("Execution Time"),
                "actual_rows": plan.get("Actual Rows"),
                "actual_loops": plan.get("Actual Loops"),
                "shared_hit_blocks": plan.get("Shared Hit Blocks", 0),
                "shared_read_blocks": plan.get("Shared Read Blocks", 0),
                "shared_dirtied_blocks": plan.get("Shared Dirtied Blocks", 0),
                "shared_written_blocks": plan.get("Shared Written Blocks", 0),
                "temp_read_blocks": plan.get("Temp Read Blocks", 0),
                "temp_written_blocks": plan.get("Temp Written Blocks", 0),
                "wal_records": plan.get("WAL Records", 0),
                "wal_bytes": plan.get("WAL Bytes", 0),
            }
        )
    return result


def _histogram(rows: Iterable[tuple[Any, Any]]) -> dict[str, int]:
    return {str(key): int(value) for key, value in rows}


def transition_work_receipt(
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
                # The transaction remains read-only after SET TRANSACTION.  Temp
                # files created by sorts/hashes are execution artifacts, not
                # semantic writes.
                cursor.execute("SET TRANSACTION READ ONLY")
                if statement_timeout_ms > 0:
                    cursor.execute("SET LOCAL statement_timeout = %s", (statement_timeout_ms,))

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
                region_id, region_kind, interface_cardinality, unresolved_count, graph_revision = (
                    int(value) for value in metadata
                )

                object_demand_count = _count(cursor, _OBJECT_DEMAND, (interface_id,))
                actor_profile_count = _count(cursor, _PROFILE_BASE, (interface_id,))
                required_key_rows = _count(cursor, _REQUIRED_KEY, (interface_id,))
                profile_key_rows = _count(cursor, _PROFILE_KEY, (interface_id,))
                unary_key_match_rows = _count(
                    cursor, _UNARY_KEY_MATCH, (interface_id, interface_id)
                )
                partial_matched_profile_rows = _count(
                    cursor, _PARTIAL_MATCHED_PROFILE, (interface_id, interface_id)
                )
                unary_conjunctive_profile_rows = _count(
                    cursor,
                    _UNARY_CONJUNCTIVE_PROFILE,
                    (interface_id, interface_id, interface_id),
                )
                profile_signature_rows = _count(cursor, _PROFILE_SIGNATURE, (interface_id,))
                composite_signature_posting_rows = _count(
                    cursor,
                    _COMPOSITE_SIGNATURE_MATCH,
                    (interface_id, interface_id),
                )
                composite_object_candidate_rows = _count(
                    cursor,
                    _COMPOSITE_OBJECT_CANDIDATE,
                    (interface_id, interface_id),
                )
                indexed_object_candidate_rows = _count(
                    cursor, _INDEXED_OBJECT_CANDIDATE, (interface_id,)
                )
                factor_candidate_rows = _count(
                    cursor, _FACTOR_CANDIDATE, (interface_id, interface_id)
                )
                raw_candidate_rows = indexed_object_candidate_rows + factor_candidate_rows
                ranked_rows = _count(
                    cursor,
                    _DOWNSTREAM,
                    (interface_id, interface_id, interface_id),
                )
                survivor_rows = _count(
                    cursor,
                    _SURVIVORS,
                    (interface_id, interface_id, interface_id),
                )

                cursor.execute(
                    f"""
                    SELECT mask, count(*)
                      FROM ({_DEMAND_SIGNATURE}) AS signature
                     GROUP BY mask
                     ORDER BY mask
                    """,
                    (interface_id,),
                )
                candidate_mask_histogram = _histogram(cursor.fetchall())

                cursor.execute(
                    f"""
                    SELECT required_count, count(*)
                      FROM (
                          SELECT demand.demand_id,
                                 ((demand.expected_factor_type_symbol_id IS NOT NULL)::INTEGER
                                  + (demand.expected_object_kind_symbol_id IS NOT NULL)::INTEGER
                                  + (demand.role_symbol_id IS NOT NULL)::INTEGER
                                  + (demand.lexical_symbol_id IS NOT NULL)::INTEGER)
                                     AS required_count
                            FROM ({_OBJECT_DEMAND}) AS demand
                      ) AS counts
                     GROUP BY required_count
                     ORDER BY required_count
                    """,
                    (interface_id,),
                )
                required_key_count_histogram = _histogram(cursor.fetchall())

                cursor.execute(
                    f"""
                    SELECT recency_class, count(*)
                      FROM ({_OBJECT_DEMAND}) AS demand
                     GROUP BY recency_class
                     ORDER BY recency_class
                    """,
                    (interface_id,),
                )
                recency_histogram = _histogram(cursor.fetchall())

                cursor.execute(
                    f"""
                    SELECT max_candidates, count(*)
                      FROM ({_PARENT_DEMAND}) AS demand
                     GROUP BY max_candidates
                     ORDER BY max_candidates
                    """,
                    (interface_id,),
                )
                max_candidates_histogram = _histogram(cursor.fetchall())

                cursor.execute(
                    f"""
                    SELECT match.key_kind, count(*)
                      FROM ({_UNARY_KEY_MATCH}) AS match
                     GROUP BY match.key_kind
                     ORDER BY match.key_kind
                    """,
                    (interface_id, interface_id),
                )
                unary_match_rows_by_key_kind = _histogram(cursor.fetchall())

                # Broadest unary postings reveal which individual keys recreate
                # most of the demand x profile product before conjunction.
                cursor.execute(
                    f"""
                    SELECT profile.key_kind,
                           profile.key_a,
                           count(*) AS profile_rows
                      FROM ({_PROFILE_KEY}) AS profile
                     GROUP BY profile.key_kind, profile.key_a
                     ORDER BY profile_rows DESC, profile.key_kind, profile.key_a
                     LIMIT 25
                    """,
                    (interface_id,),
                )
                broadest_profile_postings = [
                    {
                        "key_kind": int(key_kind),
                        "key_a": int(key_a),
                        "profile_rows": int(profile_rows),
                    }
                    for key_kind, key_a, profile_rows in cursor.fetchall()
                ]

                cursor.execute(
                    f"""
                    SELECT required.key_kind,
                           required.key_a,
                           count(*) AS demand_rows
                      FROM ({_REQUIRED_KEY}) AS required
                     GROUP BY required.key_kind, required.key_a
                     ORDER BY demand_rows DESC, required.key_kind, required.key_a
                     LIMIT 25
                    """,
                    (interface_id,),
                )
                broadest_demand_postings = [
                    {
                        "key_kind": int(key_kind),
                        "key_a": int(key_a),
                        "demand_rows": int(demand_rows),
                    }
                    for key_kind, key_a, demand_rows in cursor.fetchall()
                ]

                # Actor-retention uses only factor/kind/role.  Report its mask
                # distribution even though this diagnostic does not mutate or
                # re-run the retention DELETE.
                cursor.execute(
                    f"""
                    SELECT retention_mask, count(*)
                      FROM (
                          SELECT demand.demand_id,
                                 ((CASE WHEN demand.expected_factor_type_symbol_id IS NOT NULL THEN 4 ELSE 0 END)
                                  + (CASE WHEN demand.expected_object_kind_symbol_id IS NOT NULL THEN 2 ELSE 0 END)
                                  + (CASE WHEN demand.role_symbol_id IS NOT NULL THEN 1 ELSE 0 END))::INTEGER
                                     AS retention_mask
                            FROM ({_OBJECT_DEMAND}) AS demand
                      ) AS masks
                     GROUP BY retention_mask
                     ORDER BY retention_mask
                    """,
                    (interface_id,),
                )
                retention_mask_histogram = _histogram(cursor.fetchall())

                unconstrained_object_demands = int(candidate_mask_histogram.get("0", 0))
                wildcard_object_rows = unconstrained_object_demands * actor_profile_count

                # Candidate lifecycle rewrite surface.  The canonical reducer
                # deletes candidate rows for exported demands, then reinserts the
                # ranked survivors.  Symmetric difference measures how many row
                # identities would actually need to change if the desired set
                # were maintained incrementally.
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_demand_candidate AS candidate
                     WHERE EXISTS (
                         SELECT 1
                           FROM execution.semantic_pnf_interface_export AS export
                          WHERE export.interface_id = %s
                            AND export.target_kind = 3
                            AND export.target_id = candidate.demand_id
                     )
                    """,
                    (interface_id,),
                )
                existing_candidate_rows = int(cursor.fetchone()[0])

                desired_sql = f"""
                SELECT survivor.demand_id,
                       survivor.ordinal,
                       survivor.target_kind,
                       survivor.target_id,
                       survivor.structural_distance,
                       survivor.index_rank,
                       survivor.candidate_score
                  FROM ({_SURVIVORS}) AS survivor
                """
                existing_sql = """
                SELECT candidate.demand_id,
                       candidate.ordinal,
                       candidate.target_kind,
                       candidate.target_id,
                       candidate.ancestor_distance AS structural_distance,
                       candidate.index_rank,
                       candidate.candidate_score
                  FROM execution.semantic_pnf_demand_candidate AS candidate
                 WHERE EXISTS (
                     SELECT 1
                       FROM execution.semantic_pnf_interface_export AS export
                      WHERE export.interface_id = %s
                        AND export.target_kind = 3
                        AND export.target_id = candidate.demand_id
                 )
                """
                cursor.execute(
                    f"""
                    SELECT count(*)
                      FROM (
                          (({existing_sql}) EXCEPT ALL ({desired_sql}))
                          UNION ALL
                          (({desired_sql}) EXCEPT ALL ({existing_sql}))
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
                    ),
                )
                candidate_semantic_delta_rows = int(cursor.fetchone()[0])
                candidate_rows_rewritten_by_canonical = existing_candidate_rows + survivor_rows

                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_frontier_resolution
                     WHERE interface_id = %s
                    """,
                    (interface_id,),
                )
                existing_resolution_rows = int(cursor.fetchone()[0])
                # Canonical reduction deletes all current resolution rows for the
                # interface and republishes one row for every still-exported
                # demand considered by the resolution stage.  We expose the
                # population separately because exact semantic delta needs a
                # pre-rebuild state snapshot to distinguish state transitions.
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_interface_export AS export
                      JOIN execution.semantic_pnf_demand AS demand
                        ON demand.demand_id = export.target_id
                     WHERE export.interface_id = %s
                       AND export.target_kind = 3
                    """,
                    (interface_id,),
                )
                exported_demand_rows = int(cursor.fetchone()[0])
                resolution_rows_rewritten_by_canonical = (
                    existing_resolution_rows + exported_demand_rows
                )

                plan_receipts: dict[str, object] = {}
                if plan_mode != "none":
                    analyze = plan_mode == "analyze"
                    plan_specs = {
                        "unary_key_match": (
                            _UNARY_KEY_MATCH,
                            (interface_id, interface_id),
                        ),
                        "partial_matched_profile": (
                            _PARTIAL_MATCHED_PROFILE,
                            (interface_id, interface_id),
                        ),
                        "unary_conjunctive_profile": (
                            _UNARY_CONJUNCTIVE_PROFILE,
                            (interface_id, interface_id, interface_id),
                        ),
                        "profile_signature_projection": (
                            _PROFILE_SIGNATURE,
                            (interface_id,),
                        ),
                        "composite_signature_match": (
                            _COMPOSITE_SIGNATURE_MATCH,
                            (interface_id, interface_id),
                        ),
                        "composite_object_candidate": (
                            _COMPOSITE_OBJECT_CANDIDATE,
                            (interface_id, interface_id),
                        ),
                        "indexed_object_candidate": (
                            _INDEXED_OBJECT_CANDIDATE,
                            (interface_id,),
                        ),
                        "factor_candidate": (
                            _FACTOR_CANDIDATE,
                            (interface_id, interface_id),
                        ),
                        "ranked_candidate": (
                            _DOWNSTREAM,
                            (interface_id, interface_id, interface_id),
                        ),
                        "max_candidate_survivor": (
                            _SURVIVORS,
                            (interface_id, interface_id, interface_id),
                        ),
                    }
                    for stage_name, (stage_sql, stage_params) in plan_specs.items():
                        plan_receipts[stage_name] = _plan_receipt(
                            cursor,
                            sql=stage_sql,
                            params=stage_params,
                            analyze=analyze,
                        )

        beta_unary = _ratio(unary_key_match_rows, indexed_object_candidate_rows)
        beta_partial = _ratio(partial_matched_profile_rows, indexed_object_candidate_rows)
        beta_rank = _ratio(raw_candidate_rows, survivor_rows)
        beta_write = _ratio(
            candidate_rows_rewritten_by_canonical,
            candidate_semantic_delta_rows,
        )
        beta_signature_storage = _ratio(profile_signature_rows, actor_profile_count)
        beta_composite = _ratio(
            composite_signature_posting_rows,
            composite_object_candidate_rows,
        )

        return {
            "contract_ref": CONTRACT_REF,
            "interface_id": interface_id,
            "region_id": region_id,
            "region_kind": region_kind,
            "graph_revision": graph_revision,
            "interface_cardinality": interface_cardinality,
            "unresolved_count": unresolved_count,
            "population": {
                "object_demands": object_demand_count,
                "actor_profiles": actor_profile_count,
                "required_key_rows": required_key_rows,
                "profile_key_rows": profile_key_rows,
                "profile_signature_rows": profile_signature_rows,
                "unconstrained_object_demands": unconstrained_object_demands,
                "wildcard_object_rows": wildcard_object_rows,
                "candidate_mask_histogram": candidate_mask_histogram,
                "retention_mask_histogram": retention_mask_histogram,
                "required_key_count_histogram": required_key_count_histogram,
                "recency_histogram": recency_histogram,
                "max_candidates_histogram": max_candidates_histogram,
            },
            "exposure": {
                "unary_key_match_rows": unary_key_match_rows,
                "unary_match_rows_by_key_kind": unary_match_rows_by_key_kind,
                "partial_matched_profile_rows": partial_matched_profile_rows,
                "unary_conjunctive_profile_rows": unary_conjunctive_profile_rows,
                "composite_signature_posting_rows": composite_signature_posting_rows,
                "composite_object_candidate_rows": composite_object_candidate_rows,
                "indexed_object_candidate_rows": indexed_object_candidate_rows,
                "factor_candidate_rows": factor_candidate_rows,
                "broadest_profile_postings": broadest_profile_postings,
                "broadest_demand_postings": broadest_demand_postings,
            },
            "ranking": {
                "raw_candidate_rows": raw_candidate_rows,
                "deduplicated_rows": ranked_rows,
                "ranked_rows": ranked_rows,
                "max_candidate_survivors": survivor_rows,
            },
            "rewrite": {
                "existing_candidate_rows": existing_candidate_rows,
                "desired_candidate_rows": survivor_rows,
                "candidate_rows_rewritten_by_canonical": candidate_rows_rewritten_by_canonical,
                "candidate_semantic_delta_rows": candidate_semantic_delta_rows,
                "existing_resolution_rows": existing_resolution_rows,
                "exported_demand_rows": exported_demand_rows,
                "resolution_rows_rewritten_by_canonical": resolution_rows_rewritten_by_canonical,
                "resolution_semantic_delta_rows": None,
                "resolution_delta_reason": (
                    "requires a pre-rebuild snapshot because demand state transitions are part of canonical resolution"
                ),
            },
            "ratios": {
                "beta_unary_partial_key_rows_per_final_object_candidate": beta_unary,
                "beta_partial_profiles_per_final_object_candidate": beta_partial,
                "beta_rank_raw_rows_per_survivor": beta_rank,
                "beta_write_candidate_rows_per_semantic_delta": beta_write,
                "beta_signature_rows_per_actor_profile": beta_signature_storage,
                "beta_composite_static_rows_per_recency_candidate": beta_composite,
                "beta_write_is_unbounded_for_zero_delta": (
                    candidate_semantic_delta_rows == 0
                    and candidate_rows_rewritten_by_canonical > 0
                ),
            },
            "plans": plan_receipts,
            "decision_surface": {
                "composite_signature_candidate": (
                    beta_unary is not None
                    and beta_unary > 1.0
                    and composite_signature_posting_rows <= unary_key_match_rows
                ),
                "top_k_candidate": beta_rank is not None and beta_rank > 1.0,
                "incremental_candidate_lifecycle_candidate": (
                    candidate_rows_rewritten_by_canonical > candidate_semantic_delta_rows
                ),
                "wildcard_dominant": (
                    indexed_object_candidate_rows > 0
                    and wildcard_object_rows >= indexed_object_candidate_rows
                ),
            },
            "plan_mode": plan_mode,
            "semantics": (
                "read-only diagnostic; composite signature rows are a finite-mask counterfactual, "
                "not production authority; missing constraints remain explicit wildcard work; "
                "candidate rewrite delta compares complete ranked candidate row identities with EXCEPT ALL"
            ),
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument(
        "--plan-mode",
        choices=("none", "estimate", "analyze"),
        default="analyze",
        help="EXPLAIN mode for expensive transition stages; analyze captures actual temp/buffer work",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=0,
        help="optional per-stage PostgreSQL timeout; 0 leaves the server default",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    receipt = transition_work_receipt(
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
