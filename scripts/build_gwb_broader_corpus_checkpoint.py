#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any, Callable

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from cli_runtime import build_progress_callback, configure_cli_logging
from src.storage.repo_roots import repo_root, sensiblaw_root
from src.policy.cross_source_event_braid import build_cross_source_event_braid
from src.policy.fragment_pnf import serialize_fragment_pnfs_in_rows

REPO_ROOT = repo_root()
SENSIBLAW_ROOT = sensiblaw_root()
THIS_DIR = Path(__file__).resolve().parent
ARTIFACT_VERSION = "gwb_broader_corpus_checkpoint_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
DEFAULT_HANDOFF_SLICE_PATH = (
    SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "gwb_public_handoff_v1" / "gwb_public_handoff_v1.slice.json"
)
DEFAULT_PUBLIC_BIOS_TIMELINE_PATH = (
    SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "public_bios_v1" / "wiki_timeline_gwb_public_bios_v1_rich.json"
)
DEFAULT_CORPUS_TIMELINE_PATH = (
    SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "corpus_v1" / "wiki_timeline_gwb_corpus_v1.json"
)

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[str, dict[str, Any]], None]


def _emit_progress(progress_callback: ProgressCallback | None, stage: str, **details: Any) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, details)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relation_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(((row.get("subject") or {}).get("canonical_key")) or ""),
        str(row.get("predicate_key") or ""),
        str(((row.get("object") or {}).get("canonical_key")) or ""),
    )


def _normalized_lineage_entry(source_family: str, row: dict[str, Any]) -> dict[str, Any]:
    lineage = row.get("event_lineage") if isinstance(row.get("event_lineage"), dict) else {}
    source_path = str(lineage.get("source_path") or "").strip()
    source_url = str(lineage.get("source_url") or "").strip()
    citation_refs = lineage.get("citation_refs") if isinstance(lineage.get("citation_refs"), list) else []
    return {
        "source_family": source_family,
        "event_id": str(row.get("event_id") or lineage.get("event_id") or "").strip(),
        "source_id": str(lineage.get("source_id") or "").strip(),
        "source_path": source_path,
        "source_url": source_url,
        "source_title": str(lineage.get("source_title") or "").strip(),
        "source_section": str(lineage.get("source_section") or "").strip(),
        "source_span": str(lineage.get("source_text") or "").strip(),
        "citation_refs": [
            {
                "kind": str(citation.get("kind") or "").strip(),
                "text": str(citation.get("text") or "").strip(),
                "source_id": str(citation.get("source_id") or "").strip(),
                "follow": list(citation.get("follow") or []),
            }
            for citation in citation_refs
            if isinstance(citation, dict)
        ],
        "has_source_locator": bool(source_path or source_url),
    }


