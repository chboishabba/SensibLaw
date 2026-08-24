"""Disposable production-shaped benchmark for the exact wildcard hybrid.

The workload identity is the ordered pair

    (demand_interface_id, profile_interface_id)

because the demand/export interface and the actor-profile provenance interface
are distinct coordinates.  This benchmark never mutates persisted execution
state: all candidate surfaces are TEMP tables.

Hybrid execution:
  1. build the demand-local temporal segment carrier;
  2. compute the MUST/MAY certificate for every wildcard demand;
  3. certified demands use the bounded segment realization;
  4. uncertified demands use the historical raw-profile ranking unchanged;
  5. union both routes and compare against the current persisted legacy output.

The optional legacy baseline recomputes the historical wildcard survivor relation
for all demands.  A timeout is recorded as unknown; it is never interpreted as a
speedup measurement.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from time import perf_counter
from typing import Any

from src.storage.postgres.spacy_parser_model import connect

CONTRACT_REF = "sensiblaw.sparse-frontier-demand-local-hybrid-benchmark.v0_1"


def elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000.0


def emit(stream: Any, payload: dict[str, object]) -> None:
    text = json.dumps(payload, sort_keys=True)
    stream.write(text + "\n")
    stream.flush()
    print(text, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--demand-interface-id", required=True, type=int)
    ap.add_argument("--profile-interface-id", required=True, type=int)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--timeout-ms", type=int, default=180000)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--skip-legacy-baseline", action="store_true")
    args = ap.parse_args()
    if args.repeats <= 0:
        raise ValueError("--repeats must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    con = connect(args.database_url)
    con.autocommit = True
    try:
        with con.cursor() as cur, args.output.open("a", encoding="utf-8") as out:
            cur.execute("SELECT set_config('statement_timeout', %s, false)", (str(args.timeout_ms),))

            # Pin workload identity and freshness before any timing claim.
            cur.execute(
                """
                SELECT i.graph_revision, receipt.graph_revision, region.region_kind
                  FROM execution.semantic_pnf_interface AS i
                  JOIN execution.semantic_pnf_region AS region USING(region_id)
                  LEFT JOIN execution.semantic_pnf_frontier_reduction_receipt AS receipt
                    ON receipt.interface_id = i.interface_id
                 WHERE i.interface_id = %s
                """,
                (args.demand_interface_id,),
            )
            identity = cur.fetchone()
            if identity is None:
                raise ValueError(f"demand interface {args.demand_interface_id} missing")
            interface_revision = int(identity[0])
            receipt_revision = None if identity[1] is None else int(identity[1])
            region_kind = int(identity[2])
            persisted_oracle_current = receipt_revision == interface_revision
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM execution.semantic_pnf_interface WHERE interface_id=%s)",
                (args.profile_interface_id,),
            )
            if not bool(cur.fetchone()[0]):
                raise ValueError(f"profile interface {args.profile_interface_id} missing")

            setup_started = perf_counter()
            cur.execute("DROP TABLE IF EXISTS wildcard_bench_segment")
            cur.execute(
                """
                CREATE TEMP TABLE wildcard_bench_segment ON COMMIT PRESERVE ROWS AS
                WITH grouped AS (
                    SELECT object_id,last_end_char,
                           min(promotion_score + ln(1 + occurrence_count)::DOUBLE PRECISION) AS score_min,
                           max(promotion_score + ln(1 + occurrence_count)::DOUBLE PRECISION) AS score_max
                      FROM execution.semantic_pnf_actor_profile
                     WHERE interface_id=%s
                     GROUP BY object_id,last_end_char
                )
                SELECT grouped.*,
                       lead(last_end_char) OVER(PARTITION BY object_id ORDER BY last_end_char) AS next_end_char
                  FROM grouped
                """,
                (args.profile_interface_id,),
            )
            cur.execute("CREATE UNIQUE INDEX wildcard_bench_segment_pk ON wildcard_bench_segment(object_id,last_end_char)")
            cur.execute("CREATE INDEX wildcard_bench_segment_active_idx ON wildcard_bench_segment(last_end_char DESC,next_end_char,object_id)")
            cur.execute("ANALYZE wildcard_bench_segment")

            cur.execute("DROP TABLE IF EXISTS wildcard_bench_demand")
            cur.execute(
                """
                CREATE TEMP TABLE wildcard_bench_demand ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id,
                       COALESCE(d.source_start_char,source_region.end_char) AS demand_position,
                       d.max_candidates
                  FROM execution.semantic_pnf_interface_export e
                  JOIN execution.semantic_pnf_demand d ON d.demand_id=e.target_id
                  JOIN execution.semantic_pnf_region source_region ON source_region.region_id=d.source_region_id
                 WHERE e.interface_id=%s AND e.target_kind=3
                   AND d.state IN (1,3) AND d.expected_target_kind=1
                   AND d.expected_factor_type_symbol_id IS NULL
                   AND d.expected_object_kind_symbol_id IS NULL
                   AND d.role_symbol_id IS NULL AND d.lexical_symbol_id IS NULL
                   AND d.recency_class=3 AND d.max_candidates>0
                """,
                (args.demand_interface_id,),
            )
            cur.execute("CREATE UNIQUE INDEX wildcard_bench_demand_pk ON wildcard_bench_demand(demand_id)")
            cur.execute("ANALYZE wildcard_bench_demand")
            setup_ms = elapsed_ms(setup_started)

            certificate_started = perf_counter()
            cur.execute("DROP TABLE IF EXISTS wildcard_bench_decision")
            cur.execute(
                """
                CREATE TEMP TABLE wildcard_bench_decision ON COMMIT PRESERVE ROWS AS
                WITH boundary AS MATERIALIZED (
                    SELECT d.*,
                           kth.last_end_char AS cutoff_end,
                           (overflow.object_id IS NOT NULL) AS has_overflow
                      FROM wildcard_bench_demand d
                      LEFT JOIN LATERAL (
                          SELECT s.last_end_char
                            FROM wildcard_bench_segment s
                           WHERE s.last_end_char<=d.demand_position
                             AND (s.next_end_char IS NULL OR d.demand_position<s.next_end_char)
                           ORDER BY s.last_end_char DESC,s.object_id
                           OFFSET (d.max_candidates-1) LIMIT 1
                      ) kth ON TRUE
                      LEFT JOIN LATERAL (
                          SELECT s.object_id
                            FROM wildcard_bench_segment s
                           WHERE s.last_end_char<=d.demand_position
                             AND (s.next_end_char IS NULL OR d.demand_position<s.next_end_char)
                           ORDER BY s.last_end_char DESC,s.object_id
                           OFFSET d.max_candidates LIMIT 1
                      ) overflow ON TRUE
                ), counts AS MATERIALIZED (
                    SELECT b.*,
                           CASE WHEN b.cutoff_end IS NULL THEN 0 ELSE (
                               SELECT count(*) FROM wildcard_bench_segment s
                                WHERE s.last_end_char<=b.demand_position
                                  AND (s.next_end_char IS NULL OR b.demand_position<s.next_end_char)
                                  AND s.last_end_char>b.cutoff_end
                           ) END::BIGINT AS nearer_count
                      FROM boundary b
                ), cutoff AS MATERIALIZED (
                    SELECT c.demand_id,(c.max_candidates-c.nearer_count)::BIGINT AS remaining_slots,
                           s.object_id,s.score_min,s.score_max
                      FROM counts c JOIN wildcard_bench_segment s
                        ON s.last_end_char=c.cutoff_end
                       AND (s.next_end_char IS NULL OR c.demand_position<s.next_end_char)
                     WHERE c.has_overflow
                ), envelope AS MATERIALIZED (
                    SELECT c.demand_id,c.object_id,c.remaining_slots,
                           count(x.object_id) FILTER (WHERE x.object_id<>c.object_id AND
                             (x.score_min>c.score_max OR (x.score_min=c.score_max AND x.object_id<c.object_id)))::BIGINT AS certain,
                           count(x.object_id) FILTER (WHERE x.object_id<>c.object_id AND
                             (x.score_max>c.score_min OR (x.score_max=c.score_min AND x.object_id<c.object_id)))::BIGINT AS possible
                      FROM cutoff c JOIN cutoff x ON x.demand_id=c.demand_id
                     GROUP BY c.demand_id,c.object_id,c.remaining_slots
                ), residual AS (
                    SELECT demand_id,
                           count(*) FILTER (WHERE certain<remaining_slots AND NOT(possible<remaining_slots))::BIGINT AS unstable
                      FROM envelope GROUP BY demand_id
                )
                SELECT c.demand_id,c.demand_position,c.max_candidates,
                       COALESCE(r.unstable,0)::BIGINT AS unstable,
                       (COALESCE(r.unstable,0)=0) AS certified
                  FROM counts c LEFT JOIN residual r USING(demand_id)
                """
            )
            cur.execute("CREATE UNIQUE INDEX wildcard_bench_decision_pk ON wildcard_bench_decision(demand_id)")
            cur.execute("CREATE INDEX wildcard_bench_decision_route_idx ON wildcard_bench_decision(certified,demand_position,demand_id)")
            cur.execute("ANALYZE wildcard_bench_decision")
            certificate_ms = elapsed_ms(certificate_started)

            cur.execute(
                "SELECT count(*)::BIGINT,count(*) FILTER(WHERE certified)::BIGINT,count(*) FILTER(WHERE NOT certified)::BIGINT FROM wildcard_bench_decision"
            )
            demand_count, certified_count, fallback_count = map(int, cur.fetchone())

            hybrid_route_times: list[float] = []
            hybrid_rows = 0
            for _ in range(args.repeats):
                route_started = perf_counter()
                cur.execute("DROP TABLE IF EXISTS wildcard_bench_hybrid")
                cur.execute(
                    """
                    CREATE TEMP TABLE wildcard_bench_hybrid ON COMMIT PRESERVE ROWS AS
                    WITH certified AS MATERIALIZED (
                        SELECT d.demand_id,1::SMALLINT AS target_kind,p.object_id AS target_id,
                               %s::BIGINT AS source_interface_id
                          FROM wildcard_bench_decision d
                          CROSS JOIN LATERAL (
                              SELECT s.object_id
                                FROM wildcard_bench_segment s
                               WHERE s.last_end_char<=d.demand_position
                                 AND (s.next_end_char IS NULL OR d.demand_position<s.next_end_char)
                               ORDER BY s.last_end_char DESC,s.score_min DESC,s.object_id
                               LIMIT d.max_candidates
                          ) p
                         WHERE d.certified
                    ), fallback_raw AS MATERIALIZED (
                        SELECT d.demand_id,1::SMALLINT AS target_kind,p.object_id AS target_id,
                               %s::BIGINT AS source_interface_id,
                               abs(d.demand_position-p.last_end_char) AS structural_distance,
                               0::BIGINT AS index_rank,
                               p.promotion_score + ln(1+p.occurrence_count)::DOUBLE PRECISION AS candidate_score
                          FROM wildcard_bench_decision d
                          JOIN execution.semantic_pnf_actor_profile p
                            ON p.interface_id=%s AND p.last_end_char<=d.demand_position
                         WHERE NOT d.certified
                    ), fallback_dedup AS MATERIALIZED (
                        SELECT r.*,
                               row_number() OVER(
                                   PARTITION BY r.demand_id,r.target_kind,r.target_id
                                   ORDER BY r.structural_distance,r.index_rank,r.source_interface_id
                               ) AS target_occurrence
                          FROM fallback_raw r
                    ), fallback_ranked AS MATERIALIZED (
                        SELECT r.*,
                               row_number() OVER(
                                   PARTITION BY r.demand_id
                                   ORDER BY r.structural_distance,r.candidate_score DESC,r.index_rank,r.target_id
                               )-1 AS candidate_ordinal
                          FROM fallback_dedup r
                         WHERE r.target_occurrence=1
                    ), fallback AS (
                        SELECT r.demand_id,r.target_kind,r.target_id,r.source_interface_id
                          FROM fallback_ranked r
                          JOIN wildcard_bench_decision d USING(demand_id)
                         WHERE r.candidate_ordinal<d.max_candidates
                    )
                    SELECT * FROM certified
                    UNION ALL
                    SELECT * FROM fallback
                    """,
                    (args.profile_interface_id,args.profile_interface_id,args.profile_interface_id),
                )
                cur.execute("CREATE UNIQUE INDEX wildcard_bench_hybrid_pk ON wildcard_bench_hybrid(demand_id,target_kind,target_id)")
                cur.execute("ANALYZE wildcard_bench_hybrid")
                hybrid_route_times.append(elapsed_ms(route_started))
                cur.execute("SELECT count(*)::BIGINT FROM wildcard_bench_hybrid")
                hybrid_rows = int(cur.fetchone()[0])

            # Exact full-workload semantic gate against the current persisted legacy output.
            parity_started = perf_counter()
            cur.execute(
                """
                WITH persisted AS (
                    SELECT c.demand_id,c.target_kind,c.target_id,c.source_interface_id
                      FROM execution.semantic_pnf_demand_candidate c
                      JOIN wildcard_bench_demand d USING(demand_id)
                ), hmp AS (SELECT * FROM wildcard_bench_hybrid EXCEPT ALL SELECT * FROM persisted),
                   pmh AS (SELECT * FROM persisted EXCEPT ALL SELECT * FROM wildcard_bench_hybrid)
                SELECT (SELECT count(*) FROM hmp)::BIGINT,(SELECT count(*) FROM pmh)::BIGINT
                """
            )
            hybrid_minus_persisted, persisted_minus_hybrid = map(int,cur.fetchone())

            # Keep the mismatch attributable to the proof-directed route.  A
            # whole-workload count alone cannot distinguish a certified-route
            # error from a residual fallback implementation error.
            cur.execute(
                """
                WITH persisted AS (
                    SELECT c.demand_id,c.target_kind,c.target_id,c.source_interface_id
                      FROM execution.semantic_pnf_demand_candidate c
                      JOIN wildcard_bench_demand d USING(demand_id)
                ), hmp AS (
                    SELECT h.* FROM wildcard_bench_hybrid h
                    EXCEPT ALL SELECT * FROM persisted
                ), pmh AS (
                    SELECT p.* FROM persisted p
                    EXCEPT ALL SELECT * FROM wildcard_bench_hybrid
                ), diffs AS (
                    SELECT 'hybrid_minus_persisted'::TEXT AS direction,h.demand_id
                      FROM hmp h
                    UNION ALL
                    SELECT 'persisted_minus_hybrid'::TEXT,p.demand_id
                      FROM pmh p
                )
                SELECT
                    count(*) FILTER (WHERE d.certified AND direction='hybrid_minus_persisted'),
                    count(*) FILTER (WHERE d.certified AND direction='persisted_minus_hybrid'),
                    count(*) FILTER (WHERE NOT d.certified AND direction='hybrid_minus_persisted'),
                    count(*) FILTER (WHERE NOT d.certified AND direction='persisted_minus_hybrid')
                  FROM diffs JOIN wildcard_bench_decision d USING(demand_id)
                """
            )
            certified_hybrid_minus_persisted, certified_persisted_minus_hybrid, fallback_hybrid_minus_persisted, fallback_persisted_minus_hybrid = map(int, cur.fetchone())
            cur.execute(
                """
                WITH persisted AS (
                    SELECT c.demand_id,c.target_kind,c.target_id,c.source_interface_id
                      FROM execution.semantic_pnf_demand_candidate c
                      JOIN wildcard_bench_demand d USING(demand_id)
                ), hmp AS (
                    SELECT h.* FROM wildcard_bench_hybrid h
                    EXCEPT ALL SELECT * FROM persisted
                ), pmh AS (
                    SELECT p.* FROM persisted p
                    EXCEPT ALL SELECT * FROM wildcard_bench_hybrid
                )
                SELECT 'hybrid_minus_persisted'::TEXT,demand_id,target_kind,target_id,source_interface_id
                  FROM hmp JOIN wildcard_bench_decision d USING(demand_id)
                 WHERE NOT d.certified
                UNION ALL
                SELECT 'persisted_minus_hybrid'::TEXT,demand_id,target_kind,target_id,source_interface_id
                  FROM pmh JOIN wildcard_bench_decision d USING(demand_id)
                 WHERE NOT d.certified
                 ORDER BY 2,1,4
                 LIMIT 20
                """
            )
            fallback_mismatch_samples = [
                {
                    "direction": row[0],
                    "demand_id": int(row[1]),
                    "target_kind": int(row[2]),
                    "target_id": int(row[3]),
                    "source_interface_id": int(row[4]),
                }
                for row in cur.fetchall()
            ]

            cur.execute(
                """
                WITH hybrid_tuple AS (
                    SELECT d.demand_id,count(h.target_id)::SMALLINT AS candidate_count,
                           CASE WHEN count(h.target_id)=1 THEN min(h.target_kind) END::SMALLINT AS selected_target_kind,
                           CASE WHEN count(h.target_id)=1 THEN min(h.target_id) END::BIGINT AS selected_target_id,
                           CASE WHEN count(h.target_id)=1 THEN 2
                                WHEN count(h.target_id)=0 AND %s=10 THEN 7
                                WHEN count(h.target_id)=0 THEN 1 ELSE 3 END::SMALLINT AS outcome_state,
                           CASE WHEN count(h.target_id)=1 THEN %s::BIGINT END AS witness_interface_id
                      FROM wildcard_bench_demand d LEFT JOIN wildcard_bench_hybrid h USING(demand_id)
                     GROUP BY d.demand_id
                ), persisted AS (
                    SELECT r.demand_id,r.candidate_count,r.selected_target_kind,r.selected_target_id,
                           r.outcome_state,r.witness_interface_id
                      FROM execution.semantic_pnf_frontier_resolution r
                      JOIN wildcard_bench_demand d USING(demand_id)
                     WHERE r.interface_id=%s
                ), hmp AS (SELECT * FROM hybrid_tuple EXCEPT ALL SELECT * FROM persisted),
                   pmh AS (SELECT * FROM persisted EXCEPT ALL SELECT * FROM hybrid_tuple)
                SELECT (SELECT count(*) FROM hmp)::BIGINT,(SELECT count(*) FROM pmh)::BIGINT
                """,
                (region_kind,args.profile_interface_id,args.demand_interface_id),
            )
            hybrid_tuple_minus_persisted, persisted_tuple_minus_hybrid = map(int,cur.fetchone())
            parity_ms = elapsed_ms(parity_started)
            semantic_parity = (
                persisted_oracle_current
                and hybrid_minus_persisted==0
                and persisted_minus_hybrid==0
                and hybrid_tuple_minus_persisted==0
                and persisted_tuple_minus_hybrid==0
            )

            legacy_times: list[float] = []
            legacy_status = "skipped" if args.skip_legacy_baseline else "not_run"
            legacy_error: str | None = None
            legacy_rows: int | None = None
            if not args.skip_legacy_baseline:
                legacy_status = "completed"
                for _ in range(args.repeats):
                    legacy_started = perf_counter()
                    try:
                        cur.execute("DROP TABLE IF EXISTS wildcard_bench_legacy")
                        cur.execute(
                            """
                            CREATE TEMP TABLE wildcard_bench_legacy ON COMMIT PRESERVE ROWS AS
                            WITH raw AS MATERIALIZED (
                                SELECT d.demand_id,1::SMALLINT AS target_kind,p.object_id AS target_id,
                                       %s::BIGINT AS source_interface_id,
                                       abs(d.demand_position-p.last_end_char) AS structural_distance,
                                       0::BIGINT AS index_rank,
                                       p.promotion_score + ln(1+p.occurrence_count)::DOUBLE PRECISION AS candidate_score
                                  FROM wildcard_bench_demand d
                                  JOIN execution.semantic_pnf_actor_profile p
                                    ON p.interface_id=%s AND p.last_end_char<=d.demand_position
                            ), dedup AS MATERIALIZED (
                                SELECT r.*,
                                       row_number() OVER(
                                           PARTITION BY r.demand_id,r.target_kind,r.target_id
                                           ORDER BY r.structural_distance,r.index_rank,r.source_interface_id
                                       ) AS target_occurrence
                                  FROM raw r
                            ), ranked AS MATERIALIZED (
                                SELECT r.*,
                                       row_number() OVER(
                                           PARTITION BY r.demand_id
                                           ORDER BY r.structural_distance,r.candidate_score DESC,r.index_rank,r.target_id
                                       )-1 AS candidate_ordinal
                                  FROM dedup r WHERE r.target_occurrence=1
                            )
                            SELECT r.demand_id,r.target_kind,r.target_id,r.source_interface_id
                              FROM ranked r JOIN wildcard_bench_demand d USING(demand_id)
                             WHERE r.candidate_ordinal<d.max_candidates
                            """,
                            (args.profile_interface_id,args.profile_interface_id),
                        )
                        cur.execute("CREATE UNIQUE INDEX wildcard_bench_legacy_pk ON wildcard_bench_legacy(demand_id,target_kind,target_id)")
                        cur.execute("ANALYZE wildcard_bench_legacy")
                        legacy_times.append(elapsed_ms(legacy_started))
                        cur.execute("SELECT count(*)::BIGINT FROM wildcard_bench_legacy")
                        legacy_rows = int(cur.fetchone()[0])
                    except Exception as exc:  # statement timeout or resource failure is an unknown baseline
                        legacy_status = "timeout_or_error"
                        legacy_error = f"{type(exc).__name__}: {exc}"
                        legacy_times.clear()
                        break

            hybrid_route_median = statistics.median(hybrid_route_times)
            hybrid_total_median = setup_ms + certificate_ms + hybrid_route_median
            legacy_median = statistics.median(legacy_times) if legacy_times else None
            speedup = (legacy_median / hybrid_total_median) if legacy_median is not None and hybrid_total_median>0 else None
            cost_win = legacy_median is not None and hybrid_total_median < legacy_median
            promotion_ready = semantic_parity and cost_win

            receipt = {
                "contract_ref": CONTRACT_REF,
                "demand_interface_id": args.demand_interface_id,
                "profile_interface_id": args.profile_interface_id,
                "workload_identity": f"{args.demand_interface_id}->{args.profile_interface_id}",
                "semantic_mutation_performed": False,
                "temp_state_only": True,
                "interface_graph_revision": interface_revision,
                "frontier_receipt_graph_revision": receipt_revision,
                "persisted_legacy_oracle_current": persisted_oracle_current,
                "wildcard_demands": demand_count,
                "certified_bounded_demands": certified_count,
                "legacy_residual_fallback_demands": fallback_count,
                "hybrid_rows": hybrid_rows,
                "hybrid_minus_persisted_memberships": hybrid_minus_persisted,
                "persisted_minus_hybrid_memberships": persisted_minus_hybrid,
                "certified_hybrid_minus_persisted_memberships": certified_hybrid_minus_persisted,
                "certified_persisted_minus_hybrid_memberships": certified_persisted_minus_hybrid,
                "fallback_hybrid_minus_persisted_memberships": fallback_hybrid_minus_persisted,
                "fallback_persisted_minus_hybrid_memberships": fallback_persisted_minus_hybrid,
                "fallback_mismatch_samples": fallback_mismatch_samples,
                "hybrid_minus_persisted_consumer_tuples": hybrid_tuple_minus_persisted,
                "persisted_minus_hybrid_consumer_tuples": persisted_tuple_minus_hybrid,
                "semantic_parity": semantic_parity,
                "setup_ms": setup_ms,
                "certificate_ms": certificate_ms,
                "hybrid_route_ms_samples": hybrid_route_times,
                "hybrid_route_median_ms": hybrid_route_median,
                "hybrid_total_median_ms": hybrid_total_median,
                "parity_compare_ms": parity_ms,
                "legacy_baseline_status": legacy_status,
                "legacy_baseline_error": legacy_error,
                "legacy_rows": legacy_rows,
                "legacy_ms_samples": legacy_times,
                "legacy_median_ms": legacy_median,
                "measured_speedup": speedup,
                "cost_win": cost_win,
                "promotion_ready": promotion_ready,
                "promotion_rule": "semantic_parity_and_same_pair_measured_full_path_cost_win",
                "timeout_semantics": "unknown_not_speedup",
            }
            emit(out,receipt)
            return 0 if semantic_parity else 2
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
