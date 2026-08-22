from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-actor-retention-work-diagnostic.v0_1"

# Read-only M179 diagnostic.  Actor retention has only three semantic axes:
# factor type, object kind, and role.  The finite composite carrier therefore
# has 2^3 = 8 masks.  Lexical identity is deliberately absent because migration
# 062's retention predicate did not use it.

_CHILD_DEMAND = """
SELECT DISTINCT demand.demand_id,
       demand.expected_factor_type_symbol_id,
       demand.expected_object_kind_symbol_id,
       demand.role_symbol_id
  FROM execution.semantic_pnf_region AS child_region
  JOIN execution.semantic_pnf_interface AS child_interface
    ON child_interface.region_id = child_region.region_id
  JOIN execution.semantic_pnf_interface_export AS demand_export
    ON demand_export.interface_id = child_interface.interface_id
   AND demand_export.target_kind = 3
  JOIN execution.semantic_pnf_demand AS demand
    ON demand.demand_id = demand_export.target_id
 WHERE child_region.parent_region_id = %s
   AND demand.state IN (1, 3)
   AND demand.expected_target_kind = 1
"""

_PROFILE_BASE = """
SELECT profile.object_id,
       profile.object_kind_symbol_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id
  FROM execution.semantic_pnf_actor_profile AS profile
 WHERE profile.interface_id = %s
"""

_REQUIRED_KEY = f"""
WITH child_demand AS MATERIALIZED ({_CHILD_DEMAND})
SELECT demand.demand_id,
       key.key_kind,
       key.key_a,
       0::BIGINT AS key_b
  FROM child_demand AS demand
  CROSS JOIN LATERAL (
      VALUES
          (1::SMALLINT, demand.expected_factor_type_symbol_id),
          (2::SMALLINT, demand.expected_object_kind_symbol_id),
          (4::SMALLINT, demand.role_symbol_id)
  ) AS key(key_kind, key_a)
 WHERE key.key_a IS NOT NULL
"""

_PROFILE_KEY = f"""
WITH profile_base AS MATERIALIZED ({_PROFILE_BASE})
SELECT profile.object_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id,
       key.key_kind,
       key.key_a,
       0::BIGINT AS key_b
  FROM profile_base AS profile
  CROSS JOIN LATERAL (
      VALUES
          (1::SMALLINT, profile.factor_type_symbol_id),
          (2::SMALLINT, profile.object_kind_symbol_id),
          (4::SMALLINT, profile.role_symbol_id)
  ) AS key(key_kind, key_a)
 WHERE key.key_a IS NOT NULL
"""

_UNARY_MATCH = f"""
WITH required_key AS MATERIALIZED ({_REQUIRED_KEY}),
profile_key AS MATERIALIZED ({_PROFILE_KEY})
SELECT required_key.demand_id,
       profile.object_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id,
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
       matched.role_symbol_id,
       matched.factor_type_symbol_id,
       matched.predicate_symbol_id,
       count(*)::BIGINT AS matched_count
  FROM ({_UNARY_MATCH}) AS matched
 GROUP BY matched.demand_id,
          matched.object_id,
          matched.role_symbol_id,
          matched.factor_type_symbol_id,
          matched.predicate_symbol_id
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

_DEMAND_SIGNATURE = f"""
SELECT demand.*,
       ((CASE WHEN demand.expected_factor_type_symbol_id IS NOT NULL THEN 4 ELSE 0 END)
        + (CASE WHEN demand.expected_object_kind_symbol_id IS NOT NULL THEN 2 ELSE 0 END)
        + (CASE WHEN demand.role_symbol_id IS NOT NULL THEN 1 ELSE 0 END))::INTEGER
           AS mask,
       demand.expected_factor_type_symbol_id AS factor_key,
       demand.expected_object_kind_symbol_id AS kind_key,
       demand.role_symbol_id AS role_key
  FROM ({_CHILD_DEMAND}) AS demand
