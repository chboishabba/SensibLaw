from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from src.policy.world_model import normalize_world_model

WORLD_MODEL_PROJECTION_SCHEMA_VERSION = "sl.world_model_projection.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_projection(
    *,
    projection_id: str,
    projection_kind: str,
    world_model: Mapping[str, Any],
    payload: Mapping[str, Any],
    summary: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    return {
        "schema_version": WORLD_MODEL_PROJECTION_SCHEMA_VERSION,
        "projection_id": _text(projection_id),
        "projection_kind": _text(projection_kind),
        "source_model": {
            "model_id": model["model_id"],
            "schema_version": model["schema_version"],
            "lane_family": model["lane_family"],
            "model_status": model["model_status"],
            "source_mode": model["source_mode"],
        },
        "payload": deepcopy(dict(payload)),
        "summary": deepcopy(dict(summary or {})),
        "metadata": deepcopy(dict(metadata or {})),
    }


def _projection_payload(
    *,
    world_model: Mapping[str, Any],
    projection_id: str,
    projection_kind: str,
    payload: Mapping[str, Any],
    summary: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_projection(
        projection_id=projection_id,
        projection_kind=projection_kind,
        world_model=world_model,
        payload=payload,
        summary=summary,
        metadata=metadata,
    )


def project_report(
    world_model: Mapping[str, Any],
    *,
    schema_version: str,
    artifact_id: str,
    lane_id: str,
    family_id: str,
    compiler_contract: Mapping[str, Any] | None = None,
    promotion_gate: Mapping[str, Any] | None = None,
    workflow_summary: Mapping[str, Any] | None = None,
    operator_workflow_surface: Mapping[str, Any] | None = None,
    claims: Sequence[Mapping[str, Any]] | None = None,
    summary: Mapping[str, Any] | None = None,
    extra_fields: Mapping[str, Any] | None = None,
    projection_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    claim_rows = [deepcopy(dict(row)) for row in (claims if claims is not None else model.get("claims", []))]
    summary_payload = deepcopy(dict(summary or model.get("summary") or {}))
    projection = _projection_payload(
        projection_id=f"report:{_text(artifact_id) or model['model_id']}",
        projection_kind="report",
        world_model=model,
        payload={
            "artifact_id": _text(artifact_id) or model["model_id"],
            "lane_id": _text(lane_id) or model["lane_family"],
            "family_id": _text(family_id) or model["lane_family"],
            "claim_count": len(claim_rows),
        },
        summary=summary_payload,
        metadata={
            "projection_role": "world_model_report",
            **deepcopy(dict(projection_metadata or {})),
        },
    )
    report = {
        "schema_version": _text(schema_version),
        "artifact_id": _text(artifact_id) or model["model_id"],
        "lane_id": _text(lane_id) or model["lane_family"],
        "family_id": _text(family_id) or model["lane_family"],
        "world_model_ref": deepcopy(projection["source_model"]),
        "projection": projection,
        "compiler_contract": deepcopy(dict(compiler_contract or {})),
        "promotion_gate": deepcopy(dict(promotion_gate or {})),
        "workflow_summary": deepcopy(dict(workflow_summary or {})),
        "operator_workflow_surface": deepcopy(dict(operator_workflow_surface or {})),
        "claims": claim_rows,
        "summary": summary_payload,
    }
    report.update(deepcopy(dict(extra_fields or {})))
    return report


def project_claim_table(
    world_model: Mapping[str, Any],
    *,
    projection_id: str | None = None,
    claim_rows: Sequence[Mapping[str, Any]] | None = None,
    summary: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    rows = [deepcopy(dict(row)) for row in (claim_rows if claim_rows is not None else model.get("claims", []))]
    return _projection_payload(
        projection_id=_text(projection_id) or f"claim_table:{model['model_id']}",
        projection_kind="claim_table",
        world_model=model,
        payload={
            "row_count": len(rows),
            "rows": rows,
        },
        summary=summary if isinstance(summary, Mapping) else {"row_count": len(rows)},
        metadata=metadata,
    )


def project_timeline(
    world_model: Mapping[str, Any],
    *,
    projection_id: str | None = None,
    timeline_rows: Sequence[Mapping[str, Any]] | None = None,
    event_rows: Sequence[Mapping[str, Any]] | None = None,
    summary: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    timelines = [
        deepcopy(dict(row))
        for row in (timeline_rows if timeline_rows is not None else model.get("timelines", []))
        if isinstance(row, Mapping)
    ]
    events = [
        deepcopy(dict(row))
        for row in (event_rows if event_rows is not None else model.get("events", []))
        if isinstance(row, Mapping)
    ]
    return _projection_payload(
        projection_id=_text(projection_id) or f"timeline:{model['model_id']}",
        projection_kind="timeline",
        world_model=model,
        payload={
            "timeline_count": len(timelines),
            "event_count": len(events),
            "timelines": timelines,
            "events": events,
        },
        summary=summary if isinstance(summary, Mapping) else {"timeline_count": len(timelines), "event_count": len(events)},
        metadata=metadata,
    )


def project_review_surface(
    world_model: Mapping[str, Any],
    *,
    projection_id: str | None = None,
    review_rows: Sequence[Mapping[str, Any]] | None = None,
    workflow_summary: Mapping[str, Any] | None = None,
    operator_workflow_surface: Mapping[str, Any] | None = None,
    summary: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    rows = [deepcopy(dict(row)) for row in (review_rows if review_rows is not None else model.get("claims", []))]
    return _projection_payload(
        projection_id=_text(projection_id) or f"review_surface:{model['model_id']}",
        projection_kind="review_surface",
        world_model=model,
        payload={
            "review_row_count": len(rows),
            "review_rows": rows,
            "workflow_summary": deepcopy(dict(workflow_summary or {})),
            "operator_workflow_surface": deepcopy(dict(operator_workflow_surface or {})),
        },
        summary=summary if isinstance(summary, Mapping) else {"review_row_count": len(rows)},
        metadata=metadata,
    )


def project_linkage_case(
    world_model: Mapping[str, Any],
    *,
    projection_id: str | None = None,
    case_id: str,
    contract_id: str | None = None,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    expected_anchor_ids: Sequence[str] = (),
    expected_terminal_ids: Sequence[str] = (),
    notes: Sequence[str] = (),
    summary: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    model = normalize_world_model(world_model)
    payload = {
        "case_id": _text(case_id),
        "contract_id": _text(contract_id),
        "node_count": len([row for row in nodes if isinstance(row, Mapping)]),
        "edge_count": len([row for row in edges if isinstance(row, Mapping)]),
        "nodes": [deepcopy(dict(row)) for row in nodes if isinstance(row, Mapping)],
        "edges": [deepcopy(dict(row)) for row in edges if isinstance(row, Mapping)],
        "expected_anchor_ids": [_text(value) for value in expected_anchor_ids if _text(value)],
        "expected_terminal_ids": [_text(value) for value in expected_terminal_ids if _text(value)],
        "notes": [_text(value) for value in notes if _text(value)],
    }
    return _projection_payload(
        projection_id=_text(projection_id) or f"linkage_case:{_text(case_id) or model['model_id']}",
        projection_kind="linkage_case",
        world_model=model,
        payload=payload,
        summary=summary
        if isinstance(summary, Mapping)
        else {"node_count": payload["node_count"], "edge_count": payload["edge_count"]},
        metadata=metadata,
    )


__all__ = [
    "WORLD_MODEL_PROJECTION_SCHEMA_VERSION",
    "build_projection",
    "project_claim_table",
    "project_linkage_case",
    "project_report",
    "project_review_surface",
    "project_timeline",
]
