"""Batched persistence for semantic fibre coordinates, elements, and receipts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.pnf.factor_proposals import INTEGRATED_SEMANTIC_PRODUCER_CONTRACT
from src.pnf.integrated_semantic_producer import IntegratedProducerReceipt
from src.pnf.semantic_fibres import (
    AxisObligation,
    FibreBoundaryObligation,
    OntologyAxis,
    SemanticFibreLedger,
    SemanticTransport,
    fibre_element_from_proposal_row,
)
from src.storage.postgres.semantic_fibre_store import (
    _fibre_derivations,
    _json,
    _observation_elements,
    _proposal_coordinate,
)


def persist_semantic_fibre_artifacts_batched(
    cursor: Any,
    *,
    document_ref: str,
    observation_deltas: Sequence[Mapping[str, Any]],
    proposals: Sequence[Mapping[str, Any]],
    solver_jobs: Sequence[Mapping[str, Any]],
    solver_receipts: Sequence[Mapping[str, Any]],
    materialized_reduction: Mapping[str, Any],
    transports: Sequence[Mapping[str, Any]] = (),
    ontology_axes: Sequence[Mapping[str, Any]] = (),
    axis_obligations: Sequence[Mapping[str, Any]] = (),
    boundary_obligations: Sequence[Mapping[str, Any]] = (),
) -> IntegratedProducerReceipt:
    coordinates, elements = _observation_elements(document_ref, observation_deltas)
    content_to_element_ref = {row.content_ref: row.element_ref for row in elements}
    proposal_by_ref = {
        str(row.get("proposal_ref") or ""): row
        for row in proposals
        if row.get("proposal_ref")
    }
    proposal_extension_rows = []
    for proposal in proposals:
        coordinate = _proposal_coordinate(proposal)
        element = fibre_element_from_proposal_row(proposal)
        coordinates[coordinate.coordinate_ref] = coordinate
        elements.append(element)
        content_to_element_ref[str(proposal["proposal_ref"])] = element.element_ref
        proposal_extension_rows.append(
            (
                proposal.get("semantic_coordinate_ref"),
                proposal.get("scope_ref"),
                proposal.get("statement_role") or "main",
                proposal.get("coordinate_kind") or "object",
                proposal.get("fibre_kind") or "hypothesis",
                proposal.get("derivation_role") or "support",
                proposal.get("producer_scope") or "integrated",
                proposal.get("operation_contract"),
                _json(proposal.get("ontology_axis_refs") or ()),
                _json(proposal.get("transport_refs") or ()),
                proposal.get("support_state") or "candidate",
                proposal.get("confidence"),
                _json(proposal.get("assumptions") or ()),
                _json(proposal.get("coverage_requirements") or ()),
                _json(proposal.get("execution_metadata") or {}),
                proposal["proposal_ref"],
            )
        )
    if proposal_extension_rows:
        cursor.executemany(
            """
            UPDATE pnf_factor_proposal
            SET semantic_coordinate_ref = %s, scope_ref = %s,
                statement_role = %s, coordinate_kind = %s, fibre_kind = %s,
                derivation_role = %s, producer_scope = %s,
                operation_contract = %s, ontology_axis_refs = %s::jsonb,
                transport_refs = %s::jsonb, support_state = %s, confidence = %s,
                assumptions = %s::jsonb, coverage_requirements = %s::jsonb,
                execution_metadata = %s::jsonb
            WHERE proposal_ref = %s
            """,
            proposal_extension_rows,
        )

    derivations = _fibre_derivations(
        document_ref=document_ref,
        solver_jobs=solver_jobs,
        solver_receipts=solver_receipts,
        proposal_by_ref=proposal_by_ref,
        content_to_element_ref=content_to_element_ref,
    )
    transport_rows = tuple(
        SemanticTransport(
            document_ref=str(row["document_ref"]),
            source_coordinate_ref=str(row["source_coordinate_ref"]),
            target_coordinate_ref=str(row["target_coordinate_ref"]),
            transport_type=str(row["transport_type"]),
            strength=str(row["strength"]),
            evidence_refs=tuple(row.get("evidence_refs") or ()),
            ontology_axis_refs=tuple(row.get("ontology_axis_refs") or ()),
            allowed_operations=tuple(row.get("allowed_operations") or ()),
            residual_refs=tuple(row.get("residual_refs") or ()),
        )
        for row in transports
    )
    axis_rows = tuple(
        OntologyAxis(
            axis_ref=str(row["axis_ref"]),
            label=str(row["label"]),
            authority_ref=str(row["authority_ref"]),
            relation_refs=tuple(row.get("relation_refs") or ()),
            root_refs=tuple(row.get("root_refs") or ()),
            open_world=bool(row.get("open_world", True)),
        )
        for row in ontology_axes
    )
    obligation_rows = tuple(
        AxisObligation(
            document_ref=str(row["document_ref"]),
            coordinate_ref=str(row["coordinate_ref"]),
            axis_ref=str(row["axis_ref"]),
            obligation_type=str(row["obligation_type"]),
            trigger_refs=tuple(row.get("trigger_refs") or ()),
            frontier_refs=tuple(row.get("frontier_refs") or ()),
            state=str(row.get("state") or "open"),
            resource_limit_reached=bool(row.get("resource_limit_reached", False)),
        )
        for row in axis_obligations
    )
    boundary_rows = tuple(
        FibreBoundaryObligation(
            document_ref=str(row["document_ref"]),
            coordinate_ref=str(row["coordinate_ref"]),
            scope_ref=str(row["scope_ref"]),
            boundary_kind=str(row["boundary_kind"]),
            evidence_refs=tuple(row.get("evidence_refs") or ()),
            frontier_refs=tuple(row.get("frontier_refs") or ()),
            required_axis_refs=tuple(row.get("required_axis_refs") or ()),
            state=str(row.get("state") or "open"),
            message=str(row.get("message") or ""),
        )
        for row in boundary_obligations
    )

    coordinate_payloads = [coordinates[key].to_dict() for key in sorted(coordinates)]
    if coordinate_payloads:
        cursor.executemany(
            """
            INSERT INTO semantic_coordinate
                (coordinate_ref, document_ref, scope_ref, source_span_refs,
                 statement_role, factor_family, coordinate_kind,
                 source_coordinate_refs, target_coordinate_refs)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb)
            ON CONFLICT (coordinate_ref) DO NOTHING
            """,
            [
                (
                    row["coordinate_ref"], row["document_ref"], row["scope_ref"],
                    _json(row["source_span_refs"]), row["statement_role"],
                    row["factor_family"], row["coordinate_kind"],
                    _json(row["source_coordinate_refs"]),
                    _json(row["target_coordinate_refs"]),
                )
                for row in coordinate_payloads
            ],
        )
    element_payloads = [row.to_dict() for row in sorted(elements, key=lambda item: item.element_ref)]
    if element_payloads:
        cursor.executemany(
            """
            INSERT INTO semantic_fibre_element
                (element_ref, document_ref, coordinate_ref, fibre_kind, content_ref,
                 derivation_role, producer_contract, operation_contract, source_refs,
                 dependency_refs, transport_refs, ontology_axis_refs, assumptions,
                 coverage_requirements, support_state, confidence, payload, external,
                 execution_metadata, authority, semantic_state_promoted,
                 legal_truth_closed)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                 %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s,
                 %s::jsonb, %s, %s::jsonb, %s, FALSE, FALSE)
            ON CONFLICT (element_ref) DO NOTHING
            """,
            [
                (
                    row["element_ref"], row["document_ref"], row["coordinate_ref"],
                    row["fibre_kind"], row["content_ref"], row["derivation_role"],
                    row["producer_contract"], row["operation_contract"],
                    _json(row["source_refs"]), _json(row["dependency_refs"]),
                    _json(row["transport_refs"]), _json(row["ontology_axis_refs"]),
                    _json(row["assumptions"]), _json(row["coverage_requirements"]),
                    row["support_state"], row["confidence"], _json(row["payload"]),
                    row["external"], _json(row["execution_metadata"]), row["authority"],
                )
                for row in element_payloads
            ],
        )
    derivation_payloads = [row.to_dict() for row in derivations]
    if derivation_payloads:
        cursor.executemany(
            """
            INSERT INTO semantic_fibre_derivation
                (derivation_ref, document_ref, operation_kind, declaration_ref,
                 producer_contract, input_element_refs, output_element_refs,
                 sub_executor_ref, rule_set_revision, receipt_ref, assumptions,
                 metrics, semantic_state_promoted)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s,
                    %s::jsonb, %s::jsonb, FALSE)
            ON CONFLICT (derivation_ref) DO NOTHING
            """,
            [
                (
                    row["derivation_ref"], row["document_ref"], row["operation_kind"],
                    row["declaration_ref"], row["producer_contract"],
                    _json(row["input_element_refs"]), _json(row["output_element_refs"]),
                    row["sub_executor_ref"], row["rule_set_revision"], row["receipt_ref"],
                    _json(row["assumptions"]), _json(row["metrics"]),
                )
                for row in derivation_payloads
            ],
        )
    if transport_rows:
        cursor.executemany(
            """
            INSERT INTO semantic_transport
                (transport_ref, document_ref, source_coordinate_ref,
                 target_coordinate_ref, transport_type, strength, evidence_refs,
                 ontology_axis_refs, allowed_operations, residual_refs,
                 identity_closed, semantic_state_promoted)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, FALSE, FALSE)
            ON CONFLICT (transport_ref) DO NOTHING
            """,
            [
                (
                    payload["transport_ref"], payload["document_ref"],
                    payload["source_coordinate_ref"], payload["target_coordinate_ref"],
                    payload["transport_type"], payload["strength"],
                    _json(payload["evidence_refs"]), _json(payload["ontology_axis_refs"]),
                    _json(payload["allowed_operations"]), _json(payload["residual_refs"]),
                )
                for payload in (row.to_dict() for row in transport_rows)
            ],
        )
    if axis_rows:
        cursor.executemany(
            """
            INSERT INTO semantic_ontology_axis
                (axis_ref, label, authority_ref, relation_refs, root_refs, open_world)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (axis_ref) DO NOTHING
            """,
            [
                (row.axis_ref, row.label, row.authority_ref, _json(row.relation_refs),
                 _json(row.root_refs), row.open_world)
                for row in axis_rows
            ],
        )
    if obligation_rows:
        cursor.executemany(
            """
            INSERT INTO semantic_axis_obligation
                (obligation_ref, document_ref, coordinate_ref, axis_ref,
                 obligation_type, trigger_refs, frontier_refs, state,
                 resource_limit_reached, truth_closed)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, FALSE)
            ON CONFLICT (obligation_ref) DO NOTHING
            """,
            [
                (
                    payload["obligation_ref"], payload["document_ref"],
                    payload["coordinate_ref"], payload["axis_ref"],
                    payload["obligation_type"], _json(payload["trigger_refs"]),
                    _json(payload["frontier_refs"]), payload["state"],
                    payload["resource_limit_reached"],
                )
                for payload in (row.to_dict() for row in obligation_rows)
            ],
        )
    if boundary_rows:
        cursor.executemany(
            """
            INSERT INTO semantic_fibre_boundary_obligation
                (boundary_ref, document_ref, coordinate_ref, scope_ref,
                 boundary_kind, evidence_refs, frontier_refs,
                 required_axis_refs, state, message)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
            ON CONFLICT (boundary_ref) DO NOTHING
            """,
            [
                (
                    payload["boundary_ref"], payload["document_ref"],
                    payload["coordinate_ref"], payload["scope_ref"],
                    payload["boundary_kind"], _json(payload["evidence_refs"]),
                    _json(payload["frontier_refs"]), _json(payload["required_axis_refs"]),
                    payload["state"], payload["message"],
                )
                for payload in (row.to_dict() for row in boundary_rows)
            ],
        )

    graph_ref = str(materialized_reduction.get("graph_ref") or "")
    summary_rows = [
        (
            factor["factor_ref"], graph_ref, document_ref,
            factor.get("semantic_coordinate_ref"), factor.get("fibre_kind") or "hypothesis",
            factor["factor_type_ref"], factor.get("structural_signature") or "",
            _json(factor.get("proposal_refs") or ()),
            _json(factor.get("derivation_roles") or ()),
            _json(factor.get("ontology_axis_refs") or ()),
            _json(factor.get("transport_refs") or ()),
            _json(factor.get("support_states") or ()),
            _json(factor.get("residuals") or ()),
        )
        for factor in materialized_reduction.get("factors") or ()
    ]
    if summary_rows:
        cursor.executemany(
            """
            INSERT INTO semantic_fibre_summary
                (factor_ref, graph_ref, document_ref, semantic_coordinate_ref,
                 fibre_kind, factor_type_ref, structural_signature,
                 proposal_refs, derivation_roles, ontology_axis_refs,
                 transport_refs, support_states, residual_refs,
                 deterministic_materialisation, identity_promoted, legal_truth_closed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, TRUE, FALSE, FALSE)
            ON CONFLICT (factor_ref) DO NOTHING
            """,
            summary_rows,
        )

    ledger = SemanticFibreLedger(
        coordinates=tuple(coordinates[key] for key in sorted(coordinates)),
        elements=tuple(sorted(elements, key=lambda row: row.element_ref)),
        transports=tuple(sorted(transport_rows, key=lambda row: row.transport_ref)),
        derivations=derivations,
        ontology_axes=tuple(sorted(axis_rows, key=lambda row: row.axis_ref)),
        axis_obligations=tuple(sorted(obligation_rows, key=lambda row: row.obligation_ref)),
        boundary_obligations=tuple(sorted(boundary_rows, key=lambda row: row.boundary_ref)),
    )
    producer_receipt = IntegratedProducerReceipt(
        document_ref=document_ref,
        contract_ref=INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
        proposal_refs=tuple(sorted(str(row["proposal_ref"]) for row in proposals)),
        sub_executor_receipt_refs=tuple(
            sorted(
                str(row.get("receipt_ref") or "")
                for row in solver_receipts
                if row.get("receipt_ref")
            )
        ),
        fibre_ledger_ref=ledger.ledger_ref,
        residual_refs=tuple(
            sorted(
                str(row.get("residual_ref") or "")
                for row in materialized_reduction.get("residuals") or ()
                if row.get("residual_ref")
            )
        ),
        external_proposal_refs=tuple(
            sorted(
                str(row["proposal_ref"])
                for row in proposals
                if str(row.get("producer_scope") or "integrated") == "external"
            )
        ),
    )
    payload = producer_receipt.to_dict()
    cursor.execute(
        """
        INSERT INTO integrated_semantic_producer_receipt
            (receipt_ref, document_ref, contract_ref, proposal_refs,
             sub_executor_receipt_refs, fibre_ledger_ref, residual_refs,
             external_proposal_refs, one_proposal_contract,
             one_reduction_authority, identity_promoted, legal_truth_closed)
        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb,
                %s::jsonb, TRUE, TRUE, FALSE, FALSE)
        ON CONFLICT (receipt_ref) DO NOTHING
        """,
        (
            payload["receipt_ref"], payload["document_ref"], payload["contract_ref"],
            _json(payload["proposal_refs"]), _json(payload["sub_executor_receipt_refs"]),
            payload["fibre_ledger_ref"], _json(payload["residual_refs"]),
            _json(payload["external_proposal_refs"]),
        ),
    )
    return producer_receipt


__all__ = ["persist_semantic_fibre_artifacts_batched"]
