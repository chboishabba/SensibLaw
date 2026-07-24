from __future__ import annotations

from dataclasses import dataclass

from src.pnf.lifecycle_assessment_projection import (
    annotate_assessment_fibre_elements,
    annotate_assessment_proposals,
)


@dataclass(frozen=True)
class WorkItem:
    constraint_ref: str
    incident_factor_refs: tuple[str, ...]


def test_completed_scoped_barrier_satisfies_named_coverage_requirement() -> None:
    proposal = {
        "proposal_ref": "proposal:1",
        "scope_ref": "sentence:1",
        "input_observation_refs": ["observation:1"],
        "dependency_factor_refs": [],
        "coverage_requirements": ["sentence"],
        "candidate_payload": {"source_factor_ref": "factor:1"},
    }
    notice = {
        "notice_ref": "coverage-notice:1",
        "scope_ref": "sentence:1",
        "barrier": "sentence",
        "state": "complete",
        "evidence_refs": ["observation-delta:1"],
    }

    rows = annotate_assessment_proposals(
        proposals=(proposal,),
        work_items=(),
        coverage_notices=(notice,),
    )

    assert rows[0]["proposal_ref"] == "proposal:1"
    assert {
        "observation:1",
        "sentence",
        "coverage-notice:1",
        "observation-delta:1",
    }.issubset(set(rows[0]["input_observation_refs"]))
    assert rows[0]["candidate_payload"]["coverage_notice_refs"] == [
        "coverage-notice:1"
    ]


def test_wrong_scope_notice_does_not_discharge_requirement() -> None:
    proposal = {
        "proposal_ref": "proposal:1",
        "scope_ref": "sentence:1",
        "input_observation_refs": ["observation:1"],
        "dependency_factor_refs": [],
        "coverage_requirements": ["sentence"],
        "candidate_payload": {},
    }
    notice = {
        "notice_ref": "coverage-notice:other",
        "scope_ref": "sentence:2",
        "barrier": "sentence",
        "state": "complete",
        "evidence_refs": ["observation-delta:other"],
    }

    rows = annotate_assessment_proposals(
        proposals=(proposal,),
        work_items=(),
        coverage_notices=(notice,),
    )

    assert rows[0]["input_observation_refs"] == ["observation:1"]
    assert rows[0]["candidate_payload"]["coverage_notice_refs"] == []


def test_only_incident_constraints_are_attached() -> None:
    proposal = {
        "proposal_ref": "proposal:1",
        "scope_ref": "sentence:1",
        "input_observation_refs": [],
        "dependency_factor_refs": ["factor:dependency"],
        "coverage_requirements": [],
        "candidate_payload": {
            "source_factor_ref": "factor:source",
            "applied_constraint_refs": ["constraint:declared"],
        },
    }
    work_items = (
        WorkItem("constraint:source", ("factor:source",)),
        WorkItem("constraint:dependency", ("factor:dependency",)),
        WorkItem("constraint:unrelated", ("factor:other",)),
    )

    rows = annotate_assessment_proposals(
        proposals=(proposal,),
        work_items=work_items,
        coverage_notices=(),
    )

    assert rows[0]["candidate_payload"]["applied_constraint_refs"] == [
        "constraint:declared",
        "constraint:dependency",
        "constraint:source",
    ]


def test_unsupported_and_unresolved_states_are_assessment_undetermined() -> None:
    proposals = (
        {"proposal_ref": "proposal:unsupported", "support_state": "unsupported"},
        {"proposal_ref": "proposal:unresolved", "support_state": "unresolved"},
    )
    elements = (
        {
            "element_ref": "element:unsupported",
            "content_ref": "proposal:unsupported",
            "coordinate_ref": "coordinate:1",
            "derivation_role": "support",
        },
        {
            "element_ref": "element:unresolved",
            "content_ref": "proposal:unresolved",
            "coordinate_ref": "coordinate:2",
            "derivation_role": "support",
        },
    )

    rows = annotate_assessment_fibre_elements(
        proposals=proposals,
        fibre_elements=elements,
    )

    assert [row["derivation_role"] for row in rows] == [
        "undetermined",
        "undetermined",
    ]


def test_contested_state_exposes_support_and_contradiction() -> None:
    proposals = (
        {"proposal_ref": "proposal:contested", "support_state": "contested"},
    )
    elements = (
        {
            "element_ref": "element:support",
            "content_ref": "proposal:contested",
            "coordinate_ref": "coordinate:1",
            "derivation_role": "support",
            "source_refs": ["span:1"],
        },
    )

    rows = annotate_assessment_fibre_elements(
        proposals=proposals,
        fibre_elements=elements,
    )

    assert {row["derivation_role"] for row in rows} == {
        "support",
        "contradict",
    }
    assert all(row["assessment_support_state"] == "contested" for row in rows)
