"""Session-local C2 experiment for persisted/index-addressable candidate postings.

The C1 composite experiment proved that signature construction is cheap but a
runtime sort/materialise/join is not.  This probe tests the intended physical
architecture without changing production schema:

1. build the exact finite-mask actor-profile posting relation once;
2. materialise it in a PostgreSQL TEMP table scoped to this session;
3. build one partial B-tree per mask over only that mask's active coordinates;
4. probe each demand mask directly through its posting index;
5. compare each mask with legacy candidates by exact EXCEPT ALL.

TEMP writes are execution-only counterfactual state.  No execution.* table is
inserted, updated or deleted, and no M180 production migration is installed.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import psycopg

from diagnose_sparse_frontier_composite_signatures import _PROFILE_SIGNATURE
from diagnose_sparse_frontier_mask_buckets import (
    CONTRACT_REF as MASK_CONTRACT_REF,
    MASK_BITS,
    _active,
    _fingerprint_sql,
    _legacy_mask_candidate_sql,
    _mask_demand_sql,
    _params,
    _plan_receipt,
)
from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-temp-posting-bucket-diagnostic.v0_1"
TEMP_TABLE = "temp_sparse_frontier_profile_posting"
_PARITY_COLUMNS = """
demand_id, target_kind, target_id, structural_distance,
index_rank, candidate_score, max_candidates
"""


def _posting_columns(mask: int) -> list[str]:
    columns: list[str] = []
    if _active(mask, MASK_BITS["factor"]):
        columns.append("factor_key")
    if _active(mask, MASK_BITS["object_kind"]):
        columns.append("object_kind_key")
    if _active(mask, MASK_BITS["role"]):
        columns.append("role_key")
    if _active(mask, MASK_BITS["lexical"]):
        columns.append("lexical_key")
    return columns


def _create_temp_table(cursor: Any) -> None:
    cursor.execute(f"DROP TABLE IF EXISTS {TEMP_TABLE}")
    cursor.execute(
        f"""
        CREATE TEMP TABLE {TEMP_TABLE} (
            mask INTEGER NOT NULL,
            factor_key BIGINT,
            object_kind_key BIGINT,
            role_key BIGINT,
            lexical_key BIGINT,
            object_id BIGINT NOT NULL,
            occurrence_count BIGINT NOT NULL,
            first_start_char BIGINT NOT NULL,
            last_end_char BIGINT NOT NULL,
            promotion_score DOUBLE PRECISION NOT NULL
        ) ON COMMIT PRESERVE ROWS
        """
    )


def _populate_temp_table(cursor: Any, interface_id: int, timeout_ms: int) -> dict[str, object]:
    started = time.monotonic()
    try:
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(timeout_ms),),
        )
        sql = f"""
        INSERT INTO {TEMP_TABLE} (
            mask, factor_key, object_kind_key, role_key, lexical_key,
            object_id, occurrence_count, first_start_char, last_end_char,
            promotion_score
        )
        SELECT signature.mask,
               signature.factor_key,
               signature.object_kind_key,
               signature.role_key,
               signature.lexical_key,
               signature.object_id,
               signature.occurrence_count,
               signature.first_start_char,
               signature.last_end_char,
               signature.promotion_score
          FROM ({_PROFILE_SIGNATURE}) AS signature
        """
        cursor.execute(sql, _params(sql, interface_id))
        inserted = cursor.rowcount
        cursor.execute(f"ANALYZE {TEMP_TABLE}")
        return {
            "stage": "temp_posting_build",
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "row_count": int(inserted),
        }
    except psycopg.errors.QueryCanceled as exc:
        return {
            "stage": "temp_posting_build",
            "status": "timeout",
            "timeout_ms": timeout_ms,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stage": "temp_posting_build",
            "status": "error",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _create_mask_index(cursor: Any, mask: int, timeout_ms: int) -> dict[str, object]:
    started = time.monotonic()
    columns = _posting_columns(mask)
    key_columns = [*columns, "last_end_char DESC", "promotion_score DESC", "object_id"]
    index_name = f"temp_sparse_frontier_posting_m{mask}_idx"
    try:
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(timeout_ms),),
        )
        cursor.execute(
            f"CREATE INDEX {index_name} ON {TEMP_TABLE} "
            f"({', '.join(key_columns)}) WHERE mask = {mask}"
        )
        return {
            "stage": "temp_posting_index",
            "mask": mask,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "index_columns": key_columns,
        }
    except psycopg.errors.QueryCanceled as exc:
        return {
            "stage": "temp_posting_index",
            "mask": mask,
            "status": "timeout",
            "timeout_ms": timeout_ms,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stage": "temp_posting_index",
            "mask": mask,
            "status": "error",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _temp_candidate_sql(mask: int) -> str:
    demand_sql = _mask_demand_sql(mask)
    conditions = [f"posting.mask = {mask}"]
    if _active(mask, MASK_BITS["factor"]):
        conditions.append(
            "posting.factor_key = demand.expected_factor_type_symbol_id"
        )
    if _active(mask, MASK_BITS["object_kind"]):
        conditions.append(
            "posting.object_kind_key = demand.expected_object_kind_symbol_id"
        )
    if _active(mask, MASK_BITS["role"]):
        conditions.append("posting.role_key = demand.role_symbol_id")
    if _active(mask, MASK_BITS["lexical"]):
        conditions.append("posting.lexical_key = demand.lexical_symbol_id")
    join_conditions = "\n   AND ".join(conditions)

    return f"""
