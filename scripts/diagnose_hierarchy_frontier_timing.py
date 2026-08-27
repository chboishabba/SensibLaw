#!/usr/bin/env python3
"""Report native sparse-frontier work inside hierarchy materialization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.spacy_parser_model import connect


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    connection = connect(args.database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT region.region_kind,
                       count(*) AS interface_count,
                       COALESCE(sum(receipt.elapsed_ms), 0) AS elapsed_ms,
                       COALESCE(avg(receipt.elapsed_ms), 0) AS average_ms,
                       COALESCE(max(receipt.elapsed_ms), 0) AS max_ms,
                       COALESCE(sum(receipt.input_export_count), 0) AS input_exports,
                       COALESCE(sum(receipt.output_export_count), 0) AS output_exports
                  FROM execution.semantic_pnf_frontier_reduction_receipt AS receipt
                  JOIN execution.semantic_pnf_interface AS interface
                    ON interface.interface_id = receipt.interface_id
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id = interface.region_id
                 WHERE region.run_ref = %s
                   AND region.document_ref = %s
                 GROUP BY region.region_kind
                 ORDER BY region.region_kind
                """,
                (args.run_ref, args.document_ref),
            )
            by_region_kind = [
                {
                    "region_kind": int(row[0]),
                    "interface_count": int(row[1]),
                    "elapsed_ms": float(row[2]),
                    "average_ms": float(row[3]),
                    "max_ms": float(row[4]),
                    "input_exports": int(row[5]),
                    "output_exports": int(row[6]),
                }
                for row in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT sample.sample_id,
                       sample.row_count,
                       sample.elapsed_ms,
                       sample.observed_at
                  FROM execution.semantic_pnf_frontier_stage_sample AS sample
                  JOIN execution.semantic_pnf_run_identity AS run
                    ON run.run_id = sample.run_id
                  JOIN execution.semantic_pnf_document_identity AS document
                    ON document.document_id = sample.document_id
                 WHERE run.run_ref = %s
                   AND document.document_ref = %s
                   AND sample.stage_name = 'sparse_frontier_reduction'
                 ORDER BY sample.sample_id
                """,
                (args.run_ref, args.document_ref),
            )
            stage_samples = [
                {
                    "sample_id": int(row[0]),
                    "affected_interface_count": int(row[1]),
                    "elapsed_ms": float(row[2]),
                    "observed_at": row[3].isoformat(),
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()

    payload = {
        "contract_ref": "sensiblaw.hierarchy-frontier-timing-diagnostic.v0_1",
        "run_ref": args.run_ref,
        "document_ref": args.document_ref,
        "semantic_authority_effect": "none",
        "frontier_reducer_by_region_kind": by_region_kind,
        "frontier_stage_invocations": stage_samples,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
