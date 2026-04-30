from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


SB_TO_SL_CONSUMER_CONTRACT_VERSION = "sl.sb_to_sl_consumer_contract.v0_1"
COMPLIANCE_EVIDENCE_BUNDLE_SCHEMA_VERSION = "sl.compliance_evidence_bundle.v0_1"

SB_TO_SL_ALLOWED_FIELDS = {
    "compiled_state_id",
    "compiled_state_version",
    "follow_obligation",
    "legal_follow_pressure",
    "unresolved_pressure_status",
    "lineage_refs",
    "provenance_refs",
    "source_artifact_refs",
    "observer_overlay_refs",
    "casey_observer_refs",
}

SB_TO_SL_FORBIDDEN_FIELDS = {
    "activity_events",
    "events",
    "threads",
    "snapshots",
    "state",
    "activity_ledger",
    "drift",
    "summary_text",
    "candidate_graph",
    "workspace_payload",
}

_CASEY_ALLOWED_REF_FIELDS = {
    "workspace_id",
    "operation_id",
    "operation_kind",
    "build_id",
    "tree_id",
    "selection_digest",
    "receipt_hash",
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _normalize_opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nonempty_strings(values: Sequence[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _normalize_ref_items(values: Sequence[Any], *, keys: Sequence[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        item = {
            key: normalized
            for key in keys
            if (normalized := _normalize_opt_text(value.get(key))) is not None
        }
        if item:
            items.append(item)
    return items


def build_sb_to_sl_contract_payload(
    *,
    suite_normalized_artifact: Mapping[str, Any],
    observer_overlay_refs: Sequence[Mapping[str, Any]] | None = None,
    casey_observer_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    lineage = (
        suite_normalized_artifact.get("lineage")
        if isinstance(suite_normalized_artifact.get("lineage"), Mapping)
        else {}
    )
    provenance_anchor = (
        suite_normalized_artifact.get("provenance_anchor")
        if isinstance(suite_normalized_artifact.get("provenance_anchor"), Mapping)
        else {}
    )
    payload = {
        "compiled_state_id": _normalize_opt_text(suite_normalized_artifact.get("artifact_id")),
        "compiled_state_version": _normalize_opt_text(suite_normalized_artifact.get("schema_version")),
        "follow_obligation": (
            dict(suite_normalized_artifact.get("follow_obligation"))
            if isinstance(suite_normalized_artifact.get("follow_obligation"), Mapping)
            else None
        ),
        "legal_follow_pressure": (
            dict(suite_normalized_artifact.get("legal_follow_pressure"))
            if isinstance(suite_normalized_artifact.get("legal_follow_pressure"), Mapping)
            else None
        ),
        "unresolved_pressure_status": _normalize_opt_text(
            suite_normalized_artifact.get("unresolved_pressure_status")
        ),
        "lineage_refs": _nonempty_strings(lineage.get("upstream_artifact_ids") or []),
        "provenance_refs": _nonempty_strings(
            [
                provenance_anchor.get("source_artifact_id"),
                provenance_anchor.get("anchor_ref"),
            ]
        ),
        "source_artifact_refs": _nonempty_strings(lineage.get("upstream_artifact_ids") or []),
        "observer_overlay_refs": _normalize_ref_items(
            observer_overlay_refs or [],
            keys=("annotation_id", "observer_kind", "state_date", "sb_state_id"),
        ),
        "casey_observer_refs": _normalize_ref_items(
            casey_observer_refs or [],
            keys=tuple(sorted(_CASEY_ALLOWED_REF_FIELDS)),
        ),
    }
    return {key: value for key, value in payload.items() if value not in (None, [], {})}


def validate_sb_to_sl_contract_payload(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    keys = set(payload)
    forbidden = sorted(keys & SB_TO_SL_FORBIDDEN_FIELDS)
    errors.extend(f"forbidden SB->SL field: {field}" for field in forbidden)
    unknown = sorted(key for key in keys if key not in SB_TO_SL_ALLOWED_FIELDS and key not in SB_TO_SL_FORBIDDEN_FIELDS)
    errors.extend(f"unsupported SB->SL field: {field}" for field in unknown)

    if not _normalize_opt_text(payload.get("compiled_state_id")):
        errors.append("compiled_state_id required")
    if not _normalize_opt_text(payload.get("compiled_state_version")):
        errors.append("compiled_state_version required")

    unresolved = _normalize_opt_text(payload.get("unresolved_pressure_status"))
    if unresolved is None:
        errors.append("unresolved_pressure_status required")
    elif unresolved not in {"none", "follow_needed"}:
        errors.append(f"unsupported unresolved_pressure_status: {unresolved}")

    legal_follow_pressure = payload.get("legal_follow_pressure")
    if legal_follow_pressure is not None:
        if not isinstance(legal_follow_pressure, Mapping):
            errors.append("legal_follow_pressure must be an object")
        else:
            pressure_kind = _normalize_opt_text(legal_follow_pressure.get("kind"))
            pressure_version = _normalize_opt_text(legal_follow_pressure.get("version"))
            pressure_value = _normalize_opt_text(legal_follow_pressure.get("value"))
            if pressure_kind is None:
                errors.append("legal_follow_pressure.kind required when legal_follow_pressure is present")
            if pressure_version is None:
                errors.append("legal_follow_pressure.version required when legal_follow_pressure is present")
            if pressure_value is None:
                errors.append("legal_follow_pressure.value required when legal_follow_pressure is present")

    for index, ref in enumerate(payload.get("casey_observer_refs") or []):
        if not isinstance(ref, Mapping):
            errors.append(f"casey_observer_refs[{index}] must be an object")
            continue
        for field in ref:
            if field not in _CASEY_ALLOWED_REF_FIELDS:
                errors.append(f"casey_observer_refs[{index}] unsupported field: {field}")
        receipt_hash = _normalize_opt_text(ref.get("receipt_hash"))
        if receipt_hash is not None and not _HEX64.fullmatch(receipt_hash):
            errors.append(f"casey_observer_refs[{index}].receipt_hash must be 64 hex chars")
        if not any(_normalize_opt_text(ref.get(field)) for field in ("workspace_id", "operation_id", "build_id")):
            errors.append(
                f"casey_observer_refs[{index}] requires workspace_id, operation_id, or build_id"
            )
    return errors


def build_compliance_evidence_bundle(
    *,
    subject_ref: str,
    subject_kind: str,
    sb_contract_payload: Mapping[str, Any] | None = None,
    semantic_evidence_refs: Sequence[str] | None = None,
    native_artifact_refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    payload = dict(sb_contract_payload) if isinstance(sb_contract_payload, Mapping) else {}
    errors = validate_sb_to_sl_contract_payload(payload) if payload else []
    if errors:
        raise ValueError("; ".join(errors))

    evidence_refs = _nonempty_strings(
        [
            *(payload.get("lineage_refs") or []),
            *(payload.get("provenance_refs") or []),
            *(payload.get("source_artifact_refs") or []),
            *(semantic_evidence_refs or []),
            *(native_artifact_refs or []),
            *(
                [
                    f"legal_follow_pressure:{value}"
                    for value in (
                        _normalize_opt_text((payload.get("legal_follow_pressure") or {}).get("value")),
                        _normalize_opt_text((payload.get("legal_follow_pressure") or {}).get("version")),
                    )
                    if value
                ]
                if isinstance(payload.get("legal_follow_pressure"), Mapping)
                else []
            ),
            *[
                ref.get("annotation_id")
                for ref in payload.get("observer_overlay_refs", [])
                if isinstance(ref, Mapping)
            ],
            *[
                ref.get("operation_id") or ref.get("build_id") or ref.get("workspace_id")
                for ref in payload.get("casey_observer_refs", [])
                if isinstance(ref, Mapping)
            ],
        ]
    )
    return {
        "schema_version": COMPLIANCE_EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "subject_ref": str(subject_ref),
        "subject_kind": str(subject_kind),
        "sb_contract_payload": payload,
        "semantic_evidence_refs": _nonempty_strings(semantic_evidence_refs or []),
        "native_artifact_refs": _nonempty_strings(native_artifact_refs or []),
        "evidence_refs": evidence_refs,
    }


__all__ = [
    "COMPLIANCE_EVIDENCE_BUNDLE_SCHEMA_VERSION",
    "SB_TO_SL_ALLOWED_FIELDS",
    "SB_TO_SL_CONSUMER_CONTRACT_VERSION",
    "SB_TO_SL_FORBIDDEN_FIELDS",
    "build_compliance_evidence_bundle",
    "build_sb_to_sl_contract_payload",
    "validate_sb_to_sl_contract_payload",
]
