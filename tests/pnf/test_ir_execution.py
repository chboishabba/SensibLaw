from __future__ import annotations

from src.pnf.domain_ir import DomainIRProjection
from src.pnf.ir_execution import IRExecutionRequest, execute_ir_request


def _domain_ir(*, validation_state: str = "operational_candidate") -> DomainIRProjection:
    return DomainIRProjection(
        document_ref="document:1",
        domain="legal",
        source_resolution_ref="resolution:1",
        source_factor_ref="factor:1",
        selected_proposal_ref="proposal:1",
        structural_signature_ref="signature:1",
        projection_contract_ref="contract:legal",
        projection_receipt_ref="projection-receipt:1",
        loss_ref="loss:1",
        payload={"predicate_ref": "normative.obligation"},
        provenance_refs=("span:1",),
        residual_refs=(),
        validation_state=validation_state,
    )


def test_valid_ir_without_applicability_witness_is_refused() -> None:
    ir = _domain_ir()
    request = IRExecutionRequest(
        document_ref="document:1",
        domain_ir_ref=ir.domain_ir_ref,
        rule_or_query_ref="rule:qld:1",
        applicability_witness_refs=(),
    )

    receipt = execute_ir_request(request=request, domain_ir=ir)

    assert receipt.outcome == "refused_missing_applicability"
    assert receipt.to_dict()["semantic_similarity_executes"] is False


def test_valid_ir_and_applicability_witness_can_execute() -> None:
    ir = _domain_ir()
    request = IRExecutionRequest(
        document_ref="document:1",
        domain_ir_ref=ir.domain_ir_ref,
        rule_or_query_ref="rule:qld:1",
        applicability_witness_refs=("applicability:1",),
        required_evidence_refs=("evidence:1",),
        supplied_evidence_refs=("evidence:1",),
        requested_output={"decision": "candidate_output"},
    )

    receipt = execute_ir_request(request=request, domain_ir=ir)

    assert receipt.outcome == "executed"
    assert receipt.emitted_output == {"decision": "candidate_output"}
    assert receipt.to_dict()["legal_truth_closed"] is False


def test_invalid_ir_is_refused_even_with_applicability_witness() -> None:
    ir = _domain_ir(validation_state="invalid")
    request = IRExecutionRequest(
        document_ref="document:1",
        domain_ir_ref=ir.domain_ir_ref,
        rule_or_query_ref="rule:qld:1",
        applicability_witness_refs=("applicability:1",),
    )

    receipt = execute_ir_request(request=request, domain_ir=ir)

    assert receipt.outcome == "refused_invalid_ir"


def test_missing_ir_produces_persistable_blocked_receipt() -> None:
    request = IRExecutionRequest(
        document_ref="document:1",
        domain_ir_ref="legal-ir:missing",
        rule_or_query_ref="rule:qld:1",
        applicability_witness_refs=("applicability:1",),
    )

    receipt = execute_ir_request(request=request, domain_ir=None)

    assert receipt.outcome == "blocked_missing_evidence"
    assert receipt.domain_ir_ref == "legal-ir:missing"
