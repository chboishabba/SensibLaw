"""Generic parser-observation to PNF reference-binding projection.

Pronouns are treated as surface realizations of incompletely bound PNF
arguments. The projection uses parser POS, dependency, morphology, and factor
role metadata only; it contains no English pronoun catalogue and no
corpus-specific vocabulary.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256

from .binding_candidate_sets import compact_binding_artifacts


REFERENCE_BINDING_CONTRACT_REF = "postgres-semantic-compiler:v0_7"
REFERENCE_REDUCTION_DECLARATION_REF = "grammar:pnf:pronominal-argument:v0_2"
_REFERENCE_TYPES = (
    "entity_reference",
    "eventuality_reference",
    "proposition_reference",
)
_LOCAL_REFERENCE_RESIDUALS = {
    "antecedent_unresolved",
    "referential_type_unresolved",
    "grammatical_subject_semantic_status_unresolved",
}


def _is_argument_factor(factor: Mapping[str, Any]) -> bool:
    factor_type = str(factor.get("factor_type") or "")
    return factor_type.startswith("semantic.argument.") or factor_type == (
        "semantic.argument_reference"
    )


def _reference_alternative(
    factor_ref: str,
    referential_type: str,
    *,
    role: str,
    morphology: Mapping[str, Any],
    relation_ref: str | None,
) -> dict[str, Any]:
    return {
        "alternative_ref": f"{factor_ref}:{referential_type}",
        "value": {
            "role": role,
            "referential_type": referential_type,
            "parser_morphology": dict(morphology),
            "relation_ref": relation_ref,
        },
        "type_ref": "semantic.reference_candidate",
        "derivation_refs": [REFERENCE_REDUCTION_DECLARATION_REF],
        "authority_state": "candidate_only",
    }


def _project_factor(factor: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    result = dict(factor)
    metadata = dict(result.get("metadata") or {})
    if not _is_argument_factor(result) or str(metadata.get("parser_pos") or "") != (
        "PRON"
    ):
        return result, False
    role = str(metadata.get("role") or "argument")
    morphology = metadata.get("parser_morphology") or {}
    relation_ref = str(metadata.get("relation_ref") or "") or None
    alternatives = [dict(row) for row in result.get("alternatives") or ()]
    existing = {
        str(row.get("alternative_ref") or "") for row in alternatives
    }
    changed = False
    for referential_type in _REFERENCE_TYPES:
        alternative = _reference_alternative(
            str(result["factor_ref"]),
            referential_type,
            role=role,
            morphology=morphology if isinstance(morphology, Mapping) else {},
            relation_ref=relation_ref,
        )
        if alternative["alternative_ref"] not in existing:
            alternatives.append(alternative)
            existing.add(alternative["alternative_ref"])
            changed = True
    if role == "subject":
        alternative = _reference_alternative(
            str(result["factor_ref"]),
            "expletive_realisation",
            role=role,
            morphology=morphology if isinstance(morphology, Mapping) else {},
            relation_ref=relation_ref,
        )
        if alternative["alternative_ref"] not in existing:
            alternatives.append(alternative)
            changed = True
    residuals = set(str(row) for row in result.get("residuals") or ())
    prior_residuals = set(residuals)
    residuals.update({"antecedent_unresolved", "referential_type_unresolved"})
    if role == "subject":
        residuals.add("grammatical_subject_semantic_status_unresolved")
    if residuals != prior_residuals:
        changed = True
    metadata["reference_reduction_declaration_ref"] = (
        REFERENCE_REDUCTION_DECLARATION_REF
    )
    dependency = str(metadata.get("parser_dependency") or "")
    if dependency == "expl":
        metadata["expletive_observation_ref"] = (
            "parser-structural-evidence:dependency-expl"
        )
    result.update(
        {
            "alternatives": sorted(
                alternatives,
                key=lambda row: str(row.get("alternative_ref") or ""),
            ),
            "residuals": sorted(residuals),
            "closure_state": "requires_external_resolution",
            "metadata": metadata,
        }
    )
    return result, changed


def _project_graph(graph: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    factors: list[dict[str, Any]] = []
    changed_count = 0
    for factor in graph.get("factors") or ():
        projected, changed = _project_factor(factor)
        factors.append(projected)
        changed_count += int(changed)
    result = dict(graph)
    result["factors"] = sorted(
        factors, key=lambda row: str(row.get("factor_ref") or "")
    )
    if changed_count:
        result["graph_ref"] = "pnf-graph:" + canonical_sha256(
            {
                "document_ref": result.get("document_ref"),
                "factors": result["factors"],
                "constraints": result.get("constraints") or (),
                "reference_reduction_declaration_ref": (
                    REFERENCE_REDUCTION_DECLARATION_REF
                ),
            }
        )
    return result, changed_count


def project_pronominal_reference_arguments(
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Project parser-derived pronominal arguments into PartialPNF branches."""

    if artifacts.get("reference_binding_operational_contract") == (
        REFERENCE_BINDING_CONTRACT_REF
    ):
        return dict(artifacts)
    result = dict(artifacts)
    pnf_graph, base_changes = _project_graph(artifacts.get("pnf_graph") or {})
    refined_graph, refined_changes = _project_graph(
        artifacts.get("refined_pnf_graph") or pnf_graph
    )
    result["pnf_graph"] = pnf_graph
    result["refined_pnf_graph"] = refined_graph
    declarations = [
        dict(row) for row in artifacts.get("compiler_declarations") or ()
    ]
    declaration = {
        "declaration_ref": REFERENCE_REDUCTION_DECLARATION_REF,
        "declaration_kind": "grammar",
        "input": "parser_observed_pronominal_argument",
        "outputs": [
            "semantic.reference_candidate",
            "antecedent_unresolved",
            "referential_type_unresolved",
            "grammatical_subject_semantic_status_unresolved",
        ],
        "prohibited": [
            "lexical_pronoun_catalogue",
            "antecedent_selection",
            "identity_closure",
            "event_occurrence_closure",
            "proposition_truth_evaluation",
        ],
        "authority": "configuration_only",
    }
    if not any(
        row.get("declaration_ref") == REFERENCE_REDUCTION_DECLARATION_REF
        for row in declarations
    ):
        declarations.append(declaration)
    result["compiler_declarations"] = sorted(
        declarations, key=lambda row: str(row.get("declaration_ref") or "")
    )
    result["reference_binding_operational_contract"] = (
        REFERENCE_BINDING_CONTRACT_REF
    )
    result["reference_argument_projection_summary"] = {
        "base_factor_changes": base_changes,
        "refined_factor_changes": refined_changes,
        "reference_reduction_declaration_ref": (
            REFERENCE_REDUCTION_DECLARATION_REF
        ),
        "english_pronoun_catalogue_used": False,
        "authority": "diagnostic_only",
    }
    return result


