#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SENSIBLAW_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SENSIBLAW_ROOT.parent
SRC_ROOT = SENSIBLAW_ROOT / "src"

for path in (SCRIPT_DIR, SENSIBLAW_ROOT, SRC_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

try:
    from src.policy.parliamentary_follow_control import compute_parliamentary_weight
except ModuleNotFoundError:
    from policy.parliamentary_follow_control import compute_parliamentary_weight

try:
    from scripts.review_geometry_profiles import get_normalized_profile
    from scripts.review_geometry_normalization import (
        compute_normalized_metrics_from_profile,
        render_normalized_metrics_markdown,
    )
except ModuleNotFoundError:
    from review_geometry_profiles import get_normalized_profile
    from review_geometry_normalization import (
        compute_normalized_metrics_from_profile,
        render_normalized_metrics_markdown,
    )

try:
    from src.policy.affidavit_extraction_hints import (
        build_provisional_anchor_bundles as _build_provisional_anchor_bundles_impl,
        build_provisional_structured_anchors as _build_provisional_structured_anchors_impl,
    )
except ModuleNotFoundError:
    from policy.affidavit_extraction_hints import (
        build_provisional_anchor_bundles as _build_provisional_anchor_bundles_impl,
        build_provisional_structured_anchors as _build_provisional_structured_anchors_impl,
    )
try:
    from src.policy.compiler_contract import build_gwb_broader_review_contract
except ModuleNotFoundError:
    from policy.compiler_contract import build_gwb_broader_review_contract
try:
    from src.policy.gwb_legal_follow_graph import (
        build_gwb_legal_follow_graph,
        build_gwb_legal_follow_operator_view,
    )
except ModuleNotFoundError:
    from policy.gwb_legal_follow_graph import (
        build_gwb_legal_follow_graph,
        build_gwb_legal_follow_operator_view,
    )
try:
    from src.sources.uk_legislation import (
        load_uk_legislation_follow_candidates,
        normalize_legislation_receipts,
    )
except ModuleNotFoundError:
    def load_uk_legislation_follow_candidates() -> dict[str, list[dict[str, Any]]]:
        return {"review_item_rows": [], "source_review_rows": []}

    def normalize_legislation_receipts(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []
try:
    from src.proof.parliamentary_reasoning import build_primary_proving_cases
except ModuleNotFoundError:
    from proof.parliamentary_reasoning import build_primary_proving_cases
try:
    from src.policy.product_gate import build_product_gate
except ModuleNotFoundError:
    from policy.product_gate import build_product_gate
try:
    from SensibLaw.src.sources.national_archives.brexit_national_archives_lane import (
        fetch_brexit_archive_records,
    )
except ModuleNotFoundError:
    from src.sources.national_archives.brexit_national_archives_lane import (
        fetch_brexit_archive_records,
    )

ARTIFACT_VERSION = "gwb_broader_review_v1"
SOURCE_SLICE_PATH = (
    SENSIBLAW_ROOT
    / "tests"
    / "fixtures"
    / "zelph"
    / "gwb_broader_corpus_checkpoint_v1"
    / "gwb_broader_corpus_checkpoint_v1.json"
)
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
_GWB_BROADER_ANCHOR_KIND_WEIGHT = {
    "source_family": 12,
    "support_kind": 8,
    "review_status": 5,
    "predicate": 9,
    "ambiguous_event_count": 16,
    "unresolved_surface_count": 16,
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _build_legislation_receipt_review_item(receipts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not receipts:
        return None
    return {
        "review_item_id": "uk-legislation-live-receipts",
        "seed_id": "uk-legislation-live",
        "action_summary": "Review normalized UK legislation receipts",
        "linkage_kind": "legal_reference",
        "support_kinds": ["legislation_receipt"],
        "review_statuses": ["missing_review"],
        "coverage_status": "missing_review",
        "source_family_count": 1,
        "matched_source_family_count": 0,
    }


def _build_legislation_receipt_source_rows(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, receipt in enumerate(receipts, start=1):
        metadata = receipt.get("metadata") or {}
        section_label = metadata.get("section") or f"section-{index}"
        section_display = metadata.get("section_label") or section_label
        title = metadata.get("title") or "UK legislation"
        version_label = metadata.get("version") or "enacted"
        rows.append(
            {
                "source_row_id": f"uk_legislation_receipt:{index}",
                "seed_id": "uk-legislation-live",
                "source_kind": "uk_legislation_receipt",
                "source_family": "uk_legislation",
                "review_status": "missing_review",
                "workload_classes": ["authority_receipt_gap"],
                "primary_workload_class": "authority_receipt_gap",
                "text": f"{title} section {section_display} ({version_label})",
                "label": f"{title} section {section_display} ({version_label})",
                "metadata": {
                    "section_label": section_display,
                    "section": section_label,
                    "version": version_label,
                },
                "receipts": [receipt],
                "candidate_anchors": [
                    {
                        "anchor_kind": "source_family",
                        "anchor_label": "uk_legislation",
                        "anchor_value": "uk_legislation",
                    },
                    {
                        "anchor_kind": "section",
                        "anchor_label": section_label,
                        "anchor_value": section_label,
                    },
                    {
                        "anchor_kind": "section_label",
                        "anchor_label": section_display,
                        "anchor_value": section_display,
                    },
                    {
                        "anchor_kind": "version",
                        "anchor_label": version_label,
                        "anchor_value": version_label,
                    },
                ],
            }
        )
    return rows


def _build_parliamentary_source_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in build_primary_proving_cases():
        source_unit = case.get("source_unit")
        if not source_unit:
            continue
        normalized = source_unit.get("normalized_source_unit") or {}
        fixture = case.get("fixture", {})
        clause_ir = source_unit.get("clause_ir", {})
        claim_flag = source_unit.get("claim_type") or fixture.get("result", {}).get("signal")
        rows.append(
            {
                "source_row_id": f"parliamentary:{source_unit['source_unit_id']}",
                "seed_id": case.get("case"),
                "source_kind": "parliamentary_statement",
                "source_family": normalized.get("source_family", "parliamentary"),
                "review_status": "covered",
                "workload_classes": ["parliamentary_source_unit"],
                "primary_workload_class": "linkage_gap",
                "priority_score": 5,
                "text": fixture.get("interpretation", {}).get("quote", ""),
                "label": f"Parliamentary statement {case.get('case')}",
                "operator_label": f"Parliamentary statement {case.get('case')} ({claim_flag})",
                "operator_note": clause_ir.get("interpretive_note"),
                "metadata": {
                    "source_unit_id": source_unit["source_unit_id"],
                    "claim_type": claim_flag,
                    "clause_label": clause_ir.get("clause_label"),
                    "clause_reference": clause_ir.get("clause_reference"),
                    "interpretive_note": clause_ir.get("interpretive_note"),
                    "speaker_identity": source_unit.get("speaker_identity"),
                    "normalized_source_unit": normalized,
                    "ready_for_follow": True,
                },
                "candidate_anchors": [
                    {
                        "anchor_kind": "source_family",
                        "anchor_label": normalized.get("source_family", "parliamentary"),
                        "anchor_value": normalized.get("source_family", "parliamentary"),
                    },
                    {
                        "anchor_kind": "source_unit",
                        "anchor_label": source_unit["source_unit_id"],
                        "anchor_value": source_unit["source_unit_id"],
                    },
                    {
                        "anchor_kind": "clause_label",
                        "anchor_label": clause_ir.get("clause_label"),
                        "anchor_value": clause_ir.get("clause_label"),
                    },
                ],
            }
        )
    return rows


def _build_review_item_rows(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in slice_payload.get("merged_seed_lanes", []):
        seed_id = str(lane.get("seed_id") or "").strip()
        if not seed_id:
            continue
        matched_families = list(lane.get("matched_source_families", []))
        source_families = list(lane.get("source_families", []))
        if len(matched_families) == len(source_families):
            coverage_status = "covered"
        elif matched_families:
            coverage_status = "partial"
        else:
            coverage_status = "unsupported"
        rows.append(
            {
                "review_item_id": f"seed:{seed_id}",
                "seed_id": seed_id,
                "action_summary": lane.get("action_summary"),
                "linkage_kind": lane.get("linkage_kind"),
                "coverage_status": coverage_status,
                "source_family_count": len(source_families),
                "matched_source_family_count": len(matched_families),
                "support_kinds": list(lane.get("support_kinds", [])),
                "review_statuses": list(lane.get("review_statuses", [])),
            }
        )
    return rows


def _family_row(
    *, seed_id: str, family: str, matched: bool, review_statuses: list[str], support_kinds: list[str]
) -> dict[str, Any]:
    review_status = "covered" if matched else "missing_review"
    workload_class = "support_breadth_gap" if matched else "linkage_gap"
    return {
        "source_row_id": f"{seed_id}:{family}",
        "seed_id": seed_id,
        "source_kind": "seed_family_support",
        "source_family": family,
        "review_status": review_status,
        "workload_classes": [workload_class],
        "primary_workload_class": workload_class,
        "text": f"{seed_id} in {family}",
        "candidate_anchors": [
            {"anchor_kind": "source_family", "anchor_label": family, "anchor_value": family},
            *[
                {"anchor_kind": "support_kind", "anchor_label": kind, "anchor_value": kind}
                for kind in support_kinds
            ],
            *[
                {"anchor_kind": "review_status", "anchor_label": status, "anchor_value": status}
                for status in review_statuses
            ],
        ],
    }


def _build_source_review_rows(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in slice_payload.get("merged_seed_lanes", []):
        seed_id = str(lane.get("seed_id") or "").strip()
        matched_families = set(lane.get("matched_source_families", []))
        review_statuses = list(lane.get("review_statuses", []))
        support_kinds = list(lane.get("support_kinds", []))
        for family in lane.get("source_families", []):
            rows.append(
                _family_row(
                    seed_id=seed_id,
                    family=family,
                    matched=family in matched_families,
                    review_statuses=review_statuses,
                    support_kinds=support_kinds,
                )
            )

    for index, relation in enumerate(slice_payload.get("merged_promoted_relations", []), start=1):
        subject = relation.get("subject", {})
        obj = relation.get("object", {})
        predicate = relation.get("predicate_key")
        source_families = list(relation.get("source_families", []))
        rows.append(
            {
                "source_row_id": f"relation:{index}",
                "seed_id": None,
                "source_kind": "merged_promoted_relation",
                "source_family": ",".join(source_families),
                "review_status": "covered",
                "workload_classes": ["covered"],
                "primary_workload_class": "covered",
                "text": (
                    f"{subject.get('canonical_label')} {predicate} {obj.get('canonical_label')}"
                ),
                "candidate_anchors": [
                    {"anchor_kind": "predicate", "anchor_label": str(predicate), "anchor_value": predicate},
                    *[
                        {"anchor_kind": "source_family", "anchor_label": family, "anchor_value": family}
                        for family in source_families
                    ],
                ],
            }
        )

    for family in slice_payload.get("source_family_summaries", []):
        rows.append(
            {
                "source_row_id": f"family_summary:{family['source_family']}",
                "seed_id": None,
                "source_kind": "source_family_summary",
                "source_family": family["source_family"],
                "review_status": "missing_review",
                "workload_classes": ["event_extraction_gap"],
                "primary_workload_class": "event_extraction_gap",
                "text": (
                    f"{family['source_family']} ambiguous_events={family['ambiguous_event_count']} "
                    f"unresolved_surfaces={family['unresolved_surface_count']}"
                ),
                "candidate_anchors": [
                    {
                        "anchor_kind": "ambiguous_event_count",
                        "anchor_label": str(family["ambiguous_event_count"]),
                        "anchor_value": family["ambiguous_event_count"],
                    },
                    {
                        "anchor_kind": "unresolved_surface_count",
                        "anchor_label": str(family["unresolved_surface_count"]),
                        "anchor_value": family["unresolved_surface_count"],
                    },
                ],
            }
        )
    return rows


def _build_clusters(review_item_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    item_by_seed = {row["seed_id"]: row for row in review_item_rows}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        if row.get("seed_id") and row.get("review_status") == "missing_review":
            grouped[row["seed_id"]].append(row)
    clusters: list[dict[str, Any]] = []
    for seed_id, rows in sorted(grouped.items()):
        workload = Counter()
        anchor_rollup = Counter()
        for row in rows:
            for item in row.get("workload_classes", []):
                workload[item] += 1
            for anchor in row.get("candidate_anchors", []):
                anchor_rollup[str(anchor.get("anchor_kind"))] += 1
        clusters.append(
            {
                "cluster_id": f"cluster:{seed_id}",
                "seed_id": seed_id,
                "coverage_status": item_by_seed[seed_id]["coverage_status"],
                "candidate_source_count": len(rows),
                "dominant_workload_class": max(workload, key=workload.get),
                "workload_class_rollup": dict(sorted(workload.items())),
                "candidate_anchor_rollup": dict(sorted(anchor_rollup.items())),
            }
        )
    return clusters


def _build_workflow_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    operator_views = payload.get("operator_views", {}) if isinstance(payload.get("operator_views"), dict) else {}
    legal_follow = (
        operator_views.get("legal_follow_graph")
        if isinstance(operator_views.get("legal_follow_graph"), dict)
        else {}
    )
    legal_follow_summary = (
        legal_follow.get("summary") if isinstance(legal_follow.get("summary"), dict) else {}
    )
    legal_follow_queue_count = int(legal_follow_summary.get("queue_count") or 0)
    missing_review_count = int(summary.get("missing_review_count") or 0)
    provisional_bundle_count = int(summary.get("provisional_review_bundle_count") or 0)
    promotion_gate = payload.get("promotion_gate") if isinstance(payload.get("promotion_gate"), dict) else {}

    archive_live_count = int(summary.get("archive_follow_live_count") or 0)
    counts = {
        "missing_review_count": missing_review_count,
        "legal_follow_queue_count": legal_follow_queue_count,
        "provisional_bundle_count": provisional_bundle_count,
        "archive_follow_live_count": archive_live_count,
        "debate_edge_count": int(summary.get("debate_edge_count") or 0),
    }
    if archive_live_count > 0:
        return {
            "stage": "archive",
            "title": "Review live National Archives follow evidence",
            "recommended_view": "archive_follow_rows",
            "reason": f"{archive_live_count} live archive follow row(s) need review and ranking.",
            "counts": counts,
            "promotion_gate": dict(promotion_gate),
        }
    if legal_follow_queue_count > 0:
        return {
            "stage": "follow_up",
            "title": "Resolve bounded legal follow items",
            "recommended_view": "legal_follow_graph",
            "reason": f"{legal_follow_queue_count} legal follow item(s) remain open.",
            "counts": counts,
            "promotion_gate": dict(promotion_gate),
        }
    if missing_review_count > 0:
        return {
            "stage": "decide",
            "title": "Review unresolved broader GWB source rows",
            "recommended_view": "source_review_rows",
            "reason": f"{missing_review_count} source row(s) remain missing review coverage.",
            "counts": counts,
            "promotion_gate": dict(promotion_gate),
        }
    return {
        "stage": "record",
        "title": "Record the bounded broader GWB review state",
        "recommended_view": "summary",
        "reason": "No open legal-follow or source-review pressure remains in the current broader GWB slice.",
        "counts": counts,
        "promotion_gate": dict(promotion_gate),
    }


def _build_provisional_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provisional_rows = _build_provisional_structured_anchors_impl(
        source_rows,
        anchor_kind_weight=_GWB_BROADER_ANCHOR_KIND_WEIGHT,
        dedupe=False,
    )
    rows: list[dict[str, Any]] = []
    for row in provisional_rows:
        copied = dict(row)
        provisional_anchor_id = str(copied.pop("provisional_anchor_id", "")).strip()
        if provisional_anchor_id:
            copied["provisional_review_id"] = provisional_anchor_id.replace("#anchor:", "#p")
        rows.append(copied)
    rows.sort(key=lambda row: (-int(row["priority_score"]), str(row.get("provisional_review_id") or "")))
    for rank, row in enumerate(rows, start=1):
        row["priority_rank"] = rank
    return rows


def _build_bundles(provisional_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shared_rows: list[dict[str, Any]] = []
    for row in provisional_rows:
        copied = dict(row)
        provisional_review_id = str(copied.pop("provisional_review_id", "")).strip()
        if provisional_review_id:
            copied["provisional_anchor_id"] = provisional_review_id.replace("#p", "#anchor:")
        shared_rows.append(copied)
    bundles = _build_provisional_anchor_bundles_impl(shared_rows)
    normalized_bundles: list[dict[str, Any]] = []
    for bundle in bundles:
        normalized_bundle = {
            "source_row_id": bundle.get("source_row_id"),
            "anchor_count": bundle.get("anchor_count"),
            "top_priority_score": bundle.get("top_priority_score"),
            "bundle_rank": bundle.get("bundle_rank"),
        }
        normalized_bundles.append(normalized_bundle)
    return normalized_bundles


def build_gwb_broader_review(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    slice_payload = _load_json(SOURCE_SLICE_PATH)
    review_item_rows = _build_review_item_rows(slice_payload)
    source_review_rows = _build_source_review_rows(slice_payload)
    uk_legislation = load_uk_legislation_follow_candidates()
    if uk_legislation["review_item_rows"]:
        review_item_rows.extend(uk_legislation["review_item_rows"])
    if uk_legislation["source_review_rows"]:
        source_review_rows.extend(uk_legislation["source_review_rows"])
    legislation_receipts = normalize_legislation_receipts()
    receipt_review_item = _build_legislation_receipt_review_item(legislation_receipts)
    if receipt_review_item:
        review_item_rows.append(receipt_review_item)
    receipt_rows = _build_legislation_receipt_source_rows(legislation_receipts)
    if receipt_rows:
        source_review_rows.extend(receipt_rows)
    parliamentary_rows = _build_parliamentary_source_rows()
    if parliamentary_rows:
        source_review_rows.extend(parliamentary_rows)
    related_review_clusters = _build_clusters(review_item_rows, source_review_rows)
    provisional_review_rows = _build_provisional_rows(source_review_rows)
    provisional_review_bundles = _build_bundles(provisional_review_rows)

    archive_follow_rows = fetch_brexit_archive_records(limit=1)
    archive_live_rows = [row for row in archive_follow_rows if row.get("live_fetch")]
    if archive_live_rows:
        source_review_rows.append(
            {
                "source_row_id": f"archive:{archive_live_rows[0]["doc_id"]}",
                "source_family": "national_archives",
                "review_status": "review_required",
                "workload_classes": ["archive_follow"],
                "primary_workload_class": "archive_follow",
                "candidate_anchors": [
                    {
                        "anchor_kind": "archive",
                        "anchor_label": "live archive fetch",
                        "anchor_value": archive_live_rows[0]["doc_id"],
                    }
                ],
                "text": archive_live_rows[0]["text_excerpt"],
            }
        )
        review_item_rows.append(
            {
                "review_item_id": f"archive-live:{archive_live_rows[0]["doc_id"]}",
                "seed_id": archive_live_rows[0]["doc_id"],
                "action_summary": "Live National Archives follow",
                "linkage_kind": "archive",
                "coverage_status": "partial",
                "source_family_count": 1,
                "matched_source_family_count": 0,
                "support_kinds": ["archive_follow"],
                "review_statuses": ["review_required"],
            }
        )
    summary = {
        "review_item_count": len(review_item_rows),
        "source_row_count": len(source_review_rows),
        "covered_count": sum(1 for row in source_review_rows if row["review_status"] == "covered"),
        "missing_review_count": sum(
            1 for row in source_review_rows if row["review_status"] == "missing_review"
        ),
        "related_review_cluster_count": len(related_review_clusters),
        "candidate_anchor_count": sum(
            len(row.get("candidate_anchors", [])) for row in source_review_rows
        ),
        "provisional_review_row_count": len(provisional_review_rows),
        "provisional_review_bundle_count": len(provisional_review_bundles),
        **slice_payload["summary"],
    }
    if archive_follow_rows:
        summary["archive_follow_count"] = len(archive_follow_rows)
        summary["archive_follow_live_count"] = len(archive_live_rows)
        summary["archive_follow_live_count"] = sum(1 for row in archive_follow_rows if row.get("live_fetch"))
    payload = {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "gwb_broader_review",
        "source_input": {"path": str(SOURCE_SLICE_PATH.relative_to(REPO_ROOT))},
        "summary": summary,
        "review_item_rows": review_item_rows,
        "source_review_rows": source_review_rows,
        "related_review_clusters": related_review_clusters,
        "provisional_review_rows": provisional_review_rows,
        "provisional_review_bundles": provisional_review_bundles,
        "archive_follow_rows": archive_follow_rows,
    }
    payload["parliamentary_control"] = compute_parliamentary_weight(
        ["debate", "committee_report"]
    )
    payload["legal_follow_graph"] = build_gwb_legal_follow_graph(
        review_item_rows=review_item_rows,
        source_review_rows=source_review_rows,
    )
    graph_edges = payload["legal_follow_graph"].get("edges") if isinstance(payload["legal_follow_graph"].get("edges"), list) else []
    summary["debate_edge_count"] = sum(
        1 for edge in graph_edges if str(edge.get("source") or "").startswith("debate:")
    )
    payload["operator_views"] = {
        "legal_follow_graph": build_gwb_legal_follow_operator_view(payload["legal_follow_graph"])
    }
    payload["compiler_contract"] = build_gwb_broader_review_contract(payload)
    payload["promotion_gate"] = build_product_gate(
        lane="gwb",
        product_ref=ARTIFACT_VERSION,
        compiler_contract=payload["compiler_contract"],
    )
    payload["workflow_summary"] = _build_workflow_summary(payload)
    payload["normalized_metrics_v1"] = compute_normalized_metrics_from_profile(
        profile=get_normalized_profile("gwb"),
        artifact_id="gwb_broader_review_v1",
        lane_family="gwb",
        lane_variant="broader",
        review_item_rows=review_item_rows,
        source_review_rows=source_review_rows,
        candidate_signal_count=sum(
            len(row.get("candidate_anchors", []))
            for row in source_review_rows
            if row.get("review_status") == "missing_review"
        ),
        provisional_queue_row_count=len(provisional_review_rows),
        provisional_bundle_count=len(provisional_review_bundles),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    return {"artifact_path": str(artifact_path), "summary_path": str(summary_path)}


def build_summary_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    graph_summary = (
        payload.get("legal_follow_graph", {}).get("summary", {})
        if isinstance(payload.get("legal_follow_graph"), dict)
        else {}
    )
    graph_payload = payload.get("legal_follow_graph", {}) if isinstance(payload.get("legal_follow_graph"), dict) else {}
    graph_nodes = graph_payload.get("nodes", []) if isinstance(graph_payload.get("nodes"), list) else []
    graph_edges = graph_payload.get("edges", []) if isinstance(graph_payload.get("edges"), list) else []

    def node_label(node_id: str) -> str:
        for row in graph_nodes:
            if str(row.get("id") or "") == node_id:
                return str(row.get("label") or node_id)
        return node_id

    lines = [
        "# GWB Broader Review",
        "",
        f"- Review items: `{summary['review_item_count']}`",
        f"- Source rows: `{summary['source_row_count']}`",
        f"- Covered source rows: `{summary['covered_count']}`",
        f"- Missing-review source rows: `{summary['missing_review_count']}`",
        f"- Related review clusters: `{summary['related_review_cluster_count']}`",
        f"- Candidate anchors: `{summary['candidate_anchor_count']}`",
        f"- Provisional review rows: `{summary['provisional_review_row_count']}`",
        f"- Provisional review bundles: `{summary['provisional_review_bundle_count']}`",
        f"- Debate edges captured: `{summary.get('debate_edge_count', 0)}`",
    ]
    if graph_summary:
        lines.extend(
            [
                "",
                "## Derived Legal-Linkage Graph",
                "",
                f"- Nodes: `{graph_summary.get('node_count', 0)}`",
                f"- Edges: `{graph_summary.get('edge_count', 0)}`",
                f"- Seed lanes: `{graph_summary.get('seed_lane_count', 0)}`",
                f"- Source rows: `{graph_summary.get('source_row_count', 0)}`",
                f"- Distinct source-row nodes: `{graph_summary.get('source_row_node_count', 0)}`",
            ]
        )
        source_kind_counts = graph_summary.get("source_kind_counts", {})
        if isinstance(source_kind_counts, dict) and source_kind_counts:
            lines.append(
                f"- Source kinds: `{', '.join(f'{key}: {value}' for key, value in sorted(source_kind_counts.items()))}`"
            )
        source_family_counts = graph_summary.get("source_family_label_counts", {})
        if isinstance(source_family_counts, dict) and source_family_counts:
            lines.append(
                f"- Source families: `{', '.join(f'{key}: {value}' for key, value in sorted(source_family_counts.items()))}`"
            )
        linkage_kind_counts = graph_summary.get("linkage_kind_counts", {})
        if isinstance(linkage_kind_counts, dict) and linkage_kind_counts:
            lines.append(
                f"- Linkage kinds: `{', '.join(f'{key}: {value}' for key, value in sorted(linkage_kind_counts.items()))}`"
            )
        review_status_counts = graph_summary.get("review_status_label_counts", {})
        if isinstance(review_status_counts, dict) and review_status_counts:
            lines.append(
                f"- Review statuses: `{', '.join(f'{key}: {value}' for key, value in sorted(review_status_counts.items()))}`"
            )
    parliamentary_control = payload.get("parliamentary_control")
    if isinstance(parliamentary_control, dict):
        sources = parliamentary_control.get("sources", [])
        lines.extend(
            [
                "",
                "## Parliamentary Control Boost",
                "",
                f"- Boost score: `{parliamentary_control.get('score')}`",
                f"- Sources: `{', '.join(sources)}`",
            ]
        )
        support_kind_counts = graph_summary.get("support_kind_label_counts", {})
        if isinstance(support_kind_counts, dict) and support_kind_counts:
            lines.append(
                f"- Support kinds: `{', '.join(f'{key}: {value}' for key, value in sorted(support_kind_counts.items()))}`"
            )
        followed_source_cite_class_counts = graph_summary.get("followed_source_cite_class_counts", {})
        if isinstance(followed_source_cite_class_counts, dict) and followed_source_cite_class_counts:
            lines.append(
                f"- Followed legal-cite classes: `{', '.join(f'{key}: {value}' for key, value in sorted(followed_source_cite_class_counts.items()))}`"
            )
        if graph_summary.get("brexit_related_follow_count"):
            lines.append(f"- Brexit-related follows: `{graph_summary.get('brexit_related_follow_count', 0)}`")
        interesting_nodes = [
            row
            for row in graph_nodes
            if str(row.get("kind") or "") in {"source_family", "linkage_kind", "support_kind", "review_status", "predicate"}
        ]
        if interesting_nodes:
            lines.extend(["", "### Graph inspection", ""])
            for row in interesting_nodes[:6]:
                lines.append(f"- {row.get('kind')}: `{row.get('label')}`")
        if graph_edges:
            lines.extend(["", "### Sample typed links", ""])
            for row in graph_edges[:6]:
                lines.append(
                    f"- `{row.get('kind')}`: `{node_label(str(row.get('source') or ''))}` -> `{node_label(str(row.get('target') or ''))}`"
                )
    normalized_metrics = payload.get("normalized_metrics_v1", {})
    if isinstance(normalized_metrics, dict) and normalized_metrics:
        lines.extend(["", *render_normalized_metrics_markdown(normalized_metrics)])
    lines.extend(["", "## Top Provisional Review Bundles", ""])
    for bundle in payload["provisional_review_bundles"][:10]:
        lines.append(
            f"- `#{bundle['bundle_rank']}` `{bundle['source_row_id']}` anchors `{bundle['anchor_count']}` top-score `{bundle['top_priority_score']}`"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the GWB broader review artifact.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the broader review artifact will be written.",
    )
    args = parser.parse_args()
    print(json.dumps(build_gwb_broader_review(Path(args.output_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
