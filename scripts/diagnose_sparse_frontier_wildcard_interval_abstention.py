"""Read-only ambiguity-preserving bounded wildcard diagnostic.

The wildcard workload is semantically unconstrained and some nearest actor-profile
representatives for the same object disagree in score and producer coordinates.
This probe therefore does not choose a preferred representative.  It collapses
each object's equally-near representatives into a score interval [min,max] and
asks whether the final top-k survivor set is invariant under every admissible
representative choice.

For each demand, objects are first ordered by structural distance.  Distance is
authoritative for recency-class-3 wildcard demands.  At the cutoff distance the
probe compares score intervals.  A candidate is *certainly above* another only
when its minimum score exceeds the other's maximum score at the same distance.
If the kth boundary is not invariant, the demand is marked abstain and no
semantic claim is made.  The implementation is diagnostic only and writes TEMP
state, never execution authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-wildcard-interval-abstention.v0_1"


def _write(stream: Any, payload: dict[str, object]) -> None:
    stream.write(json.dumps(payload, sort_keys=True) + "\n")
    stream.flush()
    print(json.dumps(payload, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(args.database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor, args.output.open("a", encoding="utf-8") as stream:
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, false)",
                (str(args.timeout_ms),),
            )
            cursor.execute("DROP TABLE IF EXISTS wildcard_interval_profile")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_interval_profile ON COMMIT PRESERVE ROWS AS
                SELECT profile.object_id,
                       profile.last_end_char,
                       profile.promotion_score
                         + ln(1 + profile.occurrence_count)::DOUBLE PRECISION
                           AS candidate_score
                  FROM execution.semantic_pnf_actor_profile AS profile
                 WHERE profile.interface_id = %s
                """,
                (args.interface_id,),
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_interval_profile_idx
                    ON wildcard_interval_profile
                       (last_end_char DESC, object_id, candidate_score DESC)
                """
            )
            cursor.execute("ANALYZE wildcard_interval_profile")

            # Collapse only equally-near representatives for the same object.
            # Different distances are not merged because structural distance is
            # already part of the legacy total ranking key.
            cursor.execute("DROP TABLE IF EXISTS wildcard_object_nearest_interval")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_object_nearest_interval ON COMMIT PRESERVE ROWS AS
                WITH nearest AS (
                    SELECT object_id, max(last_end_char) AS nearest_end
                      FROM wildcard_interval_profile
                     GROUP BY object_id
                )
                SELECT profile.object_id,
                       nearest.nearest_end AS last_end_char,
                       min(profile.candidate_score) AS score_min,
                       max(profile.candidate_score) AS score_max,
                       count(*)::BIGINT AS representative_rows
                  FROM wildcard_interval_profile AS profile
                  JOIN nearest USING(object_id)
                 WHERE profile.last_end_char = nearest.nearest_end
                 GROUP BY profile.object_id, nearest.nearest_end
                """
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_object_nearest_interval_idx
                    ON wildcard_object_nearest_interval
                       (last_end_char DESC, score_max DESC, object_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_object_nearest_interval_min_idx
                    ON wildcard_object_nearest_interval
                       (last_end_char DESC, score_min DESC, object_id)
                """
            )
            cursor.execute("ANALYZE wildcard_object_nearest_interval")

            cursor.execute(
                """
                WITH demand AS (
                    SELECT demand_id, source_start_char AS demand_position,
                           max_candidates
                      FROM execution.semantic_pnf_demand
                     WHERE source_interface_id IS NOT NULL
                       AND expected_target_kind = 1
                       AND expected_factor_type_symbol_id IS NULL
                       AND expected_object_kind_symbol_id IS NULL
                       AND role_symbol_id IS NULL
                       AND lexical_symbol_id IS NULL
                       AND recency_class = 3
                       AND state IN (1, 3)
                       AND EXISTS (
                           SELECT 1
                             FROM execution.semantic_pnf_interface_export e
                            WHERE e.interface_id = %s
                              AND e.target_kind = 3
                              AND e.target_id = execution.semantic_pnf_demand.demand_id
                       )
                ),
                optimistic AS (
                    SELECT d.demand_id, p.object_id,
                           row_number() OVER (
                               PARTITION BY d.demand_id
                               ORDER BY p.last_end_char DESC, p.score_max DESC, p.object_id
                           ) AS optimistic_rank
                      FROM demand d
                      CROSS JOIN LATERAL (
                          SELECT object_id, last_end_char, score_max
                            FROM wildcard_object_nearest_interval
                           WHERE last_end_char <= d.demand_position
                           ORDER BY last_end_char DESC, score_max DESC, object_id
                           LIMIT d.max_candidates
                      ) AS p
                ),
                pessimistic AS (
                    SELECT d.demand_id, p.object_id,
                           row_number() OVER (
                               PARTITION BY d.demand_id
                               ORDER BY p.last_end_char DESC, p.score_min DESC, p.object_id
                           ) AS pessimistic_rank
                      FROM demand d
                      CROSS JOIN LATERAL (
                          SELECT object_id, last_end_char, score_min
                            FROM wildcard_object_nearest_interval
                           WHERE last_end_char <= d.demand_position
                           ORDER BY last_end_char DESC, score_min DESC, object_id
                           LIMIT d.max_candidates
                      ) AS p
                ),
                optimistic_set AS (
                    SELECT DISTINCT demand_id, object_id FROM optimistic
                ),
                pessimistic_set AS (
                    SELECT DISTINCT demand_id, object_id FROM pessimistic
                ),
                selected AS (
                    SELECT demand_id, object_id FROM optimistic_set
                    UNION
                    SELECT demand_id, object_id FROM pessimistic_set
                ),
                classified AS (
                    SELECT d.demand_id,
                           d.max_candidates,
                           count(o.object_id)::BIGINT AS optimistic_members,
                           count(p.object_id)::BIGINT AS pessimistic_members,
                           count(*) FILTER (
                               WHERE o.object_id IS NULL OR p.object_id IS NULL
                           )::BIGINT AS unstable_members
                      FROM demand d
                      LEFT JOIN selected s USING (demand_id)
                      LEFT JOIN optimistic_set o
                        ON o.demand_id=s.demand_id AND o.object_id=s.object_id
                      LEFT JOIN pessimistic_set p
                        ON p.demand_id=s.demand_id AND p.object_id=s.object_id
                      GROUP BY d.demand_id, d.max_candidates
                )
                SELECT count(*)::BIGINT AS demands,
                       count(*) FILTER (WHERE unstable_members = 0)::BIGINT
                           AS invariant_demands,
                       count(*) FILTER (WHERE unstable_members > 0)::BIGINT
                           AS abstaining_demands,
                       COALESCE(sum(unstable_members), 0)::BIGINT
                           AS unstable_memberships,
                       COALESCE(max(unstable_members), 0)::BIGINT
                           AS max_unstable_memberships
                  FROM classified
                """,
                (args.interface_id,),
            )
            demands, invariant, abstaining, unstable, max_unstable = cursor.fetchone()

            cursor.execute(
                """
                SELECT count(*)::BIGINT,
                       count(*) FILTER (WHERE representative_rows > 1)::BIGINT,
                       count(*) FILTER (WHERE score_min <> score_max)::BIGINT,
                       COALESCE(max(representative_rows), 0)::BIGINT
                  FROM wildcard_object_nearest_interval
                """
            )
            objects, tied_objects, interval_objects, max_rows = cursor.fetchone()

            receipt = {
                "contract_ref": CONTRACT_REF,
                "interface_id": args.interface_id,
                "semantic_mutation_performed": False,
                "temp_state_only": True,
                "wildcard_demands": int(demands),
                "invariant_demands": int(invariant),
                "abstaining_demands": int(abstaining),
                "unstable_memberships": int(unstable),
                "max_unstable_memberships_per_demand": int(max_unstable),
                "nearest_objects": int(objects),
                "nearest_tied_objects": int(tied_objects),
                "score_interval_objects": int(interval_objects),
                "max_nearest_representative_rows": int(max_rows),
                "authoritative_claim": "only_invariant_top_k_membership",
            }
            _write(stream, receipt)
            return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
