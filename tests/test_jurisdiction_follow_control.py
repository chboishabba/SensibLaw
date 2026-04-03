from __future__ import annotations

from src.policy.jurisdiction_follow_control import compute_jurisdiction_fit_score


def test_domestic_priority() -> None:
    assert compute_jurisdiction_fit_score(["domestic"]) > 1.0


def test_international_penalty_with_domestic() -> None:
    score = compute_jurisdiction_fit_score(["international", "domestic"], base_score=1.5)
    assert score < 2.5
    assert score <= 1.5 + 0.2 + 1.0 - 0.3


def test_regional_national_stack() -> None:
    score = compute_jurisdiction_fit_score(["regional", "national"])
    assert abs(score - (1.0 + 0.5 + 0.8)) < 1e-12
