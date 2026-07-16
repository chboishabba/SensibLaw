from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.policy.fragment_pnf import (
    DEFAULT_GWB_LANE_POLICY,
    ExportClass,
    ExportGateReceipt,
    ExportLanePolicy,
)

DEFAULT_AUDIT_PATH = Path(__file__).parent / "gwb_timeline_spot_audit.json"

def build_export_gate_receipt(
    row: dict[str, Any],
    policy: ExportLanePolicy = DEFAULT_GWB_LANE_POLICY,
) -> ExportGateReceipt:
    """Build a hard-gated export gate receipt for a single source event row.

    No scalar score, no threshold — only finite-level checks against the
    lane policy.  The export class is the highest class whose preconditions
    are all satisfied:
      high_confidence_exportable — all gates plus policy minimums
      exportable                  — pnf + time + source + fragment path
      reviewable                  — pnf closed
      candidate_only              — time + source
      blocked                     — none of the above
    """
    reasons: list[str] = []

    pnf_state = row.get("pnf") or {}
    pnf_closed = bool(
        row.get("pnf_status") == "canonicalized"
        and pnf_state.get("subject")
        and pnf_state.get("predicate")
        and pnf_state.get("object")
    )
    if not pnf_closed:
        reasons.append("pnf_not_closed")

    anchor = row.get("anchor") or {}
    time_bound = bool(
        row.get("resolved_historical_date")
        or anchor.get("year")
        or anchor.get("start_year")
        or anchor.get("text")
    )
    if not time_bound:
        reasons.append("time_not_bound")

    source_spanned = bool(row.get("text"))
    if not source_spanned:
        reasons.append("source_span_missing")

    fragment_pnfs = row.get("fragment_pnfs") or []
    has_fragment_pnf_path = bool(fragment_pnfs)
    if not has_fragment_pnf_path:
        reasons.append("fragment_pnf_missing")

    receipt_list = row.get("fragment_projection_receipts") or []
    has_formal_projection = bool(receipt_list)
    if policy.require_formal_projection and not has_formal_projection:
        reasons.append("formal_projection_missing")

    component_receipts = row.get("fragment_pnf_receipts") or []
    residual_not_blocked = True
    if component_receipts:
        for r in component_receipts:
            if r.get("export_class") == "blocked":
                residual_not_blocked = False
                break
    if not residual_not_blocked:
        reasons.append("residual_compatibility_blocked")

    braid_metrics = row.get("braid_metrics") or {}
    referentiality = braid_metrics.get("referentiality", 0)
    ref_min_value = {
        "single_source": 1,
        "same_family_multi_span": 2,
        "multi_family": 3,
        "cross_source": 4,
    }.get(policy.min_referentiality_level.value, 1)
    referentiality_adequate = referentiality >= ref_min_value
    if not referentiality_adequate:
        reasons.append("referentiality_insufficient")

    linkage_depth = row.get("linkage_depth_level")
    linkage_depth_order = {
        "flat_shortcut": 0,
        "source_span": 1,
        "fragment_pnf": 2,
        "sentence_pnf": 3,
        "document_pnf": 4,
        "braid_node": 5,
    }
    min_ld = linkage_depth_order.get(policy.min_linkage_depth_level.value, 5)
    current_ld = linkage_depth_order.get(linkage_depth or "flat_shortcut", 0)
    linkage_depth_adequate = current_ld >= min_ld
    if not linkage_depth_adequate:
        reasons.append("linkage_depth_insufficient")

    # Determine export class — highest satisfied class wins
    if (
        pnf_closed
        and time_bound
        and source_spanned
        and has_fragment_pnf_path
        and has_formal_projection
        and residual_not_blocked
        and referentiality_adequate
        and linkage_depth_adequate
    ):
        export_class = ExportClass.high_confidence_exportable
    elif pnf_closed and time_bound and source_spanned and has_fragment_pnf_path and residual_not_blocked:
        export_class = ExportClass.exportable
    elif pnf_closed:
        export_class = ExportClass.reviewable
    elif time_bound and source_spanned:
        export_class = ExportClass.candidate_only
    else:
        export_class = ExportClass.blocked

    return ExportGateReceipt(
        exportable=export_class
        in (ExportClass.exportable, ExportClass.high_confidence_exportable),
        export_class=export_class,
        pnf_closed=pnf_closed,
        time_bound=time_bound,
        source_spanned=source_spanned,
        has_fragment_pnf_path=has_fragment_pnf_path,
        has_formal_projection=has_formal_projection,
        residual_not_blocked=residual_not_blocked,
        referentiality_adequate=referentiality_adequate,
        blocked_reasons=tuple(reasons),
    )


