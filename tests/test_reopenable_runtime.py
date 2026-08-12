from __future__ import annotations

from decimal import Decimal

import pytest

from src.policy.reopenable_runtime import (
    CandidateAssessment,
    CandidateKey,
    CompressionObservation,
    EvidenceFamily,
    EvidenceHorizon,
    ExecutionDisposition,
    RelevanceAccounting,
    ScalePoint,
    SignedEvidence,
    StageCost,
    assert_same_candidate_fibre,
    find_terminalisation_witness,
    parser_dominance_ratio,
    phase_of_residual,
    progressive_signed_residual,
    validate_affine_scale_series,
)


def candidate(target_id: int = 10) -> CandidateKey:
    return CandidateKey(demand_id=1, target_kind=1, target_id=target_id)


def test_phase_is_derived_from_fine_signed_residual() -> None:
    assert phase_of_residual(-12) == -1
    assert phase_of_residual(0) == 0
    assert phase_of_residual(41) == 1


def test_h3_h6_h9_accumulate_on_same_candidate_fibre() -> None:
    key = candidate()
    evidence = (
        SignedEvidence(key, "local", EvidenceFamily.LOCAL_STRUCTURAL, 7),
        SignedEvidence(key, "discourse", EvidenceFamily.DISCOURSE_TEMPORAL, -2),
        SignedEvidence(key, "external", EvidenceFamily.EXTERNAL_AUTHORITY, 5),
    )

    assert progressive_signed_residual(
        evidence, EvidenceHorizon.H3_LOCAL_STRUCTURAL
    ) == 7
    assert progressive_signed_residual(
        evidence, EvidenceHorizon.H6_DISCOURSE_TEMPORAL
    ) == 5
    assert progressive_signed_residual(
        evidence, EvidenceHorizon.H9_EXTERNAL_AUTHORITY
    ) == 10

    fibre = {key, candidate(11)}
    assert_same_candidate_fibre((fibre, set(fibre), frozenset(fibre)))


def test_horizon_may_not_silently_recreate_candidate_fibre() -> None:
    with pytest.raises(ValueError, match="candidate fibre"):
        assert_same_candidate_fibre(({candidate()}, {candidate(), candidate(11)}))


def test_pruned_candidate_remains_represented_and_admissible() -> None:
    assessment = CandidateAssessment(
        candidate=candidate(),
        represented_possible=True,
        active=False,
        supported=True,
        preferred=False,
        admissible=True,
        refuted=False,
        execution_disposition=ExecutionDisposition.PRUNED_REOPENABLE,
    )
    assert assessment.represented_possible
    assert assessment.admissible
    assert not assessment.active


def test_semantic_refutation_requires_evidence() -> None:
    with pytest.raises(ValueError, match="requires an evidence reference"):
        CandidateAssessment(
            candidate=candidate(),
            represented_possible=True,
            active=False,
            supported=False,
            preferred=False,
            admissible=False,
            refuted=True,
            execution_disposition=ExecutionDisposition.PRUNED_REOPENABLE,
        )


def test_relevance_accounting_keeps_explicit_outside_model_mass() -> None:
    accounting = RelevanceAccounting(
        active_mass=60,
        residual_candidate_mass=20,
        represented_residual_mass=5,
        outside_model_mass=15,
        total_mass=100,
    )
    assert accounting.retained_relevance == Decimal("0.6")
    assert accounting.explicit_ignorance == Decimal("0.15")


def test_normalized_mass_does_not_require_candidate_universe_completeness() -> None:
    accounting = RelevanceAccounting(
        active_mass=100,
        residual_candidate_mass=0,
        represented_residual_mass=0,
        outside_model_mass=0,
        total_mass=100,
    )
    observation = CompressionObservation(
        represented_candidate_count=10_000,
        active_candidate_count=8,
        relevance=accounting,
    )
    assert observation.active_compression_ratio == Decimal("0.0008")
    assert observation.relevance.retained_relevance == Decimal(1)
    # Nothing in RelevanceAccounting supplies a world-coverage witness.
    assert not hasattr(accounting, "world_complete")


def test_full_current_relevance_can_still_terminalise_future_state() -> None:
    # Both states currently project to the same public observation.  The hidden
    # provenance bit changes what the same admissible "reveal" action does.
    left = ("John", 0)
    right = ("John", 1)

    def project(state: tuple[str, int]) -> str:
        return state[0]

    def step(state: tuple[str, int], action: str) -> tuple[str, int]:
        public, hidden = state
        if action == "reveal":
            return (f"{public}:{hidden}", hidden)
        return state

    witness = find_terminalisation_witness(
        left=left,
        right=right,
        actions=("reveal",),
        project=project,
        step=step,
    )
    full_mass = RelevanceAccounting(100, 0, 0, 0, 100)

    assert full_mass.retained_relevance == Decimal(1)
    assert witness is not None
    assert witness.left_future_observation != witness.right_future_observation


def stage(
    *,
    workload: str,
    name: str,
    elapsed: int,
    work: int,
) -> StageCost:
    return StageCost(
        workload_ref=workload,
        stage_name=name,
        input_units=100,
        generated_units=100,
        retained_units=100,
        output_units=100,
        work_units=work,
        elapsed_microseconds=elapsed,
    )


def test_parser_dominance_must_be_earned_by_cheaper_post_parser_work() -> None:
    ratio = parser_dominance_ratio(
        parser_before=stage(workload="doc-1", name="spacy", elapsed=1000, work=1000),
        parser_after=stage(workload="doc-1", name="spacy", elapsed=900, work=900),
        post_parser_after=stage(
            workload="doc-1", name="post_parser_total", elapsed=90, work=80
        ),
        minimum_factor=Decimal(10),
    )
    assert ratio == Decimal(10)


def test_parser_dominance_rejects_parser_slowdown() -> None:
    with pytest.raises(ValueError, match="parser slower"):
        parser_dominance_ratio(
            parser_before=stage(
                workload="doc-1", name="spacy", elapsed=1000, work=1000
            ),
            parser_after=stage(
                workload="doc-1", name="spacy", elapsed=1100, work=1000
            ),
            post_parser_after=stage(
                workload="doc-1", name="post_parser_total", elapsed=10, work=10
            ),
        )


def test_parser_dominance_requires_identical_workload() -> None:
    with pytest.raises(ValueError, match="same workload"):
        parser_dominance_ratio(
            parser_before=stage(
                workload="doc-1", name="spacy", elapsed=1000, work=1000
            ),
            parser_after=stage(
                workload="doc-2", name="spacy", elapsed=900, work=900
            ),
            post_parser_after=stage(
                workload="doc-2", name="post_parser_total", elapsed=90, work=80
            ),
        )


def test_one_benchmark_point_is_not_a_scaling_claim() -> None:
    with pytest.raises(ValueError, match="not a scaling series"):
        validate_affine_scale_series(
            (ScalePoint("one", 100, 100),), slope=2, intercept=0
        )


def test_empirical_scale_series_must_fit_every_observed_point() -> None:
    validate_affine_scale_series(
        (
            ScalePoint("small", 100, 190),
            ScalePoint("medium", 1_000, 1_950),
            ScalePoint("large", 10_000, 19_990),
        ),
        slope=2,
        intercept=10,
    )

    with pytest.raises(ValueError, match="exceeded declared work envelope"):
        validate_affine_scale_series(
            (
                ScalePoint("small", 100, 190),
                ScalePoint("explosion", 1_000, 50_000),
            ),
            slope=2,
            intercept=10,
        )
