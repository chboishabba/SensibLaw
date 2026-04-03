from __future__ import annotations

from src.policy.parliamentary_follow_control import compute_parliamentary_weight


def test_debate_materials_boost() -> None:
    result = compute_parliamentary_weight(["debate"])
    assert result["score"] > 0.2
    assert "debate" in result["sources"]


def test_multiple_materials() -> None:
    result = compute_parliamentary_weight(["committee_report", "ministerial_statement"])
    assert abs(result["score"] - (0.2 + 0.4 + 0.5)) < 1e-12


def test_empty_materials_yield_base() -> None:
    result = compute_parliamentary_weight([])
    assert result == {"score": 0.2, "sources": []}
