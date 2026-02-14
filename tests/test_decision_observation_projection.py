from __future__ import annotations

import pytest


def test_case_observation_projection_requires_judge_id() -> None:
    from src.behavior_projection.decision_observation import ProjectionError, project_case_observation
    from src.judicial_behavior.model import CaseObservation

    c = CaseObservation(
        case_id="c1",
        jurisdiction_id="j",
        court_id="court",
        court_level="trial",
        decision_date="2020-01-01",
        wrong_type_id="neg",
        predicate_keys=("x",),
        outcome="plaintiff",
        judge_id=None,
    )
    with pytest.raises(ProjectionError):
        project_case_observation(c)


def test_action_observation_projection_requires_official_id() -> None:
    from src.behavior_projection.decision_observation import ProjectionError, project_action_observation
    from src.official_behavior.action_model import ActionObservation

    a = ActionObservation(
        action_id="a1",
        jurisdiction_id="us",
        institution_id="exec",
        institution_kind="executive",
        action_date="2003-03-20",
        policy_area_id="policy.foreign",
        outcome_label="implemented",
        predicate_keys=("ctx.threat.wmd_claimed",),
        official_id=None,
    )
    with pytest.raises(ProjectionError):
        project_action_observation(a)


def test_projection_is_deterministic_and_normalized() -> None:
    from src.behavior_projection.decision_observation import project_action_observation
    from src.official_behavior.action_model import ActionObservation

    a1 = ActionObservation(
        action_id="a1",
        jurisdiction_id="us",
        institution_id="exec",
        institution_kind="executive",
        action_date="2003-03-20",
        policy_area_id="policy.foreign",
        outcome_label="implemented",
        predicate_keys=("b", "a", "a"),
        normative_reference_ids=("z", "x", "x"),
        context_keys=("post_911", "post_911"),
        official_id="o1",
    )
    a2 = ActionObservation(
        action_id="a1",
        jurisdiction_id="us",
        institution_id="exec",
        institution_kind="executive",
        action_date="2003-03-20",
        policy_area_id="policy.foreign",
        outcome_label="implemented",
        predicate_keys=("a", "b"),
        normative_reference_ids=("x", "z"),
        context_keys=("post_911",),
        official_id="o1",
    )
    d1 = project_action_observation(a1)
    d2 = project_action_observation(a2)
    assert d1 == d2
    assert d1.predicate_keys == ("a", "b")
    assert d1.normative_reference_ids == ("x", "z")
    assert d1.context_keys == ("post_911",)

