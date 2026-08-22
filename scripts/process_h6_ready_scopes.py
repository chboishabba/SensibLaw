#!/usr/bin/env python3
"""Process every H6-ready document scope for one consumer/query/policy.

Execution remains document-scoped semantically; this driver only batches those
independent scopes operationally. It never creates external needs or performs H9
provider I/O.
"""

from __future__ import annotations

import argparse
import json
from time import perf_counter

from src.storage.postgres.consumer_sufficient_runtime_store import (
    ConsumerSufficientRuntimeStore,
)
from src.storage.postgres.spacy_parser_model import connect


def _ready_scopes(
    database_url: str,
    *,
    consumer_ref: str,
    query_ref: str,
    policy_ref: str,
    include_completed: bool,
) -> tuple[tuple[int, int, int], ...]:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT region.run_id,region.document_id,count(DISTINCT work.demand_id)::BIGINT
                  FROM execution.semantic_pnf_consumer_horizon_work_queue AS work
                  JOIN execution.semantic_pnf_demand AS demand USING (demand_id)
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id=demand.source_region_id
                 WHERE work.consumer_ref=%s
                   AND work.query_ref=%s
                   AND work.policy_ref=%s
                   AND work.horizon=6
                   AND (work.work_state=1 OR (%s AND work.work_state=2))
                 GROUP BY region.run_id,region.document_id
                 ORDER BY region.run_id,region.document_id
                """,
                (consumer_ref, query_ref, policy_ref, include_completed),
            )
            return tuple(
                (int(run_id), int(document_id), int(demand_count))
                for run_id, document_id, demand_count in cursor.fetchall()
            )
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--consumer-ref", required=True)
    parser.add_argument("--query-ref", required=True)
    parser.add_argument("--policy-ref", default="")
    parser.add_argument(
        "--reprocess-completed-h6",
        action="store_true",
        help="include rows completed by the pre-110 empty H6 transition",
    )
    args = parser.parse_args()

    scopes = _ready_scopes(
        args.database_url,
        consumer_ref=args.consumer_ref,
        query_ref=args.query_ref,
        policy_ref=args.policy_ref,
        include_completed=args.reprocess_completed_h6,
    )
    store = ConsumerSufficientRuntimeStore(args.database_url)
    rows: list[dict[str, object]] = []
    total_evidence = total_h9 = total_demands = 0
    started_all = perf_counter()
    for run_id, document_id, demand_count in scopes:
        started = perf_counter()
        inserted, h9_residual = store.process_h6_for_consumer(
            run_id=run_id,
            document_id=document_id,
            consumer_ref=args.consumer_ref,
            query_ref=args.query_ref,
            policy_ref=args.policy_ref,
            reprocess_completed=args.reprocess_completed_h6,
        )
        elapsed = perf_counter() - started
        total_evidence += inserted
        total_h9 += h9_residual
        total_demands += demand_count
        rows.append(
            {
                "run_id": run_id,
                "document_id": document_id,
                "h6_input_demands": demand_count,
                "inserted_h6_evidence": inserted,
                "h9_residual_work": h9_residual,
                "elapsed_seconds": elapsed,
                "demands_per_second": (demand_count / elapsed if elapsed else None),
            }
        )

    elapsed_all = perf_counter() - started_all
    print(
        json.dumps(
            {
                "consumer_ref": args.consumer_ref,
                "query_ref": args.query_ref,
                "policy_ref": args.policy_ref,
                "scope_count": len(scopes),
                "h6_input_demands": total_demands,
                "inserted_h6_evidence": total_evidence,
                "h9_residual_work": total_h9,
                "elapsed_seconds": elapsed_all,
                "demands_per_second": (
                    total_demands / elapsed_all if elapsed_all else None
                ),
                "scopes": rows,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