def _read_checked_handoff_slice(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    return {
        "source_family": "checked_handoff",
        "timeline_path": str(path.relative_to(REPO_ROOT)),
        "selected_promoted_relations": payload.get("selected_promoted_relations", []),
        "selected_seed_lanes": payload.get("selected_seed_lanes", []),
        "ambiguous_events": payload.get("ambiguous_events", []),
        "unresolved_surfaces": payload.get("unresolved_surfaces", []),
    }


def _run_extraction_for_timeline(source_family: str, timeline_path: Path) -> dict[str, Any]:
    from build_gwb_zelph_handoff import _build_reports, _build_slice

    timeline_payload = _load_json(timeline_path)
    linkage_report, semantic_report = _build_reports(timeline_payload=timeline_payload)
    slice_payload = _build_slice(linkage_report, semantic_report, timeline_payload=timeline_payload)
    return {
        "source_family": source_family,
        "timeline_path": str(timeline_path.relative_to(REPO_ROOT)),
        "selected_promoted_relations": slice_payload.get("selected_promoted_relations", []),
        "selected_seed_lanes": slice_payload.get("selected_seed_lanes", []),
        "ambiguous_events": slice_payload.get("ambiguous_events", []),
        "unresolved_surfaces": slice_payload.get("unresolved_surfaces", []),
        "timeline_payload": timeline_payload,
        "semantic_report": semantic_report,
    }


def _braid_key(source_family: str, event_id: str) -> str:
    clean_family = str(source_family or "").strip()
    clean_event_id = str(event_id or "").strip()
    return f"{clean_family}:{clean_event_id}" if clean_family and clean_event_id else ""


def _annotate_merged_relations_with_braid(
    merged_relations: dict[tuple[str, str, str], dict[str, Any]],
    braid_payload: dict[str, Any],
    audit_registry: dict[str, Any] | None = None,
) -> None:
    merged_event_rows = [
        row for row in braid_payload.get("merged_events", []) if isinstance(row, dict)
    ]
    ordering_edge_rows = [
        row for row in braid_payload.get("ordering_edges", []) if isinstance(row, dict)
    ]
    candidate_link_rows = [
        row for row in braid_payload.get("candidate_links", []) if isinstance(row, dict)
    ]
    source_event_rows = [
        row for row in braid_payload.get("source_event_rows", []) if isinstance(row, dict)
    ]
    quality_by_event = {
        f"{str(row.get('source_family') or '').strip()}:{str(row.get('event_id') or '').strip()}": {
            "status": row.get("event_quality_status"),
            "score": row.get("event_quality_score"),
            "reasons": row.get("event_quality_reasons"),
            "time_status": row.get("event_time_anchor_status"),
            "time_precision": row.get("event_time_anchor_precision"),
            "time_confidence": row.get("event_time_anchor_confidence"),
            "time_source": row.get("event_time_anchor_source"),
            "resolved_date": row.get("resolved_historical_date"),
        }
        for row in source_event_rows
        if row.get("source_family") and row.get("event_id")
    }
    merged_event_ids_by_event = {
        event_id: str(row.get("merged_event_id") or "").strip()
        for row in merged_event_rows
        for event_id in row.get("source_event_ids", [])
        if isinstance(event_id, str) and event_id.strip()
    }
    ordering_edges_by_event: dict[str, set[str]] = {}
    ordering_basis_by_event: dict[str, set[str]] = {}
    time_basis_by_event: dict[str, set[str]] = {}
    
    for row in ordering_edge_rows:
        edge_id = str(row.get("ordering_edge_id") or "").strip()
        support_basis = {
            str(value).strip()
            for value in row.get("support_basis", [])
            if isinstance(value, str) and value.strip()
        }
        ordering_basis = str(row.get("ordering_basis") or "").strip()
        time_basis = str(row.get("time_basis") or "").strip()
        
        for event_id in row.get("source_event_ids", []):
            if not isinstance(event_id, str) or not event_id.strip():
                continue
            ordering_edges_by_event.setdefault(event_id, set()).add(edge_id)
            ordering_basis_by_event.setdefault(event_id, set()).update(support_basis)
            if ordering_basis:
                ordering_basis_by_event[event_id].add(ordering_basis)
            if time_basis:
                time_basis_by_event.setdefault(event_id, set()).add(time_basis)

    candidate_links_by_event: dict[str, set[str]] = {}
    for row in candidate_link_rows:
        link_id = str(row.get("link_id") or "").strip()
        for event_id in row.get("source_event_ids", []):
            if not isinstance(event_id, str) or not event_id.strip():
                continue
            candidate_links_by_event.setdefault(event_id, set()).add(link_id)

    status_hierarchy = ["rejected_noise", "weak_candidate", "usable_candidate", "promotable_event"]
    time_status_hierarchy = ["resolved_historical_date", "explicit_span_date", "source_metadata_date", "candidate_span_year", "ingest_only", "none"]

    for relation in list(merged_relations.values()):
        merged_event_ids: set[str] = set()
        ordering_edge_ids: set[str] = set()
        braid_support_basis: set[str] = set()
        braid_candidate_link_ids: set[str] = set()
        ordering_basis_types: set[str] = set()
        time_basis_types: set[str] = set()

        filtered_lineage = []
        for lineage in relation.get("lineage_records", []):
            if not isinstance(lineage, dict):
                continue
            event_key = _braid_key(
                str(lineage.get("source_family") or ""),
                str(lineage.get("event_id") or ""),
            )
            if not event_key:
                continue
            if audit_registry and audit_registry.get("events", {}).get(event_key, {}).get("recommended_status") == "block":
                continue
            filtered_lineage.append(lineage)
            
            merged_event_id = merged_event_ids_by_event.get(event_key)
            if merged_event_id:
                merged_event_ids.add(merged_event_id)
            ordering_edge_ids.update(ordering_edges_by_event.get(event_key, set()))
            braid_support_basis.update(ordering_basis_by_event.get(event_key, set()))
            braid_candidate_link_ids.update(candidate_links_by_event.get(event_key, set()))
            ordering_basis_types.update(ordering_basis_by_event.get(event_key, set()))
            time_basis_types.update(time_basis_by_event.get(event_key, set()))
            
            # Map quality and temporal info into the lineage entry
            quality = quality_by_event.get(event_key)
            if quality:
                lineage["event_quality_status"] = quality["status"]
                lineage["event_quality_score"] = quality["score"]
                lineage["event_quality_reasons"] = quality["reasons"]
                lineage["event_time_anchor_status"] = quality["time_status"]
                lineage["event_time_anchor_precision"] = quality["time_precision"]
                lineage["event_time_anchor_confidence"] = quality["time_confidence"]
                lineage["event_time_anchor_source"] = quality["time_source"]
                lineage["resolved_historical_date"] = quality["resolved_date"]

        relation["lineage_records"] = filtered_lineage

        if merged_event_ids:
            braid_support_basis.add("promoted_same_event_as")
        relation["merged_event_ids"] = sorted(merged_event_ids)
        relation["ordering_edge_ids"] = sorted(ordering_edge_ids)
        relation["braid_support_basis"] = sorted(braid_support_basis)
        relation["braid_candidate_link_ids"] = sorted(braid_candidate_link_ids)
        relation["ordering_basis_types"] = sorted(ordering_basis_types)
        relation["time_basis_types"] = sorted(time_basis_types)

        if merged_event_ids and ordering_edge_ids:
            relation["cross_source_braid_depth"] = "complete"
        elif merged_event_ids or ordering_edge_ids:
            relation["cross_source_braid_depth"] = "partial"
        elif braid_candidate_link_ids:
            relation["cross_source_braid_depth"] = "candidate_only"
        else:
            relation["cross_source_braid_depth"] = "missing"

        # Map aggregate relation quality & temporal info
        relation_lineage = relation.get("lineage_records", [])
        relation_scores = [
            l.get("event_quality_score")
            for l in relation_lineage
            if isinstance(l, dict) and l.get("event_quality_score") is not None
        ]
        avg_relation_score = round(sum(relation_scores) / (len(relation_scores) or 1), 2)
        relation_statuses = {
            l.get("event_quality_status")
            for l in relation_lineage
            if isinstance(l, dict) and l.get("event_quality_status")
        }
        worst_rel_status = "promotable_event"
        for status in status_hierarchy:
            if status in relation_statuses:
                worst_rel_status = status
                break
        relation_reasons = sorted({
            r
            for l in relation_lineage
            if isinstance(l, dict)
            for r in l.get("event_quality_reasons", [])
        })

        # Temporal status aggregate: pick the strongest status present
        relation_time_statuses = {
            l.get("event_time_anchor_status")
            for l in relation_lineage
            if isinstance(l, dict) and l.get("event_time_anchor_status")
        }
        best_time_status = "none"
        for status in time_status_hierarchy:
            if status in relation_time_statuses:
                best_time_status = status
                break

        # Best resolution date
        best_resolved_date = None
        for l in relation_lineage:
            if isinstance(l, dict) and l.get("resolved_historical_date"):
                best_resolved_date = l.get("resolved_historical_date")
                break

        relation["event_quality_status"] = worst_rel_status
        relation["event_quality_score"] = avg_relation_score
        relation["event_quality_reasons"] = relation_reasons
        relation["event_time_anchor_status"] = best_time_status
        relation["resolved_historical_date"] = best_resolved_date


def _merge_families(families: list[dict[str, Any]], *, braid_payload: dict[str, Any], audit_registry: dict[str, Any] | None = None) -> dict[str, Any]:
    merged_relations: dict[tuple[str, str, str], dict[str, Any]] = {}
    checked_handoff_relation_keys: set[tuple[str, str, str]] = set()
    merged_seed_lanes: dict[str, dict[str, Any]] = {}

    for family in families:
        source_family = str(family["source_family"])
        for row in family.get("selected_promoted_relations", []):
            key = _relation_key(row)
            if source_family == "checked_handoff":
                checked_handoff_relation_keys.add(key)
            merged = merged_relations.get(key)
            if merged is None:
                merged = {
                    "subject": row.get("subject"),
                    "predicate_key": row.get("predicate_key"),
                    "object": row.get("object"),
                    "confidence_tiers": [],
                    "source_families": [],
                    "lineage_records": [],
                    "merged_event_ids": [],
                    "ordering_edge_ids": [],
                    "braid_support_basis": [],
                    "braid_candidate_link_ids": [],
                    "cross_source_braid_depth": "missing",
                }
                merged_relations[key] = merged
            confidence_tier = str(row.get("confidence_tier") or "")
            if confidence_tier and confidence_tier not in merged["confidence_tiers"]:
                merged["confidence_tiers"].append(confidence_tier)
            if source_family not in merged["source_families"]:
                merged["source_families"].append(source_family)
            lineage_entry = _normalized_lineage_entry(source_family, row)
            lineage_key = (
                lineage_entry["source_family"],
                lineage_entry["event_id"],
                lineage_entry["source_path"],
                lineage_entry["source_url"],
            )
            existing_keys = {
                (
                    str(item.get("source_family") or ""),
                    str(item.get("event_id") or ""),
                    str(item.get("source_path") or ""),
                    str(item.get("source_url") or ""),
                )
                for item in merged["lineage_records"]
                if isinstance(item, dict)
            }
            if lineage_key not in existing_keys:
                merged["lineage_records"].append(lineage_entry)

        for row in family.get("selected_seed_lanes", []):
            seed_id = str(row.get("seed_id") or "")
            merged = merged_seed_lanes.get(seed_id)
            if merged is None:
                merged = {
                    "seed_id": seed_id,
                    "action_summary": row.get("action_summary"),
                    "linkage_kind": row.get("linkage_kind"),
                    "source_families": [],
                    "matched_source_families": [],
                    "support_kinds": [],
                    "review_statuses": [],
                }
                merged_seed_lanes[seed_id] = merged
            if source_family not in merged["source_families"]:
                merged["source_families"].append(source_family)
            review_status = str(row.get("review_status") or "")
            support_kind = str(row.get("support_kind") or "")
            if review_status and review_status not in merged["review_statuses"]:
                merged["review_statuses"].append(review_status)
            if support_kind and support_kind not in merged["support_kinds"]:
                merged["support_kinds"].append(support_kind)
            if review_status == "matched" and source_family not in merged["matched_source_families"]:
                merged["matched_source_families"].append(source_family)

    _annotate_merged_relations_with_braid(merged_relations, braid_payload, audit_registry=audit_registry)
    
    active_relations = {
        key: rel
        for key, rel in merged_relations.items()
        if rel.get("lineage_records")
    }

    merged_relation_rows = sorted(
        active_relations.values(),
        key=lambda row: (
            str(((row.get("subject") or {}).get("canonical_label")) or ""),
            str(row.get("predicate_key") or ""),
            str(((row.get("object") or {}).get("canonical_label")) or ""),
        ),
    )
    new_relation_rows = [
        row for key, row in sorted(active_relations.items(), key=lambda item: item[0]) if key not in checked_handoff_relation_keys
    ]
    merged_seed_rows = sorted(merged_seed_lanes.values(), key=lambda row: row["seed_id"])

    family_summaries = []
    for family in families:
        family_summaries.append(
            {
                "source_family": family["source_family"],
                "timeline_path": family.get("timeline_path", ""),
                "promoted_relation_count": len(family.get("selected_promoted_relations", [])),
                "matched_seed_lane_count": sum(
                    1 for row in family.get("selected_seed_lanes", []) if str(row.get("review_status") or "") == "matched"
                ),
                "ambiguous_event_count": len(family.get("ambiguous_events", [])),
                "unresolved_surface_count": len(family.get("unresolved_surfaces", [])),
            }
        )

    qc_meta = braid_payload.get("qc_meta") or {}
    source_event_count = qc_meta.get("source_event_count", 0)
    blocked_event_count = qc_meta.get("blocked_event_count", 0)
    active_event_count = qc_meta.get("active_event_count", 0)
    historical_timeline = qc_meta.get("historical_timeline") or {}
    
    relations_dropped_by_audit_block = len(merged_relations) - len(active_relations)
    
    qc_report = {
        "source_event_count": source_event_count,
        "blocked_event_count": blocked_event_count,
        "active_event_count": active_event_count,
        "candidate_link_count": len(braid_payload.get("candidate_links", [])),
        "merged_event_count": len(braid_payload.get("merged_events", [])),
        "ordering_edge_count": len(braid_payload.get("ordering_edges", [])),
        "historical_time_order_edge_count": sum(
            1 for e in braid_payload.get("ordering_edges", []) if e.get("ordering_basis") == "historical_time_order"
        ),
        "document_order_edge_count": sum(
            1 for e in braid_payload.get("ordering_edges", []) if e.get("ordering_basis") == "document_order"
        ),
        "ingest_order_only_edge_count": sum(
            1 for e in braid_payload.get("ordering_edges", []) if e.get("time_basis") == "ingest_order_only"
        ),
        "historical_conflict_residual_count": sum(
            1 for e in braid_payload.get("ordering_edges", []) if e.get("time_basis") == "historical_conflict_residual"
        ),
        "relations_dropped_by_audit_block": relations_dropped_by_audit_block,
        "relations_preserved_after_audit": len(active_relations),
        "quality_by_source_family": braid_payload.get("summary", {}).get("event_quality_audit_by_family", {}),
        "timeline_export_event_count": len(historical_timeline.get("source_event_rows", [])),
        "timeline_export_edge_count": len(historical_timeline.get("ordering_edges", [])),
    }

    return {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "broader_gwb_corpus_checkpoint",
        "summary": {
            "source_family_count": len(families),
            "distinct_promoted_relation_count": len(merged_relation_rows),
            "new_relation_count_vs_checked_handoff": len(new_relation_rows),
            "distinct_seed_lane_count": len(merged_seed_rows),
            "seed_lanes_supported_in_multiple_families": sum(
                1 for row in merged_seed_rows if len(row.get("matched_source_families", [])) >= 2
            ),
        },
        "source_family_summaries": family_summaries,
        "merged_promoted_relations": merged_relation_rows,
        "new_relations_vs_checked_handoff": new_relation_rows,
        "merged_seed_lanes": merged_seed_rows,
        "cross_source_event_braid": braid_payload,
        "qc_report": qc_report,
    }


def _build_summary_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    qc = payload.get("qc_report") or {}
    lines = [
        "# GWB Broader Corpus Checkpoint Summary",
        "",
        "This artifact is the first broader GWB extraction checkpoint beyond the",
        "bounded checked handoff. It combines the checked handoff lane with fresh",
        "deterministic extraction over the public-bios and corpus/book timelines.",
        "",
        "## GWB Timeline QC Report",
        "",
        f"- **Source Event Count**: {qc.get('source_event_count', 0)}",
        f"- **Blocked Event Count**: {qc.get('blocked_event_count', 0)}",
        f"- **Active Event Count**: {qc.get('active_event_count', 0)}",
        f"- **Candidate Link Count**: {qc.get('candidate_link_count', 0)}",
        f"- **Merged Event Count**: {qc.get('merged_event_count', 0)}",
        f"- **Ordering Edge Count**: {qc.get('ordering_edge_count', 0)}",
        f"  - *Historical Time Order*: {qc.get('historical_time_order_edge_count', 0)}",
        f"  - *Document Order*: {qc.get('document_order_edge_count', 0)}",
        f"  - *Ingest Order Only*: {qc.get('ingest_order_only_edge_count', 0)}",
        f"  - *Historical Conflict Residual*: {qc.get('historical_conflict_residual_count', 0)}",
        f"- **Relations Dropped by Audit Block**: {qc.get('relations_dropped_by_audit_block', 0)}",
        f"- **Relations Preserved After Audit**: {qc.get('relations_preserved_after_audit', 0)}",
        f"- **Timeline Export (Chronology Only)**:",
        f"  - *Events*: {qc.get('timeline_export_event_count', 0)}",
        f"  - *Edges*: {qc.get('timeline_export_edge_count', 0)}",
        "",
        "## Merged coverage summary",
        "",
        f"- Source families: {summary['source_family_count']}",
        f"- Distinct promoted relations: {summary['distinct_promoted_relation_count']}",
        f"- New relations beyond checked handoff: {summary['new_relation_count_vs_checked_handoff']}",
        f"- Distinct seed lanes: {summary['distinct_seed_lane_count']}",
        f"- Seed lanes matched in multiple source families: {summary['seed_lanes_supported_in_multiple_families']}",
        "",
        "## Per-source-family summary",
        "",
    ]
    for row in payload["source_family_summaries"]:
        lines.append(
            f"- {row['source_family']}: {row['promoted_relation_count']} promoted relations, "
            f"{row['matched_seed_lane_count']} matched seed lanes, "
            f"{row['ambiguous_event_count']} ambiguous events, "
            f"{row['unresolved_surface_count']} unresolved surfaces."
        )
    lines.extend(["", "## New relations beyond checked handoff", ""])
    if payload["new_relations_vs_checked_handoff"]:
        for row in payload["new_relations_vs_checked_handoff"][:12]:
            lines.append(
                f"- {row['subject']['canonical_label']} {row['predicate_key'].replace('_', ' ')} "
                f"{row['object']['canonical_label']} "
                f"(from: {', '.join(row['source_families'])})."
            )
    else:
        lines.append("- No new promoted relations were added beyond the checked handoff in the current broader pass.")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- This is still a checkpoint, not full GWB/topic closure.",
            "- It is the first machine-readable broader extraction pass over the",
            "  public-bios and corpus/book timeline lanes rather than only an",
            "  inventory of source families.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def build_broader_checkpoint(output_dir: Path, *, progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    from build_gwb_public_bios_rich_timeline import build_public_bios_timeline
    from gwb_corpus_timeline_build import build_corpus_timeline

    _emit_progress(progress_callback, "public_bios_timeline_started", section="checkpoint_inputs", message="Rebuilding richer public bios timeline.")
    build_public_bios_timeline(
        raw_root=SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "public_bios_v1" / "raw",
        out_path=DEFAULT_PUBLIC_BIOS_TIMELINE_PATH,
        max_docs=20,
        max_snippets_per_doc=12,
        snippet_chars=420,
        progress_callback=progress_callback,
    )
    _emit_progress(progress_callback, "public_bios_timeline_finished", section="checkpoint_inputs", message="Public bios timeline ready.")
    _emit_progress(progress_callback, "corpus_timeline_started", section="checkpoint_inputs", message="Rebuilding broader local corpus timeline.")
    build_corpus_timeline(
        root=SENSIBLAW_ROOT / "demo" / "ingest" / "gwb",
        out_path=DEFAULT_CORPUS_TIMELINE_PATH,
        max_docs=12,
        max_snippets_per_doc=80,
        snippet_chars=420,
        extract_chars_per_doc=20000,
        progress_callback=progress_callback,
    )
    _emit_progress(progress_callback, "corpus_timeline_finished", section="checkpoint_inputs", message="Corpus timeline ready.")
    families = [
        _read_checked_handoff_slice(DEFAULT_HANDOFF_SLICE_PATH),
        _run_extraction_for_timeline("public_bios_timeline", DEFAULT_PUBLIC_BIOS_TIMELINE_PATH),
        _run_extraction_for_timeline("corpus_book_timeline", DEFAULT_CORPUS_TIMELINE_PATH),
    ]
    raw_source_runs = [family for family in families if family["source_family"] != "checked_handoff"]
    braid_payload = build_cross_source_event_braid(raw_source_runs)

    from src.policy.gwb_spot_audit import load_spot_audit_registry, apply_spot_audit_blocks, export_historical_timeline
    audit_registry = load_spot_audit_registry()
    audited_braid = apply_spot_audit_blocks(braid_payload, audit_registry)
    historical_timeline = export_historical_timeline(braid_payload, audit_registry)

    source_event_count = len(braid_payload.get("source_event_rows", []))
    active_event_count = len(audited_braid.get("source_event_rows", []))
    blocked_event_count = source_event_count - active_event_count

    audited_braid["qc_meta"] = {
        "source_event_count": source_event_count,
        "blocked_event_count": blocked_event_count,
        "active_event_count": active_event_count,
        "historical_timeline": historical_timeline,
    }

    _emit_progress(progress_callback, "family_merge_started", section="checkpoint_merge", completed=0, total=len(families), message="Merging source families.")
    payload = _merge_families(families, braid_payload=audited_braid, audit_registry=audit_registry)
    summary_text = _build_summary_text(payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "slice_path": output_dir / f"{ARTIFACT_VERSION}.json",
        "summary_path": output_dir / f"{ARTIFACT_VERSION}.summary.md",
        "candidate_event_braid_path": output_dir / "candidate_event_braid.json",
        "historical_timeline_candidate_path": output_dir / "historical_timeline_candidate.json",
        "qc_report_path": output_dir / "gwb_timeline_qc_report.json",
    }
    # Convert FragmentPNF objects to dicts before JSON serialization
    serialize_fragment_pnfs_in_rows(payload.get("cross_source_event_braid", {}).get("source_event_rows") or [])
    serialize_fragment_pnfs_in_rows(audited_braid.get("source_event_rows") or [])
    serialize_fragment_pnfs_in_rows(historical_timeline.get("source_event_rows") or [])

    paths["slice_path"].write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["summary_path"].write_text(summary_text, encoding="utf-8")
    paths["candidate_event_braid_path"].write_text(json.dumps(audited_braid, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["historical_timeline_candidate_path"].write_text(json.dumps(historical_timeline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["qc_report_path"].write_text(json.dumps(payload.get("qc_report"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOGGER.info("Wrote broader GWB checkpoint to %s", paths["slice_path"])
    
    from scripts.build_gwb_timeline_content_review import build_timeline_content_review
    review_res = build_timeline_content_review(paths["slice_path"], output_dir)
    
    from scripts.build_gwb_human_review_timeline import build_human_review_timeline_packet
    packet_res = build_human_review_timeline_packet(
        paths["slice_path"],
        Path(review_res["json_path"]),
        paths["historical_timeline_candidate_path"],
        output_dir
    )
    
    _emit_progress(progress_callback, "family_merge_finished", section="checkpoint_merge", completed=len(families), total=len(families), message="Broader checkpoint written.")
    return {
        "summary": payload["summary"],
        **{k: str(v) for k, v in paths.items()},
        "content_review_json_path": review_res["json_path"],
        "content_review_md_path": review_res["md_path"],
        "human_review_json_path": packet_res["json_path"],
        "human_review_md_path": packet_res["md_path"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the first broader GWB corpus extraction checkpoint.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the broader GWB checkpoint into.")
    parser.add_argument("--progress", action="store_true", help="Emit progress to stderr.")
    parser.add_argument("--progress-format", choices=("human", "json"), default="human", help="Progress renderer for stderr output.")
    parser.add_argument("--log-level", default="INFO", help="stderr logging level (default: %(default)s).")
    args = parser.parse_args()
    configure_cli_logging(args.log_level)
    payload = build_broader_checkpoint(
        Path(args.output_dir).resolve(),
        progress_callback=build_progress_callback(enabled=bool(args.progress), fmt=str(args.progress_format)),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
