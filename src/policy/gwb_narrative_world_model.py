from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from src.gwb_us_law.semantic import build_gwb_semantic_report
from src.policy.world_model import build_world_model as _build_world_model
from src.policy.world_model_adapters import (
    StateNodeMapping,
    build_authority_surface_rows,
    build_claim_nodes_from_mapping,
    build_event_nodes_from_mapping,
    build_review_inputs,
    build_timeline_nodes_from_mapping,
)
from src.policy.world_model_profiles import build_profile
from src.policy.world_model_projections import (
    project_claim_table,
    project_linkage_case,
    project_report as _project_report,
    project_review_surface,
    project_timeline,
)

GWB_NARRATIVE_TIMELINE_WORLD_MODEL_SCHEMA_VERSION = "sl.gwb_narrative_timeline_world_model.v0_1"
GWB_NARRATIVE_TIMELINE_PROFILE_ID = "gwb_narrative_timeline"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _relation_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    relation_rows = [
        {
            "event_id": _text(event.get("event_id")),
            **deepcopy(dict(relation)),
        }
        for event in _mapping_rows(report.get("per_event"))
        for relation in _mapping_rows(event.get("relation_candidates"))
    ]
    return build_claim_nodes_from_mapping(
        relation_rows,
        predicate=lambda row, _context: bool(_text(row.get("event_id")) and _text(row.get("candidate_id"))),
        mapping=StateNodeMapping(
            node_id=lambda row, _context: f"relation:{_text(row.get('event_id'))}:{_text(row.get('candidate_id'))}",
            node_kind=lambda _row, _context: "relation_candidate",
            label=lambda row, _context: _text(row.get("display_label"))
            or _text(row.get("predicate_key"))
            or _text(row.get("candidate_id")),
            status=lambda row, _context: _text(row.get("promotion_status")) or "candidate",
            source_anchor_ids=lambda row, _context: [_text(row.get("event_id"))] if _text(row.get("event_id")) else [],
            promotion_status=lambda row, _context: _text(row.get("promotion_status")) or "candidate_only",
            metadata=lambda row, _context: {
                "event_id": _text(row.get("event_id")),
                "candidate_id": _text(row.get("candidate_id")),
                "predicate_key": _text(row.get("predicate_key")),
                "semantic_basis": _text(row.get("semantic_basis")),
            },
        ),
    )


def build_world_model(conn: Any, *, run_id: str) -> dict[str, Any]:
    raw_report = build_gwb_semantic_report(conn, run_id=run_id)
    profile = build_profile(
        profile_id=GWB_NARRATIVE_TIMELINE_PROFILE_ID,
        lane_family="gwb",
        source_kinds=["book_pdf", "wikipedia", "wikidata", "public_bio", "archive_record"],
        authority_surfaces=["gwb_narrative_review_surface", "workflow_tranche_anchor"],
        promotion_policy="candidate_only",
        default_projection_kinds=["report", "claim_table", "timeline", "review_surface", "linkage_case"],
        metadata={"lane_id": "gwb", "profile_role": "narrative_timeline"},
    )
    per_event_rows = _mapping_rows(raw_report.get("per_event"))
    events = build_event_nodes_from_mapping(
        per_event_rows,
        predicate=lambda row, _context: bool(_text(row.get("event_id"))),
        field_mapping={
            "event_id": "event_id",
            "status": lambda _row, _context: "candidate",
            "metadata": lambda row, _context: deepcopy(dict(row)),
        },
    )
    timelines = build_timeline_nodes_from_mapping(
        [{}],
        field_mapping={
            "timeline_id": lambda _row, context: f"timeline:{_text(context.get('run_id'))}",
            "status": lambda _row, _context: "candidate",
            "event_ids": lambda _row, context: [
                _text(row.get("event_id")) for row in _mapping_rows(context.get("per_event_rows")) if _text(row.get("event_id"))
            ],
        },
        context={"run_id": run_id, "per_event_rows": per_event_rows},
    )
    claims = _relation_rows(raw_report)
    return _build_world_model(
        model_id=run_id,
        lane_family="gwb",
        model_status="candidate",
        source_mode="gwb_semantic_report",
        claims=claims,
        events=events,
        timelines=timelines,
        authority_surfaces=build_authority_surface_rows(profile["authority_surfaces"]),
        summary={
            "claim_count": len(claims),
            "event_count": len(events),
            "promoted_relation_count": len(_mapping_rows(raw_report.get("promoted_relations"))),
            "candidate_only_relation_count": len(_mapping_rows(raw_report.get("candidate_only_relations"))),
        },
        metadata={
            "artifact_id": run_id,
            "lane_id": "gwb",
            "profile": profile,
            "adapter_stack": ["claim_nodes_from_mapping", "event_nodes_from_mapping", "timeline_nodes_from_mapping"],
            "raw_report": deepcopy(dict(raw_report)),
            "review_inputs": build_review_inputs(
                raw_report,
                field_names=("per_event", "promoted_relations", "candidate_only_relations", "source_documents", "review_summary"),
                extra_fields={"run_id": run_id},
            ),
        },
    )


def project_report(world_model: Mapping[str, Any]) -> dict[str, Any]:
    model = dict(world_model)
    metadata = model.get("metadata") if isinstance(model.get("metadata"), Mapping) else {}
    raw_report = metadata.get("raw_report") if isinstance(metadata.get("raw_report"), Mapping) else {}
    report = dict(raw_report)
    report.update(
        _project_report(
            world_model=model,
            schema_version=GWB_NARRATIVE_TIMELINE_WORLD_MODEL_SCHEMA_VERSION,
            artifact_id=_text(metadata.get("artifact_id")) or _text(model.get("model_id")),
            lane_id=_text(metadata.get("lane_id")) or "gwb",
            family_id=_text(model.get("lane_family")) or "gwb",
            claims=model.get("claims") if isinstance(model.get("claims"), Sequence) else None,
            summary=model.get("summary") if isinstance(model.get("summary"), Mapping) else None,
        )
    )
    report["claim_table"] = project_claim_table(model)
    report["timeline"] = project_timeline(model)
    report["review_surface"] = project_review_surface(model)
    from src.policy.gwb_narrative_linkage import build_case as build_linkage_case

    linkage_case_payload = build_linkage_case(raw_report)
    report["linkage_case"] = project_linkage_case(
        model,
        case_id=_text(linkage_case_payload.get("case_id")) or "gwb_narrative_timeline",
        contract_id=_text(linkage_case_payload.get("contract_id")),
        nodes=linkage_case_payload.get("nodes", []),
        edges=linkage_case_payload.get("edges", []),
        expected_anchor_ids=linkage_case_payload.get("expected_anchor_ids", []),
        expected_terminal_ids=linkage_case_payload.get("expected_terminal_ids", []),
        notes=linkage_case_payload.get("notes", []),
    )
    return report


def build_report(conn: Any, *, run_id: str) -> dict[str, Any]:
    return project_report(build_world_model(conn, run_id=run_id))


__all__ = [
    "GWB_NARRATIVE_TIMELINE_PROFILE_ID",
    "GWB_NARRATIVE_TIMELINE_WORLD_MODEL_SCHEMA_VERSION",
    "build_report",
    "build_world_model",
    "project_report",
]
