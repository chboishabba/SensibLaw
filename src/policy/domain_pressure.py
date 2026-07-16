"""Generic, receipt-ready structural-pressure assessments.

The module records diagnostic residual evidence without deciding truth,
authority, promotion, or edits. Domain profiles supply the expectations and
observations; this shared layer keeps the resulting carrier deterministic.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

DOMAIN_PRESSURE_ASSESSMENT_SCHEMA_VERSION = "sl.domain_pressure_assessment.v0_1"
RESIDUAL_STATES = frozenset({"exact", "partial", "contradictory", "unresolved"})
COVERAGE_STATES = frozenset({"observed", "incomplete", "uninspected", "invalid"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _string_rows(values: Sequence[Any]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def _residual_row(value: Mapping[str, Any]) -> dict[str, Any]:
    residual_kind = _text(value.get("residual_kind"))
    state = _text(value.get("state")) or "unresolved"
    if not residual_kind:
        raise ValueError("pressure residual requires residual_kind")
    if state not in RESIDUAL_STATES:
        raise ValueError(f"unsupported pressure residual state: {state}")

    payload = {
        "residual_kind": residual_kind,
        "state": state,
        "expected": deepcopy(dict(value.get("expected") or {})),
        "observed": deepcopy(dict(value.get("observed") or {})),
        "evidence_refs": _string_rows(value.get("evidence_refs") or ()),
        "summary": _text(value.get("summary")),
    }
    if _text(value.get("coverage_state")):
        coverage_state = _text(value.get("coverage_state"))
        if coverage_state not in COVERAGE_STATES:
            raise ValueError(f"unsupported pressure coverage state: {coverage_state}")
        payload["coverage_state"] = coverage_state
    return payload


def build_pressure_assessment(
    *,
    candidate_ref: str,
    domain_invariant_ref: str,
    residuals: Sequence[Mapping[str, Any]],
    coverage_state: str,
    review_disposition: str,
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a diagnostic-only assessment from caller-supplied residuals.

    The caller owns domain expectations and review policy. This function merely
    normalizes their comparison evidence and makes the non-authority boundary
    explicit.
    """

    normalized_coverage = _text(coverage_state) or "uninspected"
    if normalized_coverage not in COVERAGE_STATES:
        raise ValueError(
            f"unsupported assessment coverage state: {normalized_coverage}"
        )

    rows = [_residual_row(value) for value in residuals if isinstance(value, Mapping)]
    if not rows:
        raise ValueError("pressure assessment requires at least one residual")
    rows.sort(key=lambda row: row["residual_kind"])
    counts_by_state = {
        state: sum(1 for row in rows if row["state"] == state)
        for state in sorted(RESIDUAL_STATES)
    }

    return {
        "schema_version": DOMAIN_PRESSURE_ASSESSMENT_SCHEMA_VERSION,
        "candidate_ref": _text(candidate_ref),
        "domain_invariant_ref": _text(domain_invariant_ref),
        "coverage_state": normalized_coverage,
        "residuals": rows,
        "summary": {
            "residual_count": len(rows),
            "counts_by_state": counts_by_state,
            "has_unresolved": bool(counts_by_state["unresolved"]),
        },
        "evidence_refs": _string_rows(evidence_refs),
        "review_disposition": _text(review_disposition),
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
    }


__all__ = [
    "COVERAGE_STATES",
    "DOMAIN_PRESSURE_ASSESSMENT_SCHEMA_VERSION",
    "RESIDUAL_STATES",
    "build_pressure_assessment",
]