WITH demand AS MATERIALIZED ({demand_sql})
SELECT demand.demand_id,
       1::SMALLINT AS target_kind,
       posting.object_id AS target_id,
       abs(demand.demand_position - posting.last_end_char) AS structural_distance,
       0::BIGINT AS index_rank,
       posting.promotion_score
           + ln(1 + posting.occurrence_count)::DOUBLE PRECISION AS candidate_score,
       demand.max_candidates
  FROM demand
  JOIN {TEMP_TABLE} AS posting
    ON {join_conditions}
 WHERE CASE demand.recency_class
     WHEN 1 THEN
         posting.first_start_char >= demand.source_region_start
         AND posting.last_end_char <= demand.source_region_end
     WHEN 2 THEN posting.last_end_char <= demand.demand_position
     WHEN 3 THEN posting.last_end_char <= demand.demand_position
     WHEN 4 THEN TRUE
     WHEN 5 THEN TRUE
     ELSE FALSE
 END
"""


def _execute_plan(
    cursor: Any,
    interface_id: int,
    mask: int,
    mode: str,
    timeout_ms: int,
) -> dict[str, object]:
    started = time.monotonic()
    sql = _temp_candidate_sql(mask)
    try:
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(timeout_ms),),
        )
        options = (
            "ANALYZE, BUFFERS, WAL, FORMAT JSON"
            if mode == "bounded-analyze"
            else "FORMAT JSON"
        )
        cursor.execute(
            f"EXPLAIN ({options}) SELECT count(*) FROM ({sql}) AS measured",
            _params(sql, interface_id),
        )
        envelope = cursor.fetchone()[0]
        if isinstance(envelope, str):
            envelope = json.loads(envelope)
        envelope = envelope[0] if isinstance(envelope, list) else envelope
        return {
            "stage": "temp_posting_candidates",
            "mask": mask,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "plan": _plan_receipt(
                dict(envelope), analyze=mode == "bounded-analyze"
            ),
        }
    except psycopg.errors.QueryCanceled as exc:
        return {
            "stage": "temp_posting_candidates",
            "mask": mask,
            "status": "timeout",
            "timeout_ms": timeout_ms,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stage": "temp_posting_candidates",
            "mask": mask,
            "status": "error",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _fingerprint(
    cursor: Any,
    interface_id: int,
    mask: int,
    side: str,
    sql: str,
    timeout_ms: int,
) -> dict[str, object]:
    started = time.monotonic()
    statement = _fingerprint_sql(sql)
    try:
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(timeout_ms),),
        )
        cursor.execute(statement, _params(statement, interface_id))
        row_count, hash_sum = cursor.fetchone()
        return {
            "stage": "temp_posting_fingerprint",
            "mask": mask,
            "side": side,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "row_count": int(row_count),
            "hash_sum": str(hash_sum),
        }
    except psycopg.errors.QueryCanceled as exc:
        return {
            "stage": "temp_posting_fingerprint",
            "mask": mask,
            "side": side,
            "status": "timeout",
            "timeout_ms": timeout_ms,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stage": "temp_posting_fingerprint",
            "mask": mask,
            "side": side,
            "status": "error",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _difference_sql(left: str, right: str) -> str:
    return f"""
SELECT {_PARITY_COLUMNS}
  FROM ({left}) AS left_rows
EXCEPT ALL
SELECT {_PARITY_COLUMNS}
  FROM ({right}) AS right_rows
