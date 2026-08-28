#!/usr/bin/env python3
"""Run a bounded strict optimization probe with rollback-surviving diagnostics.

This is deliberately not an acceptance runner.  It launches the canonical
strict acceptance wrapper, stops it after a short operator-selected interval,
and observes PostgreSQL from a separate connection while the semantic
transaction is live.  The resulting SQL/wait/churn samples survive rollback and
are always marked acceptance-ineligible.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tranche", default="GWB", choices=("GWB", "AU", "BREXIT", "ALL"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"), required=False)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--acceptance-root", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--sample-seconds", type=float, default=2.0)
    parser.add_argument("--soft-memory-mib", type=int, default=12 * 1024)
    parser.add_argument("--hard-memory-mib", type=int, default=16 * 1024)
    parser.add_argument("--document-workers", type=int, default=1)
    parser.add_argument("--closure-workers", type=int, default=4)
    parser.add_argument("--owner-partitions", type=int, default=8)
    parser.add_argument("--parser-workers", type=int, default=1)
    parser.add_argument("--worker-budget", type=int, default=4)
    parser.add_argument("--input-path", type=Path, action="append")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--skip-legal-follow", action="store_true")
    parser.add_argument(
        "--enable-pg-stat-statements",
        action="store_true",
        help="Ask the canonical wrapper to require pg_stat_statements too.",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.seconds <= 0 or args.sample_seconds <= 0:
        parser.error("probe and sample durations must be positive")
    return args


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _db_snapshot(database_url: str) -> dict[str, Any]:
    import psycopg

    observed_at = datetime.now(UTC).isoformat()
    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pid, state, wait_event_type, wait_event, backend_type,
                       EXTRACT(EPOCH FROM (clock_timestamp() - query_start)),
                       EXTRACT(EPOCH FROM (clock_timestamp() - xact_start)),
                       left(query, 1200)
                  FROM pg_stat_activity
                 WHERE datname = current_database()
                   AND pid <> pg_backend_pid()
                 ORDER BY xact_start NULLS LAST, query_start NULLS LAST, pid
                """
            )
            activity = [
                {
                    "pid": int(row[0]),
                    "state": row[1],
                    "wait_event_type": row[2],
                    "wait_event": row[3],
                    "backend_type": row[4],
                    "query_elapsed_seconds": float(row[5]) if row[5] is not None else None,
                    "transaction_elapsed_seconds": float(row[6]) if row[6] is not None else None,
                    "query": row[7],
                }
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT mode, granted, count(*)
                  FROM pg_locks AS lock
                  JOIN pg_database AS database ON database.oid = lock.database
                 WHERE database.datname = current_database()
                 GROUP BY mode, granted
                 ORDER BY granted, mode
                """
            )
            locks = [
                {"mode": row[0], "granted": bool(row[1]), "count": int(row[2])}
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT relname, seq_scan, idx_scan, n_tup_ins, n_tup_upd,
                       n_tup_del, n_live_tup, n_dead_tup
                  FROM pg_stat_user_tables
                 WHERE schemaname = 'execution'
                   AND relname LIKE 'semantic_pnf_%'
                 ORDER BY relname
                """
            )
            tables = {
                str(row[0]): {
                    "seq_scan": int(row[1] or 0),
                    "idx_scan": int(row[2] or 0),
                    "n_tup_ins": int(row[3] or 0),
                    "n_tup_upd": int(row[4] or 0),
                    "n_tup_del": int(row[5] or 0),
                    "n_live_tup": int(row[6] or 0),
                    "n_dead_tup": int(row[7] or 0),
                }
                for row in cursor.fetchall()
            }
            statements: list[dict[str, Any]] = []
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements')")
            if bool(cursor.fetchone()[0]):
                try:
                    cursor.execute(
                        """
                        SELECT queryid, calls, total_exec_time, rows, left(query, 1600)
                          FROM pg_stat_statements
                         WHERE dbid = (SELECT oid FROM pg_database WHERE datname=current_database())
                           AND (
                               query ILIKE '%semantic_pnf_%'
                               OR query ILIKE '%reduce_numeric_pnf%'
                               OR query ILIKE '%rebuild_numeric_pnf%'
                           )
                         ORDER BY total_exec_time DESC
                         LIMIT 80
                        """
                    )
                    statements = [
                        {
                            "queryid": int(row[0]) if row[0] is not None else None,
                            "calls": int(row[1]),
                            "total_exec_time_ms": float(row[2]),
                            "rows": int(row[3]),
                            "query": row[4],
                        }
                        for row in cursor.fetchall()
                    ]
                except Exception as error:  # extension may exist but not be preloaded
                    statements = [{"state": "unavailable", "reason": str(error)}]
    return {
        "observed_at": observed_at,
        "activity": activity,
        "locks": locks,
        "tables": tables,
        "statements": statements,
    }


