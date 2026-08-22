"""Read-only mask-local candidate lookup and parity diagnostic.

This is the C2 pre-promotion probe for sparse-frontier object candidates.
It does not create a production posting table or change semantic authority.
Instead it asks whether the finite four-axis demand mask can be compiled into
index-addressable SQL branches without materialising the 16x profile-signature
relation used by the C1 experiment.

For each selected mask m in [0, 15] the probe records:

    N_D(m)      object demands in the mask fibre
    N_P(m)      actor-profile postings capable of serving that mask
    T_C2(m)     bounded EXPLAIN ANALYZE of the mask-specialised candidate branch
    parity(m)   exact EXCEPT ALL in both directions against legacy semantics

Lexical masks are split into predicate and object-head branches.  UNION is
performed over the full actor-profile identity and demand coordinates so one
profile row matching both lexical coordinates is emitted once, while genuinely
distinct profile rows remain distinct.  Mask zero remains an explicit broad
fallback; absence of constraints is never treated as negative evidence.
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
    _OBJECT_DEMAND,
)
from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-mask-bucket-diagnostic.v0_1"
MASK_BITS = {
    "factor": 8,
    "object_kind": 4,
    "role": 2,
    "lexical": 1,
}
_PARITY_COLUMNS = """
demand_id, target_kind, target_id, structural_distance,
index_rank, candidate_score, max_candidates
"""


def _params(sql: str, interface_id: int) -> tuple[int, ...]:
    return (interface_id,) * sql.count("%s")


def _mask_expression(alias: str) -> str:
    return f"""(
        (CASE WHEN {alias}.expected_factor_type_symbol_id IS NOT NULL THEN 8 ELSE 0 END)
      + (CASE WHEN {alias}.expected_object_kind_symbol_id IS NOT NULL THEN 4 ELSE 0 END)
      + (CASE WHEN {alias}.role_symbol_id IS NOT NULL THEN 2 ELSE 0 END)
      + (CASE WHEN {alias}.lexical_symbol_id IS NOT NULL THEN 1 ELSE 0 END)
    )"""


def _mask_demand_sql(mask: int) -> str:
    return f"""
SELECT demand.*
  FROM ({_OBJECT_DEMAND}) AS demand
 WHERE {_mask_expression('demand')} = {mask}
"""


def _active(mask: int, bit: int) -> bool:
    return (mask & bit) != 0


def _profile_join_conditions(mask: int) -> list[str]:
    conditions = ["profile.interface_id = %s"]
    if _active(mask, MASK_BITS["factor"]):
        conditions.append(
            "profile.factor_type_symbol_id = demand.expected_factor_type_symbol_id"
        )
    if _active(mask, MASK_BITS["object_kind"]):
        conditions.append(
            "profile.object_kind_symbol_id = demand.expected_object_kind_symbol_id"
        )
    if _active(mask, MASK_BITS["role"]):
        conditions.append("profile.role_symbol_id = demand.role_symbol_id")
    return conditions


def _profile_identity_projection() -> str:
    # Keep the physical row identity through lexical UNION.  Projecting only the
    # final candidate columns here would incorrectly collapse two distinct actor
    # profile rows that happen to produce the same candidate observation.
    return """
       demand.demand_id,
       demand.recency_class,
       demand.max_candidates,
       demand.demand_position,
       demand.source_region_start,
       demand.source_region_end,
       profile.object_id,
       profile.object_kind_symbol_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id,
       profile.occurrence_count,
       profile.first_start_char,
       profile.last_end_char,
       profile.promotion_score
"""


def _mask_profile_match_sql(mask: int) -> str:
    demand = _mask_demand_sql(mask)
    conditions = "\n   AND ".join(_profile_join_conditions(mask))
    projection = _profile_identity_projection()

    if not _active(mask, MASK_BITS["lexical"]):
        return f"""
WITH demand AS MATERIALIZED ({demand})
SELECT {projection}
  FROM demand
  JOIN execution.semantic_pnf_actor_profile AS profile
    ON {conditions}
"""

    return f"""
WITH demand AS MATERIALIZED ({demand}),
predicate_hit AS (
    SELECT {projection}
      FROM demand
      JOIN execution.semantic_pnf_actor_profile AS profile
        ON {conditions}
       AND profile.predicate_symbol_id = demand.lexical_symbol_id
),
head_hit AS (
    SELECT {projection}
      FROM demand
      JOIN execution.semantic_pnf_actor_profile AS profile
        ON {conditions}
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id = profile.object_id
       AND object.head_symbol_id = demand.lexical_symbol_id
),
profile_match AS (
    SELECT * FROM predicate_hit
    UNION
    SELECT * FROM head_hit
)
SELECT * FROM profile_match
"""


def _mask_candidate_sql(mask: int) -> str:
    match_sql = _mask_profile_match_sql(mask)
    return f"""
