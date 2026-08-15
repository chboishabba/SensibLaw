#!/usr/bin/env python3
"""Report token-normalised corpus learning and cumulative scale curves."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from typing import Any

import psycopg


@dataclass(frozen=True, slots=True)
class LearningPoint:
    measurement_id: int
    workload_ref: str
    document_id: int | None
    token_count: int
    total_work_per_token: float
    unresolved_work_per_token: float
    previous_unresolved_work_per_token: float | None
    unresolved_work_per_token_nonincreasing: bool | None
    reused_lexical_units: int
    reused_entity_units: int
    reused_external_units: int


@dataclass(frozen=True, slots=True)
class CumulativeScalePoint:
    document_count: int
    token_count: int
    semantic_work: int
    elapsed_microseconds: int
    work_per_token: float | None
    tokens_per_second: float | None


def collect(
    cursor: Any, workload_ref: str | None
) -> tuple[tuple[LearningPoint, ...], tuple[CumulativeScalePoint, ...]]:
    where = "WHERE workload_ref=%s" if workload_ref else ""
    params = (workload_ref,) if workload_ref else ()
    cursor.execute(
        f"""
        SELECT measurement_id,workload_ref,document_id,token_count,
               total_work_per_token,unresolved_work_per_token,
               previous_unresolved_work_per_token,
               unresolved_work_per_token_nonincreasing,
               reused_lexical_units,reused_entity_units,reused_external_units
          FROM execution.semantic_pnf_corpus_learning_curve_v1
          {where}
         ORDER BY measurement_id
        """,  # noqa: S608 - the only interpolation is a fixed WHERE fragment
        params,
    )
    points = tuple(
        LearningPoint(
            measurement_id=int(row[0]),
            workload_ref=str(row[1]),
            document_id=int(row[2]) if row[2] is not None else None,
            token_count=int(row[3]),
            total_work_per_token=float(row[4]),
            unresolved_work_per_token=float(row[5]),
            previous_unresolved_work_per_token=float(row[6])
            if row[6] is not None
            else None,
            unresolved_work_per_token_nonincreasing=bool(row[7])
            if row[7] is not None
            else None,
            reused_lexical_units=int(row[8]),
            reused_entity_units=int(row[9]),
            reused_external_units=int(row[10]),
        )
        for row in cursor.fetchall()
    )

    cumulative: list[CumulativeScalePoint] = []
    tokens = work = elapsed = 0
    for ordinal, point in enumerate(points, start=1):
        tokens += point.token_count
        # Recover exact total work through the measured per-token value; the DB
        # query below is used to avoid roundoff for emitted scale summaries.
        cursor.execute(
            """
            SELECT fixed_numeric_work+unresolved_resolution_work,elapsed_microseconds
              FROM execution.semantic_pnf_corpus_reuse_measurement
             WHERE measurement_id=%s
            """,
            (point.measurement_id,),
        )
        row = cursor.fetchone()
        work += int(row[0])
        elapsed += int(row[1])
        cumulative.append(
            CumulativeScalePoint(
                document_count=ordinal,
                token_count=tokens,
                semantic_work=work,
                elapsed_microseconds=elapsed,
                work_per_token=work / tokens if tokens else None,
                tokens_per_second=(tokens * 1_000_000 / elapsed) if elapsed else None,
            )
        )
    return points, tuple(cumulative)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--workload-ref")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            learning, cumulative = collect(cursor, args.workload_ref)
    print(
        json.dumps(
            {
                "learning_curve": [asdict(point) for point in learning],
                "cumulative_scale_curve": [asdict(point) for point in cumulative],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
