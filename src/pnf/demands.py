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
        alternatives = tuple(sorted(item.type_ref for item in factor.alternatives))
        metadata = dict(factor.metadata)
        factor_revision_ref = str(
            metadata.get("factor_revision_ref")
            or "factor-revision:" + canonical_sha256(factor.to_dict())
        )
        subject_kind = str(
            metadata.get("resolution_subject_kind") or factor.factor_type
        )
        formal_role = metadata.get("role")
        constraints = tuple(
            constraint.to_dict()
            for constraint in sorted(
                factor.constraints, key=lambda value: value.constraint_ref
            )
        )
        local_binding_residuals = {
            "antecedent_unresolved",
            "referential_type_unresolved",
            "grammatical_subject_semantic_status_unresolved",
        }
        local_facets = tuple(
            sorted(set(factor.residuals).intersection(local_binding_residuals))
        )
        remaining_facets = tuple(
            sorted(set(factor.residuals).difference(local_binding_residuals))
        )
        for requested_facets, local_only in (
            (local_facets, True),
            (remaining_facets, False),
        ):
            if not requested_facets:
                continue
            semantic_key = {
                "document_ref": graph.document_ref,
                "factor_ref": factor.factor_ref,
                "factor_revision_ref": factor_revision_ref,
                "factor_type": factor.factor_type,
                "subject_kind": subject_kind,
                "formal_role": formal_role,
                "expected_type_alternatives": alternatives,
                "residuals": requested_facets,
                "constraints": constraints,
            }
            demands.append(
                {
                    "schema_version": "sl.factor_resolution_demand.v0_1",
                    "demand_ref": f"demand:{canonical_sha256(semantic_key)}",
                    "graph_ref": graph.graph_ref,
                    "factor_ref": factor.factor_ref,
                    "factor_revision_ref": factor_revision_ref,
                    "factor_type": factor.factor_type,
                    "subject_kind": subject_kind,
                    "formal_role": formal_role,
                    "expected_type_alternatives": list(alternatives),
                    "requested_facets": list(requested_facets),
                    "temporal_spatial_constraints": [
                        item
                        for item in constraints
                        if item["constraint_type"]
                        in {"temporal_constraint", "spatial_constraint"}
                    ],
                    "document_scope": graph.document_ref,
                    "closure_impact": (
                        "document_local_binding_refinement"
                        if local_only
                        else "factor_residual_reduction"
                    ),
                    "coverage_impact": "typed_candidate_refinement",
                    "budget": (
                        "bounded_document_local_evidence"
                        if local_only
                        else "bounded_external_evidence"
                    ),
                    "semantic_key": semantic_key,
                    "authority": "candidate_only",
                }
            )
    return tuple(demands)
