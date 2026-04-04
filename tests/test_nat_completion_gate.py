from __future__ import annotations

from src.metrics.nat_completion_gate import load_nat_completion_fixture, scorecard


def test_nat_completion_scorecard_matches_fixture() -> None:
    report = load_nat_completion_fixture()
    metrics = scorecard(report)
    assert metrics["candidate_yield"] == 2
    assert metrics["dry_run_pass_rate"] == 1.0
    assert metrics["live_verification_pass_rate"] == 0.5
    assert metrics["data_loss_zero"] is True
    assert metrics["idempotency_score"] == 1.0
