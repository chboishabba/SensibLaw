"""Read-only L/U/C diagnostic for sparse-frontier object candidate exposure.

L = canonical legacy direct conjunction.
U = migration-178 unary-key helper.
C = counterfactual composite masked-signature exposure.

The composite path is diagnostic only. It consumes producer-native canonical
demand columns, emits the finite 16-mask profile posting family, and preserves
the historical lexical ``head OR predicate`` disjunction. Masked-off coordinates
remain NULL and are compared with PostgreSQL's null-safe equality, so every
BIGINT value (including zero) remains available to the semantic ID domain.
Promotion into the canonical reducer requires exact multiset parity plus measured
physical improvement on the same interface/workload.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import psycopg

from diagnose_sparse_frontier_candidate_work import (
    _DIRECT_OBJECT_CANDIDATE,
    _INDEXED_OBJECT_CANDIDATE,
    _OBJECT_DEMAND,
    _PROFILE_BASE,
)
from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-composite-signature-diagnostic.v0_2"
SIGNATURE_ENCODING = "nullable-mask-coordinates"

_DEMAND_SIGNATURE = f"""
WITH object_demand AS MATERIALIZED ({_OBJECT_DEMAND})
SELECT demand.demand_id,
       ((CASE WHEN demand.expected_factor_type_symbol_id IS NOT NULL THEN 8 ELSE 0 END)
        + (CASE WHEN demand.expected_object_kind_symbol_id IS NOT NULL THEN 4 ELSE 0 END)
        + (CASE WHEN demand.role_symbol_id IS NOT NULL THEN 2 ELSE 0 END)
        + (CASE WHEN demand.lexical_symbol_id IS NOT NULL THEN 1 ELSE 0 END))::INTEGER AS mask,
       demand.expected_factor_type_symbol_id::BIGINT AS factor_key,
       demand.expected_object_kind_symbol_id::BIGINT AS object_kind_key,
       demand.role_symbol_id::BIGINT AS role_key,
       demand.lexical_symbol_id::BIGINT AS lexical_key,
       demand.recency_class,
       demand.max_candidates,
       demand.demand_position,
       demand.source_region_start,
       demand.source_region_end
  FROM object_demand AS demand
"""

# One actor-profile row exposes at most sixteen mask families. For lexical masks
# it exposes head and predicate signatures independently, with UNION suppressing
# the duplicate when head == predicate. Masked-off coordinates remain NULL;
# required coordinates only emit a posting when their source value is present.
_PROFILE_SIGNATURE = f"""
WITH profile_base AS MATERIALIZED ({_PROFILE_BASE})
SELECT profile.object_id,
       mask.mask::INTEGER AS mask,
       CASE WHEN (mask.mask & 8) <> 0
            THEN profile.factor_type_symbol_id ELSE NULL END::BIGINT AS factor_key,
       CASE WHEN (mask.mask & 4) <> 0
            THEN profile.object_kind_symbol_id ELSE NULL END::BIGINT AS object_kind_key,
       CASE WHEN (mask.mask & 2) <> 0
            THEN profile.role_symbol_id ELSE NULL END::BIGINT AS role_key,
       lexical.lexical_key,
       profile.occurrence_count,
       profile.first_start_char,
       profile.last_end_char,
       profile.promotion_score
  FROM profile_base AS profile
 CROSS JOIN generate_series(0, 15) AS mask(mask)
 CROSS JOIN LATERAL (
       SELECT NULL::BIGINT AS lexical_key
        WHERE (mask.mask & 1) = 0
       UNION
       SELECT profile.head_symbol_id::BIGINT
        WHERE (mask.mask & 1) <> 0
          AND profile.head_symbol_id IS NOT NULL
       UNION
       SELECT profile.predicate_symbol_id::BIGINT
        WHERE (mask.mask & 1) <> 0
          AND profile.predicate_symbol_id IS NOT NULL
 ) AS lexical
 WHERE ((mask.mask & 8) = 0 OR profile.factor_type_symbol_id IS NOT NULL)
   AND ((mask.mask & 4) = 0 OR profile.object_kind_symbol_id IS NOT NULL)
   AND ((mask.mask & 2) = 0 OR profile.role_symbol_id IS NOT NULL)
