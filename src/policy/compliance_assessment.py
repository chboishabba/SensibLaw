from __future__ import annotations

from typing import Any, Mapping

from .control_evaluator import evaluate_control_profile


COMPLIANCE_ASSESSMENT_SCHEMA_VERSION = "sl.compliance_assessment.v0_1"


def _count_status(group_results: list[Mapping[str, Any]], status: str) -> int:
    return sum(1 for row in group_results if str(row.get("status") or "").strip() == status)


def build_compliance_assessment(
    *,
    profile: Mapping[str, Any] | str,
    evidence_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    result = evaluate_control_profile(profile=profile, evidence_bundle=evidence_bundle)
    group_results = [
        row for row in result.get("control_group_results", []) if isinstance(row, Mapping)
    ]
    return {
        "schema_version": COMPLIANCE_ASSESSMENT_SCHEMA_VERSION,
        "profile_id": result["profile_id"],
        "subject_ref": result["subject_ref"],
        "subject_kind": result["subject_kind"],
        "status": result["status"],
        "control_group_results": group_results,
        "summary": {
            "group_count": len(group_results),
            "satisfied_count": _count_status(group_results, "satisfied"),
            "not_satisfied_count": _count_status(group_results, "not_satisfied"),
            "insufficient_evidence_count": _count_status(group_results, "insufficient_evidence"),
            "not_applicable_count": _count_status(group_results, "not_applicable"),
        },
    }


__all__ = [
    "COMPLIANCE_ASSESSMENT_SCHEMA_VERSION",
    "build_compliance_assessment",
]
