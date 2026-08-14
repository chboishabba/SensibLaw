#!/usr/bin/env python3
"""Print would-be H9 provider labels without performing provider I/O."""
from __future__ import annotations

import argparse
import json

from src.storage.postgres.spacy_parser_model import connect


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--consumer-ref", required=True)
    parser.add_argument("--query-ref", required=True)
    parser.add_argument("--policy-ref", default="")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    connection = connect(args.database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT execution.refresh_numeric_pnf_parser_entity_surface_labels()")
            refreshed = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT count(DISTINCT admission.demand_id)::BIGINT
                  FROM execution.semantic_pnf_h9_external_admission_v1 admission
                 WHERE admission.consumer_ref=%s
                   AND admission.query_ref=%s
                   AND admission.policy_ref=%s
                   AND admission.contract_id IS NOT NULL
                   AND admission.admitted
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            admitted = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT DISTINCT admission.demand_id,
                       label_symbol.symbol_text AS label,
                       entity_type.symbol_text AS entity_type,
                       anchor.entity_id,
                       anchor.source_object_id
                  FROM execution.semantic_pnf_h9_external_admission_v1 admission
                  JOIN execution.semantic_pnf_h9_unique_parser_entity_anchor_v1 anchor
                    ON anchor.demand_id=admission.demand_id
                  JOIN execution.semantic_symbol label_symbol
                    ON label_symbol.symbol_id=anchor.label_symbol_id
                  JOIN execution.semantic_symbol entity_type
                    ON entity_type.symbol_id=anchor.entity_type_symbol_id
                 WHERE admission.consumer_ref=%s
                   AND admission.query_ref=%s
                   AND admission.policy_ref=%s
                   AND admission.contract_id IS NOT NULL
                   AND admission.admitted
                 ORDER BY label,admission.demand_id
                 LIMIT %s
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref, args.limit),
            )
            labels = [
                {
                    "demand_id": int(demand_id),
                    "label": str(label),
                    "entity_type": str(entity_type),
                    "entity_id": int(entity_id),
                    "source_object_id": int(source_object_id),
                }
                for demand_id, label, entity_type, entity_id, source_object_id
                in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT count(DISTINCT occurrence.demand_id)::BIGINT,
                       count(DISTINCT unique_anchor.demand_id)::BIGINT
                  FROM execution.semantic_pnf_demand_parser_entity_occurrence_v1 occurrence
                  LEFT JOIN execution.semantic_pnf_h9_unique_parser_entity_anchor_v1 unique_anchor
                    ON unique_anchor.demand_id=occurrence.demand_id
                """
            )
            occurrence_demands, unique_demands = cursor.fetchone()
    finally:
        connection.close()

    print(json.dumps({
        "surface_labels_refreshed": refreshed,
        "parser_entity_occurrence_demands": int(occurrence_demands),
        "unique_parser_entity_anchor_demands": int(unique_demands),
        "admitted_external_demands": admitted,
        "sample": labels,
        "provider_io_performed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
