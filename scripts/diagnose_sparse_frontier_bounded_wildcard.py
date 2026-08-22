"""Read-only bounded wildcard survivor diagnostic for sparse PNF frontiers.

The C2 experiments established that constrained demand fibres are cheap while
mask-0 ``anaphor_unresolved`` demands expose the full actor-profile carrier.  A
raw candidate relation for such a demand is intentionally broad, so this probe
does not claim raw-candidate parity.  It tests the stronger useful statement:
can the legacy *survivor* set be recovered from a bounded prefix of the wildcard
profile order without materialising every admissible row?

For the currently observed recency-class-3 workload, legacy structural distance
is ``demand_position - last_end_char``.  Therefore profile rows are searched in
``last_end_char DESC`` order.  If an object has at most B profile rows, then the
first ``k * B`` rows contain every object that can enter the first k distinct
objects.  The probe computes B from the selected interface and fails closed when
legacy per-object representative selection is ambiguous at the nearest position
(two rows for one object share the maximum ``last_end_char`` but disagree in
candidate score).

The result is diagnostic only.  It creates TEMP state, performs no semantic
mutation, and promotes nothing into migration 180.  Exact authority remains a
batch-local two-way ``EXCEPT ALL`` comparison against the legacy direct
conjunction followed by the historical dedup/rank/take-k semantics.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import psycopg

from diagnose_sparse_frontier_candidate_work import _DIRECT_OBJECT_CANDIDATE, _OBJECT_DEMAND
from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-bounded-wildcard-diagnostic.v0_1"

_MASK_ZERO_DEMAND = f"""
SELECT demand.*
  FROM ({_OBJECT_DEMAND}) AS demand
 WHERE demand.expected_factor_type_symbol_id IS NULL
   AND demand.expected_object_kind_symbol_id IS NULL
   AND demand.role_symbol_id IS NULL
   AND demand.lexical_symbol_id IS NULL
"""

_PARITY_COLUMNS = """
demand_id, ordinal, target_kind, target_id,
structural_distance, index_rank, candidate_score
"""


def _params(sql: str, interface_id: int) -> tuple[int, ...]:
    return (interface_id,) * sql.count("%s")


def _legacy_survivors(batch_lo: int, batch_hi: int) -> str:
    return f"""
