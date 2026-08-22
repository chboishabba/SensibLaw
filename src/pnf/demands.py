"""Backend-free demand projection from open PNF factors.

Demand provenance is authored here while the factor's typed role bindings are
still available.  Trigger, target, and evidence occurrences are deliberately
kept distinct; downstream persistence must not recover a target from lexical
similarity, neighbourhood, or entity-span containment.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256

from .graph import PNFGraph


# These are semantic role contracts of the current generic operator factors,
# not lexical repair rules.  Producers with an explicit metadata declaration
# override them below; absence of a target role remains unresolved.
_TRIGGER_ROLE_BY_FACTOR_TYPE = {
    "semantic.normative_relation": "conduct",
    "semantic.legal_condition": "condition",
    "semantic.legal_exception": "exception",
    "semantic.legal_transition": "transition",
}
_TARGET_ROLE_BY_RESIDUAL = {
    "legal_object_identity_unresolved": "legal_object",
    "condition_attachment_unresolved": "host",
    "exception_attachment_unresolved": "host",
    "norm_bearer_unresolved": "bearer",
}


def _role_contract(
    metadata: Mapping[str, Any], factor_type: str
) -> tuple[str | None, dict[str, str]]:
    trigger_role = metadata.get("demand_trigger_role")
    if trigger_role is None:
        trigger_role = _TRIGGER_ROLE_BY_FACTOR_TYPE.get(factor_type)
    declared_targets = metadata.get("demand_target_roles")
    target_roles = (
        {str(key): str(value) for key, value in declared_targets.items()}
        if isinstance(declared_targets, Mapping)
        else dict(_TARGET_ROLE_BY_RESIDUAL)
    )
    return (str(trigger_role) if trigger_role else None, target_roles)


def _occurrence_provenance(
    *,
    factor_type: str,
    metadata: Mapping[str, Any],
    requested_facets: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    role_bindings = {
        str(role): str(token_ref)
        for role, token_ref in (metadata.get("role_bindings") or {}).items()
        if str(role) and str(token_ref)
    }
    provenance_refs = tuple(
        sorted(
            {
                str(value)
                for value in metadata.get("provenance_refs") or ()
                if str(value)
            }
        )
    )
    trigger_role, target_roles = _role_contract(metadata, factor_type)
    trigger_ref = role_bindings.get(trigger_role or "")
    producer_ref = str(
        metadata.get("composition_contract_ref")
        or metadata.get("producer_contract")
        or "pnf-demand-role-contract:v1"
    )

    rows: list[dict[str, Any]] = []
    for residual_type in requested_facets:
        target_role = target_roles.get(residual_type)
        target_ref = role_bindings.get(target_role or "")
        if trigger_ref:
            rows.append(
                {
                    "residual_type": residual_type,
                    "occurrence_role": "trigger",
                    "semantic_role": trigger_role,
                    "parser_token_ref": trigger_ref,
                    "producer_ref": producer_ref,
                }
            )
        if target_ref:
            rows.append(
                {
                    "residual_type": residual_type,
                    "occurrence_role": "target",
                    "semantic_role": target_role,
                    "parser_token_ref": target_ref,
                    "producer_ref": producer_ref,
                }
            )
        excluded = {value for value in (trigger_ref, target_ref) if value}
        for ordinal, token_ref in enumerate(
            value for value in provenance_refs if value not in excluded
        ):
            rows.append(
                {
                    "residual_type": residual_type,
                    "occurrence_role": "evidence",
                    "semantic_role": None,
                    "parser_token_ref": token_ref,
                    "ordinal": ordinal,
                    "producer_ref": producer_ref,
                }
            )
    return tuple(rows)


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
                    "schema_version": "sl.factor_resolution_demand.v0_2",
                    "demand_ref": f"demand:{canonical_sha256(semantic_key)}",
                    "graph_ref": graph.graph_ref,
                    "factor_ref": factor.factor_ref,
                    "factor_revision_ref": factor_revision_ref,
                    "factor_type": factor.factor_type,
                    "subject_kind": subject_kind,
                    "formal_role": formal_role,
                    "expected_type_alternatives": list(alternatives),
                    "requested_facets": list(requested_facets),
                    "occurrence_provenance": list(
                        _occurrence_provenance(
                            factor_type=factor.factor_type,
                            metadata=metadata,
                            requested_facets=requested_facets,
                        )
                    ),
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