SELECT match.demand_id,
       1::SMALLINT AS target_kind,
       match.object_id AS target_id,
       abs(match.demand_position - match.last_end_char) AS structural_distance,
       0::BIGINT AS index_rank,
       match.promotion_score
           + ln(1 + match.occurrence_count)::DOUBLE PRECISION AS candidate_score,
       match.max_candidates
  FROM ({match_sql}) AS match
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


def _legacy_mask_candidate_sql(mask: int) -> str:
    return f"""
SELECT legacy.*
  FROM ({_DIRECT_OBJECT_CANDIDATE}) AS legacy
  JOIN execution.semantic_pnf_demand AS demand
    ON demand.demand_id = legacy.demand_id
 WHERE {_mask_expression('demand')} = {mask}
"""


def _mask_profile_posting_sql(mask: int) -> str:
    required = []
    if _active(mask, MASK_BITS["factor"]):
        required.append("profile.factor_type_symbol_id IS NOT NULL")
    if _active(mask, MASK_BITS["object_kind"]):
        required.append("profile.object_kind_symbol_id IS NOT NULL")
    if _active(mask, MASK_BITS["role"]):
        required.append("profile.role_symbol_id IS NOT NULL")
    where = "\n   AND ".join(["profile.interface_id = %s", *required])

    if not _active(mask, MASK_BITS["lexical"]):
        return f"""
SELECT profile.object_id,
       profile.object_kind_symbol_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id
  FROM execution.semantic_pnf_actor_profile AS profile
 WHERE {where}
"""

    return f"""
SELECT profile.object_id,
       profile.object_kind_symbol_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id,
       lexical.lexical_symbol_id
  FROM execution.semantic_pnf_actor_profile AS profile
  JOIN execution.semantic_pnf_object AS object
    ON object.object_id = profile.object_id
 CROSS JOIN LATERAL (
       SELECT profile.predicate_symbol_id AS lexical_symbol_id
        WHERE profile.predicate_symbol_id IS NOT NULL
       UNION
       SELECT object.head_symbol_id
        WHERE object.head_symbol_id IS NOT NULL
 ) AS lexical
 WHERE {where}
"""


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


