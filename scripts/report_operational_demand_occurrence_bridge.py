#!/usr/bin/env python3
"""Report operational->numeric demand occurrence transport without provider I/O."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.spacy_parser_model import connect  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _scalar(cursor: Any, sql: str) -> int:
    cursor.execute(sql)
    return int(cursor.fetchone()[0])


def main() -> int:
    args = _parse_args()
    connection = connect(args.database_url)
    try:
        with connection.cursor() as cursor:
            summary = {
                "operational_demands_with_occurrence_provenance": _scalar(
                    cursor,
                    "SELECT count(DISTINCT demand_ref) FROM resolution.demand_occurrence_provenance",
                ),
                "operational_trigger_demands": _scalar(
                    cursor,
                    "SELECT count(DISTINCT demand_ref) FROM resolution.demand_occurrence_provenance WHERE occurrence_role=1",
                ),
                "operational_target_demands": _scalar(
                    cursor,
                    "SELECT count(DISTINCT demand_ref) FROM resolution.demand_occurrence_provenance WHERE occurrence_role=2",
                ),
                "operational_occurrences_without_numeric_coordinates": _scalar(
                    cursor,
                    """
                    SELECT count(*)
                      FROM resolution.demand_occurrence_provenance
                     WHERE start_char IS NULL OR end_char IS NULL
                    """,
                ),
                "operational_demands_without_numeric_coordinates": _scalar(
                    cursor,
                    """
                    SELECT count(DISTINCT demand_ref)
                      FROM resolution.demand_occurrence_provenance
                     WHERE start_char IS NULL OR end_char IS NULL
                    """,
                ),
                "projected_numeric_trigger_demands": _scalar(
                    cursor,
                    """
                    SELECT count(DISTINCT demand_id)
                      FROM execution.semantic_pnf_demand_occurrence_provenance
                     WHERE occurrence_role=1
                       AND producer_ref LIKE 'operational-demand:%'
                    """,
                ),
                "projected_numeric_target_demands": _scalar(
                    cursor,
                    """
                    SELECT count(DISTINCT demand_id)
                      FROM execution.semantic_pnf_demand_occurrence_provenance
                     WHERE occurrence_role=2
                       AND producer_ref LIKE 'operational-demand:%'
                    """,
                ),
                "exact_h9_target_support": _scalar(
                    cursor,
                    "SELECT count(DISTINCT demand_id) FROM execution.semantic_pnf_demand_h9_target_support_v1",
                ),
                "quality_valid_entity_targets": _scalar(
                    cursor,
                    "SELECT count(DISTINCT demand_id) FROM execution.semantic_pnf_demand_parser_entity_occurrence_v1",
                ),
                "provider_io_performed": False,
            }
            cursor.execute(
                "SELECT * FROM execution.verify_resolution_demand_occurrence_projection()"
            )
            summary["verification"] = {
                str(row[0]): int(row[1]) for row in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT operational.demand_ref,
                       operational.residual_type_ref,
                       trigger.parser_token_ref AS trigger_ref,
                       trigger.start_char AS trigger_start,
                       trigger.end_char AS trigger_end,
                       target.parser_token_ref AS target_ref,
                       target.start_char AS target_start,
                       target.end_char AS target_end,
                       target.semantic_role_ref AS target_role,
                       numeric.demand_id AS numeric_demand_id,
                       numeric_target.token_id AS numeric_target_token_id,
                       numeric_target.object_id AS numeric_target_object_id
                  FROM resolution.demand_occurrence_provenance AS operational
                  JOIN resolution.demand_occurrence_provenance AS trigger
                    ON trigger.demand_ref=operational.demand_ref
                   AND trigger.residual_type_ref=operational.residual_type_ref
                   AND trigger.occurrence_role=1
                  LEFT JOIN resolution.demand_occurrence_provenance AS target
                    ON target.demand_ref=operational.demand_ref
                   AND target.residual_type_ref=operational.residual_type_ref
                   AND target.occurrence_role=2
                  LEFT JOIN execution.semantic_pnf_demand_occurrence_provenance AS numeric
                    ON numeric.producer_ref='operational-demand:'||operational.demand_ref
                   AND numeric.occurrence_role=1
                  LEFT JOIN execution.semantic_pnf_demand_occurrence_provenance AS numeric_target
                    ON numeric_target.demand_id=numeric.demand_id
                   AND numeric_target.producer_ref=numeric.producer_ref
                   AND numeric_target.occurrence_role=2
                 WHERE operational.occurrence_role=1
                 ORDER BY operational.demand_ref,operational.residual_type_ref
                 LIMIT %s
                """,
                (max(0, args.limit),),
            )
            summary["sample"] = [
                {
                    "demand_ref": str(row[0]),
                    "residual_type": str(row[1]),
                    "trigger_ref": str(row[2]),
                    "trigger_span": (
                        [int(row[3]), int(row[4])]
                        if row[3] is not None and row[4] is not None
                        else None
                    ),
                    "target_ref": str(row[5]) if row[5] is not None else None,
                    "target_span": (
                        [int(row[6]), int(row[7])]
                        if row[6] is not None and row[7] is not None
                        else None
                    ),
                    "target_role": str(row[8]) if row[8] is not None else None,
                    "numeric_demand_id": int(row[9]) if row[9] is not None else None,
                    "numeric_target_token_id": int(row[10]) if row[10] is not None else None,
                    "numeric_target_object_id": int(row[11]) if row[11] is not None else None,
                }
                for row in cursor.fetchall()
            ]
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
