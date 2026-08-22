#!/usr/bin/env python3
"""Report sparse numeric-PNF frontier reduction and stage receipts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Iterable

from src.storage.postgres.spacy_parser_model import connect


@dataclass(frozen=True, slots=True)
class FrontierRow:
    interface_id: int
    region_kind: int
    sequence_no: int
    input_exports: int
    output_exports: int
    actor_profiles: int
    unresolved_demands: int
    resolved_demands: int
    elapsed_ms: float

    @property
    def compression_ratio(self) -> float:
        if self.input_exports == 0:
            return 1.0 if self.output_exports == 0 else 0.0
        return self.output_exports / self.input_exports


def _frontier_rows(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[FrontierRow, ...]:
    cursor.execute(
        """
        SELECT receipt.interface_id,
               region.region_kind,
               region.sequence_no,
               receipt.input_export_count,
               receipt.output_export_count,
               receipt.actor_profile_count,
               receipt.unresolved_demand_count,
               receipt.resolved_demand_count,
               receipt.elapsed_ms
          FROM execution.semantic_pnf_frontier_reduction_receipt AS receipt
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.interface_id = receipt.interface_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE region.run_ref = %s
           AND region.document_ref = %s
         ORDER BY region.region_kind,
                  region.sequence_no,
                  receipt.interface_id
        """,
        (run_ref, document_ref),
    )
    return tuple(
        FrontierRow(
            interface_id=int(row[0]),
            region_kind=int(row[1]),
            sequence_no=int(row[2]),
            input_exports=int(row[3]),
            output_exports=int(row[4]),
            actor_profiles=int(row[5]),
            unresolved_demands=int(row[6]),
            resolved_demands=int(row[7]),
            elapsed_ms=float(row[8]),
        )
        for row in cursor.fetchall()
    )


def _stage_rows(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[tuple[str, int, float], ...]:
    cursor.execute(
        """
        SELECT receipt.stage_name,
               receipt.row_count,
               receipt.elapsed_ms
          FROM execution.semantic_pnf_frontier_stage_receipt AS receipt
          JOIN execution.semantic_pnf_run_identity AS run_identity
            ON run_identity.run_id = receipt.run_id
          JOIN execution.semantic_pnf_document_identity AS document_identity
            ON document_identity.document_id = receipt.document_id
         WHERE run_identity.run_ref = %s
           AND document_identity.document_ref = %s
         ORDER BY receipt.completed_at, receipt.stage_name
        """,
        (run_ref, document_ref),
    )
    return tuple((str(row[0]), int(row[1]), float(row[2])) for row in cursor.fetchall())


def _root_counts(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[int, int, int, int, int]:
    cursor.execute(
        """
        SELECT interface.interface_id,
               interface.interface_cardinality,
               interface.unresolved_count,
               (SELECT count(*)
                  FROM execution.semantic_pnf_global_lookup AS global
                 WHERE global.run_id = region.run_id
                   AND global.document_id = region.document_id),
               (SELECT count(*)
                  FROM execution.semantic_pnf_visible_lookup AS visible
                 WHERE visible.interface_id = interface.interface_id)
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE region.run_ref = %s
           AND region.document_ref = %s
           AND region.region_kind = 10
         LIMIT 1
        """,
        (run_ref, document_ref),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("closed numeric PNF document interface not found")
    return tuple(int(value) for value in row)  # type: ignore[return-value]


def _format_table(headers: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> str:
    materialized = tuple(rows)
    widths = [len(header) for header in headers]
    for row in materialized:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    header_line = "  ".join(
        header.ljust(widths[index]) for index, header in enumerate(headers)
    )
    divider = "  ".join("-" * width for width in widths)
    body = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in materialized
    ]
    return "\n".join((header_line, divider, *body))


def report(database_url: str, *, run_ref: str, document_ref: str) -> str:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            frontiers = _frontier_rows(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
            )
            stages = _stage_rows(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
            )
            (
                root_interface_id,
                root_cardinality,
                root_unresolved,
                global_rows,
                visible_rows,
            ) = _root_counts(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
            )
    finally:
        connection.close()

    total_input = sum(row.input_exports for row in frontiers)
    total_output = sum(row.output_exports for row in frontiers)
    overall_ratio = total_output / total_input if total_input else 0.0

    sections = [
        f"run_ref: {run_ref}",
        f"document_ref: {document_ref}",
        f"root_interface_id: {root_interface_id}",
        f"root_interface_cardinality: {root_cardinality}",
        f"root_unresolved_demands: {root_unresolved}",
        f"root_global_lookup_rows: {global_rows}",
        f"root_visible_projection_rows: {visible_rows}",
        (
            "aggregate_frontier_compression: "
            f"{total_input} -> {total_output} ({overall_ratio:.4f})"
        ),
        "",
        "Frontier reductions",
    ]
    if frontiers:
        sections.append(
            _format_table(
                (
                    "iface",
                    "kind",
                    "seq",
                    "input",
                    "output",
                    "ratio",
                    "actors",
                    "open",
                    "resolved",
                    "ms",
                ),
                (
                    (
                        str(row.interface_id),
                        str(row.region_kind),
                        str(row.sequence_no),
                        str(row.input_exports),
                        str(row.output_exports),
                        f"{row.compression_ratio:.4f}",
                        str(row.actor_profiles),
                        str(row.unresolved_demands),
                        str(row.resolved_demands),
                        f"{row.elapsed_ms:.3f}",
                    )
                    for row in frontiers
                ),
            )
        )
    else:
        sections.append("(no sparse frontier receipts)")

    sections.extend(("", "Stages"))
    if stages:
        sections.append(
            _format_table(
                ("stage", "rows", "ms"),
                (
                    (stage, str(row_count), f"{elapsed_ms:.3f}")
                    for stage, row_count, elapsed_ms in stages
                ),
            )
        )
    else:
        sections.append("(no sparse frontier stage receipts)")
    return "\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report sparse numeric-PNF frontier compression"
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref", required=True)
    args = parser.parse_args()
    print(
        report(
            args.database_url,
            run_ref=args.run_ref,
            document_ref=args.document_ref,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
