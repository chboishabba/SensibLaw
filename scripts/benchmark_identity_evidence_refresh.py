#!/usr/bin/env python3
"""Time proof-relevant semantic refresh per numeric PNF document.

This is a diagnostic harness, not semantic authority.  It exists so a slow
identity-evidence producer is visible at the document boundary instead of
appearing as an opaque tranche-wide hang.
"""

from __future__ import annotations

import argparse
from time import perf_counter
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


def _resolve_run(cursor: Any, requested_run_id: int | None) -> int:
    if requested_run_id is not None:
        cursor.execute(
            "SELECT 1 FROM execution.semantic_pnf_run_identity WHERE run_id = %s",
            (requested_run_id,),
        )
        if cursor.fetchone() is None:
            raise SystemExit(f"unknown run_id {requested_run_id}")
        return requested_run_id
    cursor.execute("SELECT max(run_id) FROM execution.semantic_pnf_region")
    row = cursor.fetchone()
    if row is None or row[0] is None:
        raise SystemExit("no numeric PNF run is available")
    return int(row[0])


def _documents(cursor: Any, run_id: int, requested: tuple[int, ...]) -> tuple[int, ...]:
    if requested:
        return tuple(sorted(set(requested)))
    cursor.execute(
        """
        SELECT DISTINCT document_id
          FROM execution.semantic_pnf_region
         WHERE run_id = %s
         ORDER BY document_id
        """,
        (run_id,),
    )
    return tuple(int(row[0]) for row in cursor.fetchall())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--document-id", action="append", type=int, default=[])
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=30_000,
        help="Fail one refresh instead of waiting indefinitely (default: 30000).",
    )
    args = parser.parse_args()
    if args.statement_timeout_ms < 1:
        raise SystemExit("--statement-timeout-ms must be positive")

    connection = connect(args.database_url)
    total_started = perf_counter()
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                run_id = _resolve_run(cursor, args.run_id)
                document_ids = _documents(cursor, run_id, tuple(args.document_id))
                print(f"run_id={run_id} documents={len(document_ids)}")
                for ordinal, document_id in enumerate(document_ids, start=1):
                    cursor.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (f"{args.statement_timeout_ms}ms",),
                    )
                    cursor.fetchone()
                    started = perf_counter()
                    cursor.execute(
                        """
                        SELECT *
                          FROM execution.refresh_numeric_pnf_semantic_derivations(%s, %s)
                        """,
                        (run_id, document_id),
                    )
                    result = cursor.fetchone()
                    elapsed_ms = (perf_counter() - started) * 1000.0
                    print(
                        f"[{ordinal}/{len(document_ids)}] document_id={document_id} "
                        f"elapsed_ms={elapsed_ms:.3f} result={result!r}",
                        flush=True,
                    )
        total_ms = (perf_counter() - total_started) * 1000.0
        print(f"total_elapsed_ms={total_ms:.3f}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
