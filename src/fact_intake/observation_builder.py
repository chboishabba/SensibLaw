from __future__ import annotations

from typing import Any, Mapping

from .payload_builder import sha256_payload


def build_observation_id(
    *,
    run_id: str,
    event_id: str,
    kind: str,
    identity_fields: Mapping[str, Any],
) -> str:
    payload = {"run_id": run_id, "event_id": event_id, "kind": kind, **dict(identity_fields)}
    return f"obs:{sha256_payload(payload)[:16]}"


def build_observation_row(
    *,
    observation_id: str,
    statement_id: str,
    excerpt_id: str,
    source_id: str,
    observation_order: int,
    predicate_key: str,
    predicate_family: str,
    object_text: str,
    object_type: str,
    object_ref: str | None,
    subject_text: str | None,
    observation_status: str,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "statement_id": statement_id,
        "excerpt_id": excerpt_id,
        "source_id": source_id,
        "observation_order": observation_order,
        "predicate_key": predicate_key,
        "predicate_family": predicate_family,
        "object_text": object_text,
        "object_type": object_type,
        "object_ref": object_ref,
        "subject_text": subject_text,
        "observation_status": observation_status,
        "provenance": dict(provenance),
    }
