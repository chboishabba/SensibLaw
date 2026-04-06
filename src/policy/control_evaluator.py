from __future__ import annotations

from typing import Any, Mapping

from .control_profiles import normalize_control_profile


CONTROL_ASSESSMENT_SCHEMA_VERSION = "sl.control_assessment.v0_1"
CONTROL_ASSESSMENT_STATUSES = (
    "satisfied",
    "not_satisfied",
    "insufficient_evidence",
    "not_applicable",
)


def _normalize_opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sb_payload(bundle: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = bundle.get("sb_contract_payload")
    return payload if isinstance(payload, Mapping) else {}


def _clause_result(
    *,
    clause_id: str,
    status: str,
    reason: str,
    evidence_refs: list[str] | None = None,
    missing_dimensions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "clause_id": clause_id,
        "status": status,
        "reason": reason,
        "evidence_refs": list(evidence_refs or []),
        "missing_dimensions": list(missing_dimensions or []),
    }


def evaluate_clause(
    *,
    clause_id: str,
    evidence_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    sb_payload = _sb_payload(evidence_bundle)
    semantic_evidence_refs = [
        str(value) for value in evidence_bundle.get("semantic_evidence_refs", []) if str(value).strip()
    ]

    if clause_id == "provenance_traceability":
        provenance_refs = [str(value) for value in sb_payload.get("provenance_refs", []) if str(value).strip()]
        lineage_refs = [str(value) for value in sb_payload.get("lineage_refs", []) if str(value).strip()]
        if provenance_refs and lineage_refs:
            return _clause_result(
                clause_id=clause_id,
                status="satisfied",
                reason="provenance and lineage refs are present",
                evidence_refs=provenance_refs + lineage_refs,
            )
        return _clause_result(
            clause_id=clause_id,
            status="insufficient_evidence",
            reason="provenance or lineage refs are missing",
            missing_dimensions=["provenance_refs", "lineage_refs"],
        )

    if clause_id == "follow_pressure_visibility":
        unresolved = _normalize_opt_text(sb_payload.get("unresolved_pressure_status"))
        if not unresolved:
            return _clause_result(
                clause_id=clause_id,
                status="insufficient_evidence",
                reason="unresolved pressure status is missing",
                missing_dimensions=["unresolved_pressure_status"],
            )
        if unresolved == "none":
            return _clause_result(
                clause_id=clause_id,
                status="satisfied",
                reason="no unresolved pressure remains",
                evidence_refs=["unresolved_pressure_status:none"],
            )
        if isinstance(sb_payload.get("follow_obligation"), Mapping):
            return _clause_result(
                clause_id=clause_id,
                status="satisfied",
                reason="follow obligation is present for unresolved pressure",
                evidence_refs=["follow_obligation"],
            )
        return _clause_result(
            clause_id=clause_id,
            status="not_satisfied",
            reason="follow obligation is missing for unresolved pressure",
            missing_dimensions=["follow_obligation"],
        )

    if clause_id == "semantic_grounding":
        if semantic_evidence_refs:
            return _clause_result(
                clause_id=clause_id,
                status="satisfied",
                reason="semantic grounding refs are present",
                evidence_refs=semantic_evidence_refs,
            )
        return _clause_result(
            clause_id=clause_id,
            status="insufficient_evidence",
            reason="semantic grounding refs are missing",
            missing_dimensions=["semantic_evidence_refs"],
        )

    if clause_id == "casey_execution_traceability":
        casey_refs = [
            ref for ref in sb_payload.get("casey_observer_refs", []) if isinstance(ref, Mapping)
        ]
        if not casey_refs:
            return _clause_result(
                clause_id=clause_id,
                status="not_applicable",
                reason="no Casey observer refs supplied",
            )
        bad_refs = [
            ref
            for ref in casey_refs
            if not _normalize_opt_text(ref.get("receipt_hash"))
            or not any(_normalize_opt_text(ref.get(field)) for field in ("workspace_id", "operation_id", "build_id"))
        ]
        if bad_refs:
            return _clause_result(
                clause_id=clause_id,
                status="not_satisfied",
                reason="Casey refs are missing required identifiers or receipt hashes",
                missing_dimensions=["casey_observer_refs"],
            )
        evidence_refs = [
            _normalize_opt_text(ref.get("operation_id"))
            or _normalize_opt_text(ref.get("build_id"))
            or _normalize_opt_text(ref.get("workspace_id"))
            for ref in casey_refs
        ]
        return _clause_result(
            clause_id=clause_id,
            status="satisfied",
            reason="Casey execution refs are traceable",
            evidence_refs=[value for value in evidence_refs if value],
        )

    raise KeyError(f"unsupported clause_id: {clause_id}")


def evaluate_control_group(
    *,
    control_group: Mapping[str, Any],
    evidence_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    clause_results = [
        evaluate_clause(clause_id=str(clause_id), evidence_bundle=evidence_bundle)
        for clause_id in control_group.get("member_clause_ids", [])
    ]
    statuses = [row["status"] for row in clause_results]
    if statuses and all(status == "not_applicable" for status in statuses):
        status = "not_applicable"
        reason = "all member clauses are not applicable"
    elif "not_satisfied" in statuses:
        status = "not_satisfied"
        reason = "at least one member clause is not satisfied"
    elif "insufficient_evidence" in statuses:
        status = "insufficient_evidence"
        reason = "at least one member clause lacks required evidence"
    else:
        status = "satisfied"
        reason = "all applicable member clauses are satisfied"
    return {
        "control_group_id": str(control_group.get("control_group_id") or ""),
        "title": str(control_group.get("title") or ""),
        "status": status,
        "reason": reason,
        "member_clause_results": clause_results,
    }


def evaluate_control_profile(
    *,
    profile: Mapping[str, Any] | str,
    evidence_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_profile = normalize_control_profile(profile)
    group_results = [
        evaluate_control_group(control_group=group, evidence_bundle=evidence_bundle)
        for group in normalized_profile.get("control_groups", [])
    ]
    statuses = [row["status"] for row in group_results]
    if statuses and all(status == "not_applicable" for status in statuses):
        overall_status = "not_applicable"
    elif "not_satisfied" in statuses:
        overall_status = "not_satisfied"
    elif "insufficient_evidence" in statuses:
        overall_status = "insufficient_evidence"
    else:
        overall_status = "satisfied"
    return {
        "schema_version": CONTROL_ASSESSMENT_SCHEMA_VERSION,
        "profile_id": normalized_profile["profile_id"],
        "title": normalized_profile["title"],
        "source_standards": list(normalized_profile.get("source_standards", [])),
        "subject_ref": str(evidence_bundle.get("subject_ref") or ""),
        "subject_kind": str(evidence_bundle.get("subject_kind") or ""),
        "status": overall_status,
        "control_group_results": group_results,
    }


__all__ = [
    "CONTROL_ASSESSMENT_SCHEMA_VERSION",
    "CONTROL_ASSESSMENT_STATUSES",
    "evaluate_clause",
    "evaluate_control_group",
    "evaluate_control_profile",
]
