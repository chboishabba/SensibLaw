#!/usr/bin/env python3
"""Read-only C2 parity receipt for the delta-fed parent boundary projection.

The shadow projection is maintained from ``semantic_pnf_interface_export``
changes only.  This benchmark compares its fused parent view against an
independent direct union of the same child boundary rows.  It deliberately does
not claim equality with the full canonical parent frontier, whose reconciliation
and promotion semantics remain authoritative until later scoped parity closes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.parent-delta-projection.v0_1"


def benchmark_parent_delta_projection(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> dict[str, Any]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                started = monotonic_ns()
                cursor.execute(
                    """
                    WITH direct AS (
                        SELECT child.parent_region_id,
                               export.export_kind,
                               export.target_kind,
                               export.target_id,
                               min(export.key_symbol_id) AS key_symbol_id,
                               min(export.role_symbol_id) AS role_symbol_id,
                               min(export.residual_type_symbol_id)
                                   AS residual_type_symbol_id,
                               min(export.rank) AS rank,
                               max(export.promotion_score) AS promotion_score,
                               count(*) AS contributing_child_count
                          FROM execution.semantic_pnf_region AS child
                          JOIN execution.semantic_pnf_interface AS interface
                            ON interface.region_id = child.region_id
                          JOIN execution.semantic_pnf_interface_export AS export
                            ON export.interface_id = interface.interface_id
                         WHERE child.run_ref = %s
                           AND child.document_ref = %s
                           AND child.parent_region_id IS NOT NULL
                           AND child.region_kind <> 9
                         GROUP BY child.parent_region_id,
                                  export.export_kind,
                                  export.target_kind,
                                  export.target_id
                    ), projected AS (
                        SELECT fused.*
                          FROM execution.semantic_pnf_parent_delta_fused_export AS fused
                          JOIN execution.semantic_pnf_region AS parent
                            ON parent.region_id = fused.parent_region_id
                         WHERE parent.run_ref = %s
                           AND parent.document_ref = %s
                    ), mismatch AS (
                        (SELECT * FROM direct EXCEPT SELECT * FROM projected)
                        UNION ALL
                        (SELECT * FROM projected EXCEPT SELECT * FROM direct)
                    )
                    SELECT
                        (SELECT count(*) FROM direct),
                        (SELECT count(*) FROM projected),
                        (SELECT count(*) FROM mismatch),
                        (SELECT count(DISTINCT parent_region_id) FROM direct),
                        (SELECT count(*)
                           FROM execution.semantic_pnf_parent_delta_projection AS p
                           JOIN execution.semantic_pnf_region AS parent
                             ON parent.region_id = p.parent_region_id
                          WHERE parent.run_ref = %s
                            AND parent.document_ref = %s)
                    """,
                    (
                        run_ref,
                        document_ref,
                        run_ref,
                        document_ref,
                        run_ref,
                        document_ref,
                    ),
                )
                direct_count, projected_count, mismatch_count, parent_count, atom_count = (
                    int(value) for value in cursor.fetchone()
                )
                parity_ns = monotonic_ns() - started

                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_parent_delta_projection AS p
                      JOIN execution.semantic_pnf_region AS child
                        ON child.region_id = p.child_region_id
                     WHERE child.run_ref = %s
                       AND child.document_ref = %s
                       AND child.parent_region_id IS DISTINCT FROM p.parent_region_id
                    """,
                    (run_ref, document_ref),
                )
                stale_parent_count = int(cursor.fetchone()[0])

                return {
                    "contract": CONTRACT,
                    "run_ref": run_ref,
                    "document_ref": document_ref,
                    "parent_count": parent_count,
                    "transported_atom_count": atom_count,
                    "direct_fused_export_count": direct_count,
                    "projected_fused_export_count": projected_count,
                    "fused_projection_mismatch_count": mismatch_count,
                    "fused_projection_equal_direct_union": mismatch_count == 0,
                    "stale_parent_address_count": stale_parent_count,
                    "parent_addresses_current": stale_parent_count == 0,
                    "timing_ns": {"direct_union_projection_parity": parity_ns},
                    "work": {
                        "source_token_rescan_count": 0,
                        "source_object_rescan_count": 0,
                        "source_factor_rescan_count": 0,
                        "transport_carrier": "semantic_pnf_interface_export",
                        "fusion": "grouped parent-local set projection",
                    },
                    "authority": {
                        "database_mutations_performed": False,
                        "provider_io_performed": False,
                        "canonical_parent_frontier_mutated": False,
                        "whole_parent_frontier_equality_claimed": False,
                        "comparison_scope": "child interface boundary transport/fusion only",
                    },
                }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = benchmark_parent_delta_projection(
        args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if (
        receipt["fused_projection_equal_direct_union"]
        and receipt["parent_addresses_current"]
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
