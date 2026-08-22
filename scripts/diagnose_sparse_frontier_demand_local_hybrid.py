"""Read-only demand-local exact wildcard hybrid diagnostic.

This probe replaces the earlier globally-collapsed wildcard interval observer.
The exact legacy recency-class-3 order is respected:

    raw actor-profile rows
      -> apply demand-local temporal eligibility
      -> choose the nearest eligible position per object
      -> retain every equal-position score representative as [min,max]
      -> compute MUST/MAY top-k membership
      -> route MUST=MAY fibres to a bounded witness realization
      -> preserve every remaining fibre as legacy residual fallback

The crucial ordering law is that temporal restriction precedes object quotienting.
A global latest-object representative is not an authority surface for a demand
that lies before that representative.

No production relation is mutated.  All carriers are TEMP tables and every
receipt field is diagnostic evidence only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-demand-local-hybrid.v0_4"
CERTIFIED_ROUTE = "certified_bounded"
FALLBACK_ROUTE = "legacy_residual_fallback"


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000.0


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
    parser.add_argument("--residual-sample-limit", type=int, default=25)
    parser.add_argument("--persisted-crosscheck-sample-limit", type=int, default=250)
    args = parser.parse_args()
    if args.residual_sample_limit < 0 or args.persisted_crosscheck_sample_limit < 0:
        raise ValueError("sample limits must be non-negative")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(args.database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor, args.output.open("a", encoding="utf-8") as stream:
            cursor.execute("SELECT set_config('statement_timeout', %s, false)", (str(args.timeout_ms),))

            setup_started = perf_counter()
            cursor.execute("DROP TABLE IF EXISTS wildcard_local_position_segment")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_local_position_segment ON COMMIT PRESERVE ROWS AS
                WITH grouped AS (
                    SELECT profile.object_id,
                           profile.last_end_char,
                           min(
                               profile.promotion_score
                               + ln(1 + profile.occurrence_count)::DOUBLE PRECISION
                           ) AS score_min,
                           max(
                               profile.promotion_score
                               + ln(1 + profile.occurrence_count)::DOUBLE PRECISION
                           ) AS score_max,
                           count(*)::BIGINT AS representative_rows
                      FROM execution.semantic_pnf_actor_profile AS profile
                     WHERE profile.interface_id = %s
                     GROUP BY profile.object_id, profile.last_end_char
                )
                SELECT grouped.*,
                       lead(grouped.last_end_char) OVER (
                           PARTITION BY grouped.object_id
                           ORDER BY grouped.last_end_char
                       ) AS next_end_char
                  FROM grouped
                """,
                (args.interface_id,),
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX wildcard_local_segment_pk
                    ON wildcard_local_position_segment (object_id, last_end_char)
                """
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_local_segment_active_idx
                    ON wildcard_local_position_segment
                       (last_end_char DESC, next_end_char, object_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_local_segment_object_idx
                    ON wildcard_local_position_segment
                       (object_id, last_end_char DESC, next_end_char)
                """
            )
            cursor.execute("ANALYZE wildcard_local_position_segment")

            cursor.execute("DROP TABLE IF EXISTS wildcard_local_demand")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_local_demand ON COMMIT PRESERVE ROWS AS
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
                """,
                (args.interface_id,),
            )
            cursor.execute(
                "CREATE UNIQUE INDEX wildcard_local_demand_pk ON wildcard_local_demand (demand_id)"
            )
            cursor.execute(
                "CREATE INDEX wildcard_local_demand_position_idx ON wildcard_local_demand (demand_position, demand_id)"
            )
            cursor.execute("ANALYZE wildcard_local_demand")
            setup_ms = _elapsed_ms(setup_started)

            # Carrier integrity is independent of any demand x object product.
            cursor.execute(
                """
                SELECT
                    (SELECT count(*)::BIGINT
                       FROM execution.semantic_pnf_actor_profile
                      WHERE interface_id = %s) AS raw_rows,
                    count(*)::BIGINT AS position_segments,
                    COALESCE(sum(representative_rows), 0)::BIGINT AS represented_rows,
                    count(*) FILTER (WHERE representative_rows > 1)::BIGINT AS tied_segments,
                    count(*) FILTER (WHERE score_min <> score_max)::BIGINT AS interval_segments,
                    COALESCE(max(representative_rows), 0)::BIGINT AS max_representatives
                  FROM wildcard_local_position_segment
                """,
                (args.interface_id,),
            )
            (
                raw_profile_rows,
                position_segments,
                represented_profile_rows,
                tied_segments,
                interval_segments,
                max_representatives,
            ) = map(int, cursor.fetchone())
            carrier_row_conservation = raw_profile_rows == represented_profile_rows

            decision_started = perf_counter()
            cursor.execute("DROP TABLE IF EXISTS wildcard_local_decision")
            cursor.execute(
                f"""
                CREATE TEMP TABLE wildcard_local_decision ON COMMIT PRESERVE ROWS AS
                WITH boundary AS MATERIALIZED (
                    SELECT d.*,
                           kth.last_end_char AS cutoff_end,
                           (overflow.object_id IS NOT NULL) AS has_overflow
                      FROM wildcard_local_demand AS d
                      LEFT JOIN LATERAL (
                          SELECT s.last_end_char
                            FROM wildcard_local_position_segment AS s
                           WHERE s.last_end_char <= d.demand_position
                             AND (s.next_end_char IS NULL
                                  OR d.demand_position < s.next_end_char)
                           ORDER BY s.last_end_char DESC, s.object_id
                           OFFSET (d.max_candidates - 1)
                           LIMIT 1
                      ) AS kth ON TRUE
                      LEFT JOIN LATERAL (
                          SELECT s.object_id
                            FROM wildcard_local_position_segment AS s
                           WHERE s.last_end_char <= d.demand_position
                             AND (s.next_end_char IS NULL
                                  OR d.demand_position < s.next_end_char)
                           ORDER BY s.last_end_char DESC, s.object_id
                           OFFSET d.max_candidates
                           LIMIT 1
                      ) AS overflow ON TRUE
                ),
                boundary_count AS MATERIALIZED (
                    SELECT b.*,
                           CASE
                               WHEN b.cutoff_end IS NULL THEN 0
                               ELSE COALESCE(nearer.nearer_count, 0)
                           END::BIGINT AS nearer_count
                      FROM boundary AS b
                      LEFT JOIN LATERAL (
                          SELECT count(*)::BIGINT AS nearer_count
                            FROM wildcard_local_position_segment AS s
                           WHERE b.cutoff_end IS NOT NULL
                             AND s.last_end_char <= b.demand_position
                             AND (s.next_end_char IS NULL
                                  OR b.demand_position < s.next_end_char)
                             AND s.last_end_char > b.cutoff_end
                      ) AS nearer ON TRUE
                ),
                cutoff_candidate AS MATERIALIZED (
                    SELECT b.demand_id,
                           (b.max_candidates - b.nearer_count)::BIGINT
                               AS remaining_slots,
                           s.object_id,
                           s.score_min,
                           s.score_max
                      FROM boundary_count AS b
                      JOIN wildcard_local_position_segment AS s
                        ON s.last_end_char = b.cutoff_end
                       AND (s.next_end_char IS NULL
                            OR b.demand_position < s.next_end_char)
                     WHERE b.has_overflow
                ),
                cutoff_envelope AS MATERIALIZED (
                    SELECT c.demand_id,
                           c.object_id,
                           c.remaining_slots,
                           count(x.object_id) FILTER (
                               WHERE x.object_id <> c.object_id
                                 AND (
                                     x.score_min > c.score_max
                                     OR (x.score_min = c.score_max
                                         AND x.object_id < c.object_id)
                                 )
                           )::BIGINT AS certain_outrankers,
                           count(x.object_id) FILTER (
                               WHERE x.object_id <> c.object_id
                                 AND (
                                     x.score_max > c.score_min
                                     OR (x.score_max = c.score_min
                                         AND x.object_id < c.object_id)
                                 )
                           )::BIGINT AS possible_outrankers
                      FROM cutoff_candidate AS c
                      JOIN cutoff_candidate AS x
                        ON x.demand_id = c.demand_id
                     GROUP BY c.demand_id, c.object_id, c.remaining_slots
                ),
                classified AS MATERIALIZED (
                    SELECT e.demand_id,
                           e.object_id,
                           (e.possible_outrankers < e.remaining_slots) AS must_in,
                           (e.certain_outrankers < e.remaining_slots) AS may_in
                      FROM cutoff_envelope AS e
                ),
                residual AS MATERIALIZED (
                    SELECT demand_id,
                           count(*) FILTER (WHERE may_in AND NOT must_in)::BIGINT
                               AS unstable_memberships
                      FROM classified
                     GROUP BY demand_id
                )
                SELECT b.demand_id,
                       b.demand_position,
                       b.max_candidates,
                       b.cutoff_end,
                       b.has_overflow,
                       b.nearer_count,
                       COALESCE(r.unstable_memberships, 0)::BIGINT
                           AS unstable_memberships,
                       (COALESCE(r.unstable_memberships, 0) = 0) AS certified,
                       CASE
                           WHEN COALESCE(r.unstable_memberships, 0) = 0
                               THEN '{CERTIFIED_ROUTE}'
                           ELSE '{FALLBACK_ROUTE}'
                       END::TEXT AS execution_route
                  FROM boundary_count AS b
                  LEFT JOIN residual AS r USING (demand_id)
                """
            )
            cursor.execute(
                "CREATE UNIQUE INDEX wildcard_local_decision_pk ON wildcard_local_decision (demand_id)"
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_local_decision_route_idx
                    ON wildcard_local_decision (execution_route, demand_position, demand_id)
                """
            )
            cursor.execute("ANALYZE wildcard_local_decision")
            decision_ms = _elapsed_ms(decision_started)

            cursor.execute(
                """
                SELECT count(*)::BIGINT,
                       count(*) FILTER (WHERE certified)::BIGINT,
                       count(*) FILTER (WHERE NOT certified)::BIGINT,
                       COALESCE(sum(unstable_memberships), 0)::BIGINT,
                       COALESCE(max(unstable_memberships), 0)::BIGINT
                  FROM wildcard_local_decision
                """
            )
            (
                demand_count,
                certified_count,
                fallback_count,
                unstable_memberships,
                max_unstable,
            ) = map(int, cursor.fetchone())
            partition_exact = certified_count + fallback_count == demand_count

            # score_min is an attained representative in every active interval.
            # On MUST=MAY fibres every admissible representative realization has
            # the same membership, so this is only a bounded witness realization,
            # not a promotion of score_min to semantic authority.
            bounded_started = perf_counter()
            cursor.execute("DROP TABLE IF EXISTS wildcard_local_bounded_membership")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_local_bounded_membership ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id,
                       1::SMALLINT AS target_kind,
                       picked.object_id AS target_id,
                       %s::BIGINT AS source_interface_id
                  FROM wildcard_local_decision AS d
                  CROSS JOIN LATERAL (
                      SELECT s.object_id
                        FROM wildcard_local_position_segment AS s
                       WHERE s.last_end_char <= d.demand_position
                         AND (s.next_end_char IS NULL
                              OR d.demand_position < s.next_end_char)
                       ORDER BY s.last_end_char DESC, s.score_min DESC, s.object_id
                       LIMIT d.max_candidates
                  ) AS picked
                 WHERE d.certified
                """,
                (args.interface_id,),
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX wildcard_local_bounded_membership_pk
                    ON wildcard_local_bounded_membership
                       (demand_id, target_kind, target_id)
                """
            )
            cursor.execute("ANALYZE wildcard_local_bounded_membership")
            bounded_ms = _elapsed_ms(bounded_started)

            cursor.execute(
                """
                SELECT count(*)::BIGINT,
                       count(DISTINCT demand_id)::BIGINT
                  FROM wildcard_local_bounded_membership
                """
            )
            bounded_memberships, bounded_demands_with_membership = map(int, cursor.fetchone())

            # Optional persisted-state cross-check.  It is explicitly NOT an
            # authority gate because demand_candidate may reflect an older planner
            # execution; it is useful only as an independent anomaly signal.
            persisted_mismatch_count = 0
            persisted_sampled_demands = 0
            if args.persisted_crosscheck_sample_limit:
                cursor.execute(
                    """
                    WITH sample AS (
                        SELECT demand_id
                          FROM wildcard_local_decision
                         WHERE certified
                         ORDER BY demand_id
                         LIMIT %s
                    ),
                    bounded AS (
                        SELECT m.demand_id, m.target_kind, m.target_id
                          FROM wildcard_local_bounded_membership AS m
                          JOIN sample USING (demand_id)
                    ),
                    persisted AS (
                        SELECT c.demand_id, c.target_kind, c.target_id
                          FROM execution.semantic_pnf_demand_candidate AS c
                          JOIN sample USING (demand_id)
                    ),
                    diff AS (
                        (SELECT * FROM bounded EXCEPT ALL SELECT * FROM persisted)
                        UNION ALL
                        (SELECT * FROM persisted EXCEPT ALL SELECT * FROM bounded)
                    )
                    SELECT (SELECT count(*) FROM sample)::BIGINT,
                           count(*)::BIGINT
                      FROM diff
                    """,
                    (args.persisted_crosscheck_sample_limit,),
                )
                persisted_sampled_demands, persisted_mismatch_count = map(int, cursor.fetchone())

            residual_samples: list[dict[str, int | None]] = []
            if args.residual_sample_limit:
                cursor.execute(
                    """
                    SELECT demand_id,
                           demand_position,
                           max_candidates,
                           cutoff_end,
                           nearer_count,
                           unstable_memberships
                      FROM wildcard_local_decision
                     WHERE NOT certified
                     ORDER BY unstable_memberships DESC, demand_id
                     LIMIT %s
                    """,
                    (args.residual_sample_limit,),
                )
                residual_samples = [
                    {
                        "demand_id": int(row[0]),
                        "demand_position": int(row[1]),
                        "max_candidates": int(row[2]),
                        "cutoff_end": None if row[3] is None else int(row[3]),
                        "nearer_count": int(row[4]),
                        "unstable_memberships": int(row[5]),
                    }
                    for row in cursor.fetchall()
                ]

            receipt = {
                "contract_ref": CONTRACT_REF,
                "interface_id": args.interface_id,
                "semantic_mutation_performed": False,
                "temp_state_only": True,
                "temporal_operator_order": "restrict_demand_then_quotient_object_position",
                "demand_position_rule": "coalesce_source_start_char_source_region_end_char",
                "position_segment_rule": "object_id_last_end_char_score_interval_with_next_end_validity",
                "carrier_row_conservation": carrier_row_conservation,
                "raw_profile_rows": raw_profile_rows,
                "represented_profile_rows": represented_profile_rows,
                "position_segments": position_segments,
                "tied_position_segments": tied_segments,
                "score_interval_segments": interval_segments,
                "max_representatives_per_position_segment": max_representatives,
                "wildcard_demands": demand_count,
                "certified_bounded_demands": certified_count,
                "legacy_residual_fallback_demands": fallback_count,
                "certified_fraction": certified_count / demand_count if demand_count else 1.0,
                "fallback_fraction": fallback_count / demand_count if demand_count else 0.0,
                "unstable_memberships": unstable_memberships,
                "max_unstable_memberships_per_demand": max_unstable,
                "hybrid_partition_exact": partition_exact,
                "bounded_memberships": bounded_memberships,
                "bounded_demands_with_membership": bounded_demands_with_membership,
                "bounded_witness_score": "score_min_attained_but_not_semantic_authority",
                "consumer_authority": "membership_count_unique_target_outcome_membership_provenance",
                "legacy_cartesian_oracle_required": False,
                "persisted_crosscheck_authority": "non_authoritative_anomaly_signal_only",
                "persisted_crosscheck_sampled_demands": persisted_sampled_demands,
                "persisted_crosscheck_membership_mismatches": persisted_mismatch_count,
                "setup_ms": setup_ms,
                "demand_local_certificate_ms": decision_ms,
                "bounded_membership_ms": bounded_ms,
                "bounded_path_observed_ms": setup_ms + decision_ms + bounded_ms,
                "residual_samples": residual_samples,
                "authoritative_claim": (
                    "demand_local_interval_certificate_only; production_promotion_still_requires_"
                    "live_receipt_and_independent_runtime_parity"
                ),
            }
            _write(stream, receipt)

            valid = carrier_row_conservation and partition_exact
            return 0 if valid else 2
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
