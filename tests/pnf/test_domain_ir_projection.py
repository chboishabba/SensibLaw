from __future__ import annotations

from dataclasses import replace

from src.pnf.domain_ir_projection import (
    LEGAL_IR_CONTRACT,
    RETRIEVAL_IR_CONTRACT,
    TIMELINE_IR_CONTRACT,
    build_domain_ir,
    project_resolved_factor,
)
from src.pnf.factor_proposals import FactorProposal
from src.pnf.semantic_lifecycle import ResolutionReceipt


def _proposal() -> FactorProposal:
    return FactorProposal(
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
        fibre_kind="composition",
        support_state="supported",
    )


def _resolution(proposal: FactorProposal) -> ResolutionReceipt:
    return ResolutionReceipt(
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


def _factor(
    *,
    jurisdiction: bool = False,
    event_time: bool = False,
    factor_type: str = "semantic.normative_relation",
    signature: str = "signature:normative:v1",
):
    roles = {"bearer": "entity:driver", "conduct": "event:drive"}
    qualifiers = {"modality": "obligation"}
    residuals = []
    if jurisdiction:
        roles["jurisdiction"] = "AU-QLD"
    else:
        residuals.append("jurisdiction_unresolved")
    if event_time:
        qualifiers["event_time"] = "2026-07-24"
    return {
        "factor_ref": "factor:source",
        "factor_type": factor_type,
        "residuals": residuals,
        "metadata": {
            "fibre_summary_ref": "fibre-summary:1",
            "structural_signature_ref": signature,
            "role_bindings": roles,
            "qualifier_state": qualifiers,
            "provenance_refs": ["span:1"],
        },
    }


def test_legal_projection_returns_missing_jurisdiction_demand() -> None:
    proposal = _proposal()
    resolution = _resolution(proposal)
    result = project_resolved_factor(
        resolution=resolution,
        factors={"fibre-summary:1": _factor()},
        proposals={proposal.proposal_ref: proposal},
        contract=LEGAL_IR_CONTRACT,
    )

    assert result.projection is None
    assert result.receipt.state == "blocked"
    assert {row.demand_kind for row in result.demands} == {
        "missing_jurisdiction"
    }
    assert result.demands[0].to_resolution_demand()["authority"] == (
        "projection_demand_only"
    )


def test_legal_projection_is_loss_receipted_when_coordinates_are_complete() -> None:
    proposal = _proposal()
    resolution = _resolution(proposal)
    result = project_resolved_factor(
        resolution=resolution,
        factors={"fibre-summary:1": _factor(jurisdiction=True)},
        proposals={proposal.proposal_ref: proposal},
        contract=LEGAL_IR_CONTRACT,
    )

    assert result.projection is not None
    assert result.receipt.state == "projected"
    assert result.loss is not None
    assert result.projection.payload["jurisdiction_ref"] == "AU-QLD"
    assert result.projection.to_dict()["applicability_closed"] is False
    assert result.loss.to_dict()["equal_ir_does_not_imply_equal_pnf"] is True


def test_timeline_projection_requires_temporal_coordinate() -> None:
    proposal = replace(
        _proposal(),
        factor_type_ref="semantic.event",
        structural_signature="signature:event:v1",
        role_bindings={"actor": "entity:driver", "event": "event:drive"},
        qualifier_state={},
        candidate_payload={"predicate_ref": "event.drive"},
    )
    resolution = _resolution(proposal)
    factor = _factor(
        jurisdiction=True,
        factor_type="semantic.event",
        signature="signature:event:v1",
    )
    factor["metadata"]["role_bindings"] = {
        "actor": "entity:driver",
        "event": "event:drive",
    }
    factor["metadata"]["qualifier_state"] = {}
    result = project_resolved_factor(
        resolution=resolution,
        factors={"fibre-summary:1": factor},
        proposals={proposal.proposal_ref: proposal},
        contract=TIMELINE_IR_CONTRACT,
    )

    assert result.projection is None
    assert result.receipt.state == "blocked"
    assert {row.demand_kind for row in result.demands} == {
        "missing_temporal_coordinate"
    }


def test_retrieval_projection_preserves_source_binding() -> None:
    proposal = _proposal()
    resolution = _resolution(proposal)
    result = project_resolved_factor(
        resolution=resolution,
        factors={"fibre-summary:1": _factor()},
        proposals={proposal.proposal_ref: proposal},
        contract=RETRIEVAL_IR_CONTRACT,
    )

    assert result.projection is not None
    assert "span:1" in result.projection.provenance_refs
    assert result.projection.payload["retrieval_keys"]


def test_domain_ir_build_has_no_memory_or_nashi_projection() -> None:
    proposal = _proposal()
    resolution = _resolution(proposal)
    build = build_domain_ir(
        document_ref="document:1",
        resolutions=(resolution,),
        factors=(_factor(jurisdiction=True, event_time=True),),
        proposals=(proposal,),
    )
    payload = build.to_dict()

    assert payload["memory_projection_included"] is False
    assert payload["nashi_projection_included"] is False
    assert {row["domain"] for row in payload["contracts"]} == {
        "legal",
        "retrieval",
        "timeline",
    }
