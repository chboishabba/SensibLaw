"""Parity helpers for portable numeric semantic publication receipts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import json


def _mapping(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected mapping receipt: {path}")
    return dict(value)


def numeric_receipt_from_progress(path: Path) -> dict[str, Any] | None:
    """Return the latest durable numeric receipt coordinate from a phase ledger."""

    if not path.exists():
        return None
    payload = _mapping(path)
    selected: dict[str, Any] | None = None
    for event in payload.get("events") or ():
        if not isinstance(event, Mapping):
            continue
        details = event.get("details")
        if not isinstance(details, Mapping):
            continue
        digest = details.get("numeric_semantic_receipt_sha256")
        ref = details.get("numeric_semantic_receipt_ref")
        if digest and ref:
            selected = {
                "schema_version": "sensiblaw.numeric-semantic-parity-coordinate.v1",
                "receipt_ref": str(ref),
                "receipt_sha256": str(digest),
                "evidence_path": str(path),
            }
    return selected


def compare_numeric_receipts(
    reference: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if reference is None or current is None:
        return {
            "semantic_parity": None,
            "state": "numeric_receipt_missing",
            "reference_present": reference is not None,
            "current_present": current is not None,
        }
    reference_digest = str(reference.get("receipt_sha256") or "")
    current_digest = str(current.get("receipt_sha256") or "")
    if len(reference_digest) != 64 or len(current_digest) != 64:
        return {
            "semantic_parity": False,
            "state": "invalid_numeric_receipt_digest",
            "reference_sha256": reference_digest,
            "current_sha256": current_digest,
        }
    equal = reference_digest == current_digest
    return {
        "semantic_parity": equal,
        "state": "equal" if equal else "different",
        "reference_sha256": reference_digest,
        "current_sha256": current_digest,
        "identity_basis": "portable_numeric_semantic_publication_receipt:v1",
    }


__all__ = ["compare_numeric_receipts", "numeric_receipt_from_progress"]
