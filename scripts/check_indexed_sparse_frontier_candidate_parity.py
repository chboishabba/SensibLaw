from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.indexed-sparse-frontier-candidate-parity.v0_1"

_LEGACY_OBJECT_CANDIDATE_SQL = """
WITH parent_demand AS (
    SELECT demand.*,
           COALESCE(demand.source_start_char, source_region.end_char)
               AS demand_position,
           source_region.start_char AS source_region_start,
           source_region.end_char AS source_region_end,
           source_region.parent_region_id AS source_parent_region_id
      FROM execution.semantic_pnf_interface_export AS demand_export
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = demand_export.target_id
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = demand.source_region_id
     WHERE demand_export.interface_id = %s
       AND demand_export.target_kind = 3
       AND demand.state IN (1, 3)
),
object_candidate AS (
    SELECT demand.demand_id,
           1::SMALLINT AS target_kind,
           profile.object_id AS target_id,
           %s::BIGINT AS source_interface_id,
           abs(demand.demand_position - profile.last_end_char)
               AS structural_distance,
           0::BIGINT AS index_rank,
           profile.promotion_score
               + ln(1 + profile.occurrence_count)::DOUBLE PRECISION
               AS candidate_score
      FROM parent_demand AS demand
      JOIN execution.semantic_pnf_actor_profile AS profile
        ON profile.interface_id = %s
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id = profile.object_id
     WHERE demand.expected_target_kind = 1
       AND (
           demand.expected_object_kind_symbol_id IS NULL
           OR demand.expected_object_kind_symbol_id
              = profile.object_kind_symbol_id
       )
       AND (
           demand.role_symbol_id IS NULL
           OR demand.role_symbol_id = profile.role_symbol_id
       )
       AND (
           demand.expected_factor_type_symbol_id IS NULL
           OR demand.expected_factor_type_symbol_id
              = profile.factor_type_symbol_id
       )
       AND (
           demand.lexical_symbol_id IS NULL
           OR demand.lexical_symbol_id = object.head_symbol_id
           OR demand.lexical_symbol_id = profile.predicate_symbol_id
       )
       AND CASE demand.recency_class
           WHEN 1 THEN
               profile.first_start_char >= demand.source_region_start
               AND profile.last_end_char <= demand.source_region_end
           WHEN 2 THEN profile.last_end_char <= demand.demand_position
           WHEN 3 THEN profile.last_end_char <= demand.demand_position
           WHEN 4 THEN TRUE
           WHEN 5 THEN TRUE
           ELSE FALSE
       END
)
SELECT demand_id,
       target_kind,
       target_id,
       source_interface_id,
       structural_distance,
       index_rank,
       candidate_score
  FROM object_candidate
"""

_INDEXED_OBJECT_CANDIDATE_SQL = """
SELECT demand_id,
       target_kind,
       target_id,
       source_interface_id,
       structural_distance,
       index_rank,
       candidate_score
  FROM execution.indexed_numeric_pnf_object_candidate_rows(%s)
"""


def _count(cursor: Any, sql: str, params: tuple[object, ...]) -> int:
    cursor.execute(f"SELECT count(*) FROM ({sql}) AS rows", params)
    return int(cursor.fetchone()[0])


def _difference_count(
    cursor: Any,
    *,
    left_sql: str,
    left_params: tuple[object, ...],
    right_sql: str,
    right_params: tuple[object, ...],
) -> int:
    # EXCEPT ALL is deliberate: parity includes row multiplicity, not merely the
    # set of target identities.  Candidate dedup/ranking occurs later.
    cursor.execute(
        f"""
        SELECT count(*)
          FROM (
              ({left_sql})
              EXCEPT ALL
              ({right_sql})
          ) AS difference
        """,
        left_params + right_params,
    )
    return int(cursor.fetchone()[0])


def candidate_parity_receipt(database_url: str, interface_id: int) -> dict[str, object]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT region.region_id,
                           region.region_kind,
                           interface.interface_cardinality,
                           interface.unresolved_count
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
                region_id, region_kind, interface_cardinality, unresolved_count = (
                    int(value) for value in row
                )

                legacy_params = (interface_id, interface_id, interface_id)
                indexed_params = (interface_id,)
                legacy_count = _count(
                    cursor, _LEGACY_OBJECT_CANDIDATE_SQL, legacy_params
                )
                indexed_count = _count(
                    cursor, _INDEXED_OBJECT_CANDIDATE_SQL, indexed_params
                )
                legacy_only = _difference_count(
                    cursor,
                    left_sql=_LEGACY_OBJECT_CANDIDATE_SQL,
                    left_params=legacy_params,
                    right_sql=_INDEXED_OBJECT_CANDIDATE_SQL,
                    right_params=indexed_params,
                )
                indexed_only = _difference_count(
                    cursor,
                    left_sql=_INDEXED_OBJECT_CANDIDATE_SQL,
                    left_params=indexed_params,
                    right_sql=_LEGACY_OBJECT_CANDIDATE_SQL,
                    right_params=legacy_params,
                )

                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_interface_export AS export
                      JOIN execution.semantic_pnf_demand AS demand
                        ON demand.demand_id = export.target_id
                     WHERE export.interface_id = %s
                       AND export.target_kind = 3
                       AND demand.state IN (1, 3)
                       AND demand.expected_target_kind = 1
                    """,
                    (interface_id,),
                )
                object_demand_count = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_interface_export AS export
                      JOIN execution.semantic_pnf_demand AS demand
                        ON demand.demand_id = export.target_id
                     WHERE export.interface_id = %s
                       AND export.target_kind = 3
                       AND demand.state IN (1, 3)
                       AND demand.expected_target_kind = 1
                       AND demand.expected_factor_type_symbol_id IS NULL
                       AND demand.expected_object_kind_symbol_id IS NULL
                       AND demand.lexical_symbol_id IS NULL
                       AND demand.role_symbol_id IS NULL
                    """,
                    (interface_id,),
                )
                unconstrained_object_demand_count = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_actor_profile
                     WHERE interface_id = %s
                    """,
                    (interface_id,),
                )
                actor_profile_count = int(cursor.fetchone()[0])

        exact = legacy_only == 0 and indexed_only == 0 and legacy_count == indexed_count
        return {
            "contract_ref": CONTRACT_REF,
            "interface_id": interface_id,
            "region_id": region_id,
            "region_kind": region_kind,
            "interface_cardinality": interface_cardinality,
            "unresolved_count": unresolved_count,
            "object_demand_count": object_demand_count,
            "unconstrained_object_demand_count": unconstrained_object_demand_count,
            "actor_profile_count": actor_profile_count,
            "legacy_candidate_rows": legacy_count,
            "indexed_candidate_rows": indexed_count,
            "legacy_only_rows": legacy_only,
            "indexed_only_rows": indexed_only,
            "exact_candidate_row_parity": exact,
            "semantics": (
                "EXCEPT ALL compares the complete pre-dedup object-candidate row relation, "
                "including multiplicity, structural distance, index rank, and score"
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

    receipt = candidate_parity_receipt(args.database_url, args.interface_id)
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if receipt["exact_candidate_row_parity"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