def _ensure_local_binding_demands(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(artifacts)
    refined_graph = artifacts.get("refined_pnf_graph") or {}
    factors = {
        str(row["factor_ref"]): row
        for row in refined_graph.get("factors") or ()
    }
    demands = [dict(row) for row in artifacts.get("resolution_demands") or ()]
    local_by_factor = {
        str(row.get("factor_ref") or "")
        for row in demands
        if row.get("budget") == "bounded_document_local_evidence"
    }
    for factor_ref, factor in sorted(factors.items()):
        candidate_set_refs = sorted(
            {
                str((alternative.get("value") or {}).get("candidate_set_ref") or "")
                for alternative in factor.get("alternatives") or ()
                if alternative.get("type_ref") == "semantic.binding_candidate_set"
                and isinstance(alternative.get("value"), Mapping)
                and (alternative.get("value") or {}).get("candidate_set_ref")
            }
        )
        if not candidate_set_refs or factor_ref in local_by_factor:
            continue
        residuals = sorted(
            set(str(row) for row in factor.get("residuals") or ()).intersection(
                _LOCAL_REFERENCE_RESIDUALS
            )
        )
        if not residuals:
            continue
        metadata = dict(factor.get("metadata") or {})
        factor_revision_ref = str(
            metadata.get("factor_revision_ref")
            or "factor-revision:"
            + canonical_sha256(factor)
        )
        alternatives = sorted(
            str(row.get("type_ref") or "")
            for row in factor.get("alternatives") or ()
        )
        constraints = [
            dict(row) for row in factor.get("constraints") or ()
        ]
        semantic_key = {
            "document_ref": refined_graph.get("document_ref"),
            "factor_ref": factor_ref,
            "factor_revision_ref": factor_revision_ref,
            "factor_type": factor.get("factor_type"),
            "subject_kind": factor.get("factor_type"),
            "formal_role": metadata.get("role"),
            "expected_type_alternatives": alternatives,
            "residuals": residuals,
            "constraints": constraints,
            "candidate_set_refs": candidate_set_refs,
        }
        demands.append(
            {
                "schema_version": "sl.factor_resolution_demand.v0_1",
                "demand_ref": "demand:" + canonical_sha256(semantic_key),
                "graph_ref": refined_graph.get("graph_ref"),
                "factor_ref": factor_ref,
                "factor_revision_ref": factor_revision_ref,
                "factor_type": factor.get("factor_type"),
                "subject_kind": factor.get("factor_type"),
                "formal_role": metadata.get("role"),
                "expected_type_alternatives": alternatives,
                "requested_facets": residuals,
                "candidate_set_refs": candidate_set_refs,
                "temporal_spatial_constraints": [],
                "document_scope": refined_graph.get("document_ref"),
                "closure_impact": "document_local_binding_set_refinement",
                "coverage_impact": "typed_candidate_refinement",
                "budget": "bounded_document_local_evidence",
                "semantic_key": semantic_key,
                "authority": "candidate_only",
            }
        )
    result["resolution_demands"] = sorted(
        demands, key=lambda row: str(row.get("demand_ref") or "")
    )
    return result


def build_set_valued_binding_artifacts(
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the complete generic local reference-binding operational surface."""

    projected = project_pronominal_reference_arguments(artifacts)
    compacted = compact_binding_artifacts(projected)
    return _ensure_local_binding_demands(compacted)


__all__ = [
    "REFERENCE_BINDING_CONTRACT_REF",
    "REFERENCE_REDUCTION_DECLARATION_REF",
    "build_set_valued_binding_artifacts",
    "project_pronominal_reference_arguments",
]
