#!/usr/bin/env python3
"""Report the consumer-indexed H3/H6/H9 semantic funnel.

This report deliberately separates:

- execution queue state;
- neutral/signed evidence;
- consumer sufficiency;
- deductive resolution;
- unresolved residual work; and
- explicit external needs.

H9-ready is therefore never reported as synonymous with Wikidata/provider work.
JSON is presentation output only; PostgreSQL remains semantic authority.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from src.storage.postgres.consumer_sufficient_runtime_store import ConsumerSufficientRuntimeStore
from src.storage.postgres.spacy_parser_model import connect


def _scalar(cursor, sql: str, params: tuple[object, ...]) -> int:
    cursor.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("expected scalar query result")
    return int(row[0])


def _scope_clause() -> str:
    return """
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
     WHERE region.run_id=%s AND region.document_id=%s
    """


def collect_report(
    database_url: str,
    *,
    run_id: int,
    document_id: int,
    consumer_ref: str,
    query_ref: str,
    policy_ref: str,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "scope": {
            "run_id": run_id,
            "document_id": document_id,
            "consumer_ref": consumer_ref,
            "query_ref": query_ref,
            "policy_ref": policy_ref,
        }
    }
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            params = (run_id, document_id)
            report["initial_demand_count"] = _scalar(
                cursor,
                "SELECT count(*) " + _scope_clause(),
                params,
            )
            cursor.execute(
                """
                SELECT demand.state,count(*)::BIGINT
                  FROM execution.semantic_pnf_demand AS demand
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id=demand.source_region_id
                 WHERE region.run_id=%s AND region.document_id=%s
                 GROUP BY demand.state ORDER BY demand.state
                """,
                params,
            )
            report["demand_state"] = {
                str(int(state)): int(count) for state, count in cursor.fetchall()
            }

            cursor.execute(
                """
                SELECT count(*)::BIGINT,count(DISTINCT candidate.demand_id)::BIGINT
                  FROM execution.semantic_pnf_demand_candidate AS candidate
                  JOIN execution.semantic_pnf_demand AS demand USING (demand_id)
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id=demand.source_region_id
                 WHERE region.run_id=%s AND region.document_id=%s
                """,
                params,
            )
            candidate_rows, candidate_demands = cursor.fetchone()
            report["candidates"] = {
                "rows": int(candidate_rows),
                "distinct_demands": int(candidate_demands),
            }

            cursor.execute(
                """
                SELECT classified.horizon,classified.evidence_class,
                       classified.evidence_polarity,
                       count(*)::BIGINT,count(DISTINCT classified.demand_id)::BIGINT
                  FROM execution.semantic_pnf_candidate_evidence_classification_v1 AS classified
                  JOIN execution.semantic_pnf_demand AS demand USING (demand_id)
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id=demand.source_region_id
                 WHERE region.run_id=%s AND region.document_id=%s
                 GROUP BY classified.horizon,classified.evidence_class,
                          classified.evidence_polarity
                 ORDER BY classified.horizon,classified.evidence_class,
                          classified.evidence_polarity
                """,
                params,
            )
            report["evidence"] = [
                {
                    "horizon": int(horizon),
                    "class": int(evidence_class),
                    "polarity": int(polarity),
                    "rows": int(rows),
                    "distinct_demands": int(demands),
                }
                for horizon, evidence_class, polarity, rows, demands in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT work.horizon,work.work_state,count(*)::BIGINT
                  FROM execution.semantic_pnf_consumer_horizon_work_queue AS work
                  JOIN execution.semantic_pnf_demand AS demand USING (demand_id)
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id=demand.source_region_id
                 WHERE work.consumer_ref=%s AND work.query_ref=%s AND work.policy_ref=%s
                   AND region.run_id=%s AND region.document_id=%s
                 GROUP BY work.horizon,work.work_state
                 ORDER BY work.horizon,work.work_state
                """,
                (consumer_ref, query_ref, policy_ref, run_id, document_id),
            )
            report["work_queue"] = [
                {"horizon": int(horizon), "work_state": int(state), "rows": int(rows)}
                for horizon, state, rows in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT outcome.horizon,outcome.outcome_state,count(*)::BIGINT,
                       count(*) FILTER (WHERE outcome.residual_required)::BIGINT,
                       sum(outcome.evidence_count)::BIGINT,
                       sum(outcome.nonneutral_evidence_count)::BIGINT,
                       sum(outcome.preferred_candidate_count)::BIGINT
                  FROM execution.semantic_pnf_consumer_horizon_outcome AS outcome
                  JOIN execution.semantic_pnf_demand AS demand USING (demand_id)
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id=demand.source_region_id
                 WHERE outcome.consumer_ref=%s AND outcome.query_ref=%s
                   AND outcome.policy_ref=%s
                   AND region.run_id=%s AND region.document_id=%s
                 GROUP BY outcome.horizon,outcome.outcome_state
                 ORDER BY outcome.horizon,outcome.outcome_state
                """,
                (consumer_ref, query_ref, policy_ref, run_id, document_id),
            )
            report["semantic_outcomes"] = [
                {
                    "horizon": int(horizon),
                    "outcome_state": int(outcome_state),
                    "demands": int(rows),
                    "residual_demands": int(residual_rows),
                    "evidence_rows_observed": int(evidence_rows or 0),
                    "nonneutral_evidence_rows": int(nonneutral_rows or 0),
                    "preferred_candidate_rows": int(preferred_rows or 0),
                }
                for (
                    horizon,
                    outcome_state,
                    rows,
                    residual_rows,
                    evidence_rows,
                    nonneutral_rows,
                    preferred_rows,
                ) in cursor.fetchall()
            ]

            report["explicit_external_needs"] = _scalar(
                cursor,
                """
                SELECT count(*)
                  FROM execution.semantic_pnf_consumer_external_need AS need
                  JOIN execution.semantic_pnf_demand AS demand USING (demand_id)
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id=demand.source_region_id
                 WHERE need.consumer_ref=%s AND need.query_ref=%s AND need.policy_ref=%s
                   AND need.active
                   AND region.run_id=%s AND region.document_id=%s
                """,
                (consumer_ref, query_ref, policy_ref, run_id, document_id),
            )
            report["provider_requests"] = _scalar(
                cursor,
                """
                SELECT count(DISTINCT request.request_id)
                  FROM execution.semantic_pnf_external_request AS request
                  JOIN execution.semantic_pnf_external_request_member AS member
                    ON member.request_id=request.request_id
                  JOIN execution.semantic_pnf_demand AS demand
                    ON demand.demand_id=member.demand_id
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id=demand.source_region_id
                 WHERE member.consumer_ref=%s AND member.query_ref=%s
                   AND member.policy_ref=%s
                   AND region.run_id=%s AND region.document_id=%s
                """,
                (consumer_ref, query_ref, policy_ref, run_id, document_id),
            )
    finally:
        connection.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--document-id", required=True, type=int)
    parser.add_argument("--consumer-ref", required=True)
    parser.add_argument("--query-ref", required=True)
    parser.add_argument("--policy-ref", default="")
    parser.add_argument(
        "--process-h6",
        action="store_true",
        help="run the numeric H6 producer before reporting",
    )
    parser.add_argument(
        "--reprocess-completed-h6",
        action="store_true",
        help="include H6 rows completed by the pre-110 empty transition",
    )
    args = parser.parse_args()

    h6_result: dict[str, int] | None = None
    if args.process_h6:
        store = ConsumerSufficientRuntimeStore(args.database_url)
        inserted, h9_residual = store.process_h6_for_consumer(
            run_id=args.run_id,
            document_id=args.document_id,
            consumer_ref=args.consumer_ref,
            query_ref=args.query_ref,
            policy_ref=args.policy_ref,
            reprocess_completed=args.reprocess_completed_h6,
        )
        h6_result = {
            "inserted_h6_evidence": inserted,
            "h9_residual_work": h9_residual,
        }

    report = collect_report(
        args.database_url,
        run_id=args.run_id,
        document_id=args.document_id,
        consumer_ref=args.consumer_ref,
        query_ref=args.query_ref,
        policy_ref=args.policy_ref,
    )
    if h6_result is not None:
        report["h6_execution"] = h6_result
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
