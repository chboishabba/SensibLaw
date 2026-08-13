#!/usr/bin/env python3
"""Report the structural gate between H9 residuals and provider work.

Text is rendered only for inspection at this reporting boundary. Admission itself
is entirely numeric/set-based in PostgreSQL.
"""
from __future__ import annotations

import argparse

from src.storage.postgres.spacy_parser_model import connect


REASONS = {
    1: "admitted_discovery",
    2: "admitted_property",
    3: "admitted_identity",
    10: "no_contract",
    11: "no_source_object",
    12: "no_entity_anchor",
    13: "no_label_anchor",
    14: "no_world_candidate",
    15: "consumer_already_sufficient",
    16: "deductively_resolved",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--consumer-ref", required=True)
    parser.add_argument("--query-ref", required=True)
    parser.add_argument("--policy-ref", default="")
    parser.add_argument("--sample", type=int, default=30)
    args = parser.parse_args()

    connection = connect(args.database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT admission_reason,admitted,count(*)::BIGINT,
                       count(DISTINCT demand_id)::BIGINT
                  FROM execution.semantic_pnf_h9_external_admission_v1
                 WHERE consumer_ref=%s AND query_ref=%s AND policy_ref=%s
                 GROUP BY admission_reason,admitted
                 ORDER BY admitted DESC,admission_reason
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            rows = cursor.fetchall()
            total_demands = 0
            admitted_demands = 0
            print("reason\tadmitted\trows\tdemands")
            for reason, admitted, count_rows, demands in rows:
                label = REASONS.get(int(reason), f"reason_{reason}")
                print(f"{label}\t{bool(admitted)}\t{int(count_rows)}\t{int(demands)}")
                total_demands += int(demands)
                if admitted:
                    admitted_demands += int(demands)

            cursor.execute(
                """
                SELECT count(DISTINCT work.demand_id)::BIGINT
                  FROM execution.semantic_pnf_consumer_horizon_work_queue AS work
                 WHERE work.consumer_ref=%s AND work.query_ref=%s
                   AND work.policy_ref=%s AND work.horizon=9 AND work.work_state=1
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            h9 = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT count(*)::BIGINT,count(DISTINCT need.demand_id)::BIGINT
                  FROM execution.semantic_pnf_consumer_external_need AS need
                 WHERE need.active AND need.consumer_ref=%s AND need.query_ref=%s
                   AND need.policy_ref=%s
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            need_rows, need_demands = (int(value) for value in cursor.fetchone())

            cursor.execute(
                """
                SELECT count(*)::BIGINT
                  FROM execution.semantic_pnf_external_request AS request
                 WHERE request.request_state=3
                   AND EXISTS (
                       SELECT 1
                         FROM execution.semantic_pnf_external_request_active_member_v1 AS member
                        WHERE member.request_id=request.request_id
                          AND member.consumer_ref=%s AND member.query_ref=%s
                          AND member.policy_ref=%s
                   )
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref),
            )
            provider_ready = int(cursor.fetchone()[0])

            print()
            print(f"h9_residual_demands\t{h9}")
            print(f"active_external_need_rows\t{need_rows}")
            print(f"active_external_need_demands\t{need_demands}")
            print(f"provider_ready_requests\t{provider_ready}")
            print(f"admission_invariant_ok\t{bool(_scalar(cursor, 'SELECT execution.verify_numeric_pnf_h9_external_admission()'))}")

            cursor.execute(
                """
                SELECT admission.demand_id,admission.need_kind,admission.anchor_kind,
                       symbol.symbol_text,admission.label_symbol_id,
                       admission.has_world_candidate,
                       admission.has_attached_world_candidate
                  FROM execution.semantic_pnf_h9_external_admission_v1 AS admission
                  JOIN execution.semantic_symbol AS symbol
                    ON symbol.symbol_id=admission.label_symbol_id
                 WHERE admission.consumer_ref=%s AND admission.query_ref=%s
                   AND admission.policy_ref=%s AND admission.admitted
                 ORDER BY admission.demand_id,admission.contract_id
                 LIMIT %s
                """,
                (args.consumer_ref, args.query_ref, args.policy_ref, args.sample),
            )
            sample_rows = cursor.fetchall()
            if sample_rows:
                print("\nadmitted sample (render boundary only):")
                print("demand\tneed\tanchor\tlabel\tsymbol_id\tworld_candidate\tattached")
                for row in sample_rows:
                    print("\t".join(str(value) for value in row))
    finally:
        connection.close()
    return 0


def _scalar(cursor, statement: str):
    cursor.execute(statement)
    return cursor.fetchone()[0]


if __name__ == "__main__":
    raise SystemExit(main())
