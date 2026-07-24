from __future__ import annotations

from src.pnf.domain_ir_applicability import build_applicable_domain_ir
from src.pnf.domain_ir_projection import LEGAL_IR_CONTRACT
from src.pnf.factor_proposals import FactorProposal
from src.pnf.semantic_lifecycle import ResolutionReceipt


def test_qualifier_role_is_inapplicable_not_missing_evidence() -> None:
    proposal = FactorProposal(
        document_ref="document:1",
        source_revision_ref="source:1",
        factor_type_ref="semantic.normative_relation",
        source_span_refs=("span:1",),
        input_observation_refs=("observation:must",),
        dependency_factor_refs=(),
        structural_signature="signature:normative:v1",
        role_bindings={"bearer": "entity:driver", "conduct": "event:drive"},
        qualifier_state={"modality": "obligation"},
        producer_contract="grammar:semantic:operator-composition:v0_1",
        declaration_revision="v1",
        candidate_payload={"predicate_ref": "normative.obligation"},
        statement_role="qualifier",
        fibre_kind="composition",
        support_state="supported",
    )
    resolution = ResolutionReceipt(
        document_ref="document:1",
        fibre_summary_ref="fibre-summary:1",
        semantic_coordinate_ref=proposal.semantic_coordinate_ref or "coordinate:1",
        state="resolved_unique",
        selected_proposal_ref=proposal.proposal_ref,
        admitted_proposal_refs=(proposal.proposal_ref,),
        retained_alternative_refs=(),
        selector_ref="deterministic-evidence-order:v0_1",
        selection_ground_refs=("admission:1",),
        unresolved_residual_refs=(),
    )
    factor = {
        "factor_ref": "factor:source",
        "factor_type": "semantic.normative_relation",
        "residuals": [],
        "metadata": {
            "fibre_summary_ref": "fibre-summary:1",
            "structural_signature_ref": "signature:normative:v1",
            "role_bindings": {
                "bearer": "entity:driver",
                "conduct": "event:drive",
                "jurisdiction": "AU-QLD",
            },
            "qualifier_state": {"modality": "obligation"},
            "provenance_refs": ["span:1"],
        },
    }

    build = build_applicable_domain_ir(
        document_ref="document:1",
        resolutions=(resolution,),
        factors=(factor,),
        proposals=(proposal,),
        contracts=(LEGAL_IR_CONTRACT,),
    )

    assert build.projections == ()
    assert build.demands == ()
    assert len(build.receipts) == 1
    assert build.receipts[0].state == "inapplicable"
    assert "statement_role_inapplicable" in build.receipts[0].reason_refs
