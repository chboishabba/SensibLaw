from __future__ import annotations

from typing import Any, Mapping

from .observation_builder import build_observation_row
from .payload_builder import sha256_payload


def append_payload_observation(
    payload: dict[str, Any],
    *,
    statement_index: int,
    predicate_key: str,
    predicate_family: str,
    object_text: str,
    object_type: str,
    subject_text: str | None = None,
    object_ref: str | None = None,
    observation_status: str = "captured",
    identity_fields: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> None:
    statement = payload["statements"][statement_index]
    excerpt = payload["excerpts"][statement_index]
    source = next((row for row in payload["sources"] if row["source_id"] == excerpt["source_id"]), payload["sources"][0])
    observation_id = f"obs:{sha256_payload({'run_id': payload['run']['run_id'], **dict(identity_fields)})[:16]}"
    payload["observations"].append(
        build_observation_row(
            observation_id=observation_id,
            statement_id=statement["statement_id"],
            excerpt_id=excerpt["excerpt_id"],
            source_id=source["source_id"],
            observation_order=len(
                [row for row in payload["observations"] if row["statement_id"] == statement["statement_id"]]
            )
            + 1,
            predicate_key=predicate_key,
            predicate_family=predicate_family,
            object_text=object_text,
            object_type=object_type,
            object_ref=object_ref,
            subject_text=subject_text,
            observation_status=observation_status,
            provenance=provenance,
        )
    )


def append_payload_review(
    payload: dict[str, Any],
    *,
    fact_index: int,
    review_status: str,
    reviewer: str,
    note: str,
    identity_fields: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> None:
    fact = payload["fact_candidates"][fact_index]
    review_id = f"review:{sha256_payload({'run_id': payload['run']['run_id'], **dict(identity_fields)})[:16]}"
    payload["reviews"].append(
        {
            "review_id": review_id,
            "fact_id": fact["fact_id"],
            "review_status": review_status,
            "reviewer": reviewer,
            "note": note,
            "provenance": dict(provenance),
        }
    )


def append_payload_contestation(
    payload: dict[str, Any],
    *,
    fact_index: int,
    statement_index: int,
    status: str,
    reason_text: str,
    author: str,
    identity_fields: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> None:
    fact = payload["fact_candidates"][fact_index]
    statement = payload["statements"][statement_index]
    contestation_id = f"contest:{sha256_payload({'run_id': payload['run']['run_id'], **dict(identity_fields)})[:16]}"
    payload["contestations"].append(
        {
            "contestation_id": contestation_id,
            "fact_id": fact["fact_id"],
            "statement_id": statement["statement_id"],
            "contestation_status": status,
            "reason_text": reason_text,
            "author": author,
            "provenance": dict(provenance),
        }
    )
