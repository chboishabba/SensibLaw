#!/usr/bin/env python3
"""Benchmark post-parser numeric PNF query shape and retrieval reduction.

Records empirical (N_input, N_generated, N_retained, N_output, W, M, T) tuples,
token-normalised throughput, support fanout and PostgreSQL retrieval reduction.
EXPLAIN is consumed in JSON form; no regex/string scraping is used.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from time import monotonic_ns
from typing import Any

import psycopg


@dataclass(frozen=True, slots=True)
class BenchmarkTuple:
    workload_ref: str
    stage_name: str
    token_count: int
    n_input: int
    n_generated: int
    n_retained: int
    n_output: int
    work_units: int
    peak_memory_bytes: int | None
    elapsed_microseconds: int

    @property
    def tokens_per_second(self) -> float | None:
        if self.elapsed_microseconds <= 0:
            return None
        return self.token_count * 1_000_000 / self.elapsed_microseconds

    @property
    def work_per_token(self) -> float | None:
        return self.work_units / self.token_count if self.token_count else None


@dataclass(frozen=True, slots=True)
class RetrievalReduction:
    workload_ref: str
    retrieval_kind: str
    universe_units: int
    frontier_units: int
    reduction_ratio: float | None
    probe_microseconds: int
    downstream_work_units: int


@dataclass(frozen=True, slots=True)
class SupportFanout:
    argument_objects: int
    support_edges: int
    maximum_fanout: float | None
    average_fanout: float | None


def _count(cursor: Any, sql: str, params: tuple[Any, ...]) -> int:
    cursor.execute(sql, params)
    return int(cursor.fetchone()[0] or 0)


def _timed_count(cursor: Any, sql: str, params: tuple[Any, ...]) -> tuple[int, int]:
    started = monotonic_ns()
    value = _count(cursor, sql, params)
    return value, max(0, (monotonic_ns() - started) // 1_000)


def _explain_microseconds(cursor: Any, sql: str, params: tuple[Any, ...]) -> int:
    cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params)
    payload = cursor.fetchone()[0]
    document = payload[0] if isinstance(payload, list) else payload
    elapsed_ms = float(document.get("Execution Time", 0.0))
    return int(elapsed_ms * 1_000)


def _document_token_count(cursor: Any, run_id: int, document_id: int) -> int:
    return _count(
        cursor,
        """
        WITH identity AS (
            SELECT run_identity.run_ref, document_identity.document_ref
              FROM execution.semantic_pnf_run_identity AS run_identity
              CROSS JOIN execution.semantic_pnf_document_identity AS document_identity
             WHERE run_identity.run_id = %s
               AND document_identity.document_id = %s
        )
        SELECT count(*)
          FROM execution.semantic_parser_token AS token
          JOIN identity ON TRUE
         WHERE token.run_ref = identity.run_ref
           AND token.document_ref = identity.document_ref
           AND token.representation_version = 2
        """,
        (run_id, document_id),
    )


def collect(
    cursor: Any, *, run_id: int, document_id: int, workload_ref: str
) -> tuple[tuple[BenchmarkTuple, ...], tuple[RetrievalReduction, ...], SupportFanout]:
    params = (run_id, document_id)
    token_count = _document_token_count(cursor, run_id, document_id)
    document_filter = """
        JOIN execution.semantic_pnf_demand AS demand
          ON demand.demand_id = candidate.demand_id
        JOIN execution.semantic_pnf_region AS region
          ON region.region_id = demand.source_region_id
       WHERE region.run_id = %s AND region.document_id = %s
    """

    n_input = _count(
        cursor,
        """
        SELECT count(*)
          FROM execution.semantic_pnf_object AS object
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = object.region_id
         WHERE region.run_id = %s AND region.document_id = %s
        """,
        params,
    )
    n_generated = _count(
        cursor,
        "SELECT count(*) FROM execution.semantic_pnf_demand_candidate_observation AS candidate "
        + document_filter,
        params,
    )
    n_retained = _count(
        cursor,
        "SELECT count(*) FROM execution.semantic_pnf_candidate_state_v1 AS candidate "
        + document_filter
        + " AND candidate.active AND candidate.admissible",
        params,
    )
    n_output = _count(
        cursor,
        """
        SELECT count(*)
          FROM execution.semantic_pnf_factor_derivation AS derivation
          JOIN execution.semantic_pnf_factor_derivation_premise AS premise
            ON premise.derivation_id = derivation.derivation_id
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = premise.factor_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = factor.region_id
         WHERE region.run_id = %s AND region.document_id = %s
           AND derivation.epistemic_level = 3
           AND derivation.derivation_state = 2
        """,
        params,
    )

    query = """
        SELECT count(*)
          FROM execution.semantic_pnf_candidate_horizon_state_v1 AS candidate
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = candidate.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = demand.source_region_id
         WHERE region.run_id = %s AND region.document_id = %s
           AND candidate.horizon = 9
           AND candidate.admissible
    """
    work_units, wall_us = _timed_count(cursor, query, params)
    explain_us = _explain_microseconds(cursor, query, params)
    stage = BenchmarkTuple(
        workload_ref=workload_ref,
        stage_name="reopenable_progressive_resolution_h9",
        token_count=token_count,
        n_input=n_input,
        n_generated=n_generated,
        n_retained=n_retained,
        n_output=n_output,
        work_units=work_units,
        peak_memory_bytes=None,
        elapsed_microseconds=max(wall_us, explain_us),
    )

    universe_units = _count(
        cursor,
        """
        SELECT count(*)
          FROM execution.semantic_pnf_global_lookup AS lookup
         WHERE lookup.run_id = %s AND lookup.document_id = %s
        """,
        params,
    )
    frontier_query = """
        SELECT count(*)
          FROM execution.semantic_pnf_demand_candidate AS candidate
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = candidate.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = demand.source_region_id
         WHERE region.run_id = %s AND region.document_id = %s
    """
    frontier_units, probe_us = _timed_count(cursor, frontier_query, params)
    retrieval = RetrievalReduction(
        workload_ref=workload_ref,
        retrieval_kind="exact_numeric_demand_frontier",
        universe_units=universe_units,
        frontier_units=frontier_units,
        reduction_ratio=(frontier_units / universe_units if universe_units else None),
        probe_microseconds=probe_us,
        downstream_work_units=work_units,
    )

    cursor.execute(
        """
        SELECT count(*),
               COALESCE(sum(fanout.support_edges), 0),
               max(fanout.support_fanout),
               avg(fanout.support_fanout)
          FROM execution.semantic_pnf_structural_support_fanout_v1 AS fanout
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = fanout.object_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = object.region_id
         WHERE region.run_id = %s AND region.document_id = %s
        """,
        params,
    )
    argument_objects, support_edges, maximum_fanout, average_fanout = cursor.fetchone()
    support = SupportFanout(
        argument_objects=int(argument_objects or 0),
        support_edges=int(support_edges or 0),
        maximum_fanout=float(maximum_fanout) if maximum_fanout is not None else None,
        average_fanout=float(average_fanout) if average_fanout is not None else None,
    )
    return (stage,), (retrieval,), support


def persist(
    cursor: Any,
    stages: tuple[BenchmarkTuple, ...],
    retrievals: tuple[RetrievalReduction, ...],
) -> None:
    for stage in stages:
        measurement_ref = f"benchmark:{stage.workload_ref}:{stage.stage_name}"
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_runtime_stage_measurement
                (measurement_ref, workload_ref, stage_name,
                 input_units, generated_units, retained_units, output_units,
                 work_units, elapsed_microseconds, peak_memory_bytes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (measurement_ref) DO UPDATE SET
                input_units=EXCLUDED.input_units,
                generated_units=EXCLUDED.generated_units,
                retained_units=EXCLUDED.retained_units,
                output_units=EXCLUDED.output_units,
                work_units=EXCLUDED.work_units,
                elapsed_microseconds=EXCLUDED.elapsed_microseconds,
                peak_memory_bytes=EXCLUDED.peak_memory_bytes
            """,
            (
                measurement_ref, stage.workload_ref, stage.stage_name,
                stage.n_input, stage.n_generated, stage.n_retained, stage.n_output,
                stage.work_units, stage.elapsed_microseconds, stage.peak_memory_bytes,
            ),
        )
    for retrieval in retrievals:
        measurement_ref = f"benchmark:{retrieval.workload_ref}:{retrieval.retrieval_kind}"
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_retrieval_measurement
                (measurement_ref, workload_ref, retrieval_kind,
                 universe_units, frontier_units, probe_microseconds,
                 downstream_work_units, exact_downstream_required)
            VALUES (%s, %s, 1, %s, %s, %s, %s, TRUE)
            ON CONFLICT (measurement_ref) DO UPDATE SET
                universe_units=EXCLUDED.universe_units,
                frontier_units=EXCLUDED.frontier_units,
                probe_microseconds=EXCLUDED.probe_microseconds,
                downstream_work_units=EXCLUDED.downstream_work_units
            """,
            (
                measurement_ref, retrieval.workload_ref,
                retrieval.universe_units, retrieval.frontier_units,
                retrieval.probe_microseconds, retrieval.downstream_work_units,
            ),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--document-id", required=True, type=int)
    parser.add_argument("--workload-ref", required=True)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            stages, retrievals, support = collect(
                cursor,
                run_id=args.run_id,
                document_id=args.document_id,
                workload_ref=args.workload_ref,
            )
            if args.persist:
                persist(cursor, stages, retrievals)
        if args.persist:
            connection.commit()
        else:
            connection.rollback()

    print(json.dumps({
        "stage_measurements": [
            {**asdict(stage), "tokens_per_second": stage.tokens_per_second,
             "work_per_token": stage.work_per_token}
            for stage in stages
        ],
        "retrieval_reduction": [asdict(item) for item in retrievals],
        "structural_support_fanout": asdict(support),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
