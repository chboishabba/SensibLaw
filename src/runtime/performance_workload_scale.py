"""Fail-closed workload scale gate for parser-relative performance claims.

Small fixtures remain useful semantic and kernel regressions, but they are not a
representative basis for ranking complete post-parser horizons.  The immediate
performance programme therefore requires at least 25,000 parsed tokens across a
controlled corpus before a run may be labelled representative.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping


PERFORMANCE_WORKLOAD_SCALE_REF = "sensiblaw.performance-workload-scale.v0_1"
MIN_REPRESENTATIVE_TOKENS = 25_000


class WorkloadScaleGate(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _parser_receipt(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    candidates = (
        receipt,
        _mapping(receipt.get("accepted_metric_ledger")),
        _mapping(receipt.get("numeric_work_timing")),
        _mapping(receipt.get("numeric_execution_timing")),
        _mapping(receipt.get("parser_receipt")),
        _mapping(receipt.get("receipt")),
        _mapping(receipt.get("details")),
        _mapping(receipt.get("artifacts")),
    )
    for candidate in candidates:
        if isinstance(candidate.get("token_count"), int):
            return candidate
        nested = _mapping(candidate.get("parser_receipt"))
        if isinstance(nested.get("token_count"), int):
            return nested
        timing = _mapping(candidate.get("numeric_work_timing"))
        if isinstance(timing.get("token_count"), int):
            return timing
    return {}


@dataclass(frozen=True, slots=True)
class WorkloadScaleAssessment:
    token_count: int | None
    document_count: int
    minimum_tokens: int
    gate: WorkloadScaleGate

    @property
    def representative(self) -> bool:
        return self.gate is WorkloadScaleGate.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": PERFORMANCE_WORKLOAD_SCALE_REF,
            "gate": self.gate.value,
            "representative": self.representative,
            "token_count": self.token_count,
            "document_count": self.document_count,
            "minimum_representative_tokens": self.minimum_tokens,
            "claim_boundary": (
                "fixtures below the token floor may establish semantic parity or "
                "kernel regressions but not representative post-parser ranking"
            ),
        }


def assess_performance_workload(
    receipts: Iterable[Mapping[str, Any]],
    *,
    minimum_tokens: int = MIN_REPRESENTATIVE_TOKENS,
) -> WorkloadScaleAssessment:
    if minimum_tokens < 1:
        raise ValueError("minimum_tokens must be positive")
    total = 0
    documents = 0
    observed_any = False
    for receipt in receipts:
        parser = _parser_receipt(receipt)
        token_count = parser.get("token_count")
        if isinstance(token_count, bool) or not isinstance(token_count, int):
            continue
        if token_count < 0:
            continue
        total += token_count
        documents += 1
        observed_any = True
    if not observed_any:
        return WorkloadScaleAssessment(
            token_count=None,
            document_count=0,
            minimum_tokens=minimum_tokens,
            gate=WorkloadScaleGate.UNKNOWN,
        )
    return WorkloadScaleAssessment(
        token_count=total,
        document_count=documents,
        minimum_tokens=minimum_tokens,
        gate=(
            WorkloadScaleGate.PASS
            if total >= minimum_tokens
            else WorkloadScaleGate.FAIL
        ),
    )


__all__ = [
    "MIN_REPRESENTATIVE_TOKENS",
    "PERFORMANCE_WORKLOAD_SCALE_REF",
    "WorkloadScaleAssessment",
    "WorkloadScaleGate",
    "assess_performance_workload",
]