"""

_PROFILE_SIGNATURE = f"""
WITH profile_base AS MATERIALIZED ({_PROFILE_BASE})
SELECT profile.object_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id,
       mask.mask,
       CASE WHEN (mask.mask & 4) <> 0 THEN profile.factor_type_symbol_id END
           AS factor_key,
       CASE WHEN (mask.mask & 2) <> 0 THEN profile.object_kind_symbol_id END
           AS kind_key,
       CASE WHEN (mask.mask & 1) <> 0 THEN profile.role_symbol_id END
           AS role_key
  FROM profile_base AS profile
  CROSS JOIN (VALUES (0),(1),(2),(3),(4),(5),(6),(7)) AS mask(mask)
 WHERE ((mask.mask & 4) = 0 OR profile.factor_type_symbol_id IS NOT NULL)
   AND ((mask.mask & 2) = 0 OR profile.object_kind_symbol_id IS NOT NULL)
   AND ((mask.mask & 1) = 0 OR profile.role_symbol_id IS NOT NULL)
"""

_COMPOSITE_MATCH = f"""
WITH demand_signature AS MATERIALIZED ({_DEMAND_SIGNATURE}),
profile_signature AS MATERIALIZED ({_PROFILE_SIGNATURE})
SELECT demand.demand_id,
       profile.object_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id
  FROM demand_signature AS demand
  JOIN profile_signature AS profile
    ON profile.mask = demand.mask
   AND profile.factor_key IS NOT DISTINCT FROM demand.factor_key
   AND profile.kind_key IS NOT DISTINCT FROM demand.kind_key
   AND profile.role_key IS NOT DISTINCT FROM demand.role_key
"""

_COMPOSITE_RETAINED = f"""
SELECT DISTINCT match.object_id,
       match.role_symbol_id,
       match.factor_type_symbol_id,
       match.predicate_symbol_id
  FROM ({_COMPOSITE_MATCH}) AS match
"""

_HELPER_RETAINED = """
SELECT object_id, role_symbol_id, factor_type_symbol_id, predicate_symbol_id
  FROM execution.indexed_numeric_pnf_demanded_actor_profiles(%s, %s)
