#!/usr/bin/env python3
"""Rank PostgreSQL function kernels exercised by a canonical PNF run.

This is a diagnosis-only E0c harness.  It enables PostgreSQL ``track_functions``
for the *isolated benchmark database*, resets function statistics, invokes an
existing benchmark command supplied by the caller, and emits the PL/pgSQL
functions ordered by exclusive/total wall contribution.

The benchmark command remains the semantic producer.  This harness neither
changes PNF authority rows nor disables triggers/functions; it only turns on
PostgreSQL's built-in function accounting for the isolated database.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT = "sensiblaw.sentence-close-kernel-profile.v0_1"


def _database_name(connection: Any) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("cannot resolve current database")
        return str(row[0])


def _configure(database_url: str) -> str:
    connection = connect(database_url)
    try:
        database = _database_name(connection)
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT datname FROM pg_database WHERE datname = current_database()"
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("profile database disappeared")
                cursor.execute(
                    f'ALTER DATABASE "{database.replace(chr(34), chr(34) * 2)}" '
                    "SET track_functions = 'pl'"
                )
                cursor.execute("SELECT pg_stat_reset()")
        return database
    finally:
        connection.close()


def _read_stats(database_url: str) -> list[dict[str, Any]]:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT schemaname,
                       funcname,
                       calls,
                       total_time,
                       self_time
                  FROM pg_stat_user_functions
                 WHERE calls > 0
                 ORDER BY total_time DESC, self_time DESC, funcname
                """
            )
            return [
                {
                    "schema": str(schema),
                    "function": str(function),
                    "calls": int(calls),
                    "total_ms": float(total_ms),
                    "self_ms": float(self_ms),
                }
                for schema, function, calls, total_ms, self_ms in cursor.fetchall()
            ]
    finally:
        connection.close()


def _run(command: str, *, database_url: str) -> int:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    completed = subprocess.run(
        shlex.split(command),
        env=environment,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument(
        "--command",
        required=True,
        help="canonical benchmark command to run after stats reset",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    if args.top < 1:
        parser.error("--top must be positive")

    database = _configure(args.database_url)
    returncode = _run(args.command, database_url=args.database_url)
    functions = _read_stats(args.database_url)
    total_self_ms = sum(item["self_ms"] for item in functions)
    for item in functions:
        item["self_share"] = (
            item["self_ms"] / total_self_ms if total_self_ms > 0 else 0.0
        )

    receipt = {
        "contract": CONTRACT,
        "database": database,
        "benchmark_returncode": returncode,
        "track_functions": "pl",
        "semantic_authority_changed_by_profiler": False,
        "triggers_disabled": False,
        "functions_replaced": False,
        "function_count": len(functions),
        "total_function_self_ms": total_self_ms,
        "top_functions": functions[: args.top],
    }
    payload = json.dumps(receipt, indent=2, sort_keys=True)
    print(payload)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    return returncode


if __name__ == "__main__":
    sys.exit(main())