def _run_plan_stage(
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
                    options = (
                        "ANALYZE, BUFFERS, WAL, FORMAT JSON"
                        if analyze
                        else "FORMAT JSON"
                    )
                    cursor.execute(
                        f"EXPLAIN ({options}) SELECT count(*) FROM ({sql}) AS measured",
                        _params(sql, interface_id),
                    )
                    envelope = _json_plan(cursor.fetchone()[0])
        return {
            "stage": name,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "plan": _plan_receipt(envelope, analyze=analyze),
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


def _count_stage(
    database_url: str,
    interface_id: int,
    name: str,
    sql: str,
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
                    cursor.execute(
                        f"SELECT count(*) FROM ({sql}) AS measured",
                        _params(sql, interface_id),
                    )
                    row_count = int(cursor.fetchone()[0])
        return {
            "stage": name,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "row_count": row_count,
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


def _difference_count_sql(left: str, right: str) -> str:
    return f"""
SELECT {_PARITY_COLUMNS}
  FROM ({left}) AS left_rows
EXCEPT ALL
SELECT {_PARITY_COLUMNS}
  FROM ({right}) AS right_rows
"""


def _fingerprint_sql(sql: str) -> str:
    # This is a cheap routing hint, not semantic authority.  Exact EXCEPT ALL
    # remains the proof gate.  The count and additive 64-bit hash make a mismatch
    # immediately localisable without pretending collision-freedom.
    return f"""
SELECT count(*)::BIGINT AS row_count,
       COALESCE(sum(hashtextextended(
           concat_ws('|',
               demand_id::TEXT,
               target_kind::TEXT,
               target_id::TEXT,
               structural_distance::TEXT,
               index_rank::TEXT,
               candidate_score::TEXT,
               max_candidates::TEXT
           ), 0
       )::NUMERIC), 0::NUMERIC)::TEXT AS hash_sum
  FROM ({sql}) AS rows
"""


def _fingerprint_stage(
    database_url: str,
    interface_id: int,
    name: str,
    sql: str,
    timeout_ms: int,
) -> dict[str, object]:
    started = time.monotonic()
    try:
        statement = _fingerprint_sql(sql)
        with connect(database_url) as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (str(timeout_ms),),
                    )
                    cursor.execute(statement, _params(statement, interface_id))
                    row_count, hash_sum = cursor.fetchone()
        return {
            "stage": name,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "row_count": int(row_count),
            "hash_sum": str(hash_sum),
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


def _mask_parity_receipt(
    database_url: str,
    interface_id: int,
    mask: int,
    timeout_ms: int,
) -> dict[str, object]:
    started = time.monotonic()
    legacy = _legacy_mask_candidate_sql(mask)
    specialised = _mask_candidate_sql(mask)
    left = _difference_count_sql(legacy, specialised)
    right = _difference_count_sql(specialised, legacy)
    try:
        with connect(database_url) as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (str(timeout_ms),),
                    )
                    cursor.execute(
                        f"SELECT count(*) FROM ({left}) AS difference",
                        _params(left, interface_id),
                    )
                    legacy_minus_specialised = int(cursor.fetchone()[0])
                    cursor.execute(
                        f"SELECT count(*) FROM ({right}) AS difference",
                        _params(right, interface_id),
                    )
                    specialised_minus_legacy = int(cursor.fetchone()[0])
        return {
            "stage": "mask_exact_parity",
            "mask": mask,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "legacy_minus_specialised": legacy_minus_specialised,
            "specialised_minus_legacy": specialised_minus_legacy,
            "exact_multiset_parity": (
                legacy_minus_specialised == 0 and specialised_minus_legacy == 0
            ),
        }
    except psycopg.errors.QueryCanceled as exc:
        return {
            "stage": "mask_exact_parity",
            "mask": mask,
            "status": "timeout",
            "timeout_ms": timeout_ms,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stage": "mask_exact_parity",
            "mask": mask,
            "status": "error",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _write(stream: Any, receipt: dict[str, object]) -> None:
    stream.write(json.dumps(receipt, sort_keys=True) + "\n")
    stream.flush()
    print(json.dumps(receipt, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--mode", choices=("estimate", "bounded-analyze"), default="bounded-analyze"
    )
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument(
        "--mask",
        dest="masks",
        action="append",
        type=int,
        help="mask to run; repeatable; defaults to all 0..15",
    )
    parser.add_argument("--skip-parity", action="store_true")
    args = parser.parse_args()

    masks = sorted(set(args.masks if args.masks is not None else range(16)))
    if any(mask < 0 or mask > 15 for mask in masks):
        parser.error("--mask values must be between 0 and 15")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    analyze = args.mode == "bounded-analyze"
    parity_results: list[bool] = []

    with args.output.open("a", encoding="utf-8") as stream:
        for mask in masks:
            demand_sql = _mask_demand_sql(mask)
            posting_sql = _mask_profile_posting_sql(mask)
            candidate_sql = _mask_candidate_sql(mask)
            legacy_sql = _legacy_mask_candidate_sql(mask)

            for name, sql in (
                ("mask_demand_count", demand_sql),
                ("mask_profile_posting_count", posting_sql),
            ):
                receipt = {
                    "contract_ref": CONTRACT_REF,
                    "interface_id": args.interface_id,
                    "mask": mask,
                    **_count_stage(
                        args.database_url,
                        args.interface_id,
                        name,
                        sql,
                        args.timeout_ms,
                    ),
                }
                _write(stream, receipt)

            plan = {
                "contract_ref": CONTRACT_REF,
                "interface_id": args.interface_id,
                "mask": mask,
                "mode": args.mode,
                **_run_plan_stage(
                    args.database_url,
                    args.interface_id,
                    "mask_specialised_candidates",
                    candidate_sql,
                    analyze=analyze,
                    timeout_ms=args.timeout_ms,
                ),
            }
            _write(stream, plan)

            for side, sql in (("legacy", legacy_sql), ("specialised", candidate_sql)):
                fingerprint = {
                    "contract_ref": CONTRACT_REF,
                    "interface_id": args.interface_id,
                    "mask": mask,
                    "side": side,
                    **_fingerprint_stage(
                        args.database_url,
                        args.interface_id,
                        "mask_candidate_fingerprint",
                        sql,
                        args.timeout_ms,
                    ),
                }
                _write(stream, fingerprint)

            if not args.skip_parity:
                parity = {
                    "contract_ref": CONTRACT_REF,
                    "interface_id": args.interface_id,
                    **_mask_parity_receipt(
                        args.database_url,
                        args.interface_id,
                        mask,
                        args.timeout_ms,
                    ),
                }
                _write(stream, parity)
                parity_results.append(parity.get("exact_multiset_parity") is True)

        complete_mask_set = masks == list(range(16))
        summary = {
            "contract_ref": CONTRACT_REF,
            "interface_id": args.interface_id,
            "stage": "mask_bucket_summary",
            "masks": masks,
            "complete_mask_set": complete_mask_set,
            "parity_requested": not args.skip_parity,
            "all_selected_masks_exact": (
                bool(parity_results) and all(parity_results)
                if not args.skip_parity
                else None
            ),
            "global_exact_parity": (
                complete_mask_set and bool(parity_results) and all(parity_results)
                if not args.skip_parity
                else None
            ),
        }
        _write(stream, summary)

    if args.skip_parity:
        return 0
    return 0 if summary["global_exact_parity"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