"""


def _count(cursor: Any, sql: str, params: tuple[object, ...]) -> int:
    cursor.execute(f"SELECT count(*) FROM ({sql}) AS measured", params)
    return int(cursor.fetchone()[0])


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _histogram(rows: list[tuple[Any, Any]]) -> dict[str, int]:
    return {str(key): int(value) for key, value in rows}


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
                "temp_read_blocks": plan.get("Temp Read Blocks", 0),
                "temp_written_blocks": plan.get("Temp Written Blocks", 0),
                "wal_records": plan.get("WAL Records", 0),
                "wal_bytes": plan.get("WAL Bytes", 0),
            }
        )
    return result


def actor_retention_work_receipt(
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
                    SELECT interface.region_id, region.region_kind
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
                region_id, region_kind = (int(value) for value in metadata)

                child_demand_count = _count(cursor, _CHILD_DEMAND, (region_id,))
                actor_profile_count = _count(cursor, _PROFILE_BASE, (interface_id,))
                required_key_rows = _count(cursor, _REQUIRED_KEY, (region_id,))
                profile_key_rows = _count(cursor, _PROFILE_KEY, (interface_id,))
                unary_match_rows = _count(
                    cursor, _UNARY_MATCH, (region_id, interface_id)
                )
                partial_profile_rows = _count(
                    cursor, _PARTIAL_PROFILE, (region_id, interface_id)
                )
                unary_conjunctive_rows = _count(
                    cursor,
                    _UNARY_CONJUNCTIVE,
                    (region_id, region_id, interface_id),
                )
                profile_signature_rows = _count(
                    cursor, _PROFILE_SIGNATURE, (interface_id,)
                )
                composite_match_rows = _count(
                    cursor, _COMPOSITE_MATCH, (region_id, interface_id)
                )
                composite_retained_rows = _count(
                    cursor, _COMPOSITE_RETAINED, (region_id, interface_id)
                )
                helper_retained_rows = _count(
                    cursor, _HELPER_RETAINED, (region_id, interface_id)
                )

                cursor.execute(
                    f"""
                    SELECT mask, count(*)
                      FROM ({_DEMAND_SIGNATURE}) AS signature
                     GROUP BY mask
                     ORDER BY mask
                    """,
                    (region_id,),
                )
                mask_histogram = _histogram(list(cursor.fetchall()))
                wildcard_demand_count = int(mask_histogram.get("0", 0))
                wildcard_rows = wildcard_demand_count * actor_profile_count

                cursor.execute(
                    f"""
                    SELECT matched.key_kind, count(*)
                      FROM ({_UNARY_MATCH}) AS matched
                     GROUP BY matched.key_kind
                     ORDER BY matched.key_kind
                    """,
                    (region_id, interface_id),
                )
                unary_match_rows_by_key_kind = _histogram(list(cursor.fetchall()))

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
                        "key_kind": int(key_kind),
                        "key_a": int(key_a),
                        "profile_rows": int(profile_rows),
                    }
                    for key_kind, key_a, profile_rows in cursor.fetchall()
                ]

                plan_receipts: dict[str, object] = {}
                if plan_mode != "none":
                    analyze = plan_mode == "analyze"
                    plan_specs = {
                        "retention_unary_match": (
                            _UNARY_MATCH,
                            (region_id, interface_id),
                        ),
                        "retention_partial_profile": (
                            _PARTIAL_PROFILE,
                            (region_id, interface_id),
                        ),
                        "retention_unary_conjunctive": (
                            _UNARY_CONJUNCTIVE,
                            (region_id, region_id, interface_id),
                        ),
                        "retention_profile_signature": (
                            _PROFILE_SIGNATURE,
                            (interface_id,),
                        ),
                        "retention_composite_match": (
                            _COMPOSITE_MATCH,
                            (region_id, interface_id),
                        ),
                        "retention_composite_retained": (
                            _COMPOSITE_RETAINED,
                            (region_id, interface_id),
                        ),
                        "retention_current_helper": (
                            _HELPER_RETAINED,
                            (region_id, interface_id),
                        ),
                    }
                    for stage_name, (stage_sql, stage_params) in plan_specs.items():
                        plan_receipts[stage_name] = _plan_receipt(
                            cursor,
                            sql=stage_sql,
                            params=stage_params,
                            analyze=analyze,
                        )

        return {
            "contract_ref": CONTRACT_REF,
            "interface_id": interface_id,
            "region_id": region_id,
            "region_kind": region_kind,
            "population": {
                "child_object_demands": child_demand_count,
                "actor_profiles": actor_profile_count,
                "required_key_rows": required_key_rows,
                "profile_key_rows": profile_key_rows,
                "profile_signature_rows": profile_signature_rows,
                "wildcard_demands": wildcard_demand_count,
                "wildcard_rows": wildcard_rows,
                "retention_mask_histogram": mask_histogram,
            },
            "exposure": {
                "unary_key_match_rows": unary_match_rows,
                "unary_match_rows_by_key_kind": unary_match_rows_by_key_kind,
                "partial_profile_rows": partial_profile_rows,
                "unary_conjunctive_rows": unary_conjunctive_rows,
                "composite_signature_match_rows": composite_match_rows,
                "composite_retained_profile_rows": composite_retained_rows,
                "current_helper_retained_profile_rows": helper_retained_rows,
                "broadest_profile_postings": broadest_profile_postings,
            },
            "ratios": {
                "beta_unary_rows_per_retained_profile": _ratio(
                    unary_match_rows, helper_retained_rows
                ),
                "beta_partial_profiles_per_retained_profile": _ratio(
                    partial_profile_rows, helper_retained_rows
                ),
                "beta_composite_rows_per_retained_profile": _ratio(
                    composite_match_rows, composite_retained_rows
                ),
                "beta_signature_rows_per_actor_profile": _ratio(
                    profile_signature_rows, actor_profile_count
                ),
            },
            "plans": plan_receipts,
            "decision_surface": {
                "composite_signature_candidate": (
                    unary_match_rows > composite_match_rows
                    and composite_retained_rows == helper_retained_rows
                ),
                "wildcard_dominant": (
                    composite_match_rows > 0 and wildcard_rows >= composite_match_rows
                ),
                "helper_composite_cardinality_parity": (
                    composite_retained_rows == helper_retained_rows
                ),
            },
            "plan_mode": plan_mode,
            "semantics": (
                "read-only actor-retention diagnostic; lexical identity is intentionally absent; "
                "mask 0 preserves broad wildcard retention; composite signatures are a counterfactual physical carrier"
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
    )
    parser.add_argument("--statement-timeout-ms", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    receipt = actor_retention_work_receipt(
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
