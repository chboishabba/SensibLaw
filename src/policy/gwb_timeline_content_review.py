from __future__ import annotations

import re
from typing import Any, Mapping

from src.policy.fragment_pnf import PredicateFrame

def classify_corroboration(relation: dict[str, Any], braid: dict[str, Any]) -> str:
    # 1. Blocked
    status = relation.get("event_quality_status")
    if status == "rejected_noise" or not relation.get("lineage_records"):
        return "blocked"
        
    # 2. Conflicted
    time_bases = relation.get("time_basis_types") or []
    reasons = relation.get("event_quality_reasons") or []
    has_conflict = (
        "historical_conflict_residual" in time_bases or
        "conflicting_span_years" in reasons
    )
    if has_conflict:
        return "conflicted"
        
    source_families = relation.get("source_families") or []
    lineage = relation.get("lineage_records") or []
    time_status = relation.get("event_time_anchor_status") or "none"
    
    # 3. Strong
    is_strong = (
        len(source_families) >= 2 and
        status == "promotable_event" and
        time_status in {"resolved_historical_date", "explicit_span_date", "source_metadata_date", "candidate_span_year"}
    )
    if is_strong:
        return "strong"
        
    # 4. Moderate
    is_moderate = (
        (len(source_families) >= 2 or len(lineage) >= 2) and
        status in {"promotable_event", "usable_candidate"}
    )
    if is_moderate:
        return "moderate"
        
    # 5. Single Source
    if len(source_families) == 1 and len(lineage) == 1 and status == "promotable_event":
        return "single_source"
        
    # 6. Weak
    return "weak"


def classify_date_confidence(relation: dict[str, Any]) -> str:
    time_bases = relation.get("time_basis_types") or []
    if "ingest_order_only" in time_bases:
        return "ingest_order_only"
        
    time_status = relation.get("event_time_anchor_status") or "none"
    
    # Check best lineage record to determine precision
    precision = "unknown"
    for record in relation.get("lineage_records", []):
        if isinstance(record, dict) and record.get("resolved_historical_date"):
            precision = record.get("event_time_anchor_precision") or "unknown"
            break
            
    if time_status in {"resolved_historical_date", "explicit_span_date"}:
        if precision == "day":
            return "exact_date"
        elif precision == "month":
            return "month_only"
        elif precision == "year":
            return "year_only"
            
    if time_status == "candidate_span_year":
        return "year_only"
        
    ordering_bases = relation.get("ordering_basis_types") or []
    if "document_order" in ordering_bases or "inferred_overlap" in ordering_bases:
        if len(ordering_bases) == 1 and "document_order" in ordering_bases:
            return "document_order_only"
        return "relative_order_only"
        
    return "unknown"


def classify_merge_risk(merged_event: dict[str, Any], braid: dict[str, Any]) -> list[str]:
    risks = []
    
    source_events_map = {
        f"{e.get('source_family')}:{e.get('event_id')}": e
        for e in braid.get("source_event_rows", [])
    }
    
    members = []
    for member_key in merged_event.get("source_event_ids", []):
        evt = source_events_map.get(member_key)
        if evt:
            members.append(evt)
            
    if not members:
        return risks
        
    # 1. Possibly Overmerged
    resolved_dates = {m.get("resolved_historical_date") for m in members if m.get("resolved_historical_date")}
    if len(resolved_dates) > 1:
        risks.append("possibly_overmerged")
        
    # 2. Date span too wide
    years = []
    for d in resolved_dates:
        # Extract 4 digit year from resolved date
        match = re.search(r"\b(\d{4})\b", d)
        if match:
            years.append(int(match.group(1)))
    if years and (max(years) - min(years)) > 1:
        risks.append("date_span_too_wide")
        
    # 3. Label too generic
    text = merged_event.get("event_label") or ""
    if len(text.strip()) < 15 or any(kw in text.lower() for kw in {"event", "snippet", "meeting", "briefing"}):
        risks.append("label_too_generic")
        
    # 4. Source family disagreement
    families = {m.get("source_family") for m in members if m.get("source_family")}
    if len(families) > 1:
        event_predicates = []
        for m in members:
            preds = {
                rel.get("predicate_key")
                for rel in m.get("relation_candidates", [])
                if isinstance(rel, dict) and rel.get("predicate_key")
            }
            if preds:
                event_predicates.append(preds)
        if len(event_predicates) > 1:
            intersection = set.intersection(*event_predicates)
            if not intersection:
                risks.append("source_family_disagreement")
            
    return risks


def build_conflict_packets(braid: dict[str, Any]) -> list[dict[str, Any]]:
    packets = []
    source_events_map = {
        f"{e.get('source_family')}:{e.get('event_id')}": e
        for e in braid.get("source_event_rows", [])
    }
    
    for edge in braid.get("ordering_edges", []):
        if edge.get("time_basis") == "historical_conflict_residual":
            left_evt = source_events_map.get(edge.get("source_event_id"))
            right_evt = source_events_map.get(edge.get("target_event_id"))
            packets.append({
                "ordering_edge_id": edge.get("ordering_edge_id"),
                "source_event_id": edge.get("source_event_id"),
                "target_event_id": edge.get("target_event_id"),
                "source_text": left_evt.get("text") if left_evt else "",
                "target_text": right_evt.get("text") if right_evt else "",
                "source_date": left_evt.get("resolved_historical_date") if left_evt else None,
                "target_date": right_evt.get("resolved_historical_date") if right_evt else None,
                "conflict_reason": "Chronological dates contradict document order direction."
            })
    return packets


