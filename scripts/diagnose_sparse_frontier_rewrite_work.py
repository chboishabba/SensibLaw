from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-rewrite-work-diagnostic.v0_1"

_PARENT_DEMAND = """
SELECT demand.demand_id
  FROM execution.semantic_pnf_interface_export AS demand_export
  JOIN execution.semantic_pnf_demand AS demand
    ON demand.demand_id = demand_export.target_id
 WHERE demand_export.interface_id = %s
   AND demand_export.target_kind = 3
   AND demand.state IN (1, 3)
"""

_CURRENT_COUNTS = f"""
WITH parent_demand AS MATERIALIZED ({_PARENT_DEMAND})
SELECT parent_demand.demand_id,
       count(candidate.demand_id)::SMALLINT AS candidate_count
  FROM parent_demand
  LEFT JOIN execution.semantic_pnf_demand_candidate AS candidate
    ON candidate.demand_id = parent_demand.demand_id
 GROUP BY parent_demand.demand_id
"""

_DESIRED_RESOLUTION = """
SELECT demand.demand_id,
       %s::BIGINT AS interface_id,
       CASE
           WHEN demand.state = 2 THEN 2
           WHEN demand.candidate_count = 0 AND %s::SMALLINT = 10 THEN 7
           WHEN demand.candidate_count = 0 THEN 1
           ELSE 3
       END::SMALLINT AS outcome_state,
       demand.candidate_count,
       demand.resolved_target_kind,
       demand.resolved_target_id,
       CASE WHEN demand.state = 2 THEN %s::BIGINT ELSE NULL END AS witness_interface_id
  FROM execution.semantic_pnf_interface_export AS demand_export
  JOIN execution.semantic_pnf_demand AS demand
    ON demand.demand_id = demand_export.target_id
 WHERE demand_export.interface_id = %s
   AND demand_export.target_kind = 3
"""

_EXISTING_RESOLUTION = """
SELECT resolution.demand_id,
       resolution.interface_id,
       resolution.outcome_state,
       resolution.candidate_count,
       resolution.selected_target_kind,
       resolution.selected_target_id,
       resolution.witness_interface_id
  FROM execution.semantic_pnf_frontier_resolution AS resolution
 WHERE resolution.interface_id = %s
"""


def _count(cursor: Any, sql: str, params: tuple[object, ...]) -> int:
    cursor.execute(f"SELECT count(*) FROM ({sql}) AS measured", params)
    return int(cursor.fetchone()[0])


