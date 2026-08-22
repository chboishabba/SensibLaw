#!/usr/bin/env python3
"""Audit trigger/target demand provenance without performing provider I/O."""

from __future__ import annotations

import argparse
import json

from src.storage.postgres.spacy_parser_model import connect


PROVENANCE_STATE = {
    1: "one_exact_target",
    2: "multiple_targets",
    10: "no_producer_occurrence",
    11: "trigger_only_factor_level",
    12: "trigger_but_target_role_unresolved",
}


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
            cursor.execute(
                """
                WITH scoped AS (
                    SELECT DISTINCT admission.demand_id
                      FROM execution.semantic_pnf_h9_external_admission_v1 AS admission
                     WHERE admission.consumer_ref=%s
                       AND admission.query_ref=%s
                       AND admission.policy_ref=%s
                       AND admission.contract_id IS NOT NULL
                )
                SELECT audit.provenance_state,audit.has_explicit_target_rule,
                       count(*)::BIGINT
                  FROM scoped
                  JOIN execution.semantic_pnf_demand_occurrence_provenance_audit_v1 audit
                    USING(demand_id)
                 GROUP BY audit.provenance_state,audit.has_explicit_target_rule
                 ORDER BY audit.provenance_state,audit.has_explicit_target_rule DESC
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            provenance_summary = [
                {
                    "state": int(state),
                    "state_name": PROVENANCE_STATE.get(int(state), "unknown"),
                    "has_explicit_target_rule": bool(has_rule),
                    "demands": int(count),
                }
                for state, has_rule, count in cursor.fetchall()
            ]

            cursor.execute(
                """
                WITH scoped AS (
                    SELECT DISTINCT admission.demand_id
                      FROM execution.semantic_pnf_h9_external_admission_v1 AS admission
                     WHERE admission.consumer_ref=%s
                       AND admission.query_ref=%s
                       AND admission.policy_ref=%s
                       AND admission.contract_id IS NOT NULL
                )
                SELECT count(*)::BIGINT,
                       count(*) FILTER (
                           WHERE EXISTS (
                               SELECT 1
                                 FROM execution.semantic_pnf_demand_trigger_occurrence_v1 t
                                WHERE t.demand_id=scoped.demand_id
                           )
                       )::BIGINT,
                       count(*) FILTER (
                           WHERE EXISTS (
                               SELECT 1
                                 FROM execution.semantic_pnf_demand_target_occurrence_v1 t
                                WHERE t.demand_id=scoped.demand_id
                           )
                       )::BIGINT,
                       count(*) FILTER (
                           WHERE EXISTS (
                               SELECT 1
                                 FROM execution.semantic_pnf_demand_h9_target_support_v1 t
                                WHERE t.demand_id=scoped.demand_id
                           )
                       )::BIGINT,
                       count(*) FILTER (
                           WHERE EXISTS (
                               SELECT 1
                                 FROM execution.semantic_pnf_demand_parser_entity_occurrence_v1 e
                                WHERE e.demand_id=scoped.demand_id
                           )
                       )::BIGINT
                  FROM scoped
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            row = cursor.fetchone()
            funnel = {
                "contract_matched_demands": int(row[0]),
                "producer_trigger_demands": int(row[1]),
                "producer_target_demands": int(row[2]),
                "h9_exact_target_support_demands": int(row[3]),
                "quality_valid_entity_target_demands": int(row[4]),
            }

            cursor.execute(
                """
                WITH scoped AS (
                    SELECT DISTINCT admission.demand_id
                      FROM execution.semantic_pnf_h9_external_admission_v1 AS admission
                     WHERE admission.consumer_ref=%s
                       AND admission.query_ref=%s
                       AND admission.policy_ref=%s
                       AND admission.contract_id IS NOT NULL
                )
                SELECT demand.demand_id,
                       residual.symbol_text AS residual_type,
                       audit.provenance_state,
                       audit.has_explicit_target_rule,
                       trigger.producer_ref,
                       trigger.token_id,
                       trigger_orth.symbol_text AS trigger_text,
                       trigger_lemma.symbol_text AS trigger_lemma,
                       target.token_id,
                       target_orth.symbol_text AS target_text,
                       target_lemma.symbol_text AS target_lemma,
                       target.object_id,
                       entity_label.symbol_text AS provider_label,
                       entity_type.symbol_text AS provider_entity_type
                  FROM scoped
                  JOIN execution.semantic_pnf_demand AS demand USING(demand_id)
                  JOIN execution.semantic_symbol AS residual
                    ON residual.symbol_id=demand.residual_type_symbol_id
                  JOIN execution.semantic_pnf_demand_occurrence_provenance_audit_v1 AS audit
                    USING(demand_id)
                  LEFT JOIN execution.semantic_pnf_demand_trigger_occurrence_v1 AS trigger
                    USING(demand_id)
                  LEFT JOIN execution.semantic_parser_token AS trigger_token
                    ON trigger_token.token_id=trigger.token_id
                  LEFT JOIN execution.semantic_symbol AS trigger_orth
                    ON trigger_orth.symbol_id=trigger_token.orth_symbol_id
                  LEFT JOIN execution.semantic_symbol AS trigger_lemma
                    ON trigger_lemma.symbol_id=trigger_token.lemma_symbol_id
                  LEFT JOIN execution.semantic_pnf_demand_target_occurrence_v1 AS target
                    USING(demand_id)
                  LEFT JOIN execution.semantic_parser_token AS target_token
                    ON target_token.token_id=target.token_id
                  LEFT JOIN execution.semantic_symbol AS target_orth
                    ON target_orth.symbol_id=target_token.orth_symbol_id
                  LEFT JOIN execution.semantic_symbol AS target_lemma
                    ON target_lemma.symbol_id=target_token.lemma_symbol_id
                  LEFT JOIN execution.semantic_pnf_demand_parser_entity_occurrence_v1 AS entity
                    ON entity.demand_id=demand.demand_id
                   AND entity.object_id=target.object_id
                  LEFT JOIN execution.semantic_symbol AS entity_label
                    ON entity_label.symbol_id=entity.label_symbol_id
                  LEFT JOIN execution.semantic_symbol AS entity_type
                    ON entity_type.symbol_id=entity.entity_type_symbol_id
                 ORDER BY
                       (target.token_id IS NOT NULL) DESC,
                       (entity.entity_id IS NOT NULL) DESC,
                       demand.demand_id
                 LIMIT %s
                """,
                (
                    args.consumer_ref,
                    args.query_ref,
                    args.policy_ref,
                    args.limit,
                ),
            )
            sample = [
                {
                    "demand_id": int(demand_id),
                    "residual_type": str(residual_type),
                    "provenance_state": int(provenance_state),
                    "provenance_state_name": PROVENANCE_STATE.get(
                        int(provenance_state), "unknown"
                    ),
                    "has_explicit_target_rule": bool(has_rule),
                    "producer_ref": str(producer_ref) if producer_ref else None,
                    "trigger_token_id": int(trigger_token_id)
                    if trigger_token_id is not None
                    else None,
                    "trigger_text": str(trigger_text) if trigger_text else None,
                    "trigger_lemma": str(trigger_lemma) if trigger_lemma else None,
                    "target_token_id": int(target_token_id)
                    if target_token_id is not None
                    else None,
                    "target_text": str(target_text) if target_text else None,
                    "target_lemma": str(target_lemma) if target_lemma else None,
                    "target_object_id": int(target_object_id)
                    if target_object_id is not None
                    else None,
                    "provider_label": str(provider_label) if provider_label else None,
                    "provider_entity_type": str(provider_entity_type)
                    if provider_entity_type
                    else None,
                }
                for (
                    demand_id,
                    residual_type,
                    provenance_state,
                    has_rule,
                    producer_ref,
                    trigger_token_id,
                    trigger_text,
                    trigger_lemma,
                    target_token_id,
                    target_text,
                    target_lemma,
                    target_object_id,
                    provider_label,
                    provider_entity_type,
                ) in cursor.fetchall()
            ]
    finally:
        connection.close()

    print(
        json.dumps(
            {
                "funnel": funnel,
                "provenance_summary": provenance_summary,
                "sample": sample,
                "provider_io_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
