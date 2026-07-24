from __future__ import annotations

import pytest

from src.pnf.semantic_fibres import (
    AxisObligation,
    FibreBoundaryObligation,
    FibreElement,
    OntologyAxis,
    SemanticCoordinate,
    SemanticFibreLedger,
    SemanticTransport,
    evaluate_fibre,
)


def _coordinate(*, role: str = "main") -> SemanticCoordinate:
    return SemanticCoordinate(
        document_ref="document:1",
        scope_ref="sentence:1",
        source_span_refs=("span:1",),
        statement_role=role,
        factor_family="semantic.causal_validation",
    )


def _element(
    coordinate: SemanticCoordinate,
    *,
    content_ref: str,
    role: str,
) -> FibreElement:
    return FibreElement(
        document_ref=coordinate.document_ref,
        coordinate_ref=coordinate.coordinate_ref,
        fibre_kind="constraint",
        content_ref=content_ref,
        derivation_role=role,
        producer_contract="integrated-semantic-producer:v0_1",
        operation_contract="constraint:causal:v1",
        source_refs=("statement:1",),
    )


def test_fibre_ledger_join_is_associative_commutative_and_idempotent() -> None:
    coordinate = _coordinate()
    support = _element(coordinate, content_ref="derivation:support", role="support")
    contradiction = _element(
        coordinate,
        content_ref="derivation:contradiction",
        role="contradict",
    )
    first = SemanticFibreLedger(coordinates=(coordinate,), elements=(support,))
    second = SemanticFibreLedger(
        coordinates=(coordinate,),
        elements=(contradiction,),
    )
    third = SemanticFibreLedger(
        coordinates=(coordinate,),
        boundary_obligations=(
            FibreBoundaryObligation(
                document_ref=coordinate.document_ref,
                coordinate_ref=coordinate.coordinate_ref,
                scope_ref=coordinate.scope_ref,
                boundary_kind="ontology_axis_frontier",
                evidence_refs=(support.element_ref,),
                frontier_refs=("class:unresolved",),
            ),
        ),
    )

    assert first.join(second).ledger_ref == second.join(first).ledger_ref
    assert first.join(first).ledger_ref == first.ledger_ref
    assert first.join(second).join(third).ledger_ref == first.join(
        second.join(third)
    ).ledger_ref
    assert len(first.join(second).fibre(coordinate.coordinate_ref)) == 2


def test_validation_is_computed_from_fibre_shape() -> None:
    coordinate = _coordinate()
    support = _element(coordinate, content_ref="support:1", role="support")
    contradiction = _element(
        coordinate,
        content_ref="contradiction:1",
        role="contradict",
    )
    unresolved = _element(
        coordinate,
        content_ref="frontier:1",
        role="undetermined",
    )

    assert evaluate_fibre(
        coordinate_ref=coordinate.coordinate_ref,
        elements=(support,),
    ).outcome == "satisfied"
    assert evaluate_fibre(
        coordinate_ref=coordinate.coordinate_ref,
        elements=(contradiction,),
    ).outcome == "violated"
    assert evaluate_fibre(
        coordinate_ref=coordinate.coordinate_ref,
        elements=(support, contradiction),
    ).outcome == "both"
    assert evaluate_fibre(
        coordinate_ref=coordinate.coordinate_ref,
        elements=(unresolved,),
    ).outcome == "undetermined"
    validation = evaluate_fibre(
        coordinate_ref=coordinate.coordinate_ref,
        elements=(support,),
        applicable=False,
    )
    assert validation.outcome == "inapplicable"
    assert validation.to_dict()["truth_closed"] is False


def test_discoverable_transport_cannot_silently_substitute_identity() -> None:
    source = _coordinate()
    target = SemanticCoordinate(
        document_ref="document:1",
        scope_ref="wikidata:Q30",
        source_span_refs=(),
        statement_role="external_target",
        factor_family="wikidata.entity",
        coordinate_kind="external",
    )
    with pytest.raises(ValueError, match="cannot permit substitution"):
        SemanticTransport(
            document_ref="document:1",
            source_coordinate_ref=source.coordinate_ref,
            target_coordinate_ref=target.coordinate_ref,
            transport_type="rdfs:seeAlso",
            strength="discoverable",
            evidence_refs=("alignment:1",),
            allowed_operations=("inspect", "substitute"),
        )

    transport = SemanticTransport(
        document_ref="document:1",
        source_coordinate_ref=source.coordinate_ref,
        target_coordinate_ref=target.coordinate_ref,
        transport_type="rdfs:seeAlso",
        strength="discoverable",
        evidence_refs=("alignment:1",),
        allowed_operations=("inspect", "enrich"),
    )
    payload = transport.to_dict()
    assert payload["identity_closed"] is False
    assert payload["semantic_state_promoted"] is False


def test_axis_obligations_and_boundaries_preserve_open_frontiers() -> None:
    coordinate = _coordinate()
    axis = OntologyAxis(
        axis_ref="ontology-axis:bfo:v1",
        label="BFO continuant/occurrent",
        authority_ref="ontology:bfo:v1",
        relation_refs=("wdt:P31", "wdt:P279"),
        root_refs=("wd:Q67518978",),
    )
    obligation = AxisObligation(
        document_ref="document:1",
        coordinate_ref=coordinate.coordinate_ref,
        axis_ref=axis.axis_ref,
        obligation_type="requires_occurrent_classification",
        trigger_refs=("statement:cause:1",),
        frontier_refs=("class:historical-topic",),
        state="undetermined",
    )
    boundary = FibreBoundaryObligation(
        document_ref="document:1",
        coordinate_ref=coordinate.coordinate_ref,
        scope_ref=coordinate.scope_ref,
        boundary_kind="ontology_axis_frontier",
        evidence_refs=(obligation.obligation_ref,),
        frontier_refs=("class:historical-topic",),
        required_axis_refs=(axis.axis_ref,),
        state="external",
    )
    ledger = SemanticFibreLedger(
        coordinates=(coordinate,),
        ontology_axes=(axis,),
        axis_obligations=(obligation,),
        boundary_obligations=(boundary,),
    )

    assert obligation.to_dict()["truth_closed"] is False
    assert ledger.boundary_obligations[0].state == "external"
    assert ledger.to_dict()["identity_promoted"] is False
