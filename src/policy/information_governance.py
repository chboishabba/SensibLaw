from __future__ import annotations

from typing import Any, Iterable

INFORMATION_ASSET_SCHEMA_VERSION = "sl.gov1.information_asset.v0_1"
PROCESSING_ACTIVITY_SCHEMA_VERSION = "sl.gov1.processing_activity.v0_1"


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _refs(values: Iterable[Any], field: str, *, required: bool = False) -> list[str]:
    refs = [str(value).strip() for value in values if str(value).strip()]
    if required and not refs:
        raise ValueError(f"{field} requires at least one ref")
    return refs


def build_information_asset(
    *,
    asset_ref: str,
    data_class: str,
    contains_pii: bool,
    sensitivity: str,
    accountable_role: str,
    purpose_ref: str,
    matter_ref: str,
    access_basis_ref: str,
    allowed_consumer_refs: Iterable[Any],
    storage_ref: str,
    external_provider_refs: Iterable[Any],
    retention_class_ref: str,
    revocation_or_deletion_state: str,
    audit_refs: Iterable[Any],
    **_: Any,
) -> dict[str, Any]:
    if not isinstance(contains_pii, bool):
        raise ValueError("contains_pii must be explicitly boolean")
    return {
        "schema_version": INFORMATION_ASSET_SCHEMA_VERSION,
        "asset_ref": _text(asset_ref, "asset_ref"),
        "data_class": _text(data_class, "data_class"),
        "contains_pii": contains_pii,
        "sensitivity": _text(sensitivity, "sensitivity"),
        "accountable_role": _text(accountable_role, "accountable_role"),
        "purpose_ref": _text(purpose_ref, "purpose_ref"),
        "matter_ref": _text(matter_ref, "matter_ref"),
        "access_basis_ref": _text(access_basis_ref, "access_basis_ref"),
        "allowed_consumer_refs": _refs(allowed_consumer_refs, "allowed_consumer_refs", required=True),
        "storage_ref": _text(storage_ref, "storage_ref"),
        "external_provider_refs": _refs(external_provider_refs, "external_provider_refs"),
        "retention_class_ref": _text(retention_class_ref, "retention_class_ref"),
        "revocation_or_deletion_state": _text(revocation_or_deletion_state, "revocation_or_deletion_state"),
        "audit_refs": _refs(audit_refs, "audit_refs", required=True),
        "creates_visibility_authority": False,
    }


def build_processing_activity(
    *,
    activity_ref: str,
    purpose_ref: str,
    input_asset_refs: Iterable[Any],
    output_asset_refs: Iterable[Any],
    processor_role_ref: str,
    external_provider_refs: Iterable[Any],
    control_refs: Iterable[Any],
    evidence_refs: Iterable[Any],
) -> dict[str, Any]:
    return {
        "schema_version": PROCESSING_ACTIVITY_SCHEMA_VERSION,
        "activity_ref": _text(activity_ref, "activity_ref"),
        "purpose_ref": _text(purpose_ref, "purpose_ref"),
        "input_asset_refs": _refs(input_asset_refs, "input_asset_refs", required=True),
        "output_asset_refs": _refs(output_asset_refs, "output_asset_refs", required=True),
        "processor_role_ref": _text(processor_role_ref, "processor_role_ref"),
        "external_provider_refs": _refs(external_provider_refs, "external_provider_refs"),
        "control_refs": _refs(control_refs, "control_refs", required=True),
        "evidence_refs": _refs(evidence_refs, "evidence_refs", required=True),
        "grants_matter_visibility": False,
        "creates_semantic_authority": False,
    }


__all__ = [
    "INFORMATION_ASSET_SCHEMA_VERSION",
    "PROCESSING_ACTIVITY_SCHEMA_VERSION",
    "build_information_asset",
    "build_processing_activity",
]
