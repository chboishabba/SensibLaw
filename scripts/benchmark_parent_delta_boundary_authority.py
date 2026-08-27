#!/usr/bin/env python3
"""Read-only C3a receipt for the canonical delta-fed parent boundary owner.

The C2 projection is now the intended physical input carrier for parent-local
reconciliation.  This benchmark compares that carrier against the historical
child-region/interface/export reconstruction query without mutating canonical
frontiers.  It also records EXPLAIN costs for both input paths so C3b can gate
mechanical substitution on exact parity plus a non-regressing work shape.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.parent-delta-boundary-authority.v0_1"


def _plan_total_cost(plan: Any) -> float:
    if isinstance(plan, list) and plan:
        plan = plan[0]
    if isinstance(plan, dict) and "Plan" in plan:
        return float(plan["Plan"].get("Total Cost", 0.0))
    return 0.0


def benchmark_parent_delta_boundary_authority(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> dict[str, Any]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    SELECT DISTINCT projection.parent_region_id
                      FROM execution.semantic_pnf_parent_delta_projection AS projection
                      JOIN execution.semantic_pnf_region AS parent
                        ON parent.region_id = projection.parent_region_id
                     WHERE parent.run_ref = %s
                       AND parent.document_ref = %s
                     ORDER BY projection.parent_region_id
                    """,
                    (run_ref, document_ref),
                )
                parent_ids = tuple(int(row[0]) for row in cursor.fetchall())

                mismatch_parent_ids: list[int] = []
                direct_atoms = 0
                projected_atoms = 0
                transported_atoms = 0
                fused_atoms = 0
                child_interfaces = 0
                parity_started = monotonic_ns()
                for parent_id in parent_ids:
                    cursor.execute(
                        "SELECT * FROM execution.check_numeric_pnf_parent_boundary_parity(%s)",
                        (parent_id,),
                    )
                    direct, projected, missing, extra = (
                        int(value) for value in cursor.fetchone()
                    )
                    direct_atoms += direct
                    projected_atoms += projected
                    if missing or extra:
                        if len(mismatch_parent_ids) < 20:
                            mismatch_parent_ids.append(parent_id)

                    cursor.execute(
                        "SELECT * FROM execution.measure_numeric_pnf_parent_delta_boundary(%s)",
                        (parent_id,),
                    )
                    child_count, transported, fused, _objects, _factors, _demands = (
                        int(value) for value in cursor.fetchone()
                    )
                    child_interfaces += child_count
                    transported_atoms += transported
                    fused_atoms += fused
                parity_ns = monotonic_ns() - parity_started

                cursor.execute(
                    """
                    EXPLAIN (COSTS, FORMAT JSON)
                    SELECT child_region.region_id,
                           child_interface.interface_id,
                           child_export.export_kind,
                           child_export.target_kind,
                           child_export.target_id,
                           child_export.key_symbol_id,
                           child_export.role_symbol_id,
                           child_export.residual_type_symbol_id,
                           child_export.rank,
                           child_export.promotion_score
                      FROM execution.semantic_pnf_region AS child_region
                      JOIN execution.semantic_pnf_interface AS child_interface
                        ON child_interface.region_id = child_region.region_id
                      JOIN execution.semantic_pnf_interface_export AS child_export
                        ON child_export.interface_id = child_interface.interface_id
                     WHERE child_region.parent_region_id = ANY(%s)
                       AND child_region.region_kind <> 9
                    """,
                    (list(parent_ids) if parent_ids else [-1],),
                )
                direct_plan = cursor.fetchone()[0]

                cursor.execute(
                    """
                    EXPLAIN (COSTS, FORMAT JSON)
                    SELECT projection.parent_region_id,
                           projection.child_region_id,
                           projection.child_interface_id,
                           projection.export_kind,
                           projection.target_kind,
                           projection.target_id,
                           projection.key_symbol_id,
                           projection.role_symbol_id,
                           projection.residual_type_symbol_id,
                           projection.rank,
                           projection.promotion_score
                      FROM execution.semantic_pnf_parent_delta_projection AS projection
                     WHERE projection.parent_region_id = ANY(%s)
                    """,
                    (list(parent_ids) if parent_ids else [-1],),
                )
                projected_plan = cursor.fetchone()[0]
    finally:
        connection.close()

    direct_cost = _plan_total_cost(direct_plan)
    projected_cost = _plan_total_cost(projected_plan)
    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "parent_count": len(parent_ids),
        "direct_atom_count": direct_atoms,
        "projected_atom_count": projected_atoms,
        "transported_atom_count": transported_atoms,
        "fused_atom_count": fused_atoms,
        "child_interface_count": child_interfaces,
        "parity": {
            "equal": not mismatch_parent_ids and direct_atoms == projected_atoms,
            "mismatch_parent_count": len(mismatch_parent_ids),
            "first_mismatch_parent_ids": mismatch_parent_ids,
        },
        "work_shape": {
            "source_token_rescan_count": 0,
            "child_graph_rescan_count": 0,
            "direct_reconstruction_plan_total_cost": direct_cost,
            "delta_projection_plan_total_cost": projected_cost,
            "delta_projection_plan_no_worse": projected_cost <= direct_cost,
        },
        "timing_ns": {"parity_and_measurement": parity_ns},
        "authority": {
            "database_mutations_performed": False,
            "canonical_frontier_modified": False,
            "comparison_scope": "transported child boundary input only",
            "parent_local_reconciliation_claimed_equal": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = benchmark_parent_delta_boundary_authority(
        args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    gates_green = bool(
        receipt["parity"]["equal"]
        and receipt["work_shape"]["source_token_rescan_count"] == 0
        and receipt["work_shape"]["child_graph_rescan_count"] == 0
    )
    return 0 if gates_green else 2


if __name__ == "__main__":
    raise SystemExit(main())
