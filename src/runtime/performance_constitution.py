"""Executable production-performance constitution for SensibLaw/ITIR.

This module intentionally separates hard semantic/runtime gates from empirical
performance targets and from claims that require paired controlled workloads.
Missing measurements remain ``unknown``; they never become evidence of failure
or success.

The north-star execution rule is:

    parse once -> compile numerically -> retain proofs -> reopen locally -> reuse

Ordinary post-spaCy execution should therefore be numeric, sparse, incremental,
and substantially cheaper than parser execution.  Compatibility/audit/export
surfaces may retain richer encodings, but those encodings are not permitted to
silently become the production semantic carrier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


PERFORMANCE_CONSTITUTION_REF = "sensiblaw.performance-constitution.v0_1"
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
    if parity is True:
        return RequirementAssessment(
            "semantic_parity",
            AssessmentState.PASS,
            observed=True,
            target=True,
            evidence="benchmark parity surface",
        )
    if parity is False:
        return RequirementAssessment(
            "semantic_parity",
            AssessmentState.FAIL,
            observed=False,
            target=True,
            evidence="benchmark parity surface",
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
        evidence="typed replay receipt",
    )


def _post_parser_ratio(run: Mapping[str, Any]) -> RequirementAssessment:
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
                "requires explicit spacy_parser and post_parser kernel timings; "
                "wall subtraction is not accepted"
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
        evidence="explicit kernel timings",
    )


def assess_replay_run(run: Mapping[str, Any]) -> dict[str, Any]:
    """Assess one replay without overclaiming absent measurements.

    A single cold run can establish strict completion, semantic parity, and an
    explicitly measured parser/post-parser ratio.  It cannot establish corpus
    learning economy or delta-local incremental work; those require controlled
    paired observations and are assessed separately by :func:`assess_reuse_pair`.
    """

    requirements = (
        _completion_state(run),
        _parity_state(run),
        _post_parser_ratio(run),
    )
    hard = tuple(
        row for row in requirements if row.requirement_ref in {"strict_replay_completed", "semantic_parity"}
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
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    """Check the controlled corpus-learning non-increase contract.

    Required observation fields are ``workload_ref``, ``configuration_ref``, and
    ``semantic_work_units``.  The comparison is deliberately unavailable when
    workload/configuration identity is not exact; similar-looking documents are
    not silently treated as the same controlled workload.
    """

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
        evidence = "requires identical workload/configuration refs and measured semantic_work_units"
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
