"""Read-only ambiguity-preserving bounded wildcard diagnostic.

The wildcard workload is semantically unconstrained and some equally-near
actor-profile representatives for one semantic object disagree in score and
producer coordinates.  This probe therefore never chooses a preferred row.
It collapses equally-near representatives to [score_min, score_max] and computes
an exact MUST/MAY top-k membership envelope over every independently admissible
score realization.

Distance is the primary ranking coordinate for the observed recency-class-3
workload, so ambiguity can affect membership only in the kth structural-distance
fibre.  Objects strictly nearer than that cutoff are MUST members; objects
strictly farther are excluded.  Inside the cutoff fibre, candidate c is:

* MUST-in when fewer than r competitors can possibly outrank c, where r is the
  number of slots remaining after all strictly-nearer objects are admitted;
* MAY-in when fewer than r competitors certainly outrank c.

For descending score with object-id tie break, competitor x certainly outranks c
iff x.score_min > c.score_max, or equality holds and x.object_id < c.object_id.
It can possibly outrank c iff x.score_max > c.score_min, with the same deterministic
tie break.  Independent score intervals make these bounds jointly realizable.
Thus MUST = MAY is an all-realizations certificate, unlike merely comparing the
all-minimum and all-maximum endpoint rankings.

The implementation is diagnostic only, writes TEMP state only, and never mutates
execution authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-wildcard-interval-abstention.v0_2"


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
                CREATE INDEX wildcard_object_nearest_interval_cutoff_idx
                    ON wildcard_object_nearest_interval
                       (last_end_char DESC, object_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_object_nearest_interval_max_idx
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

            # Exact MUST/MAY envelope.  Only the kth distance fibre needs score
            # interval reasoning; all nearer/farther membership is fixed by the
            # primary structural-distance coordinate.
            cursor.execute(
                """
                WITH demand AS MATERIALIZED (
                    SELECT demand_id,
                           source_start_char AS demand_position,
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
                       AND max_candidates > 0
                       AND EXISTS (
                           SELECT 1
                             FROM execution.semantic_pnf_interface_export e
                            WHERE e.interface_id = %s
                              AND e.target_kind = 3
                              AND e.target_id = execution.semantic_pnf_demand.demand_id
                       )
                ),
                boundary AS MATERIALIZED (
                    SELECT d.demand_id,
                           d.demand_position,
                           d.max_candidates,
                           kth.last_end_char AS cutoff_end
                      FROM demand AS d
                      LEFT JOIN LATERAL (
                          SELECT p.last_end_char
                            FROM wildcard_object_nearest_interval AS p
                           WHERE p.last_end_char <= d.demand_position
                           ORDER BY p.last_end_char DESC, p.object_id
                           OFFSET (d.max_candidates - 1)
                           LIMIT 1
                      ) AS kth ON TRUE
                ),
                boundary_counts AS MATERIALIZED (
                    SELECT b.*,
                           counts.eligible_count,
                           counts.nearer_count,
                           CASE
                               WHEN b.cutoff_end IS NULL THEN 0
                               ELSE b.max_candidates - counts.nearer_count
                           END AS remaining_slots
                      FROM boundary AS b
                      CROSS JOIN LATERAL (
                          SELECT count(*)::BIGINT AS eligible_count,
                                 count(*) FILTER (
                                     WHERE b.cutoff_end IS NOT NULL
                                       AND p.last_end_char > b.cutoff_end
                                 )::BIGINT AS nearer_count
                            FROM wildcard_object_nearest_interval AS p
                           WHERE p.last_end_char <= b.demand_position
                      ) AS counts
                ),
                cutoff_candidates AS MATERIALIZED (
                    SELECT b.demand_id,
                           b.remaining_slots,
                           p.object_id,
                           p.score_min,
                           p.score_max
                      FROM boundary_counts AS b
                      JOIN wildcard_object_nearest_interval AS p
                        ON p.last_end_char = b.cutoff_end
                     WHERE b.eligible_count > b.max_candidates
                ),
                cutoff_envelope AS MATERIALIZED (
                    SELECT c.demand_id,
                           c.object_id,
                           c.remaining_slots,
                           count(x.object_id) FILTER (
                               WHERE x.object_id <> c.object_id
                                 AND (
                                     x.score_min > c.score_max
                                     OR (
                                         x.score_min = c.score_max
                                         AND x.object_id < c.object_id
                                     )
                                 )
                           )::BIGINT AS certain_outrankers,
                           count(x.object_id) FILTER (
                               WHERE x.object_id <> c.object_id
                                 AND (
                                     x.score_max > c.score_min
                                     OR (
                                         x.score_max = c.score_min
                                         AND x.object_id < c.object_id
                                     )
                                 )
                           )::BIGINT AS possible_outrankers
                      FROM cutoff_candidates AS c
                      JOIN cutoff_candidates AS x
                        ON x.demand_id = c.demand_id
                     GROUP BY c.demand_id,
                              c.object_id,
                              c.remaining_slots
                ),
                cutoff_classification AS MATERIALIZED (
                    SELECT demand_id,
                           object_id,
                           possible_outrankers < remaining_slots AS must_in,
                           certain_outrankers < remaining_slots AS may_in
                      FROM cutoff_envelope
                ),
                classified AS (
                    SELECT b.demand_id,
                           b.max_candidates,
                           b.eligible_count,
                           b.nearer_count,
                           b.remaining_slots,
                           CASE
                               WHEN b.eligible_count <= b.max_candidates
                                   THEN b.eligible_count
                               ELSE b.nearer_count
                                   + count(*) FILTER (WHERE c.must_in)
                           END::BIGINT AS must_members,
                           CASE
                               WHEN b.eligible_count <= b.max_candidates
                                   THEN b.eligible_count
                               ELSE b.nearer_count
                                   + count(*) FILTER (WHERE c.may_in)
                           END::BIGINT AS may_members,
                           CASE
                               WHEN b.eligible_count <= b.max_candidates THEN 0
                               ELSE count(*) FILTER (
                                   WHERE c.may_in AND NOT c.must_in
                               )
                           END::BIGINT AS unstable_members
                      FROM boundary_counts AS b
                      LEFT JOIN cutoff_classification AS c
                        ON c.demand_id = b.demand_id
                     GROUP BY b.demand_id,
                              b.max_candidates,
                              b.eligible_count,
                              b.nearer_count,
                              b.remaining_slots
                )
                SELECT count(*)::BIGINT AS demands,
                       count(*) FILTER (WHERE unstable_members = 0)::BIGINT
                           AS invariant_demands,
                       count(*) FILTER (WHERE unstable_members > 0)::BIGINT
                           AS abstaining_demands,
                       COALESCE(sum(unstable_members), 0)::BIGINT
                           AS unstable_memberships,
                       COALESCE(max(unstable_members), 0)::BIGINT
                           AS max_unstable_memberships,
                       COALESCE(sum(must_members), 0)::BIGINT
                           AS must_memberships,
                       COALESCE(sum(may_members), 0)::BIGINT
                           AS may_memberships
                  FROM classified
                """,
                (args.interface_id,),
            )
            (
                demands,
                invariant,
                abstaining,
                unstable,
                max_unstable,
                must_memberships,
                may_memberships,
            ) = cursor.fetchone()

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
                "must_memberships": int(must_memberships),
                "may_memberships": int(may_memberships),
                "nearest_objects": int(objects),
                "nearest_tied_objects": int(tied_objects),
                "score_interval_objects": int(interval_objects),
                "max_nearest_representative_rows": int(max_rows),
                "membership_envelope": "must_subset_realized_subset_may",
                "authoritative_claim": "all_realizations_only_when_must_equals_may",
            }
            _write(stream, receipt)
            return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
