"""Executable production-performance constitution for SensibLaw/ITIR.

Semantic completion/parity and empirical performance acceptance are deliberately
separate gates. Missing measurements remain ``unknown``; they never become
success evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from src.runtime.accepted_metric_ledger import (
    TARGET_POST_PARSER_TO_SPACY_RATIO,
    build_accepted_metric_ledger,
)


PERFORMANCE_CONSTITUTION_REF = "sensiblaw.performance-constitution.v0_3"


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
    ledger = build_accepted_metric_ledger(run)
    ratio = ledger.parser_relative_ratio
    if ratio is not None:
        return RequirementAssessment(
            "post_parser_to_spacy_ratio",
            AssessmentState.PASS
            if ratio <= TARGET_POST_PARSER_TO_SPACY_RATIO
            else AssessmentState.FAIL,
            observed=ratio,
            target=TARGET_POST_PARSER_TO_SPACY_RATIO,
            evidence=(
                "accepted-metric ledger: direct monotonic occupancy unions; "
                f"parser/post overlap={int(ledger.parser_post_overlap_ns or 0)} ns"
            ),
        )

    # Historical explicitly measured non-overlapping kernel timers remain valid.
    # Neither side may be synthesized by subtracting from total wall time.
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
                "requires accepted monotonic occupancy or explicit parser/post-parser "
                "kernel timings; outer LOCAL_PNF_COMPILATION and wall subtraction are invalid"
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


def _state_of(requirement: RequirementAssessment) -> AssessmentState:
    return requirement.state


def assess_replay_run(run: Mapping[str, Any]) -> dict[str, Any]:
    """Assess semantic completion separately from performance acceptance."""

    completion = _completion_state(run)
    parity = _parity_state(run)
    ratio = _post_parser_ratio(run)
    requirements = (completion, parity, ratio)

    semantic = (completion, parity)
    if any(_state_of(row) is AssessmentState.FAIL for row in semantic):
        semantic_gate = AssessmentState.FAIL
    elif any(_state_of(row) is AssessmentState.UNKNOWN for row in semantic):
        semantic_gate = AssessmentState.UNKNOWN
    else:
        semantic_gate = AssessmentState.PASS

    performance_gate = ratio.state
    accepted_performance = (
        semantic_gate is AssessmentState.PASS
        and performance_gate is AssessmentState.PASS
    )
    return {
        "contract_ref": PERFORMANCE_CONSTITUTION_REF,
        # compatibility name: this remains semantic/runtime completion only.
        "hard_gate": semantic_gate.value,
        "semantic_gate": semantic_gate.value,
        "performance_gate": performance_gate.value,
        "accepted_performance": accepted_performance,
        "requirements": [row.to_dict() for row in requirements],
        "accepted_metric_ledger": build_accepted_metric_ledger(run).to_dict(),
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
