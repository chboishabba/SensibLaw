"""Characterize nearest-profile ties blocking bounded wildcard admission.

This is a read-only audit.  It does not choose a representative, add a
tie-breaker, or compare a changed survivor relation.  The bounded wildcard
probe fails closed because the legacy deduplication order leaves ties between
profile rows for the same object unspecified.  This audit records whether
those ties are score-only, how wide the score ambiguity is, and whether the
rows differ in producer coordinates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from diagnose_sparse_frontier_candidate_work import _OBJECT_DEMAND
from src.storage.postgres.spacy_parser_model import connect


CONTRACT_REF = "sensiblaw.sparse-frontier-wildcard-tie-diagnostic.v0_1"


def _profile_cte() -> str:
    return """
profile AS MATERIALIZED (
    SELECT object_id,
           object_kind_symbol_id,
           role_symbol_id,
           factor_type_symbol_id,
           predicate_symbol_id,
           last_end_char,
           promotion_score
             + ln(1 + occurrence_count)::DOUBLE PRECISION AS candidate_score
      FROM execution.semantic_pnf_actor_profile
     WHERE interface_id = %s
),
nearest AS MATERIALIZED (
    SELECT profile.*
      FROM profile
      JOIN (
          SELECT object_id, max(last_end_char) AS last_end_char
            FROM profile
           GROUP BY object_id
      ) AS maxima
        USING (object_id, last_end_char)
),
groups AS MATERIALIZED (
    SELECT object_id,
           count(*)::BIGINT AS nearest_rows,
           count(DISTINCT candidate_score)::BIGINT AS score_values,
           count(DISTINCT (
               object_kind_symbol_id,
               role_symbol_id,
               factor_type_symbol_id,
               predicate_symbol_id
           ))::BIGINT AS coordinate_values,
           min(candidate_score) AS min_score,
           max(candidate_score) AS max_score
      FROM nearest
     GROUP BY object_id
)
"""


def _summary_sql() -> str:
    return f"""
WITH {_profile_cte()}
SELECT count(*) FILTER (WHERE nearest_rows > 1)::BIGINT,
       coalesce(sum(nearest_rows) FILTER (WHERE nearest_rows > 1), 0)::BIGINT,
       count(*) FILTER (WHERE nearest_rows > 1 AND score_values = 1)::BIGINT,
       count(*) FILTER (WHERE nearest_rows > 1 AND score_values > 1)::BIGINT,
       count(*) FILTER (WHERE nearest_rows > 1 AND coordinate_values = 1)::BIGINT,
       count(*) FILTER (WHERE nearest_rows > 1 AND coordinate_values > 1)::BIGINT,
       coalesce(max(max_score - min_score) FILTER (WHERE nearest_rows > 1), 0),
       coalesce(avg(max_score - min_score) FILTER (WHERE nearest_rows > 1), 0)
  FROM groups
"""


def _sample_sql(limit: int) -> str:
    return f"""
WITH {_profile_cte()}
SELECT object_id,
       nearest_rows,
       score_values,
       coordinate_values,
       min_score,
       max_score,
       max_score - min_score AS score_spread
  FROM groups
 WHERE nearest_rows > 1
 ORDER BY score_spread DESC, object_id
 LIMIT {int(limit)}
"""


def _write(output: Path, receipt: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    if args.limit < 1:
        raise ValueError("limit must be positive")

    with connect(args.database_url) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                params = (args.interface_id,)
                cursor.execute(_summary_sql(), params)
                summary = cursor.fetchone()
                cursor.execute(_sample_sql(args.limit), params)
                samples = cursor.fetchall()

    receipt = {
        "contract_ref": CONTRACT_REF,
        "interface_id": args.interface_id,
        "provider_io_performed": False,
        "semantic_mutation_performed": False,
        "summary": {
            "ambiguous_objects": int(summary[0]),
            "ambiguous_nearest_rows": int(summary[1]),
            "score_tied_objects": int(summary[2]),
            "score_ambiguous_objects": int(summary[3]),
            "coordinate_identical_objects": int(summary[4]),
            "coordinate_ambiguous_objects": int(summary[5]),
            "maximum_score_spread": float(summary[6]),
            "mean_score_spread": float(summary[7]),
        },
        "samples": [
            {
                "object_id": int(row[0]),
                "nearest_rows": int(row[1]),
                "score_values": int(row[2]),
                "coordinate_values": int(row[3]),
                "min_score": float(row[4]),
                "max_score": float(row[5]),
                "score_spread": float(row[6]),
            }
            for row in samples
        ],
    }
    _write(args.output, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
