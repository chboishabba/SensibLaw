"""Backend-free demand projection from open PNF factors."""

from __future__ import annotations

from typing import Any

from src.policy.carriers.canonical import canonical_sha256

from .graph import PNFGraph


def derive_resolution_demands(graph: PNFGraph) -> tuple[dict[str, Any], ...]:
    demands: list[dict[str, Any]] = []
    for factor in sorted(graph.factors, key=lambda row: row.factor_ref):
        if not factor.residuals or factor.closure_state in {"closed", "not_required"}:
            continue
        semantic_key = {
            "document_ref": graph.document_ref,
            "factor_ref": factor.factor_ref,
            "factor_type": factor.factor_type,
            "residuals": sorted(factor.residuals),
            "constraint_refs": sorted(
                constraint.constraint_ref for constraint in factor.constraints
            ),
        }
        demands.append(
            {
                "schema_version": "sl.factor_resolution_demand.v0_1",
                "demand_ref": f"demand:{canonical_sha256(semantic_key)}",
                "graph_ref": graph.graph_ref,
                "factor_ref": factor.factor_ref,
                "factor_type": factor.factor_type,
                "requested_facets": sorted(factor.residuals),
                "semantic_key": semantic_key,
                "authority": "candidate_only",
            }
        )
    return tuple(demands)
