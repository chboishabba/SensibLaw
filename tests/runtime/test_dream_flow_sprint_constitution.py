from __future__ import annotations

from src.runtime.dream_flow_sprint_constitution import (
    FormalModel,
    PhysicalEvidence,
    SprintSemantics,
    evaluate_sprint_transition,
)


def _model(*, gap: int = 2) -> FormalModel:
    return FormalModel(
        O="ITIR",
        R="delta-native dream flow",
        C="candidate strategy",
        S={"gap": gap, "authority": "same"},
        L="PNF fibre lattice",
        P="replace PG-synchronous local closure",
        G="single authority / fail closed",
        F=lambda state, proposal: int(state["gap"]),
    )


def _semantics() -> SprintSemantics:
    return SprintSemantics(
        constraints={
            "one_semantic_authority": lambda model: model.G.startswith("single"),
            "proposal_is_execution_strategy": lambda model: "replace" in model.P,
        },
        invariants={
            "authority_preserved": lambda lattice, state: state["authority"] == "same",
        },
        preconditions={
            "formal_target_known": lambda model: "dream flow" in model.R,
        },
        transition=lambda code, proposal, state: {
            **state,
            "gap": max(0, state["gap"] - 1),
        },
        postconditions={
            "gap_did_not_increase": lambda model, state: state["gap"] <= model.S["gap"],
        },
    )


def test_progress_requires_semantics_and_physical_evidence() -> None:
    receipt = evaluate_sprint_transition(
        _model(),
        _semantics(),
        physical=PhysicalEvidence(
            reference_work=10,
            candidate_work=8,
            reference_boundary_crossings=10,
            candidate_boundary_crossings=2,
            reference_wall_ns=100,
            candidate_wall_ns=90,
        ),
    )

    assert receipt.semantic_ready
    assert receipt.physical_ready
    assert receipt.progress_ready
    assert not receipt.accepted
    assert receipt.gap_before == 2
    assert receipt.gap_after == 1


def test_acceptance_requires_gap_closure() -> None:
    receipt = evaluate_sprint_transition(
        _model(gap=1),
        _semantics(),
        physical=PhysicalEvidence(
            reference_work=10,
            candidate_work=8,
            reference_boundary_crossings=10,
            candidate_boundary_crossings=2,
        ),
    )

    assert receipt.progress_ready
    assert receipt.gap_closed
    assert receipt.accepted


def test_failed_precondition_blocks_transition() -> None:
    semantics = SprintSemantics(
        constraints={"constraint": lambda model: True},
        invariants={"invariant": lambda lattice, state: True},
        preconditions={"blocked": lambda model: False},
        transition=lambda code, proposal, state: {**state, "gap": 0},
        postconditions={"post": lambda model, state: True},
    )
    receipt = evaluate_sprint_transition(
        _model(gap=3),
        semantics,
        physical=PhysicalEvidence(
            reference_work=10,
            candidate_work=1,
            reference_boundary_crossings=10,
            candidate_boundary_crossings=1,
        ),
    )

    assert receipt.next_state["gap"] == 3
    assert not receipt.semantic_ready
    assert not receipt.accepted


def test_speed_cannot_rescue_semantic_failure() -> None:
    semantics = SprintSemantics(
        constraints={"authority": lambda model: False},
        invariants={"invariant": lambda lattice, state: True},
        preconditions={"pre": lambda model: True},
        transition=lambda code, proposal, state: {**state, "gap": 0},
        postconditions={"post": lambda model, state: True},
    )
    receipt = evaluate_sprint_transition(
        _model(gap=1),
        semantics,
        physical=PhysicalEvidence(
            reference_work=1000,
            candidate_work=1,
            reference_boundary_crossings=1000,
            candidate_boundary_crossings=1,
            reference_wall_ns=1000,
            candidate_wall_ns=1,
        ),
    )

    assert receipt.physical_ready
    assert not receipt.semantic_ready
    assert not receipt.progress_ready
    assert not receipt.accepted


def test_missing_physical_evidence_is_not_acceptance() -> None:
    receipt = evaluate_sprint_transition(_model(gap=1), _semantics())

    assert receipt.semantic_ready
    assert receipt.gap_closed
    assert not receipt.physical_ready
    assert not receipt.accepted
