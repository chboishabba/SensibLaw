from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


CONFLICT_SCHEMA_VERSION = "sl.world_model_conflict.v0_1"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _normalize_evidence_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized.append(
            {
                "run_id": _as_text(row.get("run_id")),
                "root_artifact_id": _as_text(row.get("root_artifact_id")),
                "canonical_form": _copy_mapping(row.get("canonical_form")),
            }
        )
    return normalized


def _semantic_conflict_view(canonical_form: Mapping[str, Any]) -> dict[str, Any]:
    qualifiers = canonical_form.get("qualifiers", {})
    if not isinstance(qualifiers, Mapping):
        qualifiers = {}
    non_temporal_qualifiers = {
        str(key): value
        for key, value in qualifiers.items()
        if str(key) not in {"P585", "P580", "P582"}
    }
    return {
        "subject": _as_text(canonical_form.get("subject")),
        "property": _as_text(canonical_form.get("property")),
        "value": _as_text(canonical_form.get("value")),
        "rank": _as_text(canonical_form.get("rank")),
        "qualifiers": non_temporal_qualifiers,
    }


def _conflict_id_for_claim(claim_id: str, rows: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(_as_text(claim_id).encode("utf-8"))
    for row in _normalize_evidence_rows(rows):
        digest.update(json.dumps(row, sort_keys=True).encode("utf-8"))
    return f"conflict:{digest.hexdigest()[:16]}"


@dataclass(frozen=True)
class ConflictSet:
    claim_id: str
    conflict_id: str
    candidate_ids: list[str]
    conflict_type: str
    evidence_rows: list[dict[str, Any]]
    resolution_status: str
    review_queue_ref: str
    schema_version: str = CONFLICT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "claim_id": self.claim_id,
            "conflict_id": self.conflict_id,
            "candidate_ids": list(self.candidate_ids),
            "conflict_type": self.conflict_type,
            "evidence_rows": list(self.evidence_rows),
            "resolution_status": self.resolution_status,
            "review_queue_ref": self.review_queue_ref,
        }


def build_conflict_set(
    *,
    claim_id: str,
    candidate_ids: Sequence[str],
    evidence_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_rows = _normalize_evidence_rows(evidence_rows)
    canonical_forms = {
        json.dumps(_semantic_conflict_view(row.get("canonical_form", {})), sort_keys=True)
        for row in normalized_rows
        if row.get("canonical_form")
    }
    has_conflict = len(canonical_forms) > 1
    conflict = ConflictSet(
        claim_id=_as_text(claim_id),
        conflict_id=_conflict_id_for_claim(claim_id, normalized_rows) if has_conflict else "",
        candidate_ids=[_as_text(value) for value in candidate_ids if _as_text(value)],
        conflict_type="canonical_form_divergence" if has_conflict else "none",
        evidence_rows=normalized_rows if has_conflict else [],
        resolution_status="requires_review" if has_conflict else "clear",
        review_queue_ref=f"review:{_as_text(claim_id)}" if has_conflict else "",
    )
    return conflict.as_dict()
