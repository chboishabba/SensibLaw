"""Bounded, resumable sparse-frontier candidate-stage diagnostics."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import psycopg

from diagnose_sparse_frontier_candidate_work import (
    _DIRECT_OBJECT_CANDIDATE,
    _DIRECT_STATIC_MATCH,
    _FACTOR_CANDIDATE,
    _INDEXED_OBJECT_CANDIDATE,
    _OBJECT_DEMAND,
    _PARTIAL_PROFILE,
    _PROFILE_BASE,
    _PROFILE_KEY,
    _RANKED,
    _REQUIRED_KEY,
    _SURVIVORS,
    _UNARY_CONJUNCTIVE,
    _UNARY_MATCH,
)
from src.storage.postgres.spacy_parser_model import connect

CONTRACT_REF = "sensiblaw.sparse-frontier-stage-diagnostic.v0_1"


def _explain(
    cursor: Any, sql: str, interface_id: int, analyze: bool
) -> dict[str, object]:
    options = "ANALYZE, BUFFERS, WAL, FORMAT JSON" if analyze else "FORMAT JSON"
    params = (interface_id,) * sql.count("%s")
    cursor.execute(
        f"EXPLAIN ({options}) SELECT count(*) FROM ({sql}) AS measured", params
    )
    envelope = cursor.fetchone()[0]
    if isinstance(envelope, str):
        envelope = json.loads(envelope)
    envelope = envelope[0] if isinstance(envelope, list) else envelope
    plan = envelope["Plan"]
    result: dict[str, object] = {
        "node_type": plan.get("Node Type"),
        "plan_rows": plan.get("Plan Rows"),
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


def run_stage(
    database_url: str,
    interface_id: int,
    name: str,
    sql: str,
    mode: str,
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
                    plan = _explain(
                        cursor, sql, interface_id, mode == "bounded-analyze"
                    )
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--mode", choices=("estimate", "bounded-analyze"), default="estimate"
    )
    parser.add_argument("--timeout-ms", type=int, default=60000)
    args = parser.parse_args()
    stages = [
        ("object_demands", _OBJECT_DEMAND),
        ("actor_profiles", _PROFILE_BASE),
        ("required_keys", _REQUIRED_KEY),
        ("profile_keys", _PROFILE_KEY),
        ("unary_matches", _UNARY_MATCH),
        ("partial_profiles", _PARTIAL_PROFILE),
        ("unary_conjunctive", _UNARY_CONJUNCTIVE),
        ("direct_static", _DIRECT_STATIC_MATCH),
        ("direct_object_candidates", _DIRECT_OBJECT_CANDIDATE),
        ("indexed_object_candidates", _INDEXED_OBJECT_CANDIDATE),
        ("factor_candidates", _FACTOR_CANDIDATE),
        ("ranked_candidates", _RANKED),
        ("survivors", _SURVIVORS),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as stream:
        for name, sql in stages:
            receipt = {
                "contract_ref": CONTRACT_REF,
                "interface_id": args.interface_id,
                "mode": args.mode,
                **run_stage(
                    args.database_url,
                    args.interface_id,
                    name,
                    sql,
                    args.mode,
                    args.timeout_ms,
                ),
            }
            stream.write(json.dumps(receipt, sort_keys=True) + "\n")
            stream.flush()
            print(json.dumps(receipt, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
