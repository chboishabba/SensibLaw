import pytest

from SensibLaw.src.metrics.proof_quality import compute_proof_quality_metrics


def test_compute_proof_quality_metrics_derives_expected_signals():
    artifacts = [
        {
            "status": "proof_ready",
            "title_quality": 0.8,
            "follow_source": "live",
            "priority": "high",
        },
        {
            "status": "needs_follow",
            "title_quality": 0.5,
            "follow_source": "fallback",
            "duplicate_of": "x",
            "priority": "medium",
        },
        {"title_quality": 0.2, "follow_source": "fallback"},
    ]

    result = compute_proof_quality_metrics(artifacts, previous_ready_count=1)

    assert result.total_artifacts == 3
    assert result.queue_readability_share == pytest.approx(2 / 3)
    assert result.proof_ready_share == pytest.approx(1 / 3)
    assert result.title_quality_score == pytest.approx((0.8 + 0.5 + 0.2) / 3)
    assert result.live_follow_share == pytest.approx(1 / 3)
    assert result.fallback_follow_share == pytest.approx(2 / 3)
    assert result.duplicate_pressure == 1
    assert result.duplicate_density == pytest.approx(1 / 3)
    assert result.status_counts == {"proof_ready": 1, "needs_follow": 1}
    assert result.priority_coverage_share == pytest.approx(2 / 3)
    assert result.plateau_flag is True


def test_compute_proof_quality_metrics_empty_history_is_safe():
    result = compute_proof_quality_metrics([])

    assert result.total_artifacts == 0
    assert result.queue_readability_share == pytest.approx(0.0)
    assert result.duplicate_density == pytest.approx(0.0)
    assert result.status_counts == {}
    assert result.plateau_flag is False
    assert result.priority_coverage_share == pytest.approx(0.0)
