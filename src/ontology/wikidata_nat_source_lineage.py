from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.policy.carriers.canonical import canonical_sha256


SOURCE_LINEAGE_RECEIPT_SCHEMA_VERSION = "sl.nat_source_lineage_receipt.v0_1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sequence(value: Any) -> Sequence[Any]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
        else ()
    )


def build_source_lineage_receipt(
    identity_receipt: Mapping[str, Any],
    *,
    relation: str,
    lineage_evidence_locator: str,
    derived_query_hints: Sequence[str] = (),
    verification_note: str = "",
) -> dict[str, Any]:
    """Preserve useful source lineage without weakening same-source identity.

    This is deliberately orthogonal to the balanced same-source fibre.  A report can
    be a source-of-source or sibling of the historical artifact while still being a
    strict ``different_source`` candidate for alternate-locator admission.
    """

    allowed = {"same_source", "source_of_source", "sibling", "unrelated", "unresolved"}
    if relation not in allowed:
        raise ValueError("invalid source-lineage relation")

    disposition = _text(identity_receipt.get("disposition"))
    if relation == "same_source" and disposition != "same_source":
        raise ValueError("same_source lineage requires same_source identity receipt")
    if relation in {"source_of_source", "sibling", "unrelated"} and disposition != "different_source":
        raise ValueError("non-identical terminal lineage requires different_source identity receipt")
    if relation == "unresolved" and disposition != "unresolved":
        raise ValueError("unresolved lineage requires unresolved identity receipt")
    if relation != "unresolved" and not lineage_evidence_locator.strip():
        raise ValueError("terminal source lineage requires an evidence locator")

    hints = sorted({_text(item) for item in _sequence(derived_query_hints) if _text(item)})
    payload_without_ref = {
        "schema_version": SOURCE_LINEAGE_RECEIPT_SCHEMA_VERSION,
        "same_source_identity_receipt_ref": _text(identity_receipt.get("receipt_ref")),
        "source_discovery_demand_ref": _text(identity_receipt.get("source_discovery_demand_ref")),
        "candidate_ref": _text(identity_receipt.get("candidate_ref")),
        "original_locator": _text(identity_receipt.get("original_locator")),
        "candidate_locator": _text(identity_receipt.get("candidate_locator")),
        "identity_disposition": disposition,
        "relation": relation,
        "lineage_evidence_locator": lineage_evidence_locator,
        "derived_query_hints": hints,
        "verification_note": verification_note,
        "alternate_fetch_admitted": relation == "same_source",
        "source_support_paid": False,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["receipt_ref"] = "nat-source-lineage-receipt:" + canonical_sha256(payload_without_ref)
    return payload


__all__ = ["SOURCE_LINEAGE_RECEIPT_SCHEMA_VERSION", "build_source_lineage_receipt"]
