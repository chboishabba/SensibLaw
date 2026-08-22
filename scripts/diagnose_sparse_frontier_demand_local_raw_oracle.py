"""Independent bounded raw-profile oracle for demand-local wildcard segments.

This probe validates the temporal carrier transformation itself.  For a bounded
sample of wildcard demands it computes the same explicit witness realization two
ways:

1. segment witness: restrict demand position against per-object validity segments,
   then rank active [score_min, score_max] groups using the attained score_min;
2. raw witness: directly scan actor-profile rows eligible at the demand position,
   choose each object's nearest position and then the minimum score at that exact
   position, and rank the resulting objects.

The two computations must have identical top-k membership.  This is not a proof
that an uncertified interval fibre has invariant membership; it is an independent
check that the segment carrier faithfully implements restriction-before-quotient.
All writes are TEMP-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-demand-local-raw-oracle.v0_1"


def _write(stream: Any, payload: dict[str, object]) -> None:
    stream.write(json.dumps(payload, sort_keys=True) + "\n")
    stream.flush()
    print(json.dumps(payload, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sample-limit", type=int, default=250)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--mismatch-sample-limit", type=int, default=25)
    args = parser.parse_args()
    if args.sample_limit <= 0:
        raise ValueError("sample-limit must be positive")
    if args.mismatch_sample_limit < 0:
        raise ValueError("mismatch-sample-limit must be non-negative")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(args.database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor, args.output.open("a", encoding="utf-8") as stream:
            cursor.execute("SELECT set_config('statement_timeout', %s, false)", (str(args.timeout_ms),))
            started = perf_counter()

            cursor.execute("DROP TABLE IF EXISTS wildcard_oracle_raw_profile")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_oracle_raw_profile ON COMMIT PRESERVE ROWS AS
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
                CREATE INDEX wildcard_oracle_raw_object_time_idx
                    ON wildcard_oracle_raw_profile
                       (object_id, last_end_char DESC, candidate_score ASC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_oracle_raw_time_idx
                    ON wildcard_oracle_raw_profile
                       (last_end_char DESC, candidate_score DESC, object_id)
                """
            )
            cursor.execute("ANALYZE wildcard_oracle_raw_profile")

            cursor.execute("DROP TABLE IF EXISTS wildcard_oracle_segment")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_oracle_segment ON COMMIT PRESERVE ROWS AS
                WITH grouped AS (
                    SELECT object_id,
                           last_end_char,
                           min(candidate_score) AS score_min,
                           max(candidate_score) AS score_max,
                           count(*)::BIGINT AS representative_rows
                      FROM wildcard_oracle_raw_profile
                     GROUP BY object_id, last_end_char
                )
                SELECT grouped.*,
                       lead(last_end_char) OVER (
                           PARTITION BY object_id ORDER BY last_end_char
                       ) AS next_end_char
                  FROM grouped
                """
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX wildcard_oracle_segment_pk
                    ON wildcard_oracle_segment (object_id, last_end_char)
                """
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_oracle_segment_active_idx
                    ON wildcard_oracle_segment
                       (last_end_char DESC, next_end_char, object_id)
                """
            )
            cursor.execute("ANALYZE wildcard_oracle_segment")

            cursor.execute("DROP TABLE IF EXISTS wildcard_oracle_demand")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_oracle_demand ON COMMIT PRESERVE ROWS AS
                SELECT demand.demand_id,
                       COALESCE(demand.source_start_char, source_region.end_char)
                           AS demand_position,
                       demand.max_candidates
                  FROM execution.semantic_pnf_interface_export AS demand_export
                  JOIN execution.semantic_pnf_demand AS demand
                    ON demand.demand_id = demand_export.target_id
                  JOIN execution.semantic_pnf_region AS source_region
                    ON source_region.region_id = demand.source_region_id
                 WHERE demand_export.interface_id = %s
                   AND demand_export.target_kind = 3
                   AND demand.state IN (1, 3)
                   AND demand.expected_target_kind = 1
                   AND demand.expected_factor_type_symbol_id IS NULL
                   AND demand.expected_object_kind_symbol_id IS NULL
                   AND demand.role_symbol_id IS NULL
                   AND demand.lexical_symbol_id IS NULL
                   AND demand.recency_class = 3
                   AND demand.max_candidates > 0
                 ORDER BY demand.demand_id
                 LIMIT %s
                """,
                (args.interface_id, args.sample_limit),
            )
            cursor.execute(
                "CREATE UNIQUE INDEX wildcard_oracle_demand_pk ON wildcard_oracle_demand (demand_id)"
            )
            cursor.execute("ANALYZE wildcard_oracle_demand")

            cursor.execute("DROP TABLE IF EXISTS wildcard_oracle_segment_membership")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_oracle_segment_membership ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id, picked.object_id
                  FROM wildcard_oracle_demand AS d
                  CROSS JOIN LATERAL (
                      SELECT s.object_id
                        FROM wildcard_oracle_segment AS s
                       WHERE s.last_end_char <= d.demand_position
                         AND (s.next_end_char IS NULL
                              OR d.demand_position < s.next_end_char)
                       ORDER BY s.last_end_char DESC, s.score_min DESC, s.object_id
                       LIMIT d.max_candidates
                  ) AS picked
                """
            )
            cursor.execute(
                "CREATE UNIQUE INDEX wildcard_oracle_segment_membership_pk ON wildcard_oracle_segment_membership (demand_id, object_id)"
            )

            cursor.execute("DROP TABLE IF EXISTS wildcard_oracle_raw_membership")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_oracle_raw_membership ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id, picked.object_id
                  FROM wildcard_oracle_demand AS d
                  CROSS JOIN LATERAL (
                      SELECT nearest.object_id
                        FROM (
                            SELECT DISTINCT ON (p.object_id)
                                   p.object_id,
                                   p.last_end_char,
                                   p.candidate_score
                              FROM wildcard_oracle_raw_profile AS p
                             WHERE p.last_end_char <= d.demand_position
                             ORDER BY p.object_id,
                                      p.last_end_char DESC,
                                      p.candidate_score ASC
                        ) AS nearest
                       ORDER BY nearest.last_end_char DESC,
                                nearest.candidate_score DESC,
                                nearest.object_id
                       LIMIT d.max_candidates
                  ) AS picked
                """
            )
            cursor.execute(
                "CREATE UNIQUE INDEX wildcard_oracle_raw_membership_pk ON wildcard_oracle_raw_membership (demand_id, object_id)"
            )

            cursor.execute(
                """
                WITH segment_minus_raw AS (
                    SELECT * FROM wildcard_oracle_segment_membership
                    EXCEPT ALL
                    SELECT * FROM wildcard_oracle_raw_membership
                ),
                raw_minus_segment AS (
                    SELECT * FROM wildcard_oracle_raw_membership
                    EXCEPT ALL
                    SELECT * FROM wildcard_oracle_segment_membership
                )
                SELECT (SELECT count(*) FROM wildcard_oracle_demand)::BIGINT,
                       (SELECT count(*) FROM segment_minus_raw)::BIGINT,
                       (SELECT count(*) FROM raw_minus_segment)::BIGINT
                """
            )
            sampled_demands, segment_minus_raw, raw_minus_segment = map(int, cursor.fetchone())

            mismatches: list[dict[str, int | str]] = []
            if args.mismatch_sample_limit and (segment_minus_raw or raw_minus_segment):
                cursor.execute(
                    """
                    WITH diff AS (
                        SELECT 'segment_minus_raw'::TEXT AS direction, *
                          FROM (
                              SELECT * FROM wildcard_oracle_segment_membership
                              EXCEPT ALL
                              SELECT * FROM wildcard_oracle_raw_membership
                          ) a
                        UNION ALL
                        SELECT 'raw_minus_segment'::TEXT AS direction, *
                          FROM (
                              SELECT * FROM wildcard_oracle_raw_membership
                              EXCEPT ALL
                              SELECT * FROM wildcard_oracle_segment_membership
                          ) b
                    )
                    SELECT direction, demand_id, object_id
                      FROM diff
                     ORDER BY demand_id, direction, object_id
                     LIMIT %s
                    """,
                    (args.mismatch_sample_limit,),
                )
                mismatches = [
                    {
                        "direction": str(row[0]),
                        "demand_id": int(row[1]),
                        "object_id": int(row[2]),
                    }
                    for row in cursor.fetchall()
                ]

            elapsed_ms = (perf_counter() - started) * 1000.0
            parity = segment_minus_raw == 0 and raw_minus_segment == 0
            receipt = {
                "contract_ref": CONTRACT_REF,
                "interface_id": args.interface_id,
                "semantic_mutation_performed": False,
                "temp_state_only": True,
                "sampled_demands": sampled_demands,
                "witness_realization": "minimum_score_at_nearest_eligible_object_position",
                "segment_minus_raw_memberships": segment_minus_raw,
                "raw_minus_segment_memberships": raw_minus_segment,
                "sample_membership_parity": parity,
                "temporal_operator_order": "restrict_demand_then_quotient_object_position",
                "mismatch_samples": mismatches,
                "elapsed_ms": elapsed_ms,
                "authoritative_claim": (
                    "sampled_independent_validation_of_temporal_segment_transform_only"
                ),
            }
            _write(stream, receipt)
            return 0 if parity else 2
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
