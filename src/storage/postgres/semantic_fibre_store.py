"""PostgreSQL persistence for the fibred integrated semantic compiler."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.pnf.factor_proposals import INTEGRATED_SEMANTIC_PRODUCER_CONTRACT
from src.pnf.integrated_semantic_producer import IntegratedProducerReceipt
from src.pnf.semantic_fibres import (
    AxisObligation,
    FibreBoundaryObligation,
    FibreDerivation,
    FibreElement,
    OntologyAxis,
    SemanticCoordinate,
    SemanticFibreLedger,
    SemanticTransport,
    fibre_element_from_proposal_row,
)


def _json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _persist_coordinate(cursor: Any, row: SemanticCoordinate) -> None:
    payload = row.to_dict()
    cursor.execute(
        """
        INSERT INTO semantic_coordinate
            (coordinate_ref, document_ref, scope_ref, source_span_refs,
             statement_role, factor_family, coordinate_kind,
             source_coordinate_refs, target_coordinate_refs)
        VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb)
        ON CONFLICT (coordinate_ref) DO NOTHING
        """,
        (
            payload["coordinate_ref"],
            payload["document_ref"],
            payload["scope_ref"],
            _json(payload["source_span_refs"]),
            payload["statement_role"],
            payload["factor_family"],
            payload["coordinate_kind"],
            _json(payload["source_coordinate_refs"]),
            _json(payload["target_coordinate_refs"]),
        ),
    )


def _persist_element(cursor: Any, row: FibreElement) -> None:
    payload = row.to_dict()
    cursor.execute(
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
        (
            payload["element_ref"],
            payload["document_ref"],
            payload["coordinate_ref"],
            payload["fibre_kind"],
            payload["content_ref"],
            payload["derivation_role"],
            payload["producer_contract"],
            payload["operation_contract"],
            _json(payload["source_refs"]),
            _json(payload["dependency_refs"]),
            _json(payload["transport_refs"]),
            _json(payload["ontology_axis_refs"]),
            _json(payload["assumptions"]),
            _json(payload["coverage_requirements"]),
            payload["support_state"],
            payload["confidence"],
            _json(payload["payload"]),
            payload["external"],
            _json(payload["execution_metadata"]),
            payload["authority"],
        ),
    )


def _persist_derivation(cursor: Any, row: FibreDerivation) -> None:
    payload = row.to_dict()
    cursor.execute(
        """
        INSERT INTO semantic_fibre_derivation
            (derivation_ref, document_ref, operation_kind, declaration_ref,
             producer_contract, input_element_refs, output_element_refs,
             sub_executor_ref, rule_set_revision, receipt_ref, assumptions,
             metrics, semantic_state_promoted)
        VALUES
            (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s,
             %s::jsonb, %s::jsonb, FALSE)
        ON CONFLICT (derivation_ref) DO NOTHING
        """,
        (
            payload["derivation_ref"],
            payload["document_ref"],
            payload["operation_kind"],
            payload["declaration_ref"],
            payload["producer_contract"],
            _json(payload["input_element_refs"]),
            _json(payload["output_element_refs"]),
            payload["sub_executor_ref"],
            payload["rule_set_revision"],
            payload["receipt_ref"],
            _json(payload["assumptions"]),
            _json(payload["metrics"]),
        ),
    )


def _proposal_coordinate(proposal: Mapping[str, Any]) -> SemanticCoordinate:
    coordinate = SemanticCoordinate(
        document_ref=str(proposal["document_ref"]),
        scope_ref=str(proposal.get("scope_ref") or "document-global"),
        source_span_refs=tuple(
            str(ref) for ref in proposal.get("source_span_refs") or ()
        ),
        statement_role=str(proposal.get("statement_role") or "main"),
        factor_family=str(proposal["factor_type_ref"]),
        coordinate_kind=str(proposal.get("coordinate_kind") or "object"),
    )
    declared_ref = str(proposal.get("semantic_coordinate_ref") or "")
    if declared_ref and declared_ref != coordinate.coordinate_ref:
        raise ValueError("persisted proposal coordinate is not canonical")
    return coordinate


def _persist_proposal_extension(cursor: Any, proposal: Mapping[str, Any]) -> None:
    cursor.execute(
        """
        UPDATE pnf_factor_proposal
        SET semantic_coordinate_ref = %s,
            scope_ref = %s,
            statement_role = %s,
            coordinate_kind = %s,
            fibre_kind = %s,
            derivation_role = %s,
            producer_scope = %s,
            operation_contract = %s,
            ontology_axis_refs = %s::jsonb,
            transport_refs = %s::jsonb,
            support_state = %s,
            confidence = %s,
            assumptions = %s::jsonb,
            coverage_requirements = %s::jsonb,
            execution_metadata = %s::jsonb
        WHERE proposal_ref = %s
        """,
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
        ),
    )


def _persist_optional_transport(cursor: Any, row: Mapping[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO semantic_transport
            (transport_ref, document_ref, source_coordinate_ref,
             target_coordinate_ref, transport_type, strength, evidence_refs,
             ontology_axis_refs, allowed_operations, residual_refs,
             identity_closed, semantic_state_promoted)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
             %s::jsonb, %s::jsonb, FALSE, FALSE)
        ON CONFLICT (transport_ref) DO NOTHING
        """,
        (
            row["transport_ref"],
            row["document_ref"],
            row["source_coordinate_ref"],
            row["target_coordinate_ref"],
            row["transport_type"],
            row["strength"],
            _json(row.get("evidence_refs") or ()),
            _json(row.get("ontology_axis_refs") or ()),
            _json(row.get("allowed_operations") or ()),
            _json(row.get("residual_refs") or ()),
        ),
    )


