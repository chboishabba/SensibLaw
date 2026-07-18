"""Canonical identity for immutable factor revisions.

A factor revision reference is derived from factor content. The derived
self-reference stored in metadata is excluded from the content hash. Legacy
transition-receipt identifiers can be normalized explicitly, while persistence
requires any supplied canonical identifier to agree with the factor payload.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256


def factor_revision_payload(factor: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(factor)
    metadata = dict(payload.get("metadata") or {})
    metadata.pop("factor_revision_ref", None)
    payload["metadata"] = metadata
    return payload


def computed_factor_revision_ref(factor: Mapping[str, Any]) -> str:
    return "factor-revision:" + canonical_sha256(factor_revision_payload(factor))


def factor_revision_ref(
    factor: Mapping[str, Any],
    *,
    validate_explicit: bool = True,
) -> str:
    computed = computed_factor_revision_ref(factor)
    explicit = str((factor.get("metadata") or {}).get("factor_revision_ref") or "")
    if explicit and validate_explicit and explicit != computed:
        raise ValueError(
            "factor_revision_ref metadata disagrees with canonical factor content"
        )
    return computed


def canonicalize_factor_revision(factor: Mapping[str, Any]) -> dict[str, Any]:
    payload = factor_revision_payload(factor)
    revision_ref = computed_factor_revision_ref(payload)
    payload["metadata"] = {
        **dict(payload.get("metadata") or {}),
        "factor_revision_ref": revision_ref,
        "factor_revision_identity_contract": "content-addressed-factor:v0_1",
    }
    return payload


def strip_factor_revision_ref(factor: Mapping[str, Any]) -> dict[str, Any]:
    return factor_revision_payload(factor)


__all__ = [
    "canonicalize_factor_revision",
    "computed_factor_revision_ref",
    "factor_revision_payload",
    "factor_revision_ref",
    "strip_factor_revision_ref",
]
