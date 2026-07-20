from __future__ import annotations

from src.pnf.legal_adjunct import (
    LegalIRObservation,
    plan_legal_sources,
    project_legal_ir,
    project_normative_interaction_demands,
    typed_legal_meet,
)


def test_bare_action_does_not_schedule_legal_acquisition() -> None:
    rows = (
        {
            "demand_ref": "demand:drive",
            "factor_revision_ref": "factor-revision:drive",
            "structural_signature_ref": "signature:operation-event",
            "predicate_ref": "drive",
            "requested_facets": ("local_type_unresolved",),
        },
    )

    assert project_normative_interaction_demands(rows) == ()


def test_explicit_legal_facets_create_ready_typed_plan() -> None:
    rows = (
        {
            "demand_ref": "demand:legal-drive",
            "factor_revision_ref": "factor-revision:drive",
            "structural_signature_ref": "signature:operation-event",
            "requested_facets": (
                "legal.relevance_unresolved",
                "legal.jurisdiction:AU",
                "legal.source_role:primary_legislation",
                "legal.authority_level:official",
                "legal.request:conduct_prohibition",
                "legal.time:2024-07-09",
            ),
        },
    )

    demands = project_normative_interaction_demands(rows)
    assert len(demands) == 1
    assert demands[0].acquisition_ready is True
    plans = plan_legal_sources(demands)
    assert plans[0].state == "ready"
    assert plans[0].jurisdiction_ref == "AU"
    assert plans[0].source_role_refs == ("primary_legislation",)
    assert plans[0].authority_level_refs == ("official",)


def test_missing_jurisdiction_fails_closed() -> None:
    rows = (
        {
            "demand_ref": "demand:legal-drive",
            "factor_revision_ref": "factor-revision:drive",
            "structural_signature_ref": "signature:operation-event",
            "requested_facets": (
                "legal.relevance_unresolved",
                "legal.source_role:primary_legislation",
                "legal.authority_level:official",
            ),
        },
    )

    demand = project_normative_interaction_demands(rows)[0]
    assert demand.acquisition_ready is False
    assert demand.open_slots == ("jurisdiction_unresolved",)
    assert plan_legal_sources((demand,))[0].state == "blocked_missing_context"


def test_legal_ir_is_only_projected_from_legal_pnf_types() -> None:
    ordinary = {
        "factor_ref": "factor:drive",
        "factor_revision_ref": "revision:drive",
        "factor_type_ref": "semantic.eventuality",
        "structural_signature_ref": "signature:operation-event",
    }
    legal = {
        "factor_ref": "factor:norm",
        "factor_revision_ref": "revision:norm",
        "factor_type_ref": "semantic.normative_relation",
        "structural_signature_ref": "signature:operation-event",
        "predicate_ref": "normative-prohibition",
        "role_bindings": {"bearer": "actor:person", "content": "event:operate"},
        "qualifier_state": {"polarity": "negative", "modality": "obligation"},
        "wrapper_state": {"authority": "statute-candidate"},
        "provenance_refs": ("span:1",),
        "residual_refs": ("commencement_unresolved",),
    }

    observations = project_legal_ir((ordinary, legal))
    assert len(observations) == 1
    assert observations[0].pnf_factor_ref == "factor:norm"
    assert observations[0].predicate_ref == "normative-prohibition"
    assert observations[0].projection_state == "candidate"


def test_cross_fibre_comparison_is_no_typed_meet() -> None:
    observation = LegalIRObservation(
        observation_ref="legal-ir:1",
        pnf_factor_ref="factor:norm",
        pnf_revision_ref="revision:norm",
        structural_signature_ref="signature:normative-operation",
        predicate_ref="normative-prohibition",
        role_bindings={},
        qualifier_state={},
        wrapper_state={},
        provenance_refs=(),
        residual_refs=(),
    )

    result = typed_legal_meet(
        {
            "factor_revision_ref": "revision:world",
            "structural_signature_ref": "signature:publication-event",
        },
        observation,
    )

    assert result.structural_state == "NO_TYPED_MEET"
    assert result.applicability_closed is False
    assert result.residual_refs == ("cross_fibre_incommensurable",)


def test_same_fibre_meet_remains_candidate_and_open() -> None:
    observation = LegalIRObservation(
        observation_ref="legal-ir:1",
        pnf_factor_ref="factor:norm",
        pnf_revision_ref="revision:norm",
        structural_signature_ref="signature:operation-event",
        predicate_ref="normative-prohibition",
        role_bindings={},
        qualifier_state={},
        wrapper_state={},
        provenance_refs=(),
        residual_refs=(),
    )

    result = typed_legal_meet(
        {
            "factor_revision_ref": "revision:world",
            "structural_signature_ref": "signature:operation-event",
            "legal_coordinates": {
                "jurisdiction_state": "satisfied",
                "temporal_state": "unresolved",
                "conduct_state": "satisfied",
            },
        },
        observation,
    )

    assert result.structural_state == "same_fibre_candidate"
    assert result.jurisdiction_state == "satisfied"
    assert result.temporal_state == "unresolved"
    assert result.applicability_closed is False
    assert "legal_applicability_unresolved" in result.residual_refs
