"""Read-only full-consumer parity and cost probe for certified wildcard fibres.

This is a pre-production counterfactual.  It recomputes the v0.3 MUST=MAY
routing certificate, sends only certified recency-class-3 mask-0 object demands
to a bounded score-interval realization, and compares those results with the
canonical legacy wildcard survivor computation.

The declared semantic consumer tuple is:

    (membership + source provenance, candidate_count, unique target, outcome)

Floating candidate_score / ordinal are deliberately excluded: migration 086
records them as planner execution observations rather than semantic evidence.
Uncertified MAY\\MUST fibres never enter the bounded parity comparison.

The probe also audits the temporal-shadow hazard: collapsing an object to its
globally latest profile before applying a demand-position predicate can hide an
earlier eligible occurrence.  Any resulting consumer mismatch fails closed.
All database writes are TEMP-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-hybrid-consumer-parity-cost.v0_1"
CERTIFIED_ROUTE = "certified_bounded"
FALLBACK_ROUTE = "legacy_residual_fallback"


def _write(stream: Any, payload: dict[str, object]) -> None:
    stream.write(json.dumps(payload, sort_keys=True) + "\n")
    stream.flush()
    print(json.dumps(payload, sort_keys=True), flush=True)


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-ms", type=int, default=120000)
    parser.add_argument("--mismatch-sample-limit", type=int, default=25)
    args = parser.parse_args()
    if args.mismatch_sample_limit < 0:
        raise ValueError("mismatch-sample-limit must be non-negative")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(args.database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor, args.output.open("a", encoding="utf-8") as stream:
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, false)",
                (str(args.timeout_ms),),
            )
            cursor.execute(
                """
                SELECT region.region_kind
                  FROM execution.semantic_pnf_interface AS interface
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id = interface.region_id
                 WHERE interface.interface_id = %s
                """,
                (args.interface_id,),
            )
            region_row = cursor.fetchone()
            if region_row is None:
                raise ValueError(f"interface {args.interface_id} does not exist")
            region_kind = int(region_row[0])

            setup_started = perf_counter()
            cursor.execute("DROP TABLE IF EXISTS wildcard_parity_profile")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_parity_profile ON COMMIT PRESERVE ROWS AS
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
                CREATE INDEX wildcard_parity_profile_time_idx
                    ON wildcard_parity_profile
                       (last_end_char DESC, candidate_score DESC, object_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_parity_profile_object_time_idx
                    ON wildcard_parity_profile
                       (object_id, last_end_char DESC, candidate_score DESC)
                """
            )
            cursor.execute("ANALYZE wildcard_parity_profile")

            cursor.execute("DROP TABLE IF EXISTS wildcard_parity_global_interval")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_parity_global_interval ON COMMIT PRESERVE ROWS AS
                WITH nearest AS (
                    SELECT object_id, max(last_end_char) AS nearest_end
                      FROM wildcard_parity_profile
                     GROUP BY object_id
                )
                SELECT p.object_id,
                       nearest.nearest_end AS last_end_char,
                       min(p.candidate_score) AS score_min,
                       max(p.candidate_score) AS score_max,
                       count(*)::BIGINT AS representative_rows
                  FROM wildcard_parity_profile AS p
                  JOIN nearest USING (object_id)
                 WHERE p.last_end_char = nearest.nearest_end
                 GROUP BY p.object_id, nearest.nearest_end
                """
            )
            cursor.execute(
                """
                CREATE INDEX wildcard_parity_global_interval_rank_idx
                    ON wildcard_parity_global_interval
                       (last_end_char DESC, score_min DESC, object_id)
                """
            )
            cursor.execute("ANALYZE wildcard_parity_global_interval")
            setup_ms = _elapsed_ms(setup_started)

            decision_started = perf_counter()
            cursor.execute("DROP TABLE IF EXISTS wildcard_parity_decision")
            cursor.execute(
                f"""
                CREATE TEMP TABLE wildcard_parity_decision ON COMMIT PRESERVE ROWS AS
                WITH demand AS MATERIALIZED (
                    SELECT demand.demand_id,
                           demand.source_start_char AS demand_position,
                           demand.max_candidates
                      FROM execution.semantic_pnf_demand AS demand
                     WHERE demand.source_interface_id IS NOT NULL
                       AND demand.expected_target_kind = 1
                       AND demand.expected_factor_type_symbol_id IS NULL
                       AND demand.expected_object_kind_symbol_id IS NULL
                       AND demand.role_symbol_id IS NULL
                       AND demand.lexical_symbol_id IS NULL
                       AND demand.recency_class = 3
                       AND demand.state IN (1, 3)
                       AND demand.max_candidates > 0
                       AND EXISTS (
                           SELECT 1
                             FROM execution.semantic_pnf_interface_export AS e
                            WHERE e.interface_id = %s
                              AND e.target_kind = 3
                              AND e.target_id = demand.demand_id
                       )
                ),
                boundary AS MATERIALIZED (
                    SELECT d.*,
                           kth.last_end_char AS cutoff_end
                      FROM demand AS d
                      LEFT JOIN LATERAL (
                          SELECT p.last_end_char
                            FROM wildcard_parity_global_interval AS p
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
                           CASE WHEN b.cutoff_end IS NULL THEN 0
                                ELSE b.max_candidates - counts.nearer_count
                           END AS remaining_slots
                      FROM boundary AS b
                      CROSS JOIN LATERAL (
                          SELECT count(*)::BIGINT AS eligible_count,
                                 count(*) FILTER (
                                     WHERE b.cutoff_end IS NOT NULL
                                       AND p.last_end_char > b.cutoff_end
                                 )::BIGINT AS nearer_count
                            FROM wildcard_parity_global_interval AS p
                           WHERE p.last_end_char <= b.demand_position
                      ) AS counts
                ),
                cutoff_candidates AS MATERIALIZED (
                    SELECT b.demand_id, b.remaining_slots,
                           p.object_id, p.score_min, p.score_max
                      FROM boundary_counts AS b
                      JOIN wildcard_parity_global_interval AS p
                        ON p.last_end_char = b.cutoff_end
                     WHERE b.eligible_count > b.max_candidates
                ),
                cutoff_envelope AS MATERIALIZED (
                    SELECT c.demand_id, c.object_id, c.remaining_slots,
                           count(x.object_id) FILTER (
                               WHERE x.object_id <> c.object_id
                                 AND (x.score_min > c.score_max
                                      OR (x.score_min = c.score_max
                                          AND x.object_id < c.object_id))
                           )::BIGINT AS certain_outrankers,
                           count(x.object_id) FILTER (
                               WHERE x.object_id <> c.object_id
                                 AND (x.score_max > c.score_min
                                      OR (x.score_max = c.score_min
                                          AND x.object_id < c.object_id))
                           )::BIGINT AS possible_outrankers
                      FROM cutoff_candidates AS c
                      JOIN cutoff_candidates AS x
                        ON x.demand_id = c.demand_id
                     GROUP BY c.demand_id, c.object_id, c.remaining_slots
                ),
                cutoff_classification AS MATERIALIZED (
                    SELECT demand_id, object_id,
                           possible_outrankers < remaining_slots AS must_in,
                           certain_outrankers < remaining_slots AS may_in
                      FROM cutoff_envelope
                ),
                classified AS (
                    SELECT b.demand_id, b.demand_position, b.max_candidates,
                           CASE WHEN b.eligible_count <= b.max_candidates THEN 0
                                ELSE count(*) FILTER (
                                    WHERE c.may_in AND NOT c.must_in
                                )
                           END::BIGINT AS unstable_members
                      FROM boundary_counts AS b
                      LEFT JOIN cutoff_classification AS c
                        ON c.demand_id = b.demand_id
                     GROUP BY b.demand_id, b.demand_position, b.max_candidates,
                              b.eligible_count
                )
                SELECT classified.*,
                       (unstable_members = 0) AS certified,
                       CASE WHEN unstable_members = 0 THEN '{CERTIFIED_ROUTE}'
                            ELSE '{FALLBACK_ROUTE}' END::TEXT AS execution_route
                  FROM classified
                """,
                (args.interface_id,),
            )
            cursor.execute(
                "CREATE UNIQUE INDEX wildcard_parity_decision_pk ON wildcard_parity_decision (demand_id)"
            )
            cursor.execute("ANALYZE wildcard_parity_decision")
            decision_ms = _elapsed_ms(decision_started)

            cursor.execute(
                """
                SELECT count(*)::BIGINT,
                       count(*) FILTER (WHERE certified)::BIGINT,
                       count(*) FILTER (WHERE NOT certified)::BIGINT
                  FROM wildcard_parity_decision
                """
            )
            demand_count, certified_count, fallback_count = map(int, cursor.fetchone())

            # Temporal-shadow audit.  A shadowed pair is an object whose global
            # latest representative is after the demand while an earlier profile
            # representative remains eligible under legacy recency-class-3.
            shadow_started = perf_counter()
            cursor.execute(
                """
                SELECT count(*)::BIGINT
                  FROM wildcard_parity_decision AS d
                 WHERE d.certified
                   AND EXISTS (
                       SELECT 1
                         FROM wildcard_parity_global_interval AS g
                        WHERE g.last_end_char > d.demand_position
                          AND EXISTS (
                              SELECT 1
                                FROM wildcard_parity_profile AS p
                               WHERE p.object_id = g.object_id
                                 AND p.last_end_char <= d.demand_position
                          )
                   )
                """
            )
            shadowed_certified_demands = int(cursor.fetchone()[0])
            shadow_audit_ms = _elapsed_ms(shadow_started)

            bounded_started = perf_counter()
            cursor.execute("DROP TABLE IF EXISTS wildcard_bounded_membership")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_bounded_membership ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id,
                       1::SMALLINT AS target_kind,
                       p.object_id AS target_id,
                       %s::BIGINT AS source_interface_id
                  FROM wildcard_parity_decision AS d
                  CROSS JOIN LATERAL (
                      SELECT g.object_id
                        FROM wildcard_parity_global_interval AS g
                       WHERE g.last_end_char <= d.demand_position
                       ORDER BY g.last_end_char DESC, g.score_min DESC, g.object_id
                       LIMIT d.max_candidates
                  ) AS p
                 WHERE d.certified
                """,
                (args.interface_id,),
            )
            cursor.execute(
                "CREATE UNIQUE INDEX wildcard_bounded_membership_pk ON wildcard_bounded_membership (demand_id, target_kind, target_id)"
            )
            cursor.execute("ANALYZE wildcard_bounded_membership")
            bounded_membership_ms = _elapsed_ms(bounded_started)

            legacy_started = perf_counter()
            cursor.execute("DROP TABLE IF EXISTS wildcard_legacy_membership")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_legacy_membership ON COMMIT PRESERVE ROWS AS
                WITH raw_candidate AS MATERIALIZED (
                    SELECT d.demand_id,
                           1::SMALLINT AS target_kind,
                           p.object_id AS target_id,
                           %s::BIGINT AS source_interface_id,
                           d.demand_position - p.last_end_char AS structural_distance,
                           0::BIGINT AS index_rank,
                           p.candidate_score
                      FROM wildcard_parity_decision AS d
                      JOIN wildcard_parity_profile AS p
                        ON p.last_end_char <= d.demand_position
                     WHERE d.certified
                ),
                deduplicated AS MATERIALIZED (
                    SELECT candidate.*,
                           row_number() OVER (
                               PARTITION BY candidate.demand_id,
                                            candidate.target_kind,
                                            candidate.target_id
                               ORDER BY candidate.structural_distance,
                                        candidate.index_rank,
                                        candidate.source_interface_id
                           ) AS target_occurrence
                      FROM raw_candidate AS candidate
                ),
                ranked AS (
                    SELECT candidate.*,
                           row_number() OVER (
                               PARTITION BY candidate.demand_id
                               ORDER BY candidate.structural_distance,
                                        candidate.candidate_score DESC,
                                        candidate.index_rank,
                                        candidate.target_id
                           ) - 1 AS candidate_ordinal
                      FROM deduplicated AS candidate
                     WHERE candidate.target_occurrence = 1
                )
                SELECT ranked.demand_id,
                       ranked.target_kind,
                       ranked.target_id,
                       ranked.source_interface_id
                  FROM ranked
                  JOIN wildcard_parity_decision AS d USING (demand_id)
                 WHERE ranked.candidate_ordinal < d.max_candidates
                """,
                (args.interface_id,),
            )
            cursor.execute(
                "CREATE UNIQUE INDEX wildcard_legacy_membership_pk ON wildcard_legacy_membership (demand_id, target_kind, target_id)"
            )
            cursor.execute("ANALYZE wildcard_legacy_membership")
            legacy_membership_ms = _elapsed_ms(legacy_started)

            # Membership + source provenance parity is the primitive semantic
            # comparison.  Count, unique target and outcome are derived below.
            parity_started = perf_counter()
            cursor.execute(
                """
                WITH bounded_minus_legacy AS (
                    SELECT * FROM wildcard_bounded_membership
                    EXCEPT ALL
                    SELECT * FROM wildcard_legacy_membership
                ),
                legacy_minus_bounded AS (
                    SELECT * FROM wildcard_legacy_membership
                    EXCEPT ALL
                    SELECT * FROM wildcard_bounded_membership
                )
                SELECT
                    (SELECT count(*) FROM bounded_minus_legacy)::BIGINT,
                    (SELECT count(*) FROM legacy_minus_bounded)::BIGINT
                """
            )
            bounded_minus_legacy, legacy_minus_bounded = map(int, cursor.fetchone())

            cursor.execute("DROP TABLE IF EXISTS wildcard_bounded_consumer_tuple")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_bounded_consumer_tuple ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id,
                       count(m.target_id)::BIGINT AS candidate_count,
                       CASE WHEN count(m.target_id) = 1 THEN min(m.target_id) END AS unique_target_id,
                       CASE
                           WHEN count(m.target_id) = 1 THEN 2
                           WHEN count(m.target_id) = 0 AND %s = 10 THEN 7
                           WHEN count(m.target_id) = 0 THEN 1
                           ELSE 3
                       END::SMALLINT AS outcome_state
                  FROM wildcard_parity_decision AS d
                  LEFT JOIN wildcard_bounded_membership AS m USING (demand_id)
                 WHERE d.certified
                 GROUP BY d.demand_id
                """,
                (region_kind,),
            )
            cursor.execute("DROP TABLE IF EXISTS wildcard_legacy_consumer_tuple")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_legacy_consumer_tuple ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id,
                       count(m.target_id)::BIGINT AS candidate_count,
                       CASE WHEN count(m.target_id) = 1 THEN min(m.target_id) END AS unique_target_id,
                       CASE
                           WHEN count(m.target_id) = 1 THEN 2
                           WHEN count(m.target_id) = 0 AND %s = 10 THEN 7
                           WHEN count(m.target_id) = 0 THEN 1
                           ELSE 3
                       END::SMALLINT AS outcome_state
                  FROM wildcard_parity_decision AS d
                  LEFT JOIN wildcard_legacy_membership AS m USING (demand_id)
                 WHERE d.certified
                 GROUP BY d.demand_id
                """,
                (region_kind,),
            )
            cursor.execute(
                """
                WITH bounded_minus_legacy AS (
                    SELECT * FROM wildcard_bounded_consumer_tuple
                    EXCEPT ALL
                    SELECT * FROM wildcard_legacy_consumer_tuple
                ),
                legacy_minus_bounded AS (
                    SELECT * FROM wildcard_legacy_consumer_tuple
                    EXCEPT ALL
                    SELECT * FROM wildcard_bounded_consumer_tuple
                )
                SELECT
                    (SELECT count(*) FROM bounded_minus_legacy)::BIGINT,
                    (SELECT count(*) FROM legacy_minus_bounded)::BIGINT
                """
            )
            tuple_bounded_minus_legacy, tuple_legacy_minus_bounded = map(
                int, cursor.fetchone()
            )
            parity_ms = _elapsed_ms(parity_started)

            mismatch_samples: list[dict[str, int | str]] = []
            if args.mismatch_sample_limit and (
                bounded_minus_legacy or legacy_minus_bounded
            ):
                cursor.execute(
                    """
                    WITH mismatch AS (
                        SELECT 'bounded_only'::TEXT AS side, *
                          FROM (
                              SELECT * FROM wildcard_bounded_membership
                              EXCEPT ALL
                              SELECT * FROM wildcard_legacy_membership
                          ) AS q
                        UNION ALL
                        SELECT 'legacy_only'::TEXT AS side, *
                          FROM (
                              SELECT * FROM wildcard_legacy_membership
                              EXCEPT ALL
                              SELECT * FROM wildcard_bounded_membership
                          ) AS q
                    )
                    SELECT side, demand_id, target_kind, target_id, source_interface_id
                      FROM mismatch
                     ORDER BY demand_id, side, target_id
                     LIMIT %s
                    """,
                    (args.mismatch_sample_limit,),
                )
                mismatch_samples = [
                    {
                        "side": str(row[0]),
                        "demand_id": int(row[1]),
                        "target_kind": int(row[2]),
                        "target_id": int(row[3]),
                        "source_interface_id": int(row[4]),
                    }
                    for row in cursor.fetchall()
                ]

            cursor.execute("SELECT count(*)::BIGINT FROM wildcard_bounded_membership")
            bounded_rows = int(cursor.fetchone()[0])
            cursor.execute("SELECT count(*)::BIGINT FROM wildcard_legacy_membership")
            legacy_rows = int(cursor.fetchone()[0])

            membership_parity = (
                bounded_minus_legacy == 0 and legacy_minus_bounded == 0
            )
            tuple_parity = (
                tuple_bounded_minus_legacy == 0
                and tuple_legacy_minus_bounded == 0
            )
            full_consumer_tuple_parity = membership_parity and tuple_parity
            fallback_untouched = fallback_count == demand_count - certified_count

            receipt = {
                "contract_ref": CONTRACT_REF,
                "interface_id": args.interface_id,
                "semantic_mutation_performed": False,
                "temp_state_only": True,
                "wildcard_demands": demand_count,
                "certified_bounded_demands": certified_count,
                "legacy_residual_fallback_demands": fallback_count,
                "fallback_partition_untouched": fallback_untouched,
                "shadowed_certified_demands": shadowed_certified_demands,
                "bounded_membership_rows": bounded_rows,
                "legacy_membership_rows": legacy_rows,
                "bounded_minus_legacy_memberships": bounded_minus_legacy,
                "legacy_minus_bounded_memberships": legacy_minus_bounded,
                "tuple_bounded_minus_legacy": tuple_bounded_minus_legacy,
                "tuple_legacy_minus_bounded": tuple_legacy_minus_bounded,
                "membership_provenance_parity": membership_parity,
                "derived_consumer_tuple_parity": tuple_parity,
                "full_consumer_tuple_parity": full_consumer_tuple_parity,
                "setup_ms": setup_ms,
                "decision_certificate_ms": decision_ms,
                "temporal_shadow_audit_ms": shadow_audit_ms,
                "bounded_membership_ms": bounded_membership_ms,
                "legacy_membership_recompute_ms": legacy_membership_ms,
                "parity_derivation_ms": parity_ms,
                "bounded_path_observed_ms": setup_ms + decision_ms + bounded_membership_ms,
                "legacy_comparison_observed_ms": legacy_membership_ms,
                "consumer_observation": (
                    "membership_source_provenance_candidate_count_unique_target_outcome"
                ),
                "candidate_score_authority": "execution_metadata_not_semantic_evidence",
                "temporal_eligibility_rule": "representative_must_be_selected_after_demand_position_filter",
                "authoritative_claim": (
                    "promotion_blocked_until_full_consumer_tuple_parity_and_cost_win"
                ),
                "mismatch_samples": mismatch_samples,
            }
            _write(stream, receipt)
            return 0 if full_consumer_tuple_parity and fallback_untouched else 2
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
