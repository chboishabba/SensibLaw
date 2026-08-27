from __future__ import annotations

from src.runtime.performance_workload_scale import (
    MIN_REPRESENTATIVE_TOKENS,
    WorkloadScaleGate,
    assess_performance_workload,
)


def test_small_semantic_fixture_is_not_representative_performance_evidence() -> None:
    assessment = assess_performance_workload([{"token_count": 2522}])

    assert assessment.gate is WorkloadScaleGate.FAIL
    assert assessment.token_count == 2522
    assert assessment.representative is False


def test_multiple_receipts_compose_into_one_representative_corpus() -> None:
    assessment = assess_performance_workload(
        [
            {"parser_receipt": {"token_count": 12_500}},
            {"numeric_work_timing": {"token_count": 12_500}},
        ]
    )

    assert assessment.gate is WorkloadScaleGate.PASS
    assert assessment.token_count == MIN_REPRESENTATIVE_TOKENS
    assert assessment.document_count == 2


def test_missing_token_measurement_remains_unknown() -> None:
    assessment = assess_performance_workload([{"sentence_count": 95}])

    assert assessment.gate is WorkloadScaleGate.UNKNOWN
    assert assessment.token_count is None


def test_boolean_is_not_accepted_as_token_count() -> None:
    assessment = assess_performance_workload([{"token_count": True}])

    assert assessment.gate is WorkloadScaleGate.UNKNOWN
