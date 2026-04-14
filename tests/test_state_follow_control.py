from __future__ import annotations

from src.policy.state_follow_control import compute_state_awareness_priority


def test_state_priority_boosts_state_sources_only() -> None:
    score = compute_state_awareness_priority(["state"])
    assert score > 1.0


def test_mixed_federal_state_penalized() -> None:
    score = compute_state_awareness_priority(["state", "federal"], base_score=1.2)
    assert score == 1.9
    assert score < 1.2 + 0.8  # penalty applied


def test_local_and_state_stack() -> None:
    score = compute_state_awareness_priority(["local", "state", "state"])
    assert abs(score - (1.0 + 0.6 + 0.8)) < 1e-12
