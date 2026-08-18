"""Executable production-performance constitution for SensibLaw/ITIR.

This module intentionally separates hard semantic/runtime gates from empirical
performance targets and from claims that require paired controlled workloads.
Missing measurements remain ``unknown``; they never become evidence of failure
or success.

The north-star execution rule is:

    parse once -> compile numerically -> retain proofs -> reopen locally -> reuse

Ordinary post-spaCy execution should therefore be numeric, sparse, incremental,
and substantially cheaper than parser execution. Compatibility/audit/export
surfaces may retain richer encodings, but those encodings are not permitted to
silently become the production semantic carrier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


PERFORMANCE_CONSTITUTION_REF = "sensiblaw.performance-constitution.v0_2"
TARGET_POST_PARSER_TO_SPACY_RATIO = 0.10


class AssessmentState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class RequirementAssessment:
    requirement_ref: str
    state: AssessmentState
    observed: float | int | str | bool | None = None
    target: float | int | str | bool | None = None
    evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_ref": self.requirement_ref,
            "state": self.state.value,
            "observed": self.observed,
            "target": self.target,
            "evidence": self.evidence,
        }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _parity_state(run: Mapping[str, Any]) -> RequirementAssessment:
    parity = _mapping(run.get("parity")).get("semantic_parity")
    if parity is None:
        parity = _mapping(run.get("numeric_semantic_parity")).get("semantic_parity")
    if parity is True:
        return RequirementAssessment(
            "semantic_parity",
            AssessmentState.PASS,
            observed=True,
            target=True,
            evidence="portable numeric or compatibility semantic parity surface",
        )
    if parity is False:
        return RequirementAssessment(
            "semantic_parity",
            AssessmentState.FAIL,
            observed=False,
            target=True,
            evidence="portable numeric or compatibility semantic parity surface",
        )
    return RequirementAssessment(
        "semantic_parity",
        AssessmentState.UNKNOWN,
        observed=None,
        target=True,
        evidence="no comparable semantic baseline supplied",
    )


def _completion_state(run: Mapping[str, Any]) -> RequirementAssessment:
    completed = run.get("completed")
    if completed is None:
        completed = run.get("accepted")
    if completed is True:
        state = AssessmentState.PASS
    elif completed is False:
        state = AssessmentState.FAIL
    else:
        state = AssessmentState.UNKNOWN
    return RequirementAssessment(
        "strict_replay_completed",
        state,
        observed=completed if isinstance(completed, bool) else None,
        target=True,
        evidence="typed replay/acceptance receipt",
    )


def _post_parser_ratio(run: Mapping[str, Any]) -> RequirementAssessment:
    # Preferred evidence: unioned monotonic wall intervals from the strict
    # pipelined parser. These are measured intervals from all worker processes,
    # not wall-total subtraction. Parser/post overlap remains present in both
    # occupancy unions and is separately reported by the timing surface; this is
    # deliberately conservative for the <=10% target.
    timing = _mapping(run.get("numeric_work_timing"))
    parser_wall_ns = _number(timing.get("spacy_parser_wall_occupancy_ns"))
    post_wall_ns = _number(timing.get("post_parser_wall_occupancy_ns"))
    timing_basis = str(timing.get("timing_basis") or "")
    if (
        parser_wall_ns is not None
        and post_wall_ns is not None
        and parser_wall_ns > 0
        and "monotonic-wall-occupancy" in timing_basis
    ):
        ratio = post_wall_ns / parser_wall_ns
        overlap = _number(timing.get("parser_post_overlap_ns"))
        return RequirementAssessment(
            "post_parser_to_spacy_ratio",
            AssessmentState.PASS
            if ratio <= TARGET_POST_PARSER_TO_SPACY_RATIO
            else AssessmentState.FAIL,
            observed=ratio,
            target=TARGET_POST_PARSER_TO_SPACY_RATIO,
            evidence=(
                "explicit monotonic wall-occupancy unions; parser/post overlap "
                f"measured separately ({int(overlap or 0)} ns)"
            ),
        )

    # Historical non-overlapping kernel timers remain valid when explicitly
    # supplied. We never synthesize either side by subtracting from total wall.
    kernels = _mapping(run.get("kernel_seconds"))
    parser_seconds = _number(kernels.get("spacy_parser"))
    post_parser_seconds = _number(kernels.get("post_parser"))
    if parser_seconds is None or post_parser_seconds is None or parser_seconds <= 0:
        return RequirementAssessment(
            "post_parser_to_spacy_ratio",
            AssessmentState.UNKNOWN,
            observed=None,
            target=TARGET_POST_PARSER_TO_SPACY_RATIO,
            evidence=(
                "requires explicit monotonic wall occupancy or explicit parser/"
                "post-parser kernel timings; wall subtraction is not accepted"
            ),
        )
    ratio = post_parser_seconds / parser_seconds
    return RequirementAssessment(
        "post_parser_to_spacy_ratio",
        AssessmentState.PASS
        if ratio <= TARGET_POST_PARSER_TO_SPACY_RATIO
        else AssessmentState.FAIL,
        observed=ratio,
        target=TARGET_POST_PARSER_TO_SPACY_RATIO,
        evidence="explicit non-derived kernel timings",
    )


def assess_replay_run(run: Mapping[str, Any]) -> dict[str, Any]:
    """Assess one replay without overclaiming absent measurements."""

    requirements = (
        _completion_state(run),
        _parity_state(run),
        _post_parser_ratio(run),
    )
    hard = tuple(
        row
        for row in requirements
        if row.requirement_ref in {"strict_replay_completed", "semantic_parity"}
    )
    hard_failure = any(row.state is AssessmentState.FAIL for row in hard)
    hard_unknown = any(row.state is AssessmentState.UNKNOWN for row in hard)
    return {
        "contract_ref": PERFORMANCE_CONSTITUTION_REF,
        "hard_gate": (
            AssessmentState.FAIL.value
            if hard_failure
            else AssessmentState.UNKNOWN.value
            if hard_unknown
            else AssessmentState.PASS.value
        ),
        "requirements": [row.to_dict() for row in requirements],
        "claims_not_established_by_single_run": [
            "incremental_economy",
            "delta_local_recomputation",
            "same_domain_reuse",
            "corpus_scale_linearity",
        ],
    }


def _identity(observation: Mapping[str, Any]) -> tuple[str, str] | None:
    workload_ref = observation.get("workload_ref")
    configuration_ref = observation.get("configuration_ref")
    if not isinstance(workload_ref, str) or not workload_ref:
        return None
    if not isinstance(configuration_ref, str) or not configuration_ref:
        return None
    return workload_ref, configuration_ref


def assess_reuse_pair(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    """Check the controlled corpus-learning non-increase contract."""

    before_identity = _identity(before)
    after_identity = _identity(after)
    before_work = _number(before.get("semantic_work_units"))
    after_work = _number(after.get("semantic_work_units"))
    if (
        before_identity is None
        or after_identity is None
        or before_identity != after_identity
        or before_work is None
        or after_work is None
    ):
        state = AssessmentState.UNKNOWN
        evidence = (
            "requires identical workload/configuration refs and measured "
            "semantic_work_units"
        )
        non_increase = None
    else:
        non_increase = after_work <= before_work
        state = AssessmentState.PASS if non_increase else AssessmentState.FAIL
        evidence = "controlled identical workload/configuration comparison"
    return {
        "contract_ref": PERFORMANCE_CONSTITUTION_REF,
        "requirement_ref": "incremental_economy",
        "state": state.value,
        "observed": {
            "before_work_units": before_work,
            "after_work_units": after_work,
            "non_increase": non_increase,
        },
        "target": "W_after <= W_before",
        "evidence": evidence,
    }


__all__ = [
    "AssessmentState",
    "PERFORMANCE_CONSTITUTION_REF",
    "RequirementAssessment",
    "TARGET_POST_PARSER_TO_SPACY_RATIO",
    "assess_replay_run",
    "assess_reuse_pair",
]
