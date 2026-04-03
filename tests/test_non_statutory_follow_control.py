from __future__ import annotations

from src.policy.non_statutory_follow_control import compute_non_statutory_weight


def test_standard_plus_statute_boost() -> None:
    score = compute_non_statutory_weight(["standard"], base_score=0.2)
    assert abs(score - 0.6) < 1e-12


def test_inquiry_and_regulator_support() -> None:
    score = compute_non_statutory_weight(["inquiry", "regulator_guidance"])
    assert abs(score - (0.5 + 0.5 + 0.6)) < 1e-12


def test_empty_vouches_returns_base() -> None:
    assert compute_non_statutory_weight([]) == 0.5