def _difference_count(
    cursor: Any,
    *,
    left_sql: str,
    left_params: tuple[object, ...],
    right_sql: str,
    right_params: tuple[object, ...],
) -> int:
    cursor.execute(
        f"""
        SELECT count(*) FROM (
            ({left_sql}) EXCEPT ALL ({right_sql})
        ) AS difference
        """,
        left_params + right_params,
    )
    return int(cursor.fetchone()[0])


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def rewrite_work_receipt(database_url: str, interface_id: int) -> dict[str, object]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    SELECT region.region_kind
                      FROM execution.semantic_pnf_interface AS interface
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = interface.region_id
                     WHERE interface.interface_id = %s
                    """,
                    (interface_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(f"PNF interface does not exist: {interface_id}")
                region_kind = int(row[0])

                candidate_count_update_rows = _count(
                    cursor, _CURRENT_COUNTS, (interface_id,)
                )
                cursor.execute(
                    f"""
                    SELECT count(*)
                      FROM ({_CURRENT_COUNTS}) AS counts
                      JOIN execution.semantic_pnf_demand AS demand
                        ON demand.demand_id = counts.demand_id
                     WHERE demand.candidate_count IS DISTINCT FROM counts.candidate_count
                        OR demand.state IS DISTINCT FROM CASE
                            WHEN demand.state = 3 AND counts.candidate_count > 0 THEN 1
                            ELSE demand.state
                        END
                    """,
                    (interface_id,),
                )
                candidate_count_semantic_delta_rows = int(cursor.fetchone()[0])

                # The second canonical UPDATE resolves only currently unresolved
                # demands having exactly one persistent candidate.
                cursor.execute(
                    f"""
                    WITH parent_demand AS MATERIALIZED ({_PARENT_DEMAND}),
                    unique_candidate AS (
                        SELECT candidate.demand_id,
                               min(candidate.target_kind) AS target_kind,
                               min(candidate.target_id) AS target_id,
                               count(*) AS candidate_count
                          FROM execution.semantic_pnf_demand_candidate AS candidate
                          JOIN parent_demand
                            ON parent_demand.demand_id = candidate.demand_id
                         GROUP BY candidate.demand_id
                        HAVING count(*) = 1
                    )
                    SELECT count(*) AS update_rows,
                           count(*) FILTER (
                               WHERE demand.state IS DISTINCT FROM 2
                                  OR demand.resolved_target_kind IS DISTINCT FROM unique_candidate.target_kind
                                  OR demand.resolved_target_id IS DISTINCT FROM unique_candidate.target_id
                                  OR demand.candidate_count IS DISTINCT FROM 1
                           ) AS semantic_delta_rows
                      FROM unique_candidate
                      JOIN execution.semantic_pnf_demand AS demand
                        ON demand.demand_id = unique_candidate.demand_id
                     WHERE demand.state IN (1, 3)
                    """,
                    (interface_id,),
                )
                unique_update_rows, unique_semantic_delta_rows = (
                    int(value) for value in cursor.fetchone()
                )

                existing_params = (interface_id,)
                desired_params = (
                    interface_id,
                    region_kind,
                    interface_id,
                    interface_id,
                )
                existing_resolution_rows = _count(
                    cursor, _EXISTING_RESOLUTION, existing_params
                )
                desired_resolution_rows = _count(
                    cursor, _DESIRED_RESOLUTION, desired_params
                )
                existing_only = _difference_count(
                    cursor,
                    left_sql=_EXISTING_RESOLUTION,
                    left_params=existing_params,
                    right_sql=_DESIRED_RESOLUTION,
                    right_params=desired_params,
                )
                desired_only = _difference_count(
                    cursor,
                    left_sql=_DESIRED_RESOLUTION,
                    left_params=desired_params,
                    right_sql=_EXISTING_RESOLUTION,
                    right_params=existing_params,
                )
                resolution_semantic_delta_rows = existing_only + desired_only
                resolution_rewrite_rows = existing_resolution_rows + desired_resolution_rows

        demand_update_rewrite_rows = candidate_count_update_rows + unique_update_rows
        demand_update_semantic_delta_rows = (
            candidate_count_semantic_delta_rows + unique_semantic_delta_rows
        )
        total_rewrite_rows = demand_update_rewrite_rows + resolution_rewrite_rows
        total_semantic_delta_rows = (
            demand_update_semantic_delta_rows + resolution_semantic_delta_rows
        )
        return {
            "contract_ref": CONTRACT_REF,
            "interface_id": interface_id,
            "region_kind": region_kind,
            "demand_updates": {
                "candidate_count_update_rows": candidate_count_update_rows,
                "candidate_count_semantic_delta_rows": candidate_count_semantic_delta_rows,
                "unique_resolution_update_rows": unique_update_rows,
                "unique_resolution_semantic_delta_rows": unique_semantic_delta_rows,
                "canonical_update_rows": demand_update_rewrite_rows,
                "semantic_delta_rows": demand_update_semantic_delta_rows,
            },
            "frontier_resolution": {
                "existing_rows": existing_resolution_rows,
                "desired_rows": desired_resolution_rows,
                "canonical_delete_insert_rows": resolution_rewrite_rows,
                "existing_only_rows": existing_only,
                "desired_only_rows": desired_only,
                "semantic_delta_rows": resolution_semantic_delta_rows,
            },
            "totals_without_candidate_table": {
                "canonical_rewrite_rows": total_rewrite_rows,
                "semantic_delta_rows": total_semantic_delta_rows,
                "beta_rewrite_rows_per_semantic_delta": _ratio(
                    total_rewrite_rows, total_semantic_delta_rows
                ),
                "beta_rewrite_is_unbounded_for_zero_delta": (
                    total_semantic_delta_rows == 0 and total_rewrite_rows > 0
                ),
            },
            "semantics": (
                "read-only no-input-change rewrite probe; semantic deltas use current persistent candidate/demand authority and EXCEPT ALL resolution comparison; "
                "created_at is excluded because it is physical churn, not resolution meaning"
            ),
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = rewrite_work_receipt(args.database_url, args.interface_id)
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