def build_gap_list(relation: dict[str, Any]) -> list[str]:
    gaps = []
    source_families = relation.get("source_families") or []
    
    if "checked_handoff" not in source_families:
        gaps.append("no_primary_source")
    if len(source_families) < 2:
        gaps.append("no_independent_corroboration")
        
    time_status = relation.get("event_time_anchor_status") or "none"
    if time_status in {"none", "ingest_only"}:
        gaps.append("date_inferred_only")
        
    score = relation.get("event_quality_score") or 0.0
    if score < 0.7:
        gaps.append("actor_uncertain")
        
    return gaps


def _collect_fragment_pnf_rows(source_event_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build per-source-event-row FragmentPNF analysis.

    Reads ``fragment_pnfs`` (serialized dicts), ``fragment_pnf_receipts``,
    ``linkage_depth_level``, and ``flat_shortcut_detected`` from each source
    event row and produces a review-ready row for each fragment found.
    """
    rows: list[dict[str, Any]] = []
    for ev in source_event_rows:
        fpnfs = ev.get("fragment_pnfs") or []
        if not fpnfs:
            continue

        event_key = f"{ev.get('source_family')}:{ev.get('event_id')}"
        anchor = ev.get("anchor") or {}
        date = ev.get("resolved_historical_date") or anchor.get("text") or ""

        # Match receipts by fragment_id
        receipts_by_fid: dict[str, dict[str, Any]] = {}
        for r in ev.get("fragment_pnf_receipts") or []:
            fid = r.get("fragment_id")
            if fid:
                receipts_by_fid[fid] = r

        for fpnf in fpnfs:
            fid = fpnf.get("fragment_id", "")
            receipt = receipts_by_fid.get(fid) or {}

            predicate_frame = fpnf.get("predicate_frame")
            frame_label = ""
            if predicate_frame:
                try:
                    frame_label = PredicateFrame(predicate_frame).value.replace("_", " ")
                except ValueError:
                    frame_label = predicate_frame.replace("_", " ")

            fallback = fpnf.get("fallback_used", False)
            fragment_subclass = fpnf.get("fragment_subclass", "")
            grammar_id = fpnf.get("grammar_id", "")

            pnf_closure = receipt.get("pnf_closure_level", "")
            projection_basis = receipt.get("projection_basis_level", "")
            ld_level = receipt.get("linkage_depth_level", "")
            export_class = receipt.get("export_class", "")
            blocked_reasons = receipt.get("blocked_reasons", [])

            rows.append({
                "event_key": event_key,
                "date": date,
                "source_text": ev.get("text", ""),
                "fragment_surface": fpnf.get("fragment_surface", ""),
                "predicate_frame": frame_label,
                "predicate_frame_key": predicate_frame or "",
                "fragment_subclass": fragment_subclass,
                "grammar_id": grammar_id,
                "fallback_used": fallback,
                "pnf_closure_level": pnf_closure,
                "projection_basis_level": projection_basis,
                "linkage_depth_level": ld_level or ev.get("linkage_depth_level", ""),
                "export_class": export_class,
                "blocked_reasons": blocked_reasons,
                "flat_shortcut_detected": ev.get("flat_shortcut_detected", False),
            })
    return rows


def build_content_review_payload(checkpoint_payload: dict[str, Any]) -> dict[str, Any]:
    braid = checkpoint_payload.get("cross_source_event_braid") or {}
    relations = checkpoint_payload.get("merged_promoted_relations") or []
    
    reviewed_items = []
    for rel in relations:
        degree = classify_corroboration(rel, braid)
        date_conf = classify_date_confidence(rel)
        gaps = build_gap_list(rel)
        
        reviewed_items.append({
            "subject": rel.get("subject"),
            "predicate_key": rel.get("predicate_key"),
            "object": rel.get("object"),
            "source_families": rel.get("source_families"),
            "event_quality_status": rel.get("event_quality_status"),
            "event_quality_score": rel.get("event_quality_score"),
            "event_time_anchor_status": rel.get("event_time_anchor_status"),
            "resolved_historical_date": rel.get("resolved_historical_date"),
            "corroboration_degree": degree,
            "date_confidence": date_conf,
            "gaps": gaps,
        })
        
    merge_risky_events = []
    for m in braid.get("merged_events", []):
        risks = classify_merge_risk(m, braid)
        if risks:
            merge_risky_events.append({
                "merged_event_id": m.get("merged_event_id"),
                "event_label": m.get("event_label"),
                "source_event_ids": m.get("source_event_ids"),
                "risks": risks
            })
            
    conflict_packets = build_conflict_packets(braid)
    
    # Collect per-source-event-row FragmentPNF analysis
    fragment_pnf_rows = _collect_fragment_pnf_rows(braid.get("source_event_rows") or [])
    
    # Summarize review statuses
    degree_counts: dict[str, int] = {}
    for item in reviewed_items:
        deg = item["corroboration_degree"]
        degree_counts[deg] = degree_counts.get(deg, 0) + 1
        
    return {
        "schema_version": "sl.gwb_content_corroboration_review.v0_1",
        "summary": {
            "total_reviewed_relations": len(reviewed_items),
            "degree_counts": degree_counts,
            "risky_merged_event_count": len(merge_risky_events),
            "conflict_packet_count": len(conflict_packets),
            "total_source_event_fragment_pnfs": len(fragment_pnf_rows),
        },
        "reviewed_relations": reviewed_items,
        "merge_risky_events": merge_risky_events,
        "conflict_packets": conflict_packets,
        "source_event_fragment_pnfs": fragment_pnf_rows,
    }