def persist_semantic_fibre_artifacts(
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
    """Persist the fibred view derived from the ordinary streaming evidence."""

    coordinates: dict[str, SemanticCoordinate] = {}
    elements: list[FibreElement] = []
    content_to_element_ref: dict[str, str] = {}

    for delta in observation_deltas:
        parser_contract = str(delta.get("parser_contract") or "")
        scope_ref = str(delta.get("scope_ref") or "document-global")
        for observation in delta.get("observations") or ():
            if not isinstance(observation, Mapping):
                continue
            observation_ref = str(observation.get("observation_ref") or "")
            coordinate_ref = str(
                observation.get("semantic_coordinate_ref") or ""
            )
            if not observation_ref or not coordinate_ref:
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
            if coordinate.coordinate_ref != coordinate_ref:
                raise ValueError("parser observation coordinate is not canonical")
            element = FibreElement(
                document_ref=document_ref,
                coordinate_ref=coordinate_ref,
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
            coordinates[coordinate_ref] = coordinate
            elements.append(element)
            content_to_element_ref[observation_ref] = element.element_ref

    for proposal in proposals:
        coordinate = _proposal_coordinate(proposal)
        element = fibre_element_from_proposal_row(proposal)
        coordinates[coordinate.coordinate_ref] = coordinate
        elements.append(element)
        content_to_element_ref[str(proposal["proposal_ref"])] = element.element_ref
        _persist_proposal_extension(cursor, proposal)

    for coordinate in coordinates.values():
        _persist_coordinate(cursor, coordinate)
    for element in elements:
        _persist_element(cursor, element)

    jobs = {
        str(row.get("job_ref") or ""): row
        for row in solver_jobs
        if row.get("job_ref")
    }
    proposal_by_ref = {
        str(row.get("proposal_ref") or ""): row
        for row in proposals
        if row.get("proposal_ref")
    }
    derivations: list[FibreDerivation] = []
    for receipt in solver_receipts:
        job = jobs.get(str(receipt.get("job_ref") or ""), {})
        proposal_refs = tuple(
            str(ref) for ref in receipt.get("proposal_refs") or ()
        )
        proposal_rows = [
            proposal_by_ref[ref] for ref in proposal_refs if ref in proposal_by_ref
        ]
        operation_contract = str(
            proposal_rows[0].get("operation_contract")
            if proposal_rows
            else job.get("declaration_ref") or ""
        )
        operation_kind = str(
            (
                proposal_rows[0].get("execution_metadata") or {}
            ).get("operation_kind")
            if proposal_rows
            else "closure"
        )
        derivation = FibreDerivation(
            document_ref=document_ref,
            operation_kind=operation_kind or "closure",
            declaration_ref=str(job.get("declaration_ref") or ""),
            producer_contract=INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
            input_element_refs=tuple(
                content_to_element_ref.get(str(ref), str(ref))
                for ref in receipt.get("input_refs") or ()
            ),
            output_element_refs=tuple(
                content_to_element_ref[ref]
                for ref in proposal_refs
                if ref in content_to_element_ref
            ),
            sub_executor_ref=str(receipt.get("backend_ref") or ""),
            rule_set_revision=str(receipt.get("rule_set_revision") or ""),
            receipt_ref=str(receipt.get("receipt_ref") or "") or None,
            assumptions=tuple(
                str(ref) for ref in receipt.get("assumptions") or ()
            ),
            metrics=dict(receipt.get("metrics") or {}),
        )
        derivations.append(derivation)
        _persist_derivation(cursor, derivation)

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
    for row in transport_rows:
        _persist_optional_transport(cursor, row.to_dict())

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
    for row in axis_rows:
        payload = row.to_dict()
        cursor.execute(
            """
            INSERT INTO semantic_ontology_axis
                (axis_ref, label, authority_ref, relation_refs, root_refs,
                 open_world)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (axis_ref) DO NOTHING
            """,
            (
                payload["axis_ref"],
                payload["label"],
                payload["authority_ref"],
                _json(payload["relation_refs"]),
                _json(payload["root_refs"]),
                payload["open_world"],
            ),
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
            resource_limit_reached=bool(
                row.get("resource_limit_reached", False)
            ),
        )
        for row in axis_obligations
    )
    for row in obligation_rows:
        payload = row.to_dict()
        cursor.execute(
            """
            INSERT INTO semantic_axis_obligation
                (obligation_ref, document_ref, coordinate_ref, axis_ref,
                 obligation_type, trigger_refs, frontier_refs, state,
                 resource_limit_reached, truth_closed)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, FALSE)
            ON CONFLICT (obligation_ref) DO NOTHING
            """,
            (
                payload["obligation_ref"],
                payload["document_ref"],
                payload["coordinate_ref"],
                payload["axis_ref"],
                payload["obligation_type"],
                _json(payload["trigger_refs"]),
                _json(payload["frontier_refs"]),
                payload["state"],
                payload["resource_limit_reached"],
            ),
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
    for row in boundary_rows:
        payload = row.to_dict()
        cursor.execute(
            """
            INSERT INTO semantic_fibre_boundary_obligation
                (boundary_ref, document_ref, coordinate_ref, scope_ref,
                 boundary_kind, evidence_refs, frontier_refs,
                 required_axis_refs, state, message)
            VALUES
                (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                 %s::jsonb, %s, %s)
            ON CONFLICT (boundary_ref) DO NOTHING
            """,
            (
                payload["boundary_ref"],
                payload["document_ref"],
                payload["coordinate_ref"],
                payload["scope_ref"],
                payload["boundary_kind"],
                _json(payload["evidence_refs"]),
                _json(payload["frontier_refs"]),
                _json(payload["required_axis_refs"]),
                payload["state"],
                payload["message"],
            ),
        )

    graph_ref = str(materialized_reduction.get("graph_ref") or "")
    for factor in materialized_reduction.get("factors") or ():
        cursor.execute(
            """
            INSERT INTO semantic_fibre_summary
                (factor_ref, graph_ref, document_ref, semantic_coordinate_ref,
                 fibre_kind, factor_type_ref, structural_signature,
                 proposal_refs, derivation_roles, ontology_axis_refs,
                 transport_refs, support_states, residual_refs,
                 deterministic_materialisation, identity_promoted,
                 legal_truth_closed)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                 %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                 TRUE, FALSE, FALSE)
            ON CONFLICT (factor_ref) DO NOTHING
            """,
            (
                factor["factor_ref"],
                graph_ref,
                document_ref,
                factor.get("semantic_coordinate_ref"),
                factor.get("fibre_kind") or "hypothesis",
                factor["factor_type_ref"],
                factor.get("structural_signature") or "",
                _json(factor.get("proposal_refs") or ()),
                _json(factor.get("derivation_roles") or ()),
                _json(factor.get("ontology_axis_refs") or ()),
                _json(factor.get("transport_refs") or ()),
                _json(factor.get("support_states") or ()),
                _json(factor.get("residuals") or ()),
            ),
        )

    ledger = SemanticFibreLedger(
        coordinates=tuple(
            coordinates[key] for key in sorted(coordinates)
        ),
        elements=tuple(sorted(elements, key=lambda row: row.element_ref)),
        transports=tuple(
            sorted(transport_rows, key=lambda row: row.transport_ref)
        ),
        derivations=tuple(
            sorted(derivations, key=lambda row: row.derivation_ref)
        ),
        ontology_axes=tuple(sorted(axis_rows, key=lambda row: row.axis_ref)),
        axis_obligations=tuple(
            sorted(obligation_rows, key=lambda row: row.obligation_ref)
        ),
        boundary_obligations=tuple(
            sorted(boundary_rows, key=lambda row: row.boundary_ref)
        ),
    )
    producer_receipt = IntegratedProducerReceipt(
        document_ref=document_ref,
        contract_ref=INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
        proposal_refs=tuple(
            sorted(str(row["proposal_ref"]) for row in proposals)
        ),
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
        VALUES
            (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb,
             %s::jsonb, TRUE, TRUE, FALSE, FALSE)
        ON CONFLICT (receipt_ref) DO NOTHING
        """,
        (
            payload["receipt_ref"],
            payload["document_ref"],
            payload["contract_ref"],
            _json(payload["proposal_refs"]),
            _json(payload["sub_executor_receipt_refs"]),
            payload["fibre_ledger_ref"],
            _json(payload["residual_refs"]),
            _json(payload["external_proposal_refs"]),
        ),
    )
    return producer_receipt


__all__ = ["persist_semantic_fibre_artifacts"]
