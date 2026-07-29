from __future__ import annotations

import pytest

from src.policy.algebra.revision_identity import factor_revision_ref
from src.policy.manifest_stream_validation import ManifestParentClosureValidator


def _factor(ref: str) -> dict[str, object]:
    return {
        "factor_ref": ref,
        "factor_type": "semantic.mention_identity",
        "alternatives": [],
        "residuals": [],
        "closure_state": "locally_closed",
        "metadata": {},
    }


def test_manifest_parent_closure_accepts_verified_cross_family_graph() -> None:
    base = _factor("factor:base")
    resulting = {**base, "closure_state": "requires_external_resolution"}
    base_revision = factor_revision_ref(base)
    resulting_revision = factor_revision_ref(resulting)
    candidate_set_ref = "candidate-set:1"
    build_ref = "build:1"

    validator = ManifestParentClosureValidator()
    validator.admit_factors((base,))
    validator.admit_refinements(
        (
            {
                "refinement_ref": "refinement:1",
                "prior_factor": base,
                "resulting_factor": resulting,
                "candidate_set_refs": (candidate_set_ref,),
            },
        )
    )
    validator.admit_candidate_sets(
        (
            {
                "candidate_set_ref": candidate_set_ref,
                "reference_factor_ref": "factor:base",
                "reference_factor_revision_ref": base_revision,
                "generator_build_ref": build_ref,
            },
        )
    )
    validator.admit_candidate_builds(
        (
            {
                "generator_build_ref": build_ref,
                "candidate_set_ref": candidate_set_ref,
                "reference_factor_revision_ref": base_revision,
            },
        )
    )
    validator.admit_demands(
        (
            {
                "demand_ref": "demand:1",
                "factor_ref": "factor:base",
                "factor_revision_ref": resulting_revision,
                "candidate_set_refs": (candidate_set_ref,),
            },
        )
    )
    validator.admit_anchors(
        (
            {
                "factor_ref": "factor:base",
                "factor_revision_ref": base_revision,
            },
        )
    )

    receipt = validator.finalize()
    assert receipt.factor_revision_count == 2
    assert receipt.candidate_set_count == 1
    assert receipt.candidate_build_count == 1
    assert receipt.candidate_link_count == 2
    assert receipt.to_dict()["parent_closure_complete"] is True


def test_manifest_parent_closure_rejects_missing_factor_revision() -> None:
    validator = ManifestParentClosureValidator()
    validator.admit_demands(
        (
            {
                "demand_ref": "demand:missing",
                "factor_ref": "factor:missing",
                "factor_revision_ref": "factor-revision:missing",
            },
        )
    )

    with pytest.raises(ValueError, match="missing_factor_revision_ref"):
        validator.finalize()


def test_manifest_parent_closure_rejects_candidate_set_without_build() -> None:
    base = _factor("factor:base")
    validator = ManifestParentClosureValidator()
    validator.admit_factors((base,))
    validator.admit_candidate_sets(
        (
            {
                "candidate_set_ref": "candidate-set:missing-build",
                "reference_factor_ref": "factor:base",
                "generator_build_ref": "build:missing",
            },
        )
    )

    with pytest.raises(ValueError, match="no verified build descriptor"):
        validator.finalize()


def test_manifest_parent_closure_rejects_link_to_unknown_set() -> None:
    base = _factor("factor:base")
    resulting = {**base, "closure_state": "requires_external_resolution"}
    validator = ManifestParentClosureValidator()
    validator.admit_factors((base,))
    validator.admit_refinements(
        (
            {
                "refinement_ref": "refinement:unknown-set",
                "prior_factor": base,
                "resulting_factor": resulting,
                "candidate_set_refs": ("candidate-set:unknown",),
            },
        )
    )

    with pytest.raises(ValueError, match="unverified set"):
        validator.finalize()