"""


def _exact_parity(
    cursor: Any,
    interface_id: int,
    mask: int,
    timeout_ms: int,
) -> dict[str, object]:
    started = time.monotonic()
    legacy = _legacy_mask_candidate_sql(mask)
    temp = _temp_candidate_sql(mask)
    left = _difference_sql(legacy, temp)
    right = _difference_sql(temp, legacy)
    try:
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(timeout_ms),),
        )
        cursor.execute(
            f"SELECT count(*) FROM ({left}) AS difference",
            _params(left, interface_id),
        )
        legacy_minus_temp = int(cursor.fetchone()[0])
        cursor.execute(
            f"SELECT count(*) FROM ({right}) AS difference",
            _params(right, interface_id),
        )
        temp_minus_legacy = int(cursor.fetchone()[0])
        return {
            "stage": "temp_posting_exact_parity",
            "mask": mask,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "legacy_minus_temp": legacy_minus_temp,
            "temp_minus_legacy": temp_minus_legacy,
            "exact_multiset_parity": (
                legacy_minus_temp == 0 and temp_minus_legacy == 0
            ),
        }
    except psycopg.errors.QueryCanceled as exc:
        return {
            "stage": "temp_posting_exact_parity",
            "mask": mask,
            "status": "timeout",
            "timeout_ms": timeout_ms,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stage": "temp_posting_exact_parity",
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
        "--mask", dest="masks", action="append", type=int,
        help="mask to run; repeatable; defaults to all 0..15",
    )
    parser.add_argument("--skip-parity", action="store_true")
    args = parser.parse_args()

    masks = sorted(set(args.masks if args.masks is not None else range(16)))
    if any(mask < 0 or mask > 15 for mask in masks):
        parser.error("--mask values must be between 0 and 15")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    parity_results: list[bool] = []

    # Autocommit isolates statement timeouts: a cancelled per-mask query does not
    # abort the session or discard the TEMP posting carrier needed by later masks.
    connection = connect(args.database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor, args.output.open("a", encoding="utf-8") as stream:
            _create_temp_table(cursor)
            build = {
                "contract_ref": CONTRACT_REF,
                "source_mask_contract_ref": MASK_CONTRACT_REF,
                "interface_id": args.interface_id,
                **_populate_temp_table(
                    cursor, args.interface_id, args.timeout_ms
                ),
            }
            _write(stream, build)
            if build.get("status") != "complete":
                return 1

            for mask in masks:
                index_receipt = {
                    "contract_ref": CONTRACT_REF,
                    "interface_id": args.interface_id,
                    **_create_mask_index(cursor, mask, args.timeout_ms),
                }
                _write(stream, index_receipt)

            cursor.execute(f"ANALYZE {TEMP_TABLE}")

            for mask in masks:
                plan = {
                    "contract_ref": CONTRACT_REF,
                    "interface_id": args.interface_id,
                    "mode": args.mode,
                    **_execute_plan(
                        cursor,
                        args.interface_id,
                        mask,
                        args.mode,
                        args.timeout_ms,
                    ),
                }
                _write(stream, plan)

                legacy = _legacy_mask_candidate_sql(mask)
                temp = _temp_candidate_sql(mask)
                for side, sql in (("legacy", legacy), ("temp_posting", temp)):
                    fingerprint = {
                        "contract_ref": CONTRACT_REF,
                        "interface_id": args.interface_id,
                        **_fingerprint(
                            cursor,
                            args.interface_id,
                            mask,
                            side,
                            sql,
                            args.timeout_ms,
                        ),
                    }
                    _write(stream, fingerprint)

                if not args.skip_parity:
                    parity = {
                        "contract_ref": CONTRACT_REF,
                        "interface_id": args.interface_id,
                        **_exact_parity(
                            cursor,
                            args.interface_id,
                            mask,
                            args.timeout_ms,
                        ),
                    }
                    _write(stream, parity)
                    parity_results.append(
                        parity.get("exact_multiset_parity") is True
                    )

            complete_mask_set = masks == list(range(16))
            summary = {
                "contract_ref": CONTRACT_REF,
                "interface_id": args.interface_id,
                "stage": "temp_posting_summary",
                "masks": masks,
                "complete_mask_set": complete_mask_set,
                "parity_requested": not args.skip_parity,
                "all_selected_masks_exact": (
                    bool(parity_results) and all(parity_results)
                    if not args.skip_parity else None
                ),
                "global_exact_parity": (
                    complete_mask_set and bool(parity_results) and all(parity_results)
                    if not args.skip_parity else None
                ),
                "production_schema_changed": False,
            }
            _write(stream, summary)
    finally:
        connection.close()

    if args.skip_parity:
        return 0
    return 0 if summary["global_exact_parity"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