def load_spot_audit_registry(path: Path | str | None = None) -> dict[str, Any]:
    if path is None:
        path = DEFAULT_AUDIT_PATH
    else:
        path = Path(path)
    
    if not path.exists():
        return {"events": {}, "edges": {}}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"events": {}, "edges": {}}


def save_spot_audit_registry(registry: Mapping[str, Any], path: Path | str | None = None) -> None:
    if path is None:
        path = DEFAULT_AUDIT_PATH
    else:
        path = Path(path)
        
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def apply_spot_audit_blocks(braid_payload: dict[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    import copy
    payload = copy.deepcopy(braid_payload)
    
    event_audits = registry.get("events") or {}
    edge_audits = registry.get("edges") or {}
    
    blocked_events: set[str] = set()
    for event_key, audit in event_audits.items():
        if audit.get("recommended_status") == "block":
            blocked_events.add(event_key)
            
    blocked_edges: set[str] = set()
    for edge_id, audit in edge_audits.items():
        if audit.get("recommended_status") == "block":
            blocked_edges.add(edge_id)

    # 1. Filter source_event_rows
    filtered_events = []
    for row in payload.get("source_event_rows", []):
        event_key = f"{row.get('source_family')}:{row.get('event_id')}"
        if event_key not in blocked_events:
            filtered_events.append(row)
    payload["source_event_rows"] = filtered_events

    # 2. Filter candidate_links
    filtered_links = []
    for link in payload.get("candidate_links", []):
        left_key = link.get("left_source_event_id")
        right_key = link.get("right_source_event_id")
        if left_key not in blocked_events and right_key not in blocked_events:
            filtered_links.append(link)
    payload["candidate_links"] = filtered_links

    # 3. Filter merged_events
    filtered_merged = []
    for m in payload.get("merged_events", []):
        members = m.get("source_event_ids", [])
        if not any(member in blocked_events for member in members):
            filtered_merged.append(m)
    payload["merged_events"] = filtered_merged

    # 4. Filter ordering_edges
    filtered_edges = []
    for edge in payload.get("ordering_edges", []):
        edge_id = edge.get("ordering_edge_id")
        left_key = edge.get("source_event_id")
        right_key = edge.get("target_event_id")
        if edge_id not in blocked_edges and left_key not in blocked_events and right_key not in blocked_events:
            filtered_edges.append(edge)
    payload["ordering_edges"] = filtered_edges

    return payload


def is_exportable(row: dict[str, Any], threshold: float = 0.5) -> bool:
    pnf_state = row.get("pnf") or {}
    pnf_closed = bool(row.get("pnf_status") == "canonicalized" and pnf_state.get("subject") and pnf_state.get("predicate") and pnf_state.get("object"))
    
    anchor = row.get("anchor") or {}
    time_bound = bool(row.get("resolved_historical_date") or anchor.get("year") or anchor.get("start_year"))
    source_spanned = bool(row.get("text"))
    
    relevance_state = row.get("relevance") or {}
    relevance_score = relevance_state.get("score") or 0.0
    
    is_blocked = row.get("event_quality_status") == "rejected_noise" or row.get("recommended_status") == "block"
    
    return pnf_closed and time_bound and source_spanned and (relevance_score >= threshold) and not is_blocked


def export_historical_timeline(braid_payload: dict[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    payload = apply_spot_audit_blocks(braid_payload, registry)
    
    historical_edges = []
    for edge in payload.get("ordering_edges", []):
        if edge.get("ordering_basis") == "historical_time_order":
            historical_edges.append(edge)
            
    referenced_events = set()
    for edge in historical_edges:
        referenced_events.add(edge.get("source_event_id"))
        referenced_events.add(edge.get("target_event_id"))
        for eid in edge.get("source_event_ids", []):
            referenced_events.add(eid)

    historical_events = []
    for row in payload.get("source_event_rows", []):
        event_key = f"{row.get('source_family')}:{row.get('event_id')}"
        status = row.get("event_time_anchor_status")
        relevance_state = row.get("relevance") or {}
        relevance_status = relevance_state.get("status") or "triage"
        
        is_handoff = row.get("source_family") == "checked_handoff"
        if is_handoff or relevance_status == "timeline_candidate" or is_exportable(row) or event_key in referenced_events or status in {"resolved_historical_date", "explicit_span_date", "source_metadata_date", "candidate_span_year"}:
            historical_events.append(row)

    return {
        "schema_version": "sl.historical_timeline_candidate.v0_1",
        "source_event_rows": historical_events,
        "ordering_edges": historical_edges,
        "merged_events": [
            m for m in payload.get("merged_events", [])
            if any(f"{row.get('source_family')}:{row.get('event_id')}" in referenced_events for row in payload.get("source_event_rows", []) if f"{row.get('source_family')}:{row.get('event_id')}" in m.get("source_event_ids", []))
        ],
    }
