from __future__ import annotations

from src.policy.polity_follow_control import compute_polity_awareness_score


def test_eu_member_state_penalty() -> None:
    score = compute_polity_awareness_score(["eu", "member_state"], base_score=0.5)
    assert abs(score - (0.5 + 0.5 + 0.8 - 0.2)) < 1e-12


def test_constitutional_and_national_boost() -> None:
    score = compute_polity_awareness_score(["constitutional_court", "national_court"], base_score=1.0)
    assert abs(score - (1.0 + 0.9 + 0.6 + 0.2)) < 1e-12


def test_regional_only() -> None:
    score = compute_polity_awareness_score(["regional_body"])
    assert abs(score - 1.4) < 1e-12
