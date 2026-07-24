"""Pure projection from streaming execution evidence to fibred build evidence."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.pnf.factor_proposals import (
    INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
    FactorProposal,
)
from src.pnf.integrated_semantic_producer import IntegratedProducerReceipt
from src.pnf.semantic_fibres import (
    FibreBoundaryObligation,
    FibreDerivation,
    FibreElement,
    SemanticCoordinate,
    SemanticFibreLedger,
    fibre_element_from_proposal_row,
)


def _proposal_from_mapping(row: Mapping[str, Any]) -> FactorProposal:
    return FactorProposal(
        document_ref=str(row["document_ref"]),
        source_revision_ref=str(row["source_revision_ref"]),
        factor_type_ref=str(row["factor_type_ref"]),
        source_span_refs=tuple(row.get("source_span_refs") or ()),
        input_observation_refs=tuple(
            row.get("input_observation_refs") or ()
        ),
        dependency_factor_refs=tuple(
            row.get("dependency_factor_refs") or ()
        ),
        structural_signature=str(row.get("structural_signature") or ""),
        role_bindings=dict(row.get("role_bindings") or {}),
        qualifier_state=dict(row.get("qualifier_state") or {}),
        producer_contract=str(row.get("producer_contract") or ""),
        declaration_revision=str(row.get("declaration_revision") or ""),
        candidate_payload=dict(row.get("candidate_payload") or {}),
        residuals=tuple(row.get("residuals") or ()),
        scope_ref=str(row.get("scope_ref") or "document-global"),
        statement_role=str(row.get("statement_role") or "main"),
        coordinate_kind=str(row.get("coordinate_kind") or "object"),
        semantic_coordinate_ref=str(
            row.get("semantic_coordinate_ref") or ""
        )
        or None,
        fibre_kind=str(row.get("fibre_kind") or "hypothesis"),
        derivation_role=str(row.get("derivation_role") or "support"),
        producer_scope=str(row.get("producer_scope") or "integrated"),
        operation_contract=str(row.get("operation_contract") or "") or None,
        ontology_axis_refs=tuple(row.get("ontology_axis_refs") or ()),
        transport_refs=tuple(row.get("transport_refs") or ()),
        support_state=str(row.get("support_state") or "candidate"),
        confidence=(
            float(row["confidence"])
            if row.get("confidence") is not None
            else None
        ),
        assumptions=tuple(row.get("assumptions") or ()),
        coverage_requirements=tuple(
            row.get("coverage_requirements") or ()
        ),
        execution_metadata=dict(row.get("execution_metadata") or {}),
    )


def project_fibred_semantic_build(
    streaming_build: Mapping[str, Any],
) -> dict[str, Any]:
    """Return fibred coordinates, elements, derivations, boundaries, and receipt."""

    document_ref = str(streaming_build.get("document_ref") or "")
    coordinates: dict[str, SemanticCoordinate] = {}
    elements: list[FibreElement] = []
    content_to_element_ref: dict[str, str] = {}

    for delta in streaming_build.get("observation_deltas") or ():
        if not isinstance(delta, Mapping):
            continue
        scope_ref = str(delta.get("scope_ref") or "document-global")
        parser_contract = str(delta.get("parser_contract") or "")
        for observation in delta.get("observations") or ():
            if not isinstance(observation, Mapping):
                continue
            observation_ref = str(observation.get("observation_ref") or "")
            if not observation_ref:
                continue
            coordinate = SemanticCoordinate(
                document_ref=document_ref,
                scope_ref=scope_ref,
                source_span_refs=(observation_ref,),
                statement_role="parser_observation",
                factor_family=str(
                    observation.get("observation_type") or "parser.observation"
                ),
                coordinate_kind="object",
            )
            declared_coordinate_ref = str(
                observation.get("semantic_coordinate_ref") or ""
            )
            if declared_coordinate_ref and (
                declared_coordinate_ref != coordinate.coordinate_ref
            ):
                raise ValueError("parser observation coordinate is not canonical")
            element = FibreElement(
                document_ref=document_ref,
                coordinate_ref=coordinate.coordinate_ref,
                fibre_kind="observation",
                content_ref=observation_ref,
                derivation_role="support",
                producer_contract=INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
                operation_contract=parser_contract,
                source_refs=(observation_ref,),
                support_state="candidate",
                payload=dict(observation),
                execution_metadata={"parser_contract": parser_contract},
            )
            coordinates[coordinate.coordinate_ref] = coordinate
            elements.append(element)
            content_to_element_ref[observation_ref] = element.element_ref

    proposals = tuple(
        _proposal_from_mapping(row)
        for row in streaming_build.get("proposals") or ()
        if isinstance(row, Mapping)
    )
    for proposal in proposals:
        coordinate = SemanticCoordinate(
            document_ref=proposal.document_ref,
            scope_ref=str(proposal.scope_ref),
            source_span_refs=proposal.source_span_refs,
            statement_role=proposal.statement_role,
            factor_family=proposal.factor_type_ref,
            coordinate_kind=proposal.coordinate_kind,
        )
        if coordinate.coordinate_ref != proposal.semantic_coordinate_ref:
            raise ValueError("proposal coordinate is not canonical")
        element = fibre_element_from_proposal_row(proposal.to_dict())
        coordinates[coordinate.coordinate_ref] = coordinate
        elements.append(element)
        content_to_element_ref[proposal.proposal_ref] = element.element_ref

    jobs = {
        str(row.get("job_ref") or ""): row
        for row in streaming_build.get("solver_jobs") or ()
        if isinstance(row, Mapping) and row.get("job_ref")
    }
    proposal_rows = {row.proposal_ref: row for row in proposals}
    derivations: list[FibreDerivation] = []
    receipt_refs: list[str] = []
    for receipt in streaming_build.get("solver_receipts") or ():
        if not isinstance(receipt, Mapping):
            continue
        receipt_ref = str(receipt.get("receipt_ref") or "")
        if receipt_ref:
            receipt_refs.append(receipt_ref)
        job = jobs.get(str(receipt.get("job_ref") or ""), {})
        output_proposals = [
            proposal_rows[str(ref)]
            for ref in receipt.get("proposal_refs") or ()
            if str(ref) in proposal_rows
        ]
        operation_contract = str(
            output_proposals[0].operation_contract
            if output_proposals
            else job.get("declaration_ref") or "unknown-operation"
        )
        operation_kind = str(
            (
                output_proposals[0].execution_metadata.get("operation_kind")
                if output_proposals
                else None
            )
            or "closure"
        )
        derivations.append(
            FibreDerivation(
                document_ref=document_ref,
                operation_kind=operation_kind,
                declaration_ref=str(job.get("declaration_ref") or ""),
                producer_contract=INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
                input_element_refs=tuple(
                    content_to_element_ref.get(str(ref), str(ref))
                    for ref in receipt.get("input_refs") or ()
                ),
                output_element_refs=tuple(
                    content_to_element_ref[row.proposal_ref]
                    for row in output_proposals
                ),
                sub_executor_ref=str(receipt.get("backend_ref") or ""),
                rule_set_revision=str(
                    receipt.get("rule_set_revision") or ""
                ),
                receipt_ref=receipt_ref or None,
                assumptions=tuple(receipt.get("assumptions") or ()),
                metrics=dict(receipt.get("metrics") or {}),
            )
        )

    boundaries: list[FibreBoundaryObligation] = []
    materialized = streaming_build.get("materialized_reduction") or {}
    for residual in materialized.get("residuals") or ():
        if not isinstance(residual, Mapping):
            continue
        coordinate_ref = str(
            residual.get("semantic_coordinate_ref") or ""
        )
        coordinate = coordinates.get(coordinate_ref)
        if coordinate is None:
            continue
        boundary_kind = str(residual.get("boundary_kind") or "fibre")
        boundaries.append(
            FibreBoundaryObligation(
                document_ref=document_ref,
                coordinate_ref=coordinate_ref,
                scope_ref=coordinate.scope_ref,
                boundary_kind=boundary_kind,
                evidence_refs=tuple(residual.get("proposal_refs") or ()),
                frontier_refs=(str(residual.get("residual_ref") or ""),),
                state=(
                    "external"
                    if boundary_kind in {"input_frontier", "ontology_axis"}
                    else "open"
                ),
                message=str(residual.get("message") or ""),
            )
        )

    ledger = SemanticFibreLedger(
        coordinates=tuple(
            coordinates[key] for key in sorted(coordinates)
        ),
        elements=tuple(sorted(elements, key=lambda row: row.element_ref)),
        derivations=tuple(
            sorted(derivations, key=lambda row: row.derivation_ref)
        ),
        boundary_obligations=tuple(
            sorted(boundaries, key=lambda row: row.boundary_ref)
        ),
    )
    producer_receipt = IntegratedProducerReceipt(
        document_ref=document_ref,
        contract_ref=INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
        proposal_refs=tuple(sorted(row.proposal_ref for row in proposals)),
        sub_executor_receipt_refs=tuple(sorted(set(receipt_refs))),
        fibre_ledger_ref=ledger.ledger_ref,
        residual_refs=tuple(
            sorted(
                str(row.get("residual_ref") or "")
                for row in materialized.get("residuals") or ()
                if isinstance(row, Mapping) and row.get("residual_ref")
            )
        ),
        external_proposal_refs=tuple(
            sorted(
                row.proposal_ref
                for row in proposals
                if row.producer_scope == "external"
            )
        ),
    )
    return {
        "fibre_ledger": ledger.to_dict(),
        "integrated_producer_receipt": producer_receipt.to_dict(),
        "semantic_coordinates": [row.to_dict() for row in ledger.coordinates],
        "fibre_elements": [row.to_dict() for row in ledger.elements],
        "fibre_derivations": [row.to_dict() for row in ledger.derivations],
        "fibre_boundary_obligations": [
            row.to_dict() for row in ledger.boundary_obligations
        ],
        "one_proposal_contract": True,
        "one_reduction_authority": True,
        "identity_promoted": False,
        "legal_truth_closed": False,
    }


__all__ = ["project_fibred_semantic_build"]
