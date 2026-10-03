from __future__ import annotations

from typing import Any, Iterable

from .control_profiles import GOV1_PROFILE_ID, get_control_profile

CONTROL_CASE_SCHEMA_VERSION = "sl.gov1.control_case.v0_1"
SERVICE_CHANGE_STATES = (
    "proposed",
    "implemented",
    "verified",
    "validated",
    "released",
    "observed",
    "incident",
    "rolled_back",
)
EVIDENCE_STATES = (
    "source_written",
    "compile_checked",
    "fixture_checked",
    "runtime_observed",
    "production_observed",
)


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _refs(values: Iterable[Any], field: str, *, required: bool = True) -> list[str]:
    refs = [str(value).strip() for value in values if str(value).strip()]
    if required and not refs:
        raise ValueError(f"{field} requires at least one ref")
    return refs


def _enum(value: Any, allowed: tuple[str, ...], field: str) -> str:
    text = _text(value, field)
    if text not in allowed:
        raise ValueError(f"unsupported {field}: {text}")
    return text


def build_control_case(
    *,
    control_case_ref: str,
    subject_ref: str,
    subject_kind: str,
    requirement_refs: Iterable[Any],
    risk_refs: Iterable[Any],
    control_refs: Iterable[Any],
    implementation_refs: Iterable[Any],
    evidence_refs: Iterable[Any],
    residual_refs: Iterable[Any] = (),
    service_change_state: str,
    evidence_state: str,
    profile: str = GOV1_PROFILE_ID,
) -> dict[str, Any]:
    normalized_profile = get_control_profile(profile)
    return {
        "schema_version": CONTROL_CASE_SCHEMA_VERSION,
        "profile_id": normalized_profile["profile_id"],
        "source_standards": list(normalized_profile["source_standards"]),
        "control_case_ref": _text(control_case_ref, "control_case_ref"),
        "subject_ref": _text(subject_ref, "subject_ref"),
        "subject_kind": _text(subject_kind, "subject_kind"),
        "requirement_refs": _refs(requirement_refs, "requirement_refs"),
        "risk_refs": _refs(risk_refs, "risk_refs"),
        "control_refs": _refs(control_refs, "control_refs"),
        "implementation_refs": _refs(implementation_refs, "implementation_refs"),
        "evidence_refs": _refs(evidence_refs, "evidence_refs"),
        "residual_refs": _refs(residual_refs, "residual_refs", required=False),
        "service_change_state": _enum(
            service_change_state, SERVICE_CHANGE_STATES, "service_change_state"
        ),
        "evidence_state": _enum(evidence_state, EVIDENCE_STATES, "evidence_state"),
        "certification_claim": False,
        "creates_semantic_authority": False,
        "creates_review_authority": False,
    }


__all__ = [
    "CONTROL_CASE_SCHEMA_VERSION",
    "GOV1_PROFILE_ID",
    "SERVICE_CHANGE_STATES",
    "EVIDENCE_STATES",
    "build_control_case",
]
