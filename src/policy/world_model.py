from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

CANDIDATE_WORLD_MODEL_SCHEMA_VERSION = "sl.candidate_world_model.v0_1"
WORLD_MODEL_STATUS_VALUES = (
    "observed",
    "extracted",
    "normalized",
    "candidate",
    "coalesced",
    "conflicted",
    "authority_supported",
    "reviewed",
    "promoted",
    "deprecated",
    "stale",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)]


def _status_counts(*collections: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for collection in collections:
        for row in collection:
            status = _text(row.get("status")) or "candidate"
            counts[status] = counts.get(status, 0) + 1
    return counts


def build_state_node(
    *,
    node_id: str,
    node_kind: str,
    label: str,
    status: str = "candidate",
    source_anchor_ids: Sequence[str] = (),
    authority_surface: str | None = None,
    promotion_status: str | None = None,
    conflict_ids: Sequence[str] = (),
    residual: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "node_id": _text(node_id),
        "node_kind": _text(node_kind),
        "label": _text(label),
        "status": _text(status) or "candidate",
        "source_anchor_ids": [_text(value) for value in source_anchor_ids if _text(value)],
        "conflict_ids": [_text(value) for value in conflict_ids if _text(value)],
        "metadata": deepcopy(dict(metadata or {})),
    }
    if _text(authority_surface):
        payload["authority_surface"] = _text(authority_surface)
    if _text(promotion_status):
        payload["promotion_status"] = _text(promotion_status)
    if isinstance(residual, Mapping):
        payload["residual"] = deepcopy(dict(residual))
    return payload


def build_relation_edge(
    *,
    relation_id: str,
    source_id: str,
    target_id: str,
    relation_kind: str,
    status: str = "candidate",
    source_anchor_ids: Sequence[str] = (),
    authority_surface: str | None = None,
    promotion_status: str | None = None,
    strength: float | int | None = None,
    residual: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "relation_id": _text(relation_id),
        "source_id": _text(source_id),
        "target_id": _text(target_id),
        "relation_kind": _text(relation_kind),
        "status": _text(status) or "candidate",
        "source_anchor_ids": [_text(value) for value in source_anchor_ids if _text(value)],
        "metadata": deepcopy(dict(metadata or {})),
    }
    if _text(authority_surface):
        payload["authority_surface"] = _text(authority_surface)
    if _text(promotion_status):
        payload["promotion_status"] = _text(promotion_status)
    if strength is not None:
        payload["strength"] = strength
    if isinstance(residual, Mapping):
        payload["residual"] = deepcopy(dict(residual))
    return payload


def build_world_model(
    *,
    model_id: str,
    lane_family: str,
    model_status: str = "candidate",
    source_mode: str | None = None,
    entities: Sequence[Mapping[str, Any]] = (),
    claims: Sequence[Mapping[str, Any]] = (),
    relations: Sequence[Mapping[str, Any]] = (),
    events: Sequence[Mapping[str, Any]] = (),
    timelines: Sequence[Mapping[str, Any]] = (),
    authority_surfaces: Sequence[Mapping[str, Any]] = (),
    provenance_graph: Sequence[Mapping[str, Any]] = (),
    conflicts: Sequence[Mapping[str, Any]] = (),
    residuals: Sequence[Mapping[str, Any]] = (),
    update_rules: Sequence[Mapping[str, Any]] = (),
    projections: Sequence[Mapping[str, Any]] = (),
    summary: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    entity_rows = _mapping_rows(entities)
    claim_rows = _mapping_rows(claims)
    relation_rows = _mapping_rows(relations)
    event_rows = _mapping_rows(events)
    timeline_rows = _mapping_rows(timelines)
    authority_rows = _mapping_rows(authority_surfaces)
    provenance_rows = _mapping_rows(provenance_graph)
    conflict_rows = _mapping_rows(conflicts)
    residual_rows = _mapping_rows(residuals)
    update_rows = _mapping_rows(update_rules)
    projection_rows = _mapping_rows(projections)

    return {
        "schema_version": CANDIDATE_WORLD_MODEL_SCHEMA_VERSION,
        "model_id": _text(model_id),
        "lane_family": _text(lane_family),
        "model_status": _text(model_status) or "candidate",
        "source_mode": _text(source_mode) or "unspecified",
        "entities": entity_rows,
        "claims": claim_rows,
        "relations": relation_rows,
        "events": event_rows,
        "timelines": timeline_rows,
        "authority_surfaces": authority_rows,
        "provenance_graph": provenance_rows,
        "conflicts": conflict_rows,
        "residuals": residual_rows,
        "update_rules": update_rows,
        "projections": projection_rows,
        "summary": deepcopy(dict(summary or {})),
        "metadata": deepcopy(dict(metadata or {})),
        "status_counts": _status_counts(entity_rows, claim_rows, relation_rows, event_rows, timeline_rows),
    }


def normalize_world_model(world_model: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = world_model if isinstance(world_model, Mapping) else {}
    return build_world_model(
        model_id=_text(payload.get("model_id")) or _text(payload.get("artifact_id")),
        lane_family=_text(payload.get("lane_family")) or _text(payload.get("family_id")) or _text(payload.get("lane_id")),
        model_status=_text(payload.get("model_status")) or "candidate",
        source_mode=_text(payload.get("source_mode")) or None,
        entities=payload.get("entities", []),
        claims=payload.get("claims", []),
        relations=payload.get("relations", []),
        events=payload.get("events", []),
        timelines=payload.get("timelines", []),
        authority_surfaces=payload.get("authority_surfaces", []),
        provenance_graph=payload.get("provenance_graph", []),
        conflicts=payload.get("conflicts", []),
        residuals=payload.get("residuals", []),
        update_rules=payload.get("update_rules", []),
        projections=payload.get("projections", []),
        summary=payload.get("summary") if isinstance(payload.get("summary"), Mapping) else None,
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else None,
    )


__all__ = [
    "CANDIDATE_WORLD_MODEL_SCHEMA_VERSION",
    "WORLD_MODEL_STATUS_VALUES",
    "build_relation_edge",
    "build_state_node",
    "build_world_model",
    "normalize_world_model",
]
