#!/usr/bin/env python3
"""Report exact demand-occurrence provenance before H9 external planning."""
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
    parser.add_argument("--sample-limit", type=int, default=20)
    args = parser.parse_args()

    connection = connect(args.database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH scoped AS (
                    SELECT DISTINCT work.demand_id
                      FROM execution.semantic_pnf_consumer_horizon_work_queue work
                      JOIN execution.semantic_pnf_h9_external_admission_v1 admission
                        ON admission.demand_id=work.demand_id
                       AND admission.consumer_ref=work.consumer_ref
                       AND admission.query_ref=work.query_ref
                       AND admission.policy_ref=work.policy_ref
                     WHERE work.horizon=9 AND work.work_state=1
                       AND work.consumer_ref=%s AND work.query_ref=%s
                       AND work.policy_ref=%s
                       AND admission.contract_id IS NOT NULL
                )
                SELECT
                    count(*)::BIGINT AS contract_matched,
                    count(*) FILTER (WHERE audit.strong_support_count>0)::BIGINT,
                    count(*) FILTER (WHERE audit.exact_interface_object_count>0)::BIGINT,
                    count(*) FILTER (WHERE audit.exact_factor_slot_count>0)::BIGINT,
                    count(*) FILTER (WHERE audit.parser_entity_reachable)::BIGINT,
                    count(*) FILTER (WHERE projection.projection_state=2)::BIGINT,
                    count(*) FILTER (WHERE projection.projection_state=3)::BIGINT,
                    count(*) FILTER (
                        WHERE audit.strong_support_count=0
                          AND audit.legacy_source_object_count>0
                    )::BIGINT,
                    count(*) FILTER (
                        WHERE audit.strong_support_count=0
                          AND audit.legacy_source_object_count=0
                    )::BIGINT
                  FROM scoped
                  JOIN execution.semantic_pnf_demand_occurrence_support_audit_v1 audit
                    USING(demand_id)
                  JOIN execution.semantic_pnf_demand_occurrence_projection_audit_v1 projection
                    USING(demand_id)
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            row = cursor.fetchone()
            summary = {
                "contract_matched_demands": int(row[0]),
                "strong_occurrence_support_demands": int(row[1]),
                "lexical_origin_support_demands": int(row[2]),
                "role_factor_origin_support_demands": int(row[3]),
                "parser_entity_reachable_demands": int(row[4]),
                "unique_strong_object_projection_demands": int(row[5]),
                "ambiguous_strong_object_demands": int(row[6]),
                "legacy_only_support_demands": int(row[7]),
                "no_occurrence_support_demands": int(row[8]),
            }

            cursor.execute(
                """
                WITH scoped AS (
                    SELECT DISTINCT work.demand_id
                      FROM execution.semantic_pnf_consumer_horizon_work_queue work
                      JOIN execution.semantic_pnf_h9_external_admission_v1 admission
                        ON admission.demand_id=work.demand_id
                       AND admission.consumer_ref=work.consumer_ref
                       AND admission.query_ref=work.query_ref
                       AND admission.policy_ref=work.policy_ref
                     WHERE work.horizon=9 AND work.work_state=1
                       AND work.consumer_ref=%s AND work.query_ref=%s
                       AND work.policy_ref=%s
                       AND admission.contract_id IS NOT NULL
                )
                SELECT shape.coordinate_shape,count(*)::BIGINT,
                       count(*) FILTER (WHERE audit.strong_support_count>0)::BIGINT,
                       count(*) FILTER (WHERE audit.parser_entity_reachable)::BIGINT
                  FROM scoped
                  JOIN execution.semantic_pnf_demand_coordinate_shape_v1 shape USING(demand_id)
                  JOIN execution.semantic_pnf_demand_occurrence_support_audit_v1 audit USING(demand_id)
                 GROUP BY shape.coordinate_shape
                 ORDER BY shape.coordinate_shape
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            summary["coordinate_shapes"] = [
                {
                    "shape": int(shape),
                    "demands": int(demands),
                    "strong_support": int(strong),
                    "parser_entity_reachable": int(entity),
                }
                for shape, demands, strong, entity in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT admission.admission_reason,admission.admitted,
                       count(DISTINCT admission.demand_id)::BIGINT
                  FROM execution.semantic_pnf_h9_external_admission_v1 admission
                 WHERE admission.consumer_ref=%s AND admission.query_ref=%s
                   AND admission.policy_ref=%s AND admission.contract_id IS NOT NULL
                 GROUP BY admission.admission_reason,admission.admitted
                 ORDER BY admission.admitted DESC,admission.admission_reason
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            summary["h9_admission"] = [
                {
                    "reason": int(reason),
                    "admitted": bool(admitted),
                    "demands": int(count),
                }
                for reason, admitted, count in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT DISTINCT admission.demand_id,symbol.symbol_text,
                       support.support_kind,support.object_id
                  FROM execution.semantic_pnf_h9_external_admission_v1 admission
                  JOIN execution.semantic_pnf_h9_preferred_entity_anchor_v1 anchor
                    ON anchor.demand_id=admission.demand_id
                  JOIN execution.semantic_symbol symbol
                    ON symbol.symbol_id=anchor.label_symbol_id
                  JOIN execution.semantic_pnf_demand_strong_occurrence_support_v1 support
                    ON support.demand_id=admission.demand_id
                   AND support.object_id=anchor.source_object_id
                 WHERE admission.consumer_ref=%s AND admission.query_ref=%s
                   AND admission.policy_ref=%s
                 ORDER BY admission.demand_id
                 LIMIT %s
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref, args.sample_limit),
            )
            summary["entity_anchor_sample"] = [
                {
                    "demand_id": int(demand_id),
                    "label": str(label),
                    "support_kind": int(support_kind),
                    "object_id": int(object_id),
                }
                for demand_id, label, support_kind, object_id in cursor.fetchall()
            ]
    finally:
        connection.close()

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