WITH wildcard AS MATERIALIZED (
    SELECT candidate.*
      FROM ({_DIRECT_OBJECT_CANDIDATE}) AS candidate
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = candidate.demand_id
     WHERE demand.demand_id >= {batch_lo}
       AND demand.demand_id < {batch_hi}
       AND demand.expected_factor_type_symbol_id IS NULL
       AND demand.expected_object_kind_symbol_id IS NULL
       AND demand.role_symbol_id IS NULL
       AND demand.lexical_symbol_id IS NULL
),
deduplicated AS MATERIALIZED (
    SELECT candidate.*,
           row_number() OVER (
               PARTITION BY candidate.demand_id,
                            candidate.target_kind,
                            candidate.target_id
               ORDER BY candidate.structural_distance,
                        candidate.index_rank,
                        candidate.target_id
           ) AS target_occurrence
      FROM wildcard AS candidate
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
       ranked.candidate_ordinal::SMALLINT AS ordinal,
       ranked.target_kind,
       ranked.target_id,
       ranked.structural_distance,
       ranked.index_rank,
       ranked.candidate_score
  FROM ranked
 WHERE ranked.candidate_ordinal < ranked.max_candidates
"""


def _bounded_survivors(batch_lo: int, batch_hi: int, multiplicity_bound: int) -> str:
    return f"""
WITH demand AS MATERIALIZED (
    SELECT *
      FROM ({_MASK_ZERO_DEMAND}) AS wildcard
     WHERE wildcard.demand_id >= {batch_lo}
       AND wildcard.demand_id < {batch_hi}
),
bounded AS (
    SELECT demand.demand_id,
           demand.max_candidates,
           demand.demand_position,
           picked.object_id,
           picked.last_end_char,
           picked.candidate_score
      FROM demand
      CROSS JOIN LATERAL (
          SELECT profile.object_id,
                 profile.last_end_char,
                 profile.candidate_score
            FROM wildcard_profile_ordered AS profile
           WHERE profile.last_end_char <= demand.demand_position
           ORDER BY profile.last_end_char DESC,
                    profile.candidate_score DESC,
                    profile.object_id
           LIMIT demand.max_candidates * {multiplicity_bound}
      ) AS picked
),
representative AS (
    SELECT DISTINCT ON (bounded.demand_id, bounded.object_id)
           bounded.demand_id,
           bounded.max_candidates,
           bounded.demand_position,
           bounded.object_id,
           bounded.last_end_char,
           bounded.candidate_score
      FROM bounded
     ORDER BY bounded.demand_id,
              bounded.object_id,
              bounded.last_end_char DESC,
              bounded.candidate_score DESC
),
ranked AS (
    SELECT representative.*,
           row_number() OVER (
               PARTITION BY representative.demand_id
               ORDER BY representative.demand_position - representative.last_end_char,
                        representative.candidate_score DESC,
                        representative.object_id
           ) - 1 AS candidate_ordinal
      FROM representative
)
SELECT ranked.demand_id,
       ranked.candidate_ordinal::SMALLINT AS ordinal,
       1::SMALLINT AS target_kind,
       ranked.object_id AS target_id,
       ranked.demand_position - ranked.last_end_char AS structural_distance,
       0::BIGINT AS index_rank,
       ranked.candidate_score
  FROM ranked
 WHERE ranked.candidate_ordinal < ranked.max_candidates
"""


def _difference(left: str, right: str) -> str:
    return f"""
SELECT {_PARITY_COLUMNS} FROM ({left}) AS left_rows
EXCEPT ALL
SELECT {_PARITY_COLUMNS} FROM ({right}) AS right_rows
"""


def _write(stream: Any, payload: dict[str, object]) -> None:
    stream.write(json.dumps(payload, sort_keys=True) + "\n")
    stream.flush()
    print(json.dumps(payload, sort_keys=True), flush=True)


def _run_batch(
    cursor: Any,
    *,
    interface_id: int,
    batch_lo: int,
    batch_hi: int,
    multiplicity_bound: int,
    timeout_ms: int,
) -> dict[str, object]:
    legacy = _legacy_survivors(batch_lo, batch_hi)
    bounded = _bounded_survivors(batch_lo, batch_hi, multiplicity_bound)
    left = _difference(legacy, bounded)
    right = _difference(bounded, legacy)
    started = time.monotonic()
    try:
        cursor.execute("SELECT set_config('statement_timeout', %s, false)", (str(timeout_ms),))
        cursor.execute(
            f"SELECT count(*) FROM ({bounded}) AS rows",
            _params(bounded, interface_id),
        )
        bounded_rows = int(cursor.fetchone()[0])
        cursor.execute(f"SELECT count(*) FROM ({left}) AS diff", _params(left, interface_id))
        legacy_minus_bounded = int(cursor.fetchone()[0])
        cursor.execute(f"SELECT count(*) FROM ({right}) AS diff", _params(right, interface_id))
        bounded_minus_legacy = int(cursor.fetchone()[0])
        return {
            "batch_lo": batch_lo,
            "batch_hi": batch_hi,
            "status": "complete",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "bounded_rows": bounded_rows,
            "legacy_minus_bounded": legacy_minus_bounded,
            "bounded_minus_legacy": bounded_minus_legacy,
            "exact_survivor_parity": legacy_minus_bounded == 0 and bounded_minus_legacy == 0,
        }
    except psycopg.errors.QueryCanceled as exc:
        return {
            "batch_lo": batch_lo,
            "batch_hi": batch_hi,
            "status": "timeout",
            "timeout_ms": timeout_ms,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    args = parser.parse_args()
    if args.batch_size < 1:
        raise ValueError("batch-size must be positive")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    complete = True
    connection = connect(args.database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor, args.output.open("a", encoding="utf-8") as stream:
            # TEMP construction is session-local and intentionally the only write.
            cursor.execute("DROP TABLE IF EXISTS wildcard_profile_ordered")
            cursor.execute(
                """
                CREATE TEMP TABLE wildcard_profile_ordered ON COMMIT PRESERVE ROWS AS
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
                CREATE INDEX wildcard_profile_order_idx
                    ON wildcard_profile_ordered
                       (last_end_char DESC, candidate_score DESC, object_id)
                """
            )
            cursor.execute("ANALYZE wildcard_profile_ordered")

            cursor.execute(
                """
                SELECT COALESCE(max(row_count), 0)::BIGINT
                  FROM (
                      SELECT object_id, count(*)::BIGINT AS row_count
                        FROM wildcard_profile_ordered
                       GROUP BY object_id
                  ) AS multiplicity
                """
            )
            multiplicity_bound = int(cursor.fetchone()[0])
            cursor.execute(
                """
                WITH nearest AS (
                    SELECT object_id, max(last_end_char) AS last_end_char
                      FROM wildcard_profile_ordered
                     GROUP BY object_id
                )
                SELECT count(*)::BIGINT
                  FROM (
                      SELECT profile.object_id
                        FROM wildcard_profile_ordered AS profile
                        JOIN nearest
                          ON nearest.object_id = profile.object_id
                         AND nearest.last_end_char = profile.last_end_char
                       GROUP BY profile.object_id
                      HAVING min(profile.candidate_score)
                             IS DISTINCT FROM max(profile.candidate_score)
                  ) AS ambiguous
                """
            )
            ambiguous_representatives = int(cursor.fetchone()[0])

            cursor.execute(
                f"""
                SELECT count(*)::BIGINT,
                       min(demand_id)::BIGINT,
                       max(demand_id)::BIGINT,
                       count(*) FILTER (WHERE recency_class <> 3)::BIGINT,
                       count(*) FILTER (WHERE max_candidates <= 0)::BIGINT
                  FROM ({_MASK_ZERO_DEMAND}) AS demand
                """,
                (args.interface_id,),
            )
            demand_count, min_id, max_id, non_recency3, bad_k = cursor.fetchone()
            summary = {
                "contract_ref": CONTRACT_REF,
                "interface_id": args.interface_id,
                "semantic_mutation_performed": False,
                "temp_state_only": True,
                "wildcard_demands": int(demand_count),
                "multiplicity_bound": multiplicity_bound,
                "ambiguous_nearest_object_representatives": ambiguous_representatives,
                "non_recency_class_3_demands": int(non_recency3),
                "nonpositive_max_candidates": int(bad_k),
            }
            _write(stream, {"stage": "precondition", **summary})

            if ambiguous_representatives or non_recency3 or bad_k or multiplicity_bound < 1:
                _write(
                    stream,
                    {
                        "stage": "final",
                        **summary,
                        "status": "fail_closed",
                        "global_exact_survivor_parity": False,
                    },
                )
                return 2

            if min_id is None or max_id is None:
                _write(
                    stream,
                    {
                        "stage": "final",
                        **summary,
                        "status": "complete",
                        "global_exact_survivor_parity": True,
                        "batches": 0,
                    },
                )
                return 0

            batch_count = 0
            all_parity = True
            lo = int(min_id)
            max_demand_id = int(max_id)
            while lo <= max_demand_id:
                hi = lo + args.batch_size
                receipt = _run_batch(
                    cursor,
                    interface_id=args.interface_id,
                    batch_lo=lo,
                    batch_hi=hi,
                    multiplicity_bound=multiplicity_bound,
                    timeout_ms=args.timeout_ms,
                )
                _write(stream, {"stage": "batch", **summary, **receipt})
                batch_count += 1
                if receipt.get("exact_survivor_parity") is not True:
                    all_parity = False
                    complete = False
                lo = hi

            _write(
                stream,
                {
                    "stage": "final",
                    **summary,
                    "status": "complete" if complete else "incomplete",
                    "batches": batch_count,
                    "global_exact_survivor_parity": all_parity and complete,
                },
            )
            return 0 if all_parity and complete else 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
