"""Manifest-first parity for reference-backed semantic executions."""

from __future__ import annotations

from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256


REFERENCE_PARITY_SCHEMA_VERSION = "sensiblaw.reference-semantic-parity.v1"


def _family_surface(build: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    manifests = build.get("family_manifests") or {}
    if not isinstance(manifests, Mapping):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for family in sorted(manifests):
        descriptor = manifests[family]
        if not isinstance(descriptor, Mapping):
            continue
        result[str(family)] = {
            "record_count": int(descriptor.get("record_count") or 0),
            "byte_count": int(descriptor.get("byte_count") or 0),
            "ordered_digest": str(descriptor.get("ordered_digest") or ""),
            "encoding_ref": str(descriptor.get("encoding_ref") or ""),
        }
    return result


def reference_semantic_surface(build: Mapping[str, Any]) -> dict[str, Any]:
    """Return the compact identities required before any row-level diff."""

    materialized = build.get("materialized_reduction") or {}
    certificate = build.get("fixed_point_certificate") or {}
    typing = build.get("typing_hierarchies") or {}
    typing_refs = {
        str(key): str((value or {}).get("logical_typing_ref") or "")
        for key, value in typing.items()
        if isinstance(value, Mapping)
    }
    surface = {
        "document_ref": str(build.get("document_ref") or ""),
        "revision": int(build.get("revision") or 0),
        "materialized_graph_ref": str(
            materialized.get("graph_ref")
            or certificate.get("materialized_graph_ref")
            or ""
        ),
        "certificate_ref": str(certificate.get("certificate_ref") or ""),
        "ledger_ref": str(certificate.get("ledger_ref") or ""),
        "local_fixed_point": str(certificate.get("local_fixed_point") or ""),
        "owner_fingerprint": dict(build.get("owner_fingerprint") or {}),
        "families": _family_surface(build),
        "logical_typing_refs": dict(sorted(typing_refs.items())),
        "reference_finalization_contract": str(
            build.get("reference_finalization_contract") or ""
        ),
        "semantic_authority": "one_document",
    }
    return {
        **surface,
        "surface_ref": "reference-semantic-surface:"
        + canonical_sha256(surface),
    }


def compare_reference_surfaces(
    current: Mapping[str, Any], reference: Mapping[str, Any]
) -> dict[str, Any]:
    current_surface = reference_semantic_surface(current)
    reference_surface = reference_semantic_surface(reference)
    keys = sorted(set(current_surface) | set(reference_surface))
    mismatches = {
        key: {
            "current": current_surface.get(key),
            "reference": reference_surface.get(key),
        }
        for key in keys
        if current_surface.get(key) != reference_surface.get(key)
    }
    return {
        "schema_version": REFERENCE_PARITY_SCHEMA_VERSION,
        "matched": not mismatches,
        "current_surface_ref": current_surface["surface_ref"],
        "reference_surface_ref": reference_surface["surface_ref"],
        "mismatches": mismatches,
        "row_level_diff_required": bool(mismatches),
        "full_receipts_loaded_together": False,
    }


__all__ = [
    "REFERENCE_PARITY_SCHEMA_VERSION",
    "compare_reference_surfaces",
    "reference_semantic_surface",
]
