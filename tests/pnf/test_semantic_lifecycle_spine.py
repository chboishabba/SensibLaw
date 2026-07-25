from __future__ import annotations

from dataclasses import replace

import pytest

from src.pnf.semantic_lifecycle import CandidateAssessment
from src.pnf.semantic_lifecycle_spine import (
    normalize_definitive_invalidation,
    validate_projection_demand_factor_closure,
)


def _assessment(*, outcome: str, grounds: tuple[str, ...]) -> CandidateAssessment:
    return CandidateAssessment(
        document_ref="document:1",
        proposal_ref="proposal:1",
        semantic_coordinate_ref="coordinate:1",
        outcome=outcome,
        invalidation_grounds=grounds,
        evidence_refs=("evidence:1",),
        residual_refs=("NO_TYPED_MEET",),
        required_coverage_refs=(),
        observed_coverage_refs=("evidence:1",),
        applied_constraint_refs=(),
        applicable=True,
        coverage_complete=True,
    )


def test_definitive_invalidation_dominates_derivational_support() -> None:
    row = normalize_definitive_invalidation(
        (_assessment(outcome="both", grounds=("failed_typed_meet",)),)
    )[0]
    assert row.outcome == "violated"


def test_both_remains_for_genuine_counter_support() -> None:
    row = normalize_definitive_invalidation(
        (_assessment(outcome="both", grounds=()),)
    )[0]
    assert row.outcome == "both"


def test_projection_demand_requires_durable_factor() -> None:
    with pytest.raises(ValueError, match="durable graph factors"):
        validate_projection_demand_factor_closure(
            demands=(
                {
                    "demand_ref": "demand:1",
                    "source_factor_ref": "factor:summary-only",
                },
            ),
            durable_factor_refs=("factor:canonical",),
        )
