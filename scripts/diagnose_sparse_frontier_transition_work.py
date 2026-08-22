from __future__ import annotations

import argparse
import json
from pathlib import Path

from diagnose_sparse_frontier_actor_retention_work import actor_retention_work_receipt
from diagnose_sparse_frontier_candidate_work import candidate_work_receipt
from diagnose_sparse_frontier_rewrite_work import rewrite_work_receipt


CONTRACT_REF = "sensiblaw.sparse-frontier-transition-work-diagnostic.v0_3"


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def transition_work_receipt(
    database_url: str,
    interface_id: int,
    *,
    plan_mode: str = "analyze",
    statement_timeout_ms: int = 0,
) -> dict[str, object]:
    """Measure M179 retention, M178 candidate/ranking, and rewrite amplification.

    This is deliberately a read-only diagnostic surface.  It does not install a
    migration and does not claim that the finite-mask counterfactual is already
    a production implementation.  The child receipts expose enough detail to
    choose the next optimisation from measured fanout, ranking and rewrite
    costs rather than final relation cardinality alone.
    """

    candidate = candidate_work_receipt(
        database_url,
        interface_id,
        plan_mode=plan_mode,
        statement_timeout_ms=statement_timeout_ms,
    )
    retention = actor_retention_work_receipt(
        database_url,
        interface_id,
        plan_mode=plan_mode,
        statement_timeout_ms=statement_timeout_ms,
    )
    rewrite = rewrite_work_receipt(database_url, interface_id)

    candidate_decision = dict(candidate["decision_surface"])
    retention_decision = dict(retention["decision_surface"])

    candidate_rewrite_rows = int(candidate["rewrite"]["candidate_rows_rewritten_by_canonical"])
    candidate_delta_rows = int(candidate["rewrite"]["candidate_semantic_delta_rows"])
    other_rewrite_rows = int(
        rewrite["totals_without_candidate_table"]["canonical_rewrite_rows"]
    )
    other_delta_rows = int(
        rewrite["totals_without_candidate_table"]["semantic_delta_rows"]
    )
    total_rewrite_rows = candidate_rewrite_rows + other_rewrite_rows
    total_semantic_delta_rows = candidate_delta_rows + other_delta_rows

    next_targets: list[str] = []
    if retention_decision.get("composite_signature_candidate"):
        next_targets.append("actor_retention_conjunctive_exposure")
    if candidate_decision.get("conjunctive_exposure_candidate"):
        next_targets.append("object_candidate_conjunctive_exposure")
    if candidate_decision.get("top_k_candidate"):
        next_targets.append("bounded_top_k_ranking")
    if total_rewrite_rows > total_semantic_delta_rows:
        next_targets.append("incremental_candidate_and_resolution_lifecycle")
    if candidate_decision.get("wildcard_dominant") or retention_decision.get(
        "wildcard_dominant"
    ):
        next_targets.append("upstream_constraint_quality_or_irreducible_wildcard")

    return {
        "contract_ref": CONTRACT_REF,
        "interface_id": interface_id,
        "plan_mode": plan_mode,
        "candidate": candidate,
        "actor_retention": retention,
        "rewrite": rewrite,
        "combined_rewrite": {
            "canonical_rows_rewritten": total_rewrite_rows,
            "semantic_delta_rows": total_semantic_delta_rows,
            "beta_write_rows_per_semantic_delta": _ratio(
                total_rewrite_rows, total_semantic_delta_rows
            ),
            "beta_write_is_unbounded_for_zero_delta": (
                total_semantic_delta_rows == 0 and total_rewrite_rows > 0
            ),
        },
        "next_round_decision_surface": {
            "ranked_targets": next_targets,
            "candidate_direct_helper_cardinality_parity": candidate["exposure"][
                "direct_helper_cardinality_parity"
            ],
            "retention_helper_composite_cardinality_parity": retention[
                "decision_surface"
            ]["helper_composite_cardinality_parity"],
            "requires_sql_change_this_round": False,
        },
        "semantics": (
            "combined read-only receipt for extensional parity versus physical exposure/materialization/rewrite; "
            "use actual EXPLAIN ANALYZE temp/buffer metrics plus multiplicity and semantic-delta ratios to choose the next SQL optimisation"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--interface-id", required=True, type=int)
    parser.add_argument(
        "--plan-mode",
        choices=("none", "estimate", "analyze"),
        default="analyze",
        help="analyze captures actual rows, buffers and temp spill for each expensive stage",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=0,
        help="optional PostgreSQL timeout per child diagnostic; 0 uses server default",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    receipt = transition_work_receipt(
        args.database_url,
        args.interface_id,
        plan_mode=args.plan_mode,
        statement_timeout_ms=args.statement_timeout_ms,
    )
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
