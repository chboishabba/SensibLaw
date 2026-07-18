"""Canonical operational assembly for local PNF reference binding."""

from __future__ import annotations

from typing import Any, Mapping

from .binding_candidate_sets import compact_binding_artifacts
from .reference_binding import (
    REFERENCE_BINDING_CONTRACT_REF,
    REFERENCE_REDUCTION_DECLARATION_REF,
    _ensure_local_binding_demands,
    _normalise_refinement_receipts,
    project_pronominal_reference_arguments,
)
from .revision_normalization import normalize_factor_revision_artifacts


def build_operational_reference_binding_artifacts(
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Build canonical set-valued local binding artifacts.

    The order is deliberate:

    1. project parser-observed pronominal arguments into PNF;
    2. migrate legacy refinement identities before candidate build keys exist;
    3. generate candidate sets directly from normalized graph indexes;
    4. remove only the retired pairwise compatibility carrier;
    5. normalize resulting factor revisions/refinement/demand identities again;
    6. add any missing local set-bound demands.
    """

    projected = project_pronominal_reference_arguments(artifacts)
    normalized_input = normalize_factor_revision_artifacts(projected)
    pairwise_binding_evidence_refs = {
        str(row.get("evidence_ref") or "")
        for row in normalized_input.get("local_evidence") or ()
        if row.get("evidence_type") == "typed_binding_candidate"
        and row.get("evidence_ref")
    }
    original_evidence_by_factor: dict[str, set[str]] = {}
    for refinement in normalized_input.get("factor_refinements") or ():
        prior = refinement.get("prior_factor") or {}
        resulting = refinement.get("resulting_factor") or {}
        factor_ref = str(
            prior.get("factor_ref") or resulting.get("factor_ref") or ""
        )
        if not factor_ref:
            continue
        original_evidence_by_factor.setdefault(factor_ref, set()).update(
            str(ref)
            for ref in refinement.get("evidence_refs") or ()
            if str(ref) not in pairwise_binding_evidence_refs
        )
    compacted = compact_binding_artifacts(normalized_input)
    receipts = _normalise_refinement_receipts(
        compacted,
        pairwise_binding_evidence_refs=pairwise_binding_evidence_refs,
        original_evidence_by_factor=original_evidence_by_factor,
    )
    normalized_output = normalize_factor_revision_artifacts(receipts)
    completed = _ensure_local_binding_demands(normalized_output)
    completed["reference_binding_operational_contract"] = (
        REFERENCE_BINDING_CONTRACT_REF
    )
    completed["reference_binding_assembly"] = {
        "reference_reduction_declaration_ref": (
            REFERENCE_REDUCTION_DECLARATION_REF
        ),
        "revision_identity_contract": "content-addressed-factor:v0_1",
        "candidate_generation": "direct_observation_graph_index",
        "pairwise_binding_evidence_operational": False,
        "authority": "compiler_assembly_only",
    }
    return completed


build_set_valued_binding_artifacts = build_operational_reference_binding_artifacts


__all__ = [
    "REFERENCE_BINDING_CONTRACT_REF",
    "REFERENCE_REDUCTION_DECLARATION_REF",
    "build_operational_reference_binding_artifacts",
    "build_set_valued_binding_artifacts",
]
