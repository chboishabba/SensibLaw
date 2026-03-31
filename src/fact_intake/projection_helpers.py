from __future__ import annotations

from typing import Any, Mapping

from .observation_builder import build_observation_id, build_observation_row


def observation_status_from_relation(row: Mapping[str, Any]) -> str:
    promotion_status = str(row.get("promotion_status") or "").strip()
    if promotion_status == "promoted":
        return "captured"
    if promotion_status == "abstained":
        return "abstained"
    return "uncertain"


def fact_status_for_statement(observations: list[dict[str, Any]]) -> str:
    statuses = {str(row.get("observation_status") or "") for row in observations}
    if "captured" in statuses or "uncertain" in statuses:
        return "candidate"
    if "abstained" in statuses:
        return "abstained"
    return "no_fact"


def build_role_observation(
    *,
    run_id: str,
    event_id: str,
    statement_id: str,
    excerpt_id: str,
    source_id: str,
    observation_order: int,
    role_index: int,
    predicate_key: str,
    predicate_family: str,
    object_text: str,
    object_type: str,
    object_ref: str | None,
    subject_text: str | None,
    observation_status: str,
    semantic_run_id: str,
    role_kind: str,
    extra_identity_fields: Mapping[str, Any] | None = None,
    extra_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity_fields = {
        "index": role_index,
        "predicate_key": predicate_key,
        "object_text": object_text,
    }
    if extra_identity_fields:
        identity_fields.update(dict(extra_identity_fields))
    provenance = {
        "semantic_run_id": semantic_run_id,
        "source_event_id": event_id,
        "role_kind": role_kind,
    }
    if extra_provenance:
        provenance.update(dict(extra_provenance))
    return build_observation_row(
        observation_id=build_observation_id(
            run_id=run_id,
            event_id=event_id,
            kind="role",
            identity_fields=identity_fields,
        ),
        statement_id=statement_id,
        excerpt_id=excerpt_id,
        source_id=source_id,
        observation_order=observation_order,
        predicate_key=predicate_key,
        predicate_family=predicate_family,
        object_text=object_text,
        object_type=object_type,
        object_ref=object_ref,
        subject_text=subject_text,
        observation_status=observation_status,
        provenance=provenance,
    )


def build_relation_observation(
    *,
    run_id: str,
    event_id: str,
    kind: str,
    statement_id: str,
    excerpt_id: str,
    source_id: str,
    observation_order: int,
    relation_index: int,
    predicate_key: str,
    predicate_family: str,
    object_text: str,
    object_type: str,
    object_ref: str | None,
    subject_text: str | None,
    observation_status: str,
    semantic_run_id: str,
    relation_candidate_id: Any,
    source_predicate_key: str,
    promotion_status: str,
    extra_identity_fields: Mapping[str, Any] | None = None,
    extra_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity_fields = {
        "index": relation_index,
        "predicate_key": source_predicate_key,
        "object_text": object_text,
    }
    if extra_identity_fields:
        identity_fields.update(dict(extra_identity_fields))
    provenance = {
        "semantic_run_id": semantic_run_id,
        "source_event_id": event_id,
        "relation_candidate_id": relation_candidate_id,
        "source_predicate_key": source_predicate_key,
        "promotion_status": promotion_status,
    }
    if extra_provenance:
        provenance.update(dict(extra_provenance))
    return build_observation_row(
        observation_id=build_observation_id(
            run_id=run_id,
            event_id=event_id,
            kind=kind,
            identity_fields=identity_fields,
        ),
        statement_id=statement_id,
        excerpt_id=excerpt_id,
        source_id=source_id,
        observation_order=observation_order,
        predicate_key=predicate_key,
        predicate_family=predicate_family,
        object_text=object_text,
        object_type=object_type,
        object_ref=object_ref,
        subject_text=subject_text,
        observation_status=observation_status,
        provenance=provenance,
    )
