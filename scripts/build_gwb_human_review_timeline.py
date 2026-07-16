#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR.parent))

from src.policy.gwb_timeline_content_review import build_content_review_payload

LOGGER = logging.getLogger(__name__)

def compile_human_review_timeline(
    checkpoint_payload: dict[str, Any],
    review_payload: dict[str, Any],
    historical_timeline: dict[str, Any],
    *,
    audit_registry: dict[str, Any] | None = None
) -> dict[str, Any]:
    # Extract metadata and metrics
    qc = checkpoint_payload.get("qc_report") or {}
    
    # 1. Metrics
    metrics = {
        "source_event_count": qc.get("source_event_count", 0),
        "active_event_count": qc.get("active_event_count", 0),
        "blocked_event_count": qc.get("blocked_event_count", 0),
        "historical_timeline_event_count": len(historical_timeline.get("source_event_rows", [])),
        "historical_timeline_edge_count": len(historical_timeline.get("ordering_edges", [])),
        "conflict_residual_count": len(review_payload.get("conflict_packets", [])),
        "relations_dropped_by_audit_block": qc.get("relations_dropped_by_audit_block", 0)
    }
    
    # Map reviewed relations by canonical keys
    relations_map = {}
    for r in review_payload.get("reviewed_relations", []):
        sub_lbl = r.get("subject", {}).get("canonical_label")
        pred = r.get("predicate_key")
        obj_lbl = r.get("object", {}).get("canonical_label")
        key = (sub_lbl, pred, obj_lbl)
        relations_map[key] = r

    # 2. Timeline Rows
    timeline_rows = []
    for ev in historical_timeline.get("source_event_rows", []):
        date = ev.get("anchor", {}).get("text") or ev.get("resolved_historical_date") or "unknown"
        event_text = ev.get("text")
        
        corroboration_degree = "weak"
        date_confidence = "unknown"
        gaps_str = "no_relation"
        action = "review"
        event_label = event_text
        sources_str = "1 family"
        
        # Check first candidate
        for cand in ev.get("relation_candidates", []):
            sub_lbl = cand.get("subject", {}).get("canonical_label")
            pred = cand.get("predicate_key")
            obj_lbl = cand.get("object", {}).get("canonical_label")
            key = (sub_lbl, pred, obj_lbl)
            if key in relations_map:
                r = relations_map[key]
                corroboration_degree = r.get("corroboration_degree", "weak")
                date_confidence = r.get("date_confidence", "unknown")
                gaps_str = "; ".join(r.get("gaps", []))
                sources_str = f"{len(r.get('source_families', []))} families"
                
                if corroboration_degree == "strong":
                    action = "verify_span" if r.get("gaps") else "promote"
                elif corroboration_degree == "single_source":
                    action = "verify_corrob"
                elif corroboration_degree == "conflicted":
                    action = "resolve_conflict"
                elif corroboration_degree == "weak":
                    action = "downgrade"
                else:
                    action = "review"
                    
                event_label = f"{sub_lbl} {pred.replace('_', ' ')} {obj_lbl}"
                break
                
        # Extract FragmentPNF provenance from receipts (set by _compute_component_relevance)
        fpnfs = ev.get("fragment_pnfs") or []
        fragment_frame = ""
        projection_basis = ""
        depth_level = ""
        export_class = ""
        blocked_reasons: list[str] = []
        flat_shortcut = False

        if fpnfs:
            primary_frames: list[str] = []
            has_generic_fallback = False
            for f in fpnfs:
                pf = f.get("predicate_frame", "")
                if pf:
                    label = pf.replace("_", " ")
                    if label == "generic relation":
                        has_generic_fallback = True
                    else:
                        if label not in primary_frames:
                            primary_frames.append(label)
            if primary_frames:
                fragment_frame = ", ".join(sorted(primary_frames))
                if has_generic_fallback:
                    fragment_frame += " (+ generic fallback)"
            elif has_generic_fallback:
                fragment_frame = "generic relation"

            receipts = ev.get("fragment_pnf_receipts") or []
            if receipts:
                r0 = receipts[0]
                export_class = r0.get("export_class", "")
                blocked_reasons = r0.get("blocked_reasons", [])
                depth_level = r0.get("linkage_depth_level", "")
                projection_basis = r0.get("projection_basis_level", "")
                flat_shortcut = (depth_level == "flat_shortcut")
        else:
            blocked_reasons = ["fragment_pnf_missing"]
            export_class = "blocked"

        timeline_rows.append({
            "date": date,
            "event": event_label,
            "corroboration": corroboration_degree,
            "sources": sources_str,
            "confidence": date_confidence,
            "gaps": gaps_str or "none",
            "action": action,
            "fragment_frame": fragment_frame,
            "projection_basis": projection_basis,
            "depth_level": depth_level,
            "export_class": export_class,
            "blocked_reasons": blocked_reasons,
            "flat_shortcut_detected": flat_shortcut,
        })
        
    # Sort timeline rows by date/year
    def safe_year(row: dict[str, Any]) -> int:
        match = re.search(r"\b(\d{4})\b", row["date"])
        return int(match.group(1)) if match else 9999
    import re
    timeline_rows.sort(key=safe_year)
    
    # 3. Excluded Items
    excluded_items = []
    
    # A. Blocked Events
    unfiltered_braid = checkpoint_payload.get("cross_source_event_braid") or {}
    active_ev_ids = {e.get("event_id") for e in unfiltered_braid.get("source_event_rows", [])}
    # Wait, the unfiltered braid in payload is actually the audited braid (audited_braid is stored in payload["cross_source_event_braid"]).
    # So we don't have the pre-block braid in the payload. But we can count how many were blocked by using the audit_registry!
    # Let's check how many events are in the registry with status == "block"
    if audit_registry is None:
        from src.policy.gwb_spot_audit import load_spot_audit_registry
        audit_registry = load_spot_audit_registry()
    for ev_key, block_dec in audit_registry.items():
        if block_dec.get("status") == "block":
            excluded_items.append({
                "item": ev_key,
                "type": "Event",
                "reason": "blocked_by_spot_audit",
                "effect": "excluded"
            })
            
    # B. Noise Events in braid
    for ev in unfiltered_braid.get("source_event_rows", []):
        status = ev.get("event_quality_status")
        if status in {"rejected_noise", "frontmatter_or_index"}:
            excluded_items.append({
                "item": f"{ev.get('source_family')}:{ev.get('event_id')}",
                "type": "Event",
                "reason": status,
                "effect": "excluded_from_historical_timeline"
            })
            
    # C. Excluded Edges (non-chronological)
    for edge in unfiltered_braid.get("ordering_edges", []):
        basis = edge.get("ordering_basis")
        if basis != "historical_time_order":
            excluded_items.append({
                "item": edge.get("ordering_edge_id"),
                "type": "Edge",
                "reason": basis or "document_order",
                "effect": "not_chronological"
            })
            
    # D. Merge-Risk Clusters
    for mr in review_payload.get("merge_risky_events", []):
        excluded_items.append({
            "item": mr.get("merged_event_id"),
            "type": "Merge",
            "reason": ", ".join(mr.get("risks", [])),
            "effect": "needs_review"
        })
        
    # 4. Review Queue
    review_queue = []
    for r in review_payload.get("reviewed_relations", []):
        sub_lbl = r.get("subject", {}).get("canonical_label")
        pred = r.get("predicate_key")
        obj_lbl = r.get("object", {}).get("canonical_label")
        label = f"{sub_lbl} {pred.replace('_', ' ')} {obj_lbl}"
        degree = r.get("corroboration_degree", "weak")
        gaps = r.get("gaps", [])
        
        if degree == "conflicted":
            review_queue.append({
                "priority": "high",
                "target": label,
                "action": "resolve_conflict",
                "reason": "historical conflict residual detected"
            })
        elif degree == "strong" and gaps:
            review_queue.append({
                "priority": "high",
                "target": label,
                "action": "verify_primary_source_span",
                "reason": f"strong corroboration but has gaps: {', '.join(gaps)}"
            })
        elif degree == "single_source":
            review_queue.append({
                "priority": "medium",
                "target": label,
                "action": "verify_corrob",
                "reason": "needs independent corroboration"
            })
        elif degree in {"moderate", "weak"} and gaps:
            review_queue.append({
                "priority": "low",
                "target": label,
                "action": "review",
                "reason": f"reasons: {', '.join(gaps)}"
            })
            
    # Sort review queue by priority (high, then medium, then low)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    review_queue.sort(key=lambda x: priority_order.get(x["priority"], 3))
    
    # 5. Extract Recovered Event Atoms and Expanded Cells
    recovered_atoms = []
    expanded_cells_dict = {}
    
    for ev in historical_timeline.get("source_event_rows", []):
        parent_id = ev.get("parent_event_id")
        if parent_id:
            date = ev.get("anchor", {}).get("text") or ev.get("resolved_historical_date") or "unknown"
            event_text = ev.get("text")
            
            corroboration_degree = "weak"
            date_confidence = "unknown"
            gaps_str = "no_relation"
            action = "review"
            event_label = event_text
            sources_str = "1 family"
            
            for cand in ev.get("relation_candidates", []):
                sub_lbl = cand.get("subject", {}).get("canonical_label")
                pred = cand.get("predicate_key")
                obj_lbl = cand.get("object", {}).get("canonical_label")
                key = (sub_lbl, pred, obj_lbl)
                if key in relations_map:
                     r = relations_map[key]
                     corroboration_degree = r.get("corroboration_degree", "weak")
                     date_confidence = r.get("date_confidence", "unknown")
                     gaps_str = "; ".join(r.get("gaps", []))
                     sources_str = f"{len(r.get('source_families', []))} families"
                     
                     if corroboration_degree == "strong":
                         action = "verify_span" if r.get("gaps") else "promote"
                     elif corroboration_degree == "single_source":
                         action = "verify_corrob"
                     elif corroboration_degree == "conflicted":
                         action = "resolve_conflict"
                     elif corroboration_degree == "weak":
                         action = "downgrade"
                     else:
                         action = "review"
                         
                     event_label = f"{sub_lbl} {pred.replace('_', ' ')} {obj_lbl}"
                     break
                     
            recovered_atoms.append({
                "date": date,
                "event": event_label,
                "parent_cell_id": parent_id,
                "confidence": date_confidence,
                "action": action
            })
            
            if parent_id not in expanded_cells_dict:
                expanded_cells_dict[parent_id] = {
                    "parent_cell_id": parent_id,
                    "atom_count": 0,
                    "parent_status": ev.get("parent_quality_status") or "weak",
                    "action": "Review atoms"
                }
            expanded_cells_dict[parent_id]["atom_count"] += 1
            
    expanded_cells = list(expanded_cells_dict.values())
    
    return {
        "schema_version": "sl.gwb_human_review_timeline.v0_1",
        "metrics": metrics,
        "timeline_rows": timeline_rows,
        "excluded_items": excluded_items,
        "review_queue": review_queue,
        "recovered_atoms": recovered_atoms,
        "expanded_cells": expanded_cells
    }


