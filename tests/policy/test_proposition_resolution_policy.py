from __future__ import annotations

import pytest

from src.policy import (
    PROPOSITION_RESOLUTION_POLICY_VERSION,
    PROPOSITION_RESOLUTION_STATES,
    build_proposition_resolution_policy,
    validate_proposition_resolution_state,
)


def test_build_proposition_resolution_policy_is_fail_closed_and_policy_only() -> None:
    policy = build_proposition_resolution_policy()

    assert policy["version"] == PROPOSITION_RESOLUTION_POLICY_VERSION
    assert policy["allowed_states"] == ["abstain", "hold"]
    assert policy["default_state"] == "hold"
    assert policy["fail_closed"] is True
    assert "promote" in policy["excluded_categories"]["runtime_resolution"]
    assert "review_claim" in policy["excluded_categories"]["review_pressure"]
    assert "canonical_form_divergence" in policy["excluded_categories"]["contradiction_labels"]
    assert any("Policy-only resolution layer" in note for note in policy["notes"])


@pytest.mark.parametrize("state", sorted(PROPOSITION_RESOLUTION_STATES))
def test_validate_proposition_resolution_state_accepts_allowed_values(state: str) -> None:
    assert validate_proposition_resolution_state(state) == state


def test_validate_proposition_resolution_state_rejects_runtime_and_review_states() -> None:
    with pytest.raises(ValueError):
        validate_proposition_resolution_state("promote")

    with pytest.raises(ValueError):
        validate_proposition_resolution_state("must_review")

    with pytest.raises(ValueError):
        validate_proposition_resolution_state("direct_denial")
