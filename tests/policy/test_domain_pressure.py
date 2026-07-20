from __future__ import annotations

import pytest

from src.policy.domain_pressure import build_pressure_assessment


def test_build_pressure_assessment_is_diagnostic_only_and_deterministic() -> None:
    assessment = build_pressure_assessment(
        candidate_ref="candidate:1",
        domain_invariant_ref="domain:climate:v1",
        coverage_state="observed",
        review_disposition="C",
        evidence_refs=["P14143", "P5991", "P14143"],
        residuals=[
            {
                "residual_kind": "subject_type",
                "state": "exact",
                "expected": {"kind": "company"},
                "observed": {"kind": "company"},
            },
            {
                "residual_kind": "peer_cohort",
                "state": "unresolved",
                "expected": {"members": "reviewed_only"},
                "observed": {"members": 0},
                "coverage_state": "uninspected",
            },
        ],
    )

    assert [row["residual_kind"] for row in assessment["residuals"]] == [
        "peer_cohort",
        "subject_type",
    ]
    assert assessment["evidence_refs"] == ["P14143", "P5991"]
    assert assessment["summary"]["has_unresolved"] is True
    assert assessment["authority"] == "diagnostic_only"
    assert assessment["promotion_effect"] == "not_evaluated"


def test_build_pressure_assessment_rejects_unknown_residual_state() -> None:
    with pytest.raises(ValueError, match="unsupported pressure residual state"):
        build_pressure_assessment(
            candidate_ref="candidate:1",
            domain_invariant_ref="domain:test:v1",
            coverage_state="observed",
            review_disposition="hold",
            residuals=[{"residual_kind": "shape", "state": "assumed"}],
        )
