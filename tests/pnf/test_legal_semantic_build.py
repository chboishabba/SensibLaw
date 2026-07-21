from __future__ import annotations

from src.pnf.legal_adjunct import LegalIRObservation
from src.pnf.legal_semantic_build import build_legal_semantic_build, normalize_legacy_witnesses


def _compilation() -> dict:
    return {
        "document_ref": "document:legal-1",
        "content_sha256": "content-1",
        "artifacts": {
            "canonical_text": "A person must not drive unless licensed.",
            "build_key_sha256": "build-key-1",
            "parser_receipt": {"parser": "shared"},
            "semantic_reduction_refs": ["grammar:shared:v1"],
            "refined_pnf_graph": {
                "graph_ref": "pnf-graph:1",
                "factors": [
                    {"factor_ref": "factor:norm", "factor_type": "semantic.normative_relation", "metadata": {"role": "predicate"}},
                    {"factor_ref": "factor:actor", "factor_type": "semantic.argument", "metadata": {"role": "bearer"}},
                    {"factor_ref": "factor:drive", "factor_type": "semantic.eventuality", "metadata": {"role": "conduct"}},
                ],
            },
        },
    }


def _legal_ir() -> tuple[LegalIRObservation, ...]:
    return (
        LegalIRObservation(
            observation_ref="legal-ir:1",
            pnf_factor_ref="factor:norm",
            pnf_revision_ref="revision:norm",
            structural_signature_ref="signature:normative-operation:v1",
            predicate_ref="normative.prohibition",
            role_bindings={"bearer": "factor:actor", "conduct": "factor:drive"},
            qualifier_state={"modality": "obligation", "polarity": "negative"},
            wrapper_state={},
            provenance_refs=("span:1",),
            residual_refs=("exception_unresolved",),
        ),
    )


def test_build_unifies_surfaces_without_flattening_authority() -> None:
    result = build_legal_semantic_build(
        compilation=_compilation(),
        legal_ir=_legal_ir(),
        legacy_rows=(
            {
                "type": "prohibition",
                "actor": "A person",
                "action": "drive",
                "conditions": [{"type": "unless", "text": "licensed"}],
                "span_refs": ["span:1"],
            },
        ),
        declaration_revision_refs=("grammar:shared:v1",),
    )
    build = result["build"]
    assert build["flattened_union"] is False
    assert build["surface_authority"]["refined_pnf_graph"] == "candidate_semantic_state"
    assert build["surface_authority"]["legacy_observations"] == "diagnostic_witness_only"
    assert result["summary"]["semantic_promotion_count"] == 0
    assert result["legacy_witnesses"][0]["promotes_pnf"] is False
    assert any(row["comparison_state"] == "aligned" for row in result["comparison_ledger"])
    assert any(
        demand["missing_factor_type"] == "semantic.legal_exception"
        for demand in result["coverage_demands"]
    )


def test_legacy_witness_is_attributed_detection_not_legal_fact() -> None:
    witnesses = normalize_legacy_witnesses(
        ({"type": "permission", "actor": "Minister", "action": "grant"},),
        document_ref="document:1",
    )
    payload = witnesses[0].to_dict()
    assert payload["authority"] == "diagnostic_only"
    assert payload["promotes_pnf"] is False
    assert payload["candidate_kind"] == "permission"
