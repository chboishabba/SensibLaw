"""Read-only live consumer parity/cost gate for demand-local wildcard fibres.

This gate avoids the historical ~62M demand×profile materialization.  It rebuilds
only the demand-local temporal segment carrier and MUST/MAY certificate, realizes
one attained score choice on certified fibres, and compares that semantic output
with the *already materialized* legacy frontier.  Persisted legacy state is used
as an oracle only when the frontier reduction receipt graph revision matches the
interface graph revision.

Semantic comparison is consumer-indexed:
  membership + source-interface provenance,
  candidate_count, unique target, outcome, witness interface.
Planner ordinal/distance/rank/score are execution/history observations under
migration 086 and are not required to be equal.

TEMP/read-only only; no production mutation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from src.storage.postgres.spacy_parser_model import connect

CONTRACT_REF = "sensiblaw.sparse-frontier-demand-local-live-consumer-gate.v0_1"


def ms(t: float) -> float:
    return (perf_counter() - t) * 1000.0


def emit(stream: Any, payload: dict[str, object]) -> None:
    text = json.dumps(payload, sort_keys=True)
    stream.write(text + "\n")
    stream.flush()
    print(text, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--interface-id", required=True, type=int)
    ap.add_argument(
        "--profile-interface-id",
        type=int,
        help="interface whose actor-profile fibre supplies candidate provenance (defaults to --interface-id)",
    )
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--timeout-ms", type=int, default=60000)
    args = ap.parse_args()
    profile_interface_id = args.profile_interface_id or args.interface_id
    args.output.parent.mkdir(parents=True, exist_ok=True)

    con = connect(args.database_url)
    con.autocommit = True
    try:
        with con.cursor() as cur, args.output.open("a", encoding="utf-8") as out:
            cur.execute("SELECT set_config('statement_timeout', %s, false)", (str(args.timeout_ms),))
            cur.execute(
                """
                SELECT i.graph_revision,
                       r.graph_revision,
                       region.region_kind
                  FROM execution.semantic_pnf_interface AS i
                  JOIN execution.semantic_pnf_region AS region USING (region_id)
                  LEFT JOIN execution.semantic_pnf_frontier_reduction_receipt AS r
                    ON r.interface_id = i.interface_id
                 WHERE i.interface_id = %s
                """,
                (args.interface_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"interface {args.interface_id} missing")
            interface_revision = int(row[0])
            receipt_revision = None if row[1] is None else int(row[1])
            region_kind = int(row[2])
            persisted_oracle_current = receipt_revision == interface_revision

            started = perf_counter()
            cur.execute("DROP TABLE IF EXISTS wildcard_gate_segment")
            cur.execute(
                """
                CREATE TEMP TABLE wildcard_gate_segment ON COMMIT PRESERVE ROWS AS
                WITH grouped AS (
                    SELECT object_id, last_end_char,
                           min(promotion_score + ln(1 + occurrence_count)::DOUBLE PRECISION) AS score_min,
                           max(promotion_score + ln(1 + occurrence_count)::DOUBLE PRECISION) AS score_max
                      FROM execution.semantic_pnf_actor_profile
                     WHERE interface_id = %s
                     GROUP BY object_id, last_end_char
                )
                SELECT grouped.*,
                       lead(last_end_char) OVER (PARTITION BY object_id ORDER BY last_end_char) AS next_end_char
                  FROM grouped
                """,
                (profile_interface_id,),
            )
            cur.execute("CREATE UNIQUE INDEX wildcard_gate_segment_pk ON wildcard_gate_segment(object_id,last_end_char)")
            cur.execute("CREATE INDEX wildcard_gate_segment_active_idx ON wildcard_gate_segment(last_end_char DESC,next_end_char,object_id)")
            cur.execute("ANALYZE wildcard_gate_segment")

            cur.execute("DROP TABLE IF EXISTS wildcard_gate_demand")
            cur.execute(
                """
                CREATE TEMP TABLE wildcard_gate_demand ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id,
                       COALESCE(d.source_start_char, source_region.end_char) AS demand_position,
                       d.max_candidates
                  FROM execution.semantic_pnf_interface_export AS e
                  JOIN execution.semantic_pnf_demand AS d ON d.demand_id=e.target_id
                  JOIN execution.semantic_pnf_region AS source_region ON source_region.region_id=d.source_region_id
                 WHERE e.interface_id=%s AND e.target_kind=3
                   AND d.state IN (1,3) AND d.expected_target_kind=1
                   AND d.expected_factor_type_symbol_id IS NULL
                   AND d.expected_object_kind_symbol_id IS NULL
                   AND d.role_symbol_id IS NULL AND d.lexical_symbol_id IS NULL
                   AND d.recency_class=3 AND d.max_candidates>0
                """,
                (args.interface_id,),
            )
            cur.execute("CREATE UNIQUE INDEX wildcard_gate_demand_pk ON wildcard_gate_demand(demand_id)")
            cur.execute("ANALYZE wildcard_gate_demand")
            setup_ms = ms(started)

            cert_started = perf_counter()
            cur.execute("DROP TABLE IF EXISTS wildcard_gate_decision")
            cur.execute(
                """
                CREATE TEMP TABLE wildcard_gate_decision ON COMMIT PRESERVE ROWS AS
                WITH boundary AS MATERIALIZED (
                    SELECT d.*,
                           kth.last_end_char AS cutoff_end,
                           (overflow.object_id IS NOT NULL) AS has_overflow
                      FROM wildcard_gate_demand AS d
                      LEFT JOIN LATERAL (
                          SELECT s.last_end_char FROM wildcard_gate_segment AS s
                           WHERE s.last_end_char<=d.demand_position
                             AND (s.next_end_char IS NULL OR d.demand_position<s.next_end_char)
                           ORDER BY s.last_end_char DESC,s.object_id
                           OFFSET (d.max_candidates-1) LIMIT 1
                      ) kth ON TRUE
                      LEFT JOIN LATERAL (
                          SELECT s.object_id FROM wildcard_gate_segment AS s
                           WHERE s.last_end_char<=d.demand_position
                             AND (s.next_end_char IS NULL OR d.demand_position<s.next_end_char)
                           ORDER BY s.last_end_char DESC,s.object_id
                           OFFSET d.max_candidates LIMIT 1
                      ) overflow ON TRUE
                ), counts AS MATERIALIZED (
                    SELECT b.*,
                           CASE WHEN b.cutoff_end IS NULL THEN 0 ELSE (
                               SELECT count(*) FROM wildcard_gate_segment s
                                WHERE s.last_end_char<=b.demand_position
                                  AND (s.next_end_char IS NULL OR b.demand_position<s.next_end_char)
                                  AND s.last_end_char>b.cutoff_end
                           ) END::BIGINT AS nearer_count
                      FROM boundary b
                ), cutoff AS MATERIALIZED (
                    SELECT c.demand_id,(c.max_candidates-c.nearer_count)::BIGINT AS remaining_slots,
                           s.object_id,s.score_min,s.score_max
                      FROM counts c JOIN wildcard_gate_segment s
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
                           count(*) FILTER (WHERE certain<remaining_slots AND NOT (possible<remaining_slots))::BIGINT AS unstable
                      FROM envelope GROUP BY demand_id
                )
                SELECT c.demand_id,c.demand_position,c.max_candidates,
                       COALESCE(r.unstable,0)::BIGINT AS unstable,
                       (COALESCE(r.unstable,0)=0) AS certified
                  FROM counts c LEFT JOIN residual r USING(demand_id)
                """
            )
            cur.execute("CREATE UNIQUE INDEX wildcard_gate_decision_pk ON wildcard_gate_decision(demand_id)")
            cur.execute("ANALYZE wildcard_gate_decision")
            certificate_ms = ms(cert_started)

            bounded_started = perf_counter()
            cur.execute("DROP TABLE IF EXISTS wildcard_gate_bounded")
            cur.execute(
                """
                CREATE TEMP TABLE wildcard_gate_bounded ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id,1::SMALLINT AS target_kind,p.object_id AS target_id,%s::BIGINT AS source_interface_id
                  FROM wildcard_gate_decision d
                  CROSS JOIN LATERAL (
                      SELECT s.object_id FROM wildcard_gate_segment s
                       WHERE s.last_end_char<=d.demand_position
                         AND (s.next_end_char IS NULL OR d.demand_position<s.next_end_char)
                       ORDER BY s.last_end_char DESC,s.score_min DESC,s.object_id
                       LIMIT d.max_candidates
                  ) p
                 WHERE d.certified
                """,
                (profile_interface_id,),
            )
            cur.execute("CREATE UNIQUE INDEX wildcard_gate_bounded_pk ON wildcard_gate_bounded(demand_id,target_kind,target_id)")
            cur.execute("ANALYZE wildcard_gate_bounded")
            bounded_ms = ms(bounded_started)

            parity_started = perf_counter()
            cur.execute(
                """
                WITH persisted AS (
                    SELECT c.demand_id,c.target_kind,c.target_id,c.source_interface_id
                      FROM execution.semantic_pnf_demand_candidate c
                      JOIN wildcard_gate_decision d USING(demand_id)
                     WHERE d.certified
                ), bml AS (SELECT * FROM wildcard_gate_bounded EXCEPT ALL SELECT * FROM persisted),
                   lmb AS (SELECT * FROM persisted EXCEPT ALL SELECT * FROM wildcard_gate_bounded)
                SELECT (SELECT count(*) FROM bml)::BIGINT,(SELECT count(*) FROM lmb)::BIGINT
                """
            )
            bounded_minus_legacy, legacy_minus_bounded = map(int, cur.fetchone())

            cur.execute("DROP TABLE IF EXISTS wildcard_gate_tuple")
            cur.execute(
                """
                CREATE TEMP TABLE wildcard_gate_tuple ON COMMIT PRESERVE ROWS AS
                SELECT d.demand_id,count(b.target_id)::SMALLINT AS candidate_count,
                       CASE WHEN count(b.target_id)=1 THEN min(b.target_kind) END::SMALLINT AS selected_target_kind,
                       CASE WHEN count(b.target_id)=1 THEN min(b.target_id) END::BIGINT AS selected_target_id,
                       CASE WHEN count(b.target_id)=1 THEN 2
                            WHEN count(b.target_id)=0 AND %s=10 THEN 7
                            WHEN count(b.target_id)=0 THEN 1 ELSE 3 END::SMALLINT AS outcome_state,
                       CASE WHEN count(b.target_id)=1 THEN %s::BIGINT END AS witness_interface_id
                  FROM wildcard_gate_decision d LEFT JOIN wildcard_gate_bounded b USING(demand_id)
                 WHERE d.certified GROUP BY d.demand_id
                """,
                (region_kind,profile_interface_id),
            )
            cur.execute(
                """
                WITH persisted AS (
                    SELECT r.demand_id,r.candidate_count,r.selected_target_kind,r.selected_target_id,
                           r.outcome_state,r.witness_interface_id
                      FROM execution.semantic_pnf_frontier_resolution r
                      JOIN wildcard_gate_decision d USING(demand_id)
                     WHERE d.certified AND r.interface_id=%s
                ), bml AS (SELECT * FROM wildcard_gate_tuple EXCEPT ALL SELECT * FROM persisted),
                   lmb AS (SELECT * FROM persisted EXCEPT ALL SELECT * FROM wildcard_gate_tuple)
                SELECT (SELECT count(*) FROM bml)::BIGINT,(SELECT count(*) FROM lmb)::BIGINT
                """,
                (args.interface_id,),
            )
            tuple_minus_legacy, legacy_minus_tuple = map(int, cur.fetchone())
            parity_ms = ms(parity_started)

            cur.execute("SELECT count(*)::BIGINT,count(*) FILTER (WHERE certified)::BIGINT,count(*) FILTER (WHERE NOT certified)::BIGINT FROM wildcard_gate_decision")
            demand_count,certified_count,fallback_count = map(int,cur.fetchone())
            full_membership_parity = bounded_minus_legacy==0 and legacy_minus_bounded==0
            full_tuple_parity = tuple_minus_legacy==0 and legacy_minus_tuple==0
            semantic_gate = persisted_oracle_current and full_membership_parity and full_tuple_parity
            bounded_observed_ms = setup_ms + certificate_ms + bounded_ms

            receipt = {
                "contract_ref": CONTRACT_REF,
                "interface_id": args.interface_id,
                "profile_interface_id": profile_interface_id,
                "semantic_mutation_performed": False,
                "temp_state_only": True,
                "interface_graph_revision": interface_revision,
                "frontier_receipt_graph_revision": receipt_revision,
                "persisted_legacy_oracle_current": persisted_oracle_current,
                "wildcard_demands": demand_count,
                "certified_bounded_demands": certified_count,
                "legacy_residual_fallback_demands": fallback_count,
                "bounded_minus_legacy_memberships": bounded_minus_legacy,
                "legacy_minus_bounded_memberships": legacy_minus_bounded,
                "bounded_minus_legacy_consumer_tuples": tuple_minus_legacy,
                "legacy_minus_bounded_consumer_tuples": legacy_minus_tuple,
                "full_membership_parity": full_membership_parity,
                "full_consumer_tuple_parity": full_tuple_parity,
                "semantic_gate_passed": semantic_gate,
                "setup_ms": setup_ms,
                "certificate_ms": certificate_ms,
                "bounded_realization_ms": bounded_ms,
                "parity_compare_ms": parity_ms,
                "bounded_path_observed_ms": bounded_observed_ms,
                "legacy_materialization_cost": "already_materialized_not_recomputed",
                "candidate_score_authority": "execution_history_not_semantic_evidence",
                "promotion_gate": "current_legacy_revision_and_membership_and_consumer_tuple_parity",
            }
            emit(out, receipt)
            return 0 if semantic_gate else 2
    finally:
        con.close()

if __name__ == "__main__":
    raise SystemExit(main())
