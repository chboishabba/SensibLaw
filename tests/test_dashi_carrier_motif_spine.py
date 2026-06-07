from __future__ import annotations

import pytest

from src.text.dashi_carrier_motif_spine import (
    CARRIER_MOTIF_MODIFIER_KEY,
    CARRIER_MOTIF_SCHEMA,
    CarrierMotif,
    CarrierRole,
    ProjectionTarget,
    attach_carrier_motif_modifier,
    coerce_carrier_motif_annotation,
)
from src.text.residual_lattice import (
    PredicateAtom,
    QualifierState,
    ResidualLevel,
    TypedArg,
    WrapperState,
    meet_atom,
)


def _atom(*, wrapper_evidence_only: bool = True) -> PredicateAtom:
    return PredicateAtom(
        predicate="observe_projection_pressure",
        structural_signature="carrier_motif:projection_pressure",
        roles={
            "source": TypedArg(value="local-doc:example", entity_type="source_surface"),
            "phenomenon": TypedArg(value="contraction", entity_type="carrier_observation"),
        },
        qualifiers=QualifierState(polarity="positive"),
        wrapper=WrapperState(status="carrier_motif_review", evidence_only=wrapper_evidence_only),
        provenance=("../dashi_agda/FascisticContractionBridge.agda",),
        domain="carrier_motif_review",
    )


def test_coerce_annotation_normalizes_boundary_and_projection_alias() -> None:
    annotation = coerce_carrier_motif_annotation(
        {
            "schema": CARRIER_MOTIF_SCHEMA,
            "motif": "motifBraid",
            "roles": ["orientation", "pressure"],
            "source_surface": {
                "kind": "dashi_formal_receipt",
                "path": "../dashi_agda/DASHI/Physics/Closure/CarrierBraidStructureReceipt.agda",
            },
            "projection_target": "modifier_diagnostic",
        }
    )

    payload = annotation.to_dict()

    assert annotation.motif is CarrierMotif.MOTIF_BRAID
    assert annotation.projection_target is ProjectionTarget.MODIFIER_DIAGNOSTIC
    assert annotation.roles == (
        CarrierRole.ORIENTATION,
        CarrierRole.PRESSURE,
        CarrierRole.NON_PROMOTION_BOUNDARY,
    )
    assert payload["authority_boundary"] == {
        "non_authoritative": True,
        "promotion_authority": False,
        "legal_authority": False,
        "wikidata_live_edit_authority": False,
    }


def test_strict_coercion_rejects_unknown_motif() -> None:
    with pytest.raises(ValueError, match="unknown carrier motif"):
        coerce_carrier_motif_annotation({"motif": "Sweetgrass"})


def test_lenient_coercion_holds_unknown_motif_as_diagnostic() -> None:
    annotation = coerce_carrier_motif_annotation({"motif": "Sweetgrass"}, strict=False)

    assert annotation.motif is CarrierMotif.MOTIF_DIALECTIC
    assert annotation.diagnostics == ("unknown motif 'Sweetgrass'; held as diagnostic",)
    assert CarrierRole.NON_PROMOTION_BOUNDARY in annotation.roles


def test_coercion_rejects_authority_creep() -> None:
    with pytest.raises(ValueError, match="wikidata_live_edit_authority"):
        coerce_carrier_motif_annotation(
            {
                "motif": "motifWeave",
                "authority_boundary": {
                    "non_authoritative": True,
                    "promotion_authority": False,
                    "legal_authority": False,
                    "wikidata_live_edit_authority": True,
                },
            }
        )


def test_attach_carrier_motif_modifier_preserves_atom_shape_and_forces_evidence_only() -> None:
    original = _atom(wrapper_evidence_only=False)

    annotated = attach_carrier_motif_modifier(
        original,
        {
            "motif": "motifFascisticContraction",
            "roles": ["pressure", "defect"],
            "projection_target": "modifierDiagnosticTarget",
        },
    )

    assert original.modifiers == {}
    assert annotated.predicate == original.predicate
    assert annotated.structural_signature == original.structural_signature
    assert annotated.roles == original.roles
    assert annotated.qualifiers == original.qualifiers
    assert annotated.wrapper.evidence_only is True
    payload = annotated.modifiers[CARRIER_MOTIF_MODIFIER_KEY]
    assert payload["motif"] == "motifFascisticContraction"
    assert payload["projection_target"] == "modifierDiagnosticTarget"
    assert payload["authority_boundary"]["legal_authority"] is False


def test_carrier_motif_annotation_does_not_change_residual_meet() -> None:
    query = _atom()
    candidate = _atom()
    annotated_candidate = attach_carrier_motif_modifier(
        candidate,
        {
            "motif": "motifKnot",
            "roles": ["binding", "memory"],
            "projection_target": "provenance_target",
        },
    )

    baseline = meet_atom(query, candidate)
    annotated = meet_atom(query, annotated_candidate)

    assert baseline.level is ResidualLevel.EXACT
    assert annotated.level is baseline.level
    assert annotated.shared_roles == baseline.shared_roles
    assert annotated.missing_roles == baseline.missing_roles
    assert annotated.contradictions == baseline.contradictions


def test_carrier_motif_annotation_cannot_suppress_contradiction() -> None:
    query = _atom()
    candidate = PredicateAtom(
        predicate=query.predicate,
        structural_signature=query.structural_signature,
        roles={
            "source": TypedArg(value="local-doc:example", entity_type="source_surface"),
            "phenomenon": TypedArg(value="expansion", entity_type="carrier_observation"),
        },
        qualifiers=query.qualifiers,
        wrapper=query.wrapper,
        provenance=query.provenance,
        domain=query.domain,
    )
    annotated_candidate = attach_carrier_motif_modifier(
        candidate,
        {
            "motif": "motifAntifascistInvertibility",
            "roles": ["admissibility", "orientation"],
        },
    )

    assert meet_atom(query, annotated_candidate).level is ResidualLevel.CONTRADICTION