def _statement_delta(first: dict[str, Any], last: dict[str, Any]) -> list[dict[str, Any]]:
    before = {
        row.get("queryid"): row
        for row in first.get("statements", [])
        if isinstance(row, dict) and row.get("queryid") is not None
    }
    result: list[dict[str, Any]] = []
    for row in last.get("statements", []):
        if not isinstance(row, dict) or row.get("queryid") is None:
            continue
        old = before.get(row["queryid"], {})
        calls = int(row.get("calls", 0)) - int(old.get("calls", 0))
        elapsed = float(row.get("total_exec_time_ms", 0.0)) - float(old.get("total_exec_time_ms", 0.0))
        rows = int(row.get("rows", 0)) - int(old.get("rows", 0))
        if calls or elapsed or rows:
            result.append(
                {
                    "queryid": row["queryid"],
                    "calls_delta": calls,
                    "total_exec_time_ms_delta": elapsed,
                    "rows_delta": rows,
                    "query": row.get("query"),
                }
            )
    result.sort(key=lambda row: row["total_exec_time_ms_delta"], reverse=True)
    return result


def main() -> int:
    args = _args()
    root = args.acceptance_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    sql_samples_path = root / "iteration-sql-observer.jsonl"
    summary_path = root / "iteration-probe-summary.json"

    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_strict_tranche_acceptance.py"),
        "--tranche", args.tranche,
        "--database-url", args.database_url,
        "--postgres-mode", "existing",
        "--output-root", str(args.output_root.resolve()),
        "--acceptance-root", str(root),
        "--strict-exact",
        "--soft-memory-mib", str(args.soft_memory_mib),
        "--hard-memory-mib", str(args.hard_memory_mib),
        "--sample-seconds", "1",
        "--document-workers", str(args.document_workers),
        "--closure-workers", str(args.closure_workers),
        "--owner-partitions", str(args.owner_partitions),
        "--parser-workers", str(args.parser_workers),
        "--worker-budget", str(args.worker_budget),
    ]
    for path in args.input_path or ():
        command.extend(("--input-path", str(path.resolve())))
    if args.offline:
        command.append("--offline")
    if args.skip_legal_follow:
        command.append("--skip-legal-follow")
    if args.enable_pg_stat_statements:
        command.append("--enable-pg-stat-statements")

    started_at = datetime.now(UTC).isoformat()
    process = subprocess.Popen(command, cwd=ROOT)
    samples: list[dict[str, Any]] = []
    deadline = time.monotonic() + args.seconds
    with sql_samples_path.open("w", encoding="utf-8") as stream:
        while process.poll() is None and time.monotonic() < deadline:
            try:
                sample = _db_snapshot(args.database_url)
            except Exception as error:
                sample = {
                    "observed_at": datetime.now(UTC).isoformat(),
                    "observer_error": str(error),
                }
            samples.append(sample)
            stream.write(json.dumps(sample, sort_keys=True) + "\n")
            stream.flush()
            time.sleep(args.sample_seconds)

    terminated_by_probe = process.poll() is None
    if terminated_by_probe:
        process.send_signal(signal.SIGTERM)
    try:
        returncode = process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        returncode = process.wait()

    if not samples:
        try:
            samples.append(_db_snapshot(args.database_url))
        except Exception:
            pass
    wait_samples = Counter()
    for sample in samples:
        for row in sample.get("activity", []):
            key = f"{row.get('wait_event_type') or 'none'}:{row.get('wait_event') or 'none'}"
            wait_samples[key] += 1

    statement_delta = _statement_delta(samples[0], samples[-1]) if len(samples) >= 2 else []
    summary = {
        "schema_version": "sensiblaw.strict-iteration-probe.v0_1",
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "requested_probe_seconds": args.seconds,
        "sample_seconds": args.sample_seconds,
        "sample_count": len(samples),
        "terminated_by_probe": terminated_by_probe,
        "acceptance_wrapper_returncode": returncode,
        "acceptance_eligible": False,
        "partial_run_evidence": True,
        "semantic_authority_effect": "none",
        "semantic_identity_effect": "none",
        "diagnostic_semantics": (
            "External PostgreSQL/process observation only. A killed or incomplete probe "
            "cannot satisfy semantic or parser-relative acceptance."
        ),
        "wait_sample_counts": dict(wait_samples.most_common()),
        "pg_stat_statements_delta": statement_delta,
        "artifacts": {
            "sql_observer_jsonl": str(sql_samples_path),
            "canonical_acceptance_root": str(root),
            "resource_checkpoints": str(root / "resource-checkpoints"),
            "rss_samples": str(root / "rss.jsonl"),
            "canonical_acceptance_receipt": str(root / "acceptance-receipt.json"),
        },
        "command": command,
    }
    _atomic_json(summary_path, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
