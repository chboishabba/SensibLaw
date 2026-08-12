#!/usr/bin/env python3
"""Report the numeric PNF reopenable-runtime observatory for one document.

This CLI is read-only.  It deliberately reports proof, preference, execution,
open-world and cost surfaces separately so a compact execution frontier cannot
be mistaken for semantic closure.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from typing import Any

import psycopg


@dataclass(frozen=True, slots=True)
class RuntimeObservatory:
    run_id: int
    document_id: int
    identity_factor_alignment: dict[str, int]
    unexplained_identity_factor_percent: float
    typed_demand_funnel: dict[str, int]
    horizon_escalation: dict[str, Any]
    pqro: dict[str, int]
    compression_relevance: dict[str, Any]
    supported_l3_yield: dict[str, int | float]
    parser_post_parser_ratio: float | None


def _scalar(cursor: Any, sql: str, params: tuple[Any, ...]) -> int:
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return int(row[0] or 0)


def collect(cursor: Any, *, run_id: int, document_id: int) -> RuntimeObservatory:
    cursor.execute(
        """
        SELECT alignment_class, projection_count
          FROM execution.semantic_pnf_identity_factor_alignment_summary_v1
         WHERE run_id = %s AND document_id = %s
        """,
        (run_id, document_id),
    )
    alignment = {str(name): int(count) for name, count in cursor.fetchall()}
    total_projection = sum(alignment.values())
    unexplained = alignment.get("same_region_unbridged", 0) + alignment.get(
        "no_structural_bridge", 0
    )
    unexplained_percent = (
        100.0 * unexplained / total_projection if total_projection else 0.0
    )

    cursor.execute(
        """
        SELECT
            count(*) AS demand_count,
            count(*) FILTER (WHERE represented_candidate_count > 0),
            count(*) FILTER (WHERE active_candidate_count > 0),
            count(*) FILTER (WHERE residual_candidate_count > 0),
            count(*) FILTER (WHERE refuted_candidate_count > 0),
            count(*) FILTER (WHERE evidence_count > 0),
            count(*) FILTER (WHERE admitted_identity_witness_count > 0),
            count(*) FILTER (WHERE outside_model_possible),
            count(*) FILTER (WHERE resource_limited)
          FROM execution.semantic_pnf_demand_funnel_v1
         WHERE run_id = %s AND document_id = %s
        """,
        (run_id, document_id),
    )
    row = cursor.fetchone()
    funnel = dict(
        zip(
            (
                "demands",
                "with_represented_candidates",
                "with_active_candidates",
                "with_residual_candidates",
                "with_refuted_candidates",
                "with_evidence",
                "with_admitted_identity_witness",
                "outside_model_possible",
                "resource_limited",
            ),
            (int(value or 0) for value in row),
            strict=True,
        )
    )

    cursor.execute(
        """
        SELECT escalation.fibre_cardinality_invariant,
               count(*) FILTER (WHERE COALESCE(escalation.h3_evidenced, 0) > 0),
               count(*) FILTER (WHERE COALESCE(escalation.h6_evidenced, 0) > 0),
               count(*) FILTER (WHERE COALESCE(escalation.h9_evidenced, 0) > 0),
               count(*) FILTER (WHERE COALESCE(escalation.h3_preferred, 0) > 0),
               count(*) FILTER (WHERE COALESCE(escalation.h6_preferred, 0) > 0),
               count(*) FILTER (WHERE COALESCE(escalation.h9_preferred, 0) > 0)
          FROM execution.semantic_pnf_horizon_escalation_v1 AS escalation
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = escalation.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = demand.source_region_id
         WHERE region.run_id = %s AND region.document_id = %s
         GROUP BY escalation.fibre_cardinality_invariant
         ORDER BY escalation.fibre_cardinality_invariant DESC
        """,
        (run_id, document_id),
    )
    horizon_rows = cursor.fetchall()
    horizon = {
        "all_fibres_invariant": all(bool(row[0]) for row in horizon_rows),
        "h3_evidenced_demands": sum(int(row[1]) for row in horizon_rows),
        "h6_evidenced_demands": sum(int(row[2]) for row in horizon_rows),
        "h9_evidenced_demands": sum(int(row[3]) for row in horizon_rows),
        "h3_preferred_demands": sum(int(row[4]) for row in horizon_rows),
        "h6_preferred_demands": sum(int(row[5]) for row in horizon_rows),
        "h9_preferred_demands": sum(int(row[6]) for row in horizon_rows),
    }

    cursor.execute(
        """
        SELECT
            count(*) FILTER (WHERE state.active AND state.admissible) AS p,
            count(*) FILTER (
                WHERE state.represented_possible AND NOT state.active
                  AND state.admissible
            ) AS q,
            COALESCE(sum(open_world.represented_residual_count), 0) AS r,
            count(*) FILTER (WHERE open_world.outside_model_possible) AS o
          FROM execution.semantic_pnf_candidate_state_v1 AS state
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = state.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = demand.source_region_id
          JOIN execution.semantic_pnf_demand_open_world_state AS open_world
            ON open_world.demand_id = demand.demand_id
         WHERE region.run_id = %s AND region.document_id = %s
        """,
        (run_id, document_id),
    )
    p, q, r, o = cursor.fetchone()
    pqro = {"P": int(p or 0), "Q": int(q or 0), "R": int(r or 0), "O": int(o or 0)}

    cursor.execute(
        """
        WITH latest AS (
            SELECT DISTINCT ON (accounting.demand_id, accounting.consumer_ref,
                                accounting.mass_kind, accounting.horizon)
                   accounting.*
              FROM execution.semantic_pnf_demand_relevance_accounting AS accounting
              JOIN execution.semantic_pnf_demand AS demand
                ON demand.demand_id = accounting.demand_id
              JOIN execution.semantic_pnf_region AS region
                ON region.region_id = demand.source_region_id
             WHERE region.run_id = %s AND region.document_id = %s
             ORDER BY accounting.demand_id, accounting.consumer_ref,
                      accounting.mass_kind, accounting.horizon,
                      accounting.accounting_id DESC
        )
        SELECT COALESCE(sum(active_mass), 0),
               COALESCE(sum(residual_candidate_mass), 0),
               COALESCE(sum(represented_residual_mass), 0),
               COALESCE(sum(outside_model_mass), 0),
               COALESCE(sum(total_mass), 0)
          FROM latest
        """,
        (run_id, document_id),
    )
    active_mass, q_mass, r_mass, o_mass, total_mass = (
        int(value or 0) for value in cursor.fetchone()
    )
    compression = {
        "represented_candidates": total_projection,
        "active_candidates": pqro["P"],
        "active_candidate_ratio": (
            pqro["P"] / total_projection if total_projection else None
        ),
        "active_mass": active_mass,
        "residual_candidate_mass": q_mass,
        "represented_residual_mass": r_mass,
        "outside_model_mass": o_mass,
        "total_relevance_mass": total_mass,
        "retained_relevance_ratio": active_mass / total_mass if total_mass else None,
    }

    supported_derivations = _scalar(
        cursor,
        """
        SELECT count(DISTINCT support.derivation_id)
          FROM execution.semantic_pnf_factor_derivation_support AS support
          JOIN execution.semantic_pnf_factor_derivation AS derivation
            ON derivation.derivation_id = support.derivation_id
          JOIN execution.semantic_pnf_factor_derivation_premise AS premise
            ON premise.derivation_id = derivation.derivation_id
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = premise.factor_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = factor.region_id
         WHERE region.run_id = %s AND region.document_id = %s
           AND derivation.epistemic_level = 3
        """,
        (run_id, document_id),
    )
    admitted_witnesses = _scalar(
        cursor,
        """
        SELECT count(*)
          FROM execution.semantic_pnf_identity_witness AS witness
          JOIN execution.semantic_pnf_identity_witness_admission AS admission
            ON admission.witness_id = witness.witness_id
           AND admission.admission_state = 2
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = witness.source_object_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = object.region_id
         WHERE region.run_id = %s AND region.document_id = %s
        """,
        (run_id, document_id),
    )
    supported_l3 = {
        "admitted_identity_witnesses": admitted_witnesses,
        "supported_l3_derivations": supported_derivations,
        "supported_l3_per_admitted_witness": (
            supported_derivations / admitted_witnesses if admitted_witnesses else 0.0
        ),
    }

    cursor.execute(
        """
        SELECT parser_post_parser_ratio
          FROM execution.semantic_pnf_parser_dominance_v1
         WHERE workload_ref IN (
             SELECT workload_ref
               FROM execution.semantic_pnf_runtime_stage_measurement
              ORDER BY measurement_id DESC
         )
           AND parser_post_parser_ratio IS NOT NULL
         ORDER BY workload_ref DESC
         LIMIT 1
        """
    )
    ratio_row = cursor.fetchone()
    parser_ratio = float(ratio_row[0]) if ratio_row and ratio_row[0] is not None else None

    return RuntimeObservatory(
        run_id=run_id,
        document_id=document_id,
        identity_factor_alignment=alignment,
        unexplained_identity_factor_percent=unexplained_percent,
        typed_demand_funnel=funnel,
        horizon_escalation=horizon,
        pqro=pqro,
        compression_relevance=compression,
        supported_l3_yield=supported_l3,
        parser_post_parser_ratio=parser_ratio,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--document-id", required=True, type=int)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            report = collect(cursor, run_id=args.run_id, document_id=args.document_id)
    print(json.dumps(asdict(report), indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
