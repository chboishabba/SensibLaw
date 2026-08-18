#!/usr/bin/env python3
"""Print quality-gated would-be H9 provider labels without provider I/O."""

from __future__ import annotations

import argparse
import json

from src.storage.postgres.spacy_parser_model import connect


QUALITY_REASON = {
    1: "provider_admissible",
    10: "no_owned_sentence",
    11: "no_covered_parser_tokens",
    12: "not_token_boundary_aligned",
    13: "noncontiguous_sentence_tokens",
    14: "contains_verbal_predicate",
    15: "oversized_provider_label",
    16: "non_world_bearing_entity_type",
    17: "no_nominal_anchor",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--consumer-ref", required=True)
    parser.add_argument("--query-ref", required=True)
    parser.add_argument("--policy-ref", default="")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--rejected-limit", type=int, default=20)
    args = parser.parse_args()

    connection = connect(args.database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT execution.refresh_numeric_pnf_parser_entity_surface_labels()"
            )
            refreshed = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT execution.refresh_semantic_parser_entity_quality_constants()"
            )
            cursor.fetchone()

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
                for demand_id, label, entity_type, entity_id, source_object_id in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT count(DISTINCT raw.demand_id)::BIGINT,
                       count(DISTINCT safe.demand_id)::BIGINT,
                       count(DISTINCT unique_anchor.demand_id)::BIGINT
                  FROM execution.semantic_pnf_demand_raw_parser_entity_occurrence_v1 raw
                  LEFT JOIN execution.semantic_pnf_demand_parser_entity_occurrence_v1 safe
                    ON safe.demand_id=raw.demand_id
                  LEFT JOIN execution.semantic_pnf_h9_unique_parser_entity_anchor_v1 unique_anchor
                    ON unique_anchor.demand_id=raw.demand_id
                """
            )
            raw_occurrence_demands, safe_occurrence_demands, unique_demands = (
                cursor.fetchone()
            )

            cursor.execute(
                """
                SELECT raw.quality_state,count(DISTINCT raw.demand_id)::BIGINT
                  FROM execution.semantic_pnf_demand_raw_parser_entity_occurrence_v1 raw
                  JOIN execution.semantic_pnf_h9_external_admission_v1 admission
                    ON admission.demand_id=raw.demand_id
                 WHERE admission.consumer_ref=%s
                   AND admission.query_ref=%s
                   AND admission.policy_ref=%s
                   AND admission.contract_id IS NOT NULL
                 GROUP BY raw.quality_state
                 ORDER BY raw.quality_state
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            rejection_summary = [
                {
                    "quality_state": int(state),
                    "reason": QUALITY_REASON.get(int(state), "unknown"),
                    "demands": int(count),
                }
                for state, count in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT DISTINCT raw.demand_id,label.symbol_text,
                       entity_type.symbol_text,raw.quality_state,raw.entity_id
                  FROM execution.semantic_pnf_demand_raw_parser_entity_occurrence_v1 raw
                  JOIN execution.semantic_pnf_h9_external_admission_v1 admission
                    ON admission.demand_id=raw.demand_id
                  JOIN execution.semantic_pnf_parser_entity_surface_label surface
                    ON surface.entity_id=raw.entity_id
                  JOIN execution.semantic_symbol label
                    ON label.symbol_id=surface.label_symbol_id
                  JOIN execution.semantic_symbol entity_type
                    ON entity_type.symbol_id=raw.entity_type_symbol_id
                 WHERE admission.consumer_ref=%s
                   AND admission.query_ref=%s
                   AND admission.policy_ref=%s
                   AND admission.contract_id IS NOT NULL
                   AND raw.quality_state<>1
                 ORDER BY raw.quality_state,label.symbol_text,raw.demand_id
                 LIMIT %s
                """,
                (
                    args.consumer_ref,
                    args.query_ref,
                    args.policy_ref,
                    args.rejected_limit,
                ),
            )
            rejected_sample = [
                {
                    "demand_id": int(demand_id),
                    "label": str(label),
                    "entity_type": str(entity_type),
                    "quality_state": int(state),
                    "reason": QUALITY_REASON.get(int(state), "unknown"),
                    "entity_id": int(entity_id),
                }
                for demand_id, label, entity_type, state, entity_id in cursor.fetchall()
            ]
    finally:
        connection.close()

    print(
        json.dumps(
            {
                "surface_labels_refreshed": refreshed,
                "raw_parser_entity_occurrence_demands": int(raw_occurrence_demands),
                "quality_gated_parser_entity_occurrence_demands": int(
                    safe_occurrence_demands
                ),
                "unique_parser_entity_anchor_demands": int(unique_demands),
                "admitted_external_demands": admitted,
                "quality_summary": rejection_summary,
                "rejected_sample": rejected_sample,
                "sample": labels,
                "provider_io_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