"""

_COMPOSITE_STATIC_MATCH = f"""
WITH demand_signature AS MATERIALIZED ({_DEMAND_SIGNATURE}),
profile_signature AS MATERIALIZED ({_PROFILE_SIGNATURE})
SELECT demand.demand_id,
       profile.object_id,
       profile.occurrence_count,
       profile.first_start_char,
       profile.last_end_char,
       profile.promotion_score,
       demand.recency_class,
       demand.max_candidates,
       demand.demand_position,
       demand.source_region_start,
       demand.source_region_end
  FROM demand_signature AS demand
  JOIN profile_signature AS profile
    ON profile.mask = demand.mask
   AND profile.factor_key IS NOT DISTINCT FROM demand.factor_key
   AND profile.object_kind_key IS NOT DISTINCT FROM demand.object_kind_key
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
  FROM ({_COMPOSITE_STATIC_MATCH}) AS match
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

_PARITY_COLUMNS = """
demand_id, target_kind, target_id, structural_distance,
index_rank, candidate_score, max_candidates
"""


def _params(sql: str, interface_id: int) -> tuple[int, ...]:
    return (interface_id,) * sql.count("%s")


def _json_plan(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, list):
        return dict(value[0])
    return dict(value)


def _walk_plan(plan: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield plan
    for child in plan.get("Plans", ()):
        yield from _walk_plan(dict(child))


def _plan_receipt(envelope: dict[str, Any], *, analyze: bool) -> dict[str, object]:
    root = dict(envelope["Plan"])
    nodes = list(_walk_plan(root))
    node_types = Counter(str(node.get("Node Type")) for node in nodes)
    receipt: dict[str, object] = {
        "node_type": root.get("Node Type"),
        "plan_rows": root.get("Plan Rows"),
        "total_cost": root.get("Total Cost"),
        "plan_node_count": len(nodes),
        "node_types": dict(sorted(node_types.items())),
    }
    if analyze:
        receipt.update(
            {
                "planning_ms": envelope.get("Planning Time"),
                "execution_ms": envelope.get("Execution Time"),
                "actual_rows": root.get("Actual Rows"),
                "actual_loops": root.get("Actual Loops"),
                # Root cumulative counters are the authoritative whole-plan
                # values. Child sums would double-count inclusive metrics.
                "shared_hit_blocks": root.get("Shared Hit Blocks", 0),
                "shared_read_blocks": root.get("Shared Read Blocks", 0),
                "temp_read_blocks": root.get("Temp Read Blocks", 0),
                "temp_written_blocks": root.get("Temp Written Blocks", 0),
                "wal_records": root.get("WAL Records", 0),
                "wal_bytes": root.get("WAL Bytes", 0),
                "max_actual_loops": max(
                    (int(node.get("Actual Loops", 0) or 0) for node in nodes),
                    default=0,
                ),
                "max_rows_removed_by_filter": max(
                    (int(node.get("Rows Removed by Filter", 0) or 0) for node in nodes),
                    default=0,
                ),
            }
        )
    return receipt


def _explain(
    cursor: Any,
    sql: str,
    interface_id: int,
    *,
    analyze: bool,
) -> dict[str, object]:
    options = "ANALYZE, BUFFERS, WAL, FORMAT JSON" if analyze else "FORMAT JSON"
    cursor.execute(
        f"EXPLAIN ({options}) SELECT count(*) FROM ({sql}) AS measured",
        _params(sql, interface_id),
    )
    envelope = _json_plan(cursor.fetchone()[0])
    return _plan_receipt(envelope, analyze=analyze)


def _count(cursor: Any, sql: str, interface_id: int) -> int:
    cursor.execute(
        f"SELECT count(*) FROM ({sql}) AS measured", _params(sql, interface_id)
    )
    return int(cursor.fetchone()[0])


def _multiset_difference_count(
    cursor: Any,
    left: str,
    right: str,
    interface_id: int,
) -> int:
    sql = f"""
    SELECT count(*)
      FROM (
          (SELECT {_PARITY_COLUMNS} FROM ({left}) AS left_rows
           EXCEPT ALL
           SELECT {_PARITY_COLUMNS} FROM ({right}) AS right_rows)
      ) AS difference
    """
    cursor.execute(sql, _params(sql, interface_id))
    return int(cursor.fetchone()[0])


def _stage(
    database_url: str,
    interface_id: int,
    name: str,
    sql: str,
    *,
    analyze: bool,
    timeout_ms: int,
) -> dict[str, object]:
    started = time.monotonic()
    try:
        with connect(database_url) as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (str(timeout_ms),),
                    )
                    plan = _explain(cursor, sql, interface_id, analyze=analyze)
        return {
            "stage": name,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "plan": plan,
        }
    except psycopg.errors.QueryCanceled as exc:
        return {
            "stage": name,
            "status": "timeout",
            "timeout_ms": timeout_ms,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stage": name,
            "status": "error",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _parity_receipt(
    database_url: str,
    interface_id: int,
    timeout_ms: int,
) -> dict[str, object]:
    started = time.monotonic()
    try:
        with connect(database_url) as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (str(timeout_ms),),
                    )
                    legacy_rows = _count(cursor, _DIRECT_OBJECT_CANDIDATE, interface_id)
                    composite_rows = _count(
                        cursor, _COMPOSITE_OBJECT_CANDIDATE, interface_id
                    )
                    legacy_minus_composite = _multiset_difference_count(
                        cursor,
                        _DIRECT_OBJECT_CANDIDATE,
                        _COMPOSITE_OBJECT_CANDIDATE,
                        interface_id,
                    )
                    composite_minus_legacy = _multiset_difference_count(
                        cursor,
                        _COMPOSITE_OBJECT_CANDIDATE,
                        _DIRECT_OBJECT_CANDIDATE,
                        interface_id,
                    )
        return {
            "stage": "legacy_composite_parity",
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "legacy_rows": legacy_rows,
            "composite_rows": composite_rows,
            "legacy_minus_composite": legacy_minus_composite,
            "composite_minus_legacy": composite_minus_legacy,
            "exact_multiset_parity": (
                legacy_minus_composite == 0 and composite_minus_legacy == 0
            ),
        }
    except psycopg.errors.QueryCanceled as exc:
        return {
            "stage": "legacy_composite_parity",
            "status": "timeout",
            "timeout_ms": timeout_ms,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stage": "legacy_composite_parity",
            "status": "error",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--mode", choices=("estimate", "bounded-analyze"), default="bounded-analyze"
    )
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--skip-unary", action="store_true")
    args = parser.parse_args()

    stages: list[tuple[str, str]] = [
        ("legacy_direct_object_candidates", _DIRECT_OBJECT_CANDIDATE),
    ]
    if not args.skip_unary:
        stages.append(("m178_unary_object_candidates", _INDEXED_OBJECT_CANDIDATE))
    stages.extend(
        [
            ("composite_demand_signatures", _DEMAND_SIGNATURE),
            ("composite_profile_signatures", _PROFILE_SIGNATURE),
            ("composite_static_matches", _COMPOSITE_STATIC_MATCH),
            ("composite_object_candidates", _COMPOSITE_OBJECT_CANDIDATE),
        ]
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    analyze = args.mode == "bounded-analyze"
    with args.output.open("a", encoding="utf-8") as stream:
        for name, sql in stages:
            receipt = {
                "contract_ref": CONTRACT_REF,
                "signature_encoding": SIGNATURE_ENCODING,
                "interface_id": args.interface_id,
                "mode": args.mode,
                **_stage(
                    args.database_url,
                    args.interface_id,
                    name,
                    sql,
                    analyze=analyze,
                    timeout_ms=args.timeout_ms,
                ),
            }
            stream.write(json.dumps(receipt, sort_keys=True) + "\n")
            stream.flush()
            print(json.dumps(receipt, sort_keys=True), flush=True)

        parity = {
            "contract_ref": CONTRACT_REF,
            "signature_encoding": SIGNATURE_ENCODING,
            "interface_id": args.interface_id,
            "mode": args.mode,
            **_parity_receipt(args.database_url, args.interface_id, args.timeout_ms),
        }
        stream.write(json.dumps(parity, sort_keys=True) + "\n")
        stream.flush()
        print(json.dumps(parity, sort_keys=True), flush=True)

    return 0 if parity.get("exact_multiset_parity") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
