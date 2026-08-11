#!/usr/bin/env python3
"""Measure proof-relevant identity evidence yield over a numeric PNF run.

The report never treats lexical co-occurrence as identity.  It separates parser
candidates, source->entity proofs, anchor/base witnesses, current projections,
factor-bearing projections, Level-3 substitutions, overflow receipts and world
authority.  Refresh, when requested, commits one document at a time.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


def _scalar(cursor: Any, query: str, params: tuple[object, ...]) -> int:
    cursor.execute(query, params)
    row = cursor.fetchone()
    return int(row[0]) if row is not None and row[0] is not None else 0


def _rows(cursor: Any, query: str, params: tuple[object, ...]) -> tuple[tuple[Any, ...], ...]:
    cursor.execute(query, params)
    return tuple(cursor.fetchall())


def _resolve_run(cursor: Any, run_id: int | None) -> int:
    if run_id is not None:
        cursor.execute(
            """
            SELECT 1
              FROM execution.semantic_pnf_run_identity
             WHERE run_id = %s
            """,
            (run_id,),
        )
        if cursor.fetchone() is None:
            raise SystemExit(f"unknown run_id {run_id}")
        return run_id
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


def _document_ids(cursor: Any, run_id: int, requested: tuple[int, ...]) -> tuple[int, ...]:
    if requested:
        return tuple(sorted(set(requested)))
    return tuple(
        int(row[0])
        for row in _rows(
            cursor,
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
    )


def _refresh_documents(
    connection: Any,
    *,
    run_id: int,
    document_ids: tuple[int, ...],
    statement_timeout_ms: int,
) -> None:
    for ordinal, document_id in enumerate(document_ids, start=1):
        started = perf_counter()
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (f"{statement_timeout_ms}ms",),
                )
                cursor.fetchone()
                cursor.execute(
                    "SELECT * FROM execution.refresh_numeric_pnf_semantic_derivations(%s, %s)",
                    (run_id, document_id),
                )
                result = cursor.fetchone()
        elapsed_ms = (perf_counter() - started) * 1000.0
        print(
            f"refresh [{ordinal}/{len(document_ids)}] document_id={document_id} "
            f"elapsed_ms={elapsed_ms:.3f} result={result!r}",
            file=sys.stderr,
            flush=True,
        )


def _surface_rows(
    cursor: Any,
    run_id: int,
    document_ids: tuple[int, ...],
    surfaces: tuple[str, ...],
) -> tuple[tuple[Any, ...], ...]:
    if not surfaces:
        return ()
    return _rows(
        cursor,
        """
        WITH requested(surface) AS (
            SELECT unnest(%s::TEXT[])
        ), symbols AS (
            SELECT requested.surface, symbol.symbol_id
              FROM requested
              JOIN execution.semantic_symbol AS symbol
                ON lower(symbol.symbol_text) = lower(requested.surface)
        ), objects AS (
            SELECT symbols.surface, object.object_id
              FROM symbols
              JOIN execution.semantic_pnf_object AS object
                ON object.head_symbol_id = symbols.symbol_id
              JOIN execution.semantic_pnf_region AS region
                ON region.region_id = object.region_id
               AND region.run_id = %s
               AND region.document_id = ANY(%s)
        )
        SELECT objects.surface,
               count(DISTINCT objects.object_id) AS local_objects,
               count(DISTINCT edge.factor_id) AS direct_factors,
               count(DISTINCT projection.target_entity_id) AS admitted_entities,
               count(DISTINCT projection.source_object_id) AS projected_objects,
               count(DISTINCT projection.source_object_id) FILTER (
                   WHERE edge.factor_id IS NOT NULL
               ) AS factor_bearing_projected_objects
          FROM objects
          LEFT JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.object_id = objects.object_id
          LEFT JOIN execution.semantic_pnf_identity_projection AS projection
            ON projection.source_object_id = objects.object_id
         GROUP BY objects.surface
         ORDER BY objects.surface
        """,
        (list(surfaces), run_id, list(document_ids)),
    )


def build_report(
    database_url: str,
    *,
    run_id: int | None,
    document_ids: tuple[int, ...],
    surfaces: tuple[str, ...],
    refresh: bool,
    statement_timeout_ms: int = 30_000,
) -> str:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                selected_run_id = _resolve_run(cursor, run_id)
                selected_documents = _document_ids(cursor, selected_run_id, document_ids)

        if refresh:
            _refresh_documents(
                connection,
                run_id=selected_run_id,
                document_ids=selected_documents,
                statement_timeout_ms=statement_timeout_ms,
            )

        with connection.transaction():
            with connection.cursor() as cursor:
                params: tuple[object, ...] = (
                    selected_run_id,
                    list(selected_documents),
                )

                local_objects = _scalar(
                    cursor,
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_object AS object
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = object.region_id
                     WHERE region.run_id = %s
                       AND region.document_id = ANY(%s)
                    """,
                    params,
                )
                factor_participants = _scalar(
                    cursor,
                    """
                    SELECT count(DISTINCT edge.object_id)
                      FROM execution.semantic_pnf_hyperedge AS edge
                      JOIN execution.semantic_pnf_object AS object
                        ON object.object_id = edge.object_id
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = object.region_id
                     WHERE region.run_id = %s
                       AND region.document_id = ANY(%s)
                    """,
                    params,
                )
                candidates = _scalar(
                    cursor,
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_identity_evidence_candidate
                     WHERE run_id = %s
                       AND document_id = ANY(%s)
                       AND evidence_state IN (1, 2, 3)
                    """,
                    params,
                )
                accepted_candidates = _scalar(
                    cursor,
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_identity_evidence_candidate
                     WHERE run_id = %s
                       AND document_id = ANY(%s)
                       AND evidence_state = 2
                    """,
                    params,
                )
                parser_source_witnesses = _scalar(
                    cursor,
                    """
                    SELECT count(DISTINCT provenance.witness_id)
                      FROM execution.semantic_pnf_identity_evidence_witness AS provenance
                      JOIN execution.semantic_pnf_identity_evidence_candidate AS candidate
                        ON candidate.candidate_id = provenance.candidate_id
                      JOIN execution.semantic_pnf_identity_witness_admission AS admission
                        ON admission.witness_id = provenance.witness_id
                       AND admission.admission_state = 2
                     WHERE candidate.run_id = %s
                       AND candidate.document_id = ANY(%s)
                       AND provenance.witness_role = 2
                    """,
                    params,
                )
                parser_anchor_witnesses = _scalar(
                    cursor,
                    """
                    SELECT count(DISTINCT provenance.witness_id)
                      FROM execution.semantic_pnf_identity_evidence_witness AS provenance
                      JOIN execution.semantic_pnf_identity_evidence_candidate AS candidate
                        ON candidate.candidate_id = provenance.candidate_id
                      JOIN execution.semantic_pnf_identity_witness_admission AS admission
                        ON admission.witness_id = provenance.witness_id
                       AND admission.admission_state = 2
                     WHERE candidate.run_id = %s
                       AND candidate.document_id = ANY(%s)
                       AND provenance.witness_role = 1
                    """,
                    params,
                )
                demand_source_witnesses = _scalar(
                    cursor,
                    """
                    SELECT count(DISTINCT witness.witness_id)
                      FROM execution.semantic_pnf_identity_witness AS witness
                      JOIN execution.semantic_pnf_identity_witness_admission AS admission
                        ON admission.witness_id = witness.witness_id
                       AND admission.admission_state = 2
                      JOIN execution.semantic_pnf_object AS source
                        ON source.object_id = witness.source_object_id
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = source.region_id
                     WHERE region.run_id = %s
                       AND region.document_id = ANY(%s)
                       AND witness.demand_id IS NOT NULL
                    """,
                    params,
                )
                projections = _scalar(
                    cursor,
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_identity_projection AS projection
                      JOIN execution.semantic_pnf_object AS source
                        ON source.object_id = projection.source_object_id
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = source.region_id
                     WHERE region.run_id = %s
                       AND region.document_id = ANY(%s)
                    """,
                    params,
                )
                factor_bearing_projections = _scalar(
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
                       AND region.document_id = ANY(%s)
                    """,
                    params,
                )
                derived = _scalar(
                    cursor,
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_factor_derivation AS derivation
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.interface_id = derivation.scope_interface_id
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = interface.region_id
                     WHERE derivation.rule_ref = 'identity-substitution:v1'
                       AND derivation.derivation_state = 2
                       AND region.run_id = %s
                       AND region.document_id = ANY(%s)
                    """,
                    params,
                )
                world_entities = _scalar(
                    cursor,
                    """
                    SELECT count(DISTINCT projection.target_entity_id)
                      FROM execution.semantic_pnf_identity_projection AS projection
                      JOIN execution.semantic_pnf_canonical_entity AS entity
                        ON entity.entity_id = projection.target_entity_id
                      JOIN execution.semantic_pnf_object AS source
                        ON source.object_id = projection.source_object_id
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = source.region_id
                     WHERE region.run_id = %s
                       AND region.document_id = ANY(%s)
                       AND entity.authority_class = 4
                    """,
                    params,
                )
                composition_overflow = _scalar(
                    cursor,
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_factor_composition_overflow
                     WHERE run_id = %s AND document_id = ANY(%s)
                    """,
                    params,
                )
                proper_name_overflow = _scalar(
                    cursor,
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_proper_name_evidence_overflow
                     WHERE run_id = %s AND document_id = ANY(%s)
                    """,
                    params,
                )
                unretained_name_targets = _scalar(
                    cursor,
                    """
                    SELECT COALESCE(sum(
                               GREATEST(possible_target_count - retained_target_limit, 0)
                           ), 0)
                      FROM execution.semantic_pnf_proper_name_evidence_overflow
                     WHERE run_id = %s AND document_id = ANY(%s)
                    """,
                    params,
                )

                kind_rows = _rows(
                    cursor,
                    """
                    SELECT kind.witness_name,
                           count(*) AS candidates,
                           count(*) FILTER (WHERE candidate.evidence_state = 2) AS admitted,
                           count(*) FILTER (WHERE candidate.candidate_count > 1) AS ambiguous
                      FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
                      JOIN execution.semantic_pnf_identity_witness_kind AS kind
                        ON kind.witness_kind = candidate.witness_kind
                     WHERE candidate.run_id = %s
                       AND candidate.document_id = ANY(%s)
                       AND candidate.evidence_state IN (1, 2, 3)
                     GROUP BY kind.witness_name
                     ORDER BY kind.witness_name
                    """,
                    params,
                )
                surface_rows = _surface_rows(
                    cursor,
                    selected_run_id,
                    selected_documents,
                    surfaces,
                )

                lines = [
                    "# Identity Evidence Yield",
                    "",
                    f"- Run: **{selected_run_id}**",
                    f"- Documents: **{len(selected_documents)}**",
                    f"- Local objects: **{local_objects}**",
                    f"- Factor participants: **{factor_participants}**",
                    f"- Parser-grounded identity candidates: **{candidates}**",
                    f"- Admitted parser candidates: **{accepted_candidates}**",
                    f"- Admitted parser source proofs: **{parser_source_witnesses}**",
                    f"- Parser anchor/base witnesses: **{parser_anchor_witnesses}**",
                    f"- Admitted typed-demand source proofs: **{demand_source_witnesses}**",
                    f"- Current identity projections: **{projections}**",
                    f"- Factor-bearing identity projections: **{factor_bearing_projections}**",
                    f"- Level-3 identity substitutions: **{derived}**",
                    f"- Proper-name overflow mentions: **{proper_name_overflow}**",
                    f"- Unretained ambiguous name targets: **{unretained_name_targets}**",
                    f"- Composition overflow bridges: **{composition_overflow}**",
                    f"- World-authority entities: **{world_entities}**",
                    "",
                    "## Evidence kinds",
                    "",
                    "| witness kind | candidates | admitted | ambiguous/non-unique |",
                    "|---|---:|---:|---:|",
                ]
                lines.extend(
                    f"| {name} | {int(total)} | {int(admitted)} | {int(ambiguous)} |"
                    for name, total, admitted, ambiguous in kind_rows
                )
                if surface_rows:
                    lines.extend(
                        [
                            "",
                            "## Requested surfaces",
                            "",
                            "| surface | local objects | direct factors | admitted entities | projected objects | factor-bearing projected objects |",
                            "|---|---:|---:|---:|---:|---:|",
                        ]
                    )
                    lines.extend(
                        f"| {surface} | {int(objects)} | {int(factors)} | {int(entities)} | {int(projected)} | {int(factor_projected)} |"
                        for surface, objects, factors, entities, projected, factor_projected in surface_rows
                    )
                lines.extend(
                    [
                        "",
                        "## Epistemic boundary",
                        "",
                        "A parser source proof is not automatically a factor derivation. Only factor-bearing projections can contribute to Level-3 substitutions. Proper-name and composition overflow are execution receipts only; candidate evidence is not identity authority; world identity still requires external-authority evidence.",
                    ]
                )
                return "\n".join(lines) + "\n"
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--document-id", action="append", type=int, default=[])
    parser.add_argument("--surface", action="append", default=[])
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--statement-timeout-ms", type=int, default=30_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.statement_timeout_ms < 1:
        raise SystemExit("--statement-timeout-ms must be positive")
    report = build_report(
        args.database_url,
        run_id=args.run_id,
        document_ids=tuple(args.document_id),
        surfaces=tuple(args.surface),
        refresh=args.refresh,
        statement_timeout_ms=args.statement_timeout_ms,
    )
    if args.output is None:
        print(report, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