def generate_triage_markdown(packet: dict[str, Any]) -> str:
    metrics = packet["metrics"]
    timeline = packet["timeline_rows"]
    excluded = packet["excluded_items"]
    queue = packet["review_queue"]
    recovered_atoms = packet.get("recovered_atoms") or []
    expanded_cells = packet.get("expanded_cells") or []
    
    candidate_rows = []
    conflict_rows = []
    triage_rows = []
    
    for row in timeline:
        corrob = row.get("corroboration")
        event = row.get("event")
        gaps = row.get("gaps")
        confidence = row.get("confidence")
        
        # Exclude recovered atoms from appearing in the main timeline or triage tables if they are listed separately,
        # but wait - do we want them in triage_rows or candidate_rows?
        # The prompt says: "The main timeline candidate is not the evidence dump. It is the filtered chronology candidate.
        # Weak/no_relation/unknown/ingest rows remain reviewable, but they must appear in triage or exclusion sections, not the main timeline."
        # If an event is an atom, it is also in timeline_rows. But wait! We want the main timeline candidate table to show candidate atom rows
        # if they pass the filtering rule!
        # The prompt says: "The Markdown should stop showing these giant parent cells in the main timeline. Instead: ## Historical Timeline Candidate (shows atom rows) ... ## Recovered Event Atoms ... ## Compound Cells Expanded"
        # So yes, atoms can appear in candidate_rows if they are promoted/strong, or in triage_rows if they are weak.
        # They will also be listed in "Recovered Event Atoms" table for full audit visibility.
        if corrob == "conflicted":
            conflict_rows.append(row)
        elif (
            event not in {"", None} and
            gaps != "no_relation" and
            confidence not in {"unknown", "ingest_order_only"} and
            corrob in {"strong", "moderate", "single_source"}
        ):
            candidate_rows.append(row)
        else:
            triage_rows.append(row)
            
    rows_with_fragment_frame = sum(1 for r in timeline if r.get('fragment_frame'))
    rows_with_projection = sum(1 for r in timeline if r.get('projection_basis'))
    rows_with_formal_projection = sum(
        1 for r in timeline
        if r.get('projection_basis') in ('grammar_projected', 'fallback_projected')
    )
    rows_with_depth = sum(1 for r in timeline if r.get('depth_level'))
    rows_with_fragment_pnf_depth = sum(
        1 for r in timeline
        if r.get('depth_level') in ('fragment_pnf', 'sentence_pnf', 'document_pnf', 'braid_node')
    )
    rows_with_braid_node_depth = sum(1 for r in timeline if r.get('depth_level') == 'braid_node')
    rows_with_export_class = sum(1 for r in timeline if r.get('export_class'))

    # Build blocked-reason distribution
    blocked_reason_counts: dict[str, int] = {}
    for r in timeline:
        for br in r.get("blocked_reasons", []):
            blocked_reason_counts[br] = blocked_reason_counts.get(br, 0) + 1

    lines = [
        "# GWB Human Review Timeline Packet",
        "",
        "This packet provides a scannable triage view of the candidate GWB timeline, highlighting what was included, what was excluded (and why), and recommended actions.",
        "",
        "## Metrics",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Source events | {metrics['source_event_count']} |",
        f"| Active events | {metrics['active_event_count']} |",
        f"| Blocked events | {metrics['blocked_event_count']} |",
        f"| Historical timeline rows | {len(candidate_rows)} |",
        f"| Historical edges | {metrics['historical_timeline_edge_count']} |",
        f"| Conflict residuals | {len(conflict_rows)} |",
        f"| Dropped relations | {metrics['relations_dropped_by_audit_block']} |",
        "",
        "### FragmentPNF Provenance",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Total source events with PNF fragments | {rows_with_fragment_frame} |",
        f"| Flat-shortcut events | {sum(1 for r in timeline if r.get('flat_shortcut_detected'))} |",
        f"| Events with depth level assigned | {rows_with_depth} |",
        f"| Events with export class | {rows_with_export_class} |",
        "",
        "### Export-Gate Receipt Chain",
        "",
        "| Gate Stage | Events |",
        "|---|---:|",
        f"| Rows with FragmentPNF receipts | {rows_with_fragment_frame} |",
        f"| Rows with projection basis | {rows_with_projection} |",
        f"| Rows with formal projection | {rows_with_formal_projection} |",
        f"| Rows with linkage depth >= fragment_pnf | {rows_with_fragment_pnf_depth} |",
        f"| Rows with braid-node depth | {rows_with_braid_node_depth} |",
        f"| Rows with export class | {rows_with_export_class} |",
    ]

    if blocked_reason_counts:
        lines.extend([
            "",
            "### Blocked-Reason Distribution",
            "",
            "| Blocked Reason | Events |",
            "|---|---:|",
        ])
        for reason, count in sorted(blocked_reason_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason.replace('_', ' ')} | {count} |")

    # Projection-basis distribution
    proj_basis_counts: dict[str, int] = {}
    for r in timeline:
        pb = r.get("projection_basis")
        if pb:
            proj_basis_counts[pb] = proj_basis_counts.get(pb, 0) + 1
    if proj_basis_counts:
        lines.extend([
            "",
            "### Projection-Basis Distribution",
            "",
            "| Projection Basis | Events |",
            "|---|---:|",
        ])
        for basis, count in sorted(proj_basis_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {basis.replace('_', ' ')} | {count} |")

    lines.extend([
        "",
        "## Historical Timeline Candidate",
        "",
        "| Date | Event | Corroboration | Sources | Confidence | Gaps | PNF Frame | Projection | Depth | Export | Blocked Reasons | Action |",
        "|---|---:|---:|---|---|---|---|---|---|---|---|",
    ])
    
    for row in candidate_rows:
        blocked_str = "; ".join(row.get("blocked_reasons", [])) if row.get("blocked_reasons") else ""
        lines.append(
            f"| {row['date']} | {row['event']} | {row['corroboration'].capitalize()} | {row['sources']} | "
            f"{row['confidence'].replace('_', ' ')} | {row['gaps'].replace('; ', '<br>')} | "
            f"{row.get('fragment_frame', '')} | {row.get('projection_basis', '')} | "
            f"{row.get('depth_level', '')} | {row.get('export_class', '')} | "
            f"{blocked_str} | {row['action'].capitalize()} |"
        )
        
    lines.extend([
        "",
        "## Needs Triage / Weak Extracted Rows",
        "",
        "| Date | Extracted text | PNF Frame | Projection | Depth | Export | Blocked Reasons | Action |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for row in triage_rows:
        blocked_str = "; ".join(row.get("blocked_reasons", [])) if row.get("blocked_reasons") else ""
        lines.append(
            f"| {row['date']} | {row['event']} | {row.get('fragment_frame', '')} | "
            f"{row.get('projection_basis', '')} | {row.get('depth_level', '')} | "
            f"{row.get('export_class', '')} | {blocked_str} | {row['action'].capitalize()} |"
        )
        
    lines.extend([
        "",
        "## Conflict Residuals",
        "",
        "| Event | Sources | Issue | Action |",
        "|---|---:|---|---|",
    ])
    for row in conflict_rows:
        lines.append(
            f"| {row['event']} | {row['sources']} | historical conflict residual | {row['action'].capitalize()} |"
        )
        
    lines.extend([
        "",
        "## Excluded / Non-Timeline Items",
        "",
        "| Item | Type | Reason | Effect |",
        "|---|---|---|---|",
    ])
    for item in excluded[:20]:  # Cap at 20 for scannability
        lines.append(
            f"| `{item['item']}` | {item['type']} | {item['reason'].replace('_', ' ')} | {item['effect']} |"
        )
    if len(excluded) > 20:
        lines.append(f"| ... | ... | and {len(excluded) - 20} more items | ... |")
        
    lines.extend([
        "",
        "## Recovered Event Atoms",
        "",
        "| Date | Event | Parent Cell | Confidence | Action |",
        "|---|---|---|---|---|",
    ])
    for row in recovered_atoms:
        lines.append(
            f"| {row['date']} | {row['event']} | `{row['parent_cell_id']}` | {row['confidence'].replace('_', ' ')} | {row['action'].capitalize()} |"
        )
        
    lines.extend([
        "",
        "## Compound Cells Expanded",
        "",
        "| Parent Cell | Atoms | Parent Status | Action |",
        "|---|---:|---|---|",
    ])
    for row in expanded_cells:
        lines.append(
            f"| `{row['parent_cell_id']}` | {row['atom_count']} | {row['parent_status'].replace('_', ' ')} | {row['action']} |"
        )

    lines.extend([
        "",
        "## Recommended Next Human Review Queue",
        "",
        "| Priority | Target | Recommended Action | Reason |",
        "|---|---|---|---|",
    ])
    for q in queue[:15]:  # Cap at 15
        lines.append(
            f"| {q['priority'].upper()} | {q['target']} | {q['action'].replace('_', ' ')} | {q['reason']} |"
        )
    if len(queue) > 15:
        lines.append(f"| ... | ... | and {len(queue) - 15} more queue items | ... |")
        
    return "\n".join(lines) + "\n"


def build_human_review_timeline_packet(
    checkpoint_path: Path,
    review_path: Path,
    timeline_path: Path,
    output_dir: Path
) -> dict[str, Any]:
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        checkpoint_payload = json.load(f)
    with open(review_path, "r", encoding="utf-8") as f:
        review_payload = json.load(f)
    with open(timeline_path, "r", encoding="utf-8") as f:
        historical_timeline = json.load(f)
        
    packet = compile_human_review_timeline(checkpoint_payload, review_payload, historical_timeline)
    markdown_text = generate_triage_markdown(packet)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "gwb_human_review_timeline.json"
    md_path = output_dir / "gwb_human_review_timeline.md"
    
    json_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown_text, encoding="utf-8")
    
    LOGGER.info("Wrote GWB human review timeline to %s", json_path)
    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "metrics": packet["metrics"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the GWB human review timeline packet.")
    parser.add_argument("--checkpoint-path", required=True, help="Path to broader GWB checkpoint JSON.")
    parser.add_argument("--review-path", required=True, help="Path to content corroboration review JSON.")
    parser.add_argument("--timeline-path", required=True, help="Path to historical timeline candidate JSON.")
    parser.add_argument("--output-dir", required=True, help="Directory to write review packet to.")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    result = build_human_review_timeline_packet(
        Path(args.checkpoint_path),
        Path(args.review_path),
        Path(args.timeline_path),
        Path(args.output_dir)
    )
    print(json.dumps(result["metrics"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
