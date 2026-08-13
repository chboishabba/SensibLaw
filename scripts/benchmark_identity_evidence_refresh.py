#!/usr/bin/env python3
"""Time proof-relevant semantic refresh by document and semantic phase.

This is diagnostic execution, not semantic authority. Each document runs in its
own transaction and each production refresh function is timed independently so
locks are released at document boundaries and a slow operator is visible instead
of appearing as an opaque tranche-wide hang.
"""

from __future__ import annotations

import argparse
from time import perf_counter
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


_PHASES = (
    ("typed_identity", "execution.refresh_numeric_pnf_identity_witnesses", 2),
    ("parser_evidence", "execution.refresh_numeric_pnf_parser_identity_evidence", 2),
    ("parser_admission", "execution.admit_numeric_pnf_parser_identity_evidence", 2),
    (
        "identity_substitution",
        "execution.refresh_numeric_pnf_identity_substitution_derivations",
        2,
    ),
    ("factor_composition", "execution.refresh_numeric_pnf_factor_composition_candidates", 3),
)


def _resolve_run(cursor: Any, requested_run_id: int | None) -> int:
    if requested_run_id is not None:
        cursor.execute(
            "SELECT 1 FROM execution.semantic_pnf_run_identity WHERE run_id = %s",
            (requested_run_id,),
        )
        if cursor.fetchone() is None:
            raise SystemExit(f"unknown run_id {requested_run_id}")
        return requested_run_id
    cursor.execute(
        """
        SELECT max(region.run_id)
          FROM execution.semantic_pnf_region AS region
          JOIN execution.semantic_pnf_run_identity AS identity
            ON identity.run_id = region.run_id
        """
    )
    row = cursor.fetchone()
    if row is None or row[0] is None:
        raise SystemExit("no numeric PNF run with a registered run identity is available")
    return int(row[0])


def _documents(cursor: Any, run_id: int, requested: tuple[int, ...]) -> tuple[int, ...]:
    if requested:
        return tuple(sorted(set(requested)))
    cursor.execute(
        """
        SELECT DISTINCT region.document_id
          FROM execution.semantic_pnf_region AS region
          JOIN execution.semantic_pnf_document_identity AS identity
            ON identity.document_id = region.document_id
         WHERE region.run_id = %s
         ORDER BY region.document_id
        """,
        (run_id,),
    )
    return tuple(int(row[0]) for row in cursor.fetchall())


def _time_phase(
    cursor: Any,
    *,
    phase: str,
    function_name: str,
    arity: int,
    run_id: int,
    document_id: int,
    composition_limit: int,
) -> tuple[float, object]:
    started = perf_counter()
    if arity == 2:
        cursor.execute(
            f"SELECT {function_name}(%s, %s)",
            (run_id, document_id),
        )
    else:
        cursor.execute(
            f"SELECT {function_name}(%s, %s, %s)",
            (run_id, document_id, composition_limit),
        )
    row = cursor.fetchone()
    elapsed_ms = (perf_counter() - started) * 1000.0
    result = None if row is None else row[0]
    print(
        f"    phase={phase} elapsed_ms={elapsed_ms:.3f} result={result!r}",
        flush=True,
    )
    return elapsed_ms, result


def _count(cursor: Any, query: str, params: tuple[object, ...]) -> int:
    cursor.execute(query, params)
    row = cursor.fetchone()
    return int(row[0]) if row is not None else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--document-id", action="append", type=int, default=[])
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=30_000,
        help="Fail one semantic phase instead of waiting indefinitely (default: 30000).",
    )
    parser.add_argument(
        "--composition-limit",
        type=int,
        default=16,
        help="Maximum retained composition candidates per bridge (default: 16).",
    )
    args = parser.parse_args()
    if args.statement_timeout_ms < 1:
        raise SystemExit("--statement-timeout-ms must be positive")
    if not 1 <= args.composition_limit <= 256:
        raise SystemExit("--composition-limit must be between 1 and 256")

    connection = connect(args.database_url)
    total_started = perf_counter()
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                run_id = _resolve_run(cursor, args.run_id)
                document_ids = _documents(cursor, run_id, tuple(args.document_id))
        print(f"run_id={run_id} documents={len(document_ids)}")

        for ordinal, document_id in enumerate(document_ids, start=1):
            print(
                f"[{ordinal}/{len(document_ids)}] document_id={document_id}",
                flush=True,
            )
            document_started = perf_counter()
            with connection.transaction():
                with connection.cursor() as cursor:
                    for phase, function_name, arity in _PHASES:
                        cursor.execute(
                            "SELECT set_config('statement_timeout', %s, true)",
                            (f"{args.statement_timeout_ms}ms",),
                        )
                        cursor.fetchone()
                        _time_phase(
                            cursor,
                            phase=phase,
                            function_name=function_name,
                            arity=arity,
                            run_id=run_id,
                            document_id=document_id,
                            composition_limit=args.composition_limit,
                        )
                    composition_overflow = _count(
                        cursor,
                        """
                        SELECT count(*)
                          FROM execution.semantic_pnf_factor_composition_overflow
                         WHERE run_id = %s AND document_id = %s
                        """,
                        (run_id, document_id),
                    )
                    name_overflow = _count(
                        cursor,
                        """
                        SELECT count(*)
                          FROM execution.semantic_pnf_proper_name_evidence_overflow
                         WHERE run_id = %s AND document_id = %s
                        """,
                        (run_id, document_id),
                    )
                    factor_bearing_projections = _count(
                        cursor,
                        """
                        SELECT count(DISTINCT projection.source_object_id)
                          FROM execution.semantic_pnf_identity_projection AS projection
                          JOIN execution.semantic_pnf_hyperedge AS edge
                            ON edge.object_id = projection.source_object_id
                          JOIN execution.semantic_pnf_object AS source
                            ON source.object_id = projection.source_object_id
                          JOIN execution.semantic_pnf_region AS region
                            ON region.region_id = source.region_id
                         WHERE region.run_id = %s
                           AND region.document_id = %s
                        """,
                        (run_id, document_id),
                    )
            document_ms = (perf_counter() - document_started) * 1000.0
            print(
                f"    document_total_ms={document_ms:.3f} "
                f"proper_name_overflow_mentions={name_overflow} "
                f"factor_bearing_projections={factor_bearing_projections} "
                f"composition_overflow_bridges={composition_overflow}",
                flush=True,
            )

        total_ms = (perf_counter() - total_started) * 1000.0
        print(f"total_elapsed_ms={total_ms:.3f}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
