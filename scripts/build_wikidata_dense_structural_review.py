#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))

from scripts.build_wikidata_structural_handoff import (
    DISJOINTNESS_CASE_PATHS,
    HOTSPOT_MANIFEST_PATH,
    QUALIFIER_BASELINE_PATH,
    QUALIFIER_DRIFT_PROJECTION_PATH,
    _build_slice,
)
from scripts.build_wikidata_structural_review import (
    _make_clusters,
    _make_review_items,
)
try:
    from src.policy.wikidata_review_queue import (
        make_bundles as _make_bundles,
        make_provisional_rows as _make_provisional_rows,
        next_action_for_workload as _next_action_for_workload,
    )
except ModuleNotFoundError:
    from policy.wikidata_review_queue import (
        make_bundles as _make_bundles,
        make_provisional_rows as _make_provisional_rows,
        next_action_for_workload as _next_action_for_workload,
    )
from scripts.review_geometry_profiles import get_normalized_profile
from scripts.review_geometry_normalization import (
    compute_normalized_metrics_from_profile,
    render_normalized_metrics_markdown,
)
from src.policy.wikidata_structural_geometry import (
    build_dense_disjointness_cues,
    build_dense_disjointness_row,
    build_dense_hotspot_cues,
    build_dense_hotspot_rows,
    build_dense_qualifier_drift_cues,
    build_dense_qualifier_drift_row,
)
from src.policy.wikidata_structural_io import (
    load_json_object,
    relative_repo_path,
    write_json_markdown_artifact,
)


ARTIFACT_VERSION = "wikidata_dense_structural_review_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION


def _relative(path: Path) -> str:
    return relative_repo_path(path, repo_root=REPO_ROOT)


def _label_for(label_map: dict[str, Any], qid: str | None) -> str:
    if not qid:
        return "unknown"
    return str(label_map.get(qid) or qid)


def _build_source_review_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    checked_slice = _build_slice()
    baseline_payload = load_json_object(QUALIFIER_BASELINE_PATH)
    drift_projection = load_json_object(QUALIFIER_DRIFT_PROJECTION_PATH)
    hotspot_manifest = load_json_object(HOTSPOT_MANIFEST_PATH)
    baseline_item_id = "review:qualifier_baseline"
    drift_item_id = f"review:qualifier_drift:{checked_slice['qualifier_core']['drift_case']['slot_id']}"

    for window in baseline_payload.get("windows", []):
        window_id = window.get("id")
        for index, bundle in enumerate(window.get("statement_bundles", []), start=1):
            subject = str(bundle.get("subject") or "")
            value = str(bundle.get("value") or "")
            qualifiers = bundle.get("qualifiers") or {}
            qualifier_keys = sorted(qualifiers)
            rows.append(
                {
                    "source_row_id": f"source:dense:qualifier_baseline:{window_id}:{index}",
                    "review_item_id": baseline_item_id,
                    "source_kind": "qualifier_statement_bundle",
                    "workload_class": "baseline_confirmation",
                    "review_status": "baseline",
                    "recommended_next_action": _next_action_for_workload("baseline_confirmation"),
                    "source_path": _relative(QUALIFIER_BASELINE_PATH),
                    "text": (
                        f"{subject} {bundle.get('property')} {value} in {window_id} "
                        f"with qualifiers {','.join(qualifier_keys) or 'none'}."
                    ),
                    "cue_payload": {
                        "subject": subject,
                        "value": value,
                        "qualifier_keys": qualifier_keys,
                        "rank": bundle.get("rank"),
                    },
                }
            )

    for drift_row in drift_projection.get("qualifier_drift", []):
        rows.append(
            build_dense_qualifier_drift_row(
                drift_row=drift_row,
                review_item_id=drift_item_id,
                source_path=_relative(QUALIFIER_DRIFT_PROJECTION_PATH),
                recommended_next_action=_next_action_for_workload("qualifier_drift_gap"),
            )
        )

    for pack in hotspot_manifest.get("entries", []):
        pack_id = pack.get("pack_id")
        if pack_id not in checked_slice["hotspot_governance"]["selected_pack_ids"]:
            continue
        workload_class = "governance_gap" if pack.get("promotion_status") != "promoted" else "cluster_promotion_gap"
        review_status = "review_required" if workload_class == "governance_gap" else "promoted"
        item_id = f"review:hotspot_pack:{pack_id}"
        rows.extend(
            build_dense_hotspot_rows(
                pack=pack,
                item_id=item_id,
                workload_class=workload_class,
                review_status=review_status,
                recommended_next_action=_next_action_for_workload(workload_class),
                source_path=_relative(HOTSPOT_MANIFEST_PATH),
            )
        )

    for case_id, path in DISJOINTNESS_CASE_PATHS.items():
        payload = load_json_object(path)
        label_map = payload.get("metadata", {}).get("label_map", {})
        review_item_id = f"review:disjointness_case:{case_id}"
        workload_class = "baseline_confirmation"
        review_status = "baseline"
        if "contradiction" in case_id:
            workload_class = "structural_contradiction"
            review_status = "review_required"
        for window in payload.get("windows", []):
            for index, bundle in enumerate(window.get("statement_bundles", []), start=1):
                subject = str(bundle.get("subject") or "")
                value = str(bundle.get("value") or "")
                text = (
                    f"{_label_for(label_map, subject)} ({subject}) {bundle.get('property')} "
                    f"{_label_for(label_map, value)} ({value})"
                )
                rows.append(
                    build_dense_disjointness_row(
                        case_id=case_id,
                        review_item_id=review_item_id,
                        workload_class=workload_class,
                        review_status=review_status,
                        recommended_next_action=_next_action_for_workload(workload_class),
                        source_path=_relative(path),
                        index=index,
                        text=text,
                        subject=subject,
                        value=value,
                        property_pid=str(bundle.get("property") or ""),
                        qualifier_keys=sorted((bundle.get("qualifiers") or {}).keys()),
                    )
                )
    return rows


def _make_candidate_structural_cues(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for row in source_rows:
        payload = row.get("cue_payload") or {}
        if row["source_kind"] == "qualifier_statement_bundle":
            cues.append(
                {
                    "cue_id": f"{row['source_row_id']}:subject",
                    "source_row_id": row["source_row_id"],
                    "review_item_id": row["review_item_id"],
                    "cue_kind": "subject_qid",
                    "cue_value": payload["subject"],
                }
            )
            for key in payload.get("qualifier_keys", []):
                cues.append(
                    {
                        "cue_id": f"{row['source_row_id']}:qualifier:{key}",
                        "source_row_id": row["source_row_id"],
                        "review_item_id": row["review_item_id"],
                        "cue_kind": "qualifier_property",
                        "cue_value": key,
                    }
            )
        elif row["source_kind"] == "qualifier_drift_summary":
            cues.extend(build_dense_qualifier_drift_cues(row))
        elif row["source_kind"] in {"hotspot_pack_summary", "hotspot_focus_qid", "hotspot_cluster_family"}:
            cues.extend(build_dense_hotspot_cues(row))
        elif row["source_kind"] == "disjointness_statement_bundle":
            cues.extend(build_dense_disjointness_cues(row))
    return cues


def build_dense_review_artifact(output_dir: Path) -> dict[str, Any]:
    checked_slice = _build_slice()
    review_item_rows = _make_review_items(checked_slice)
    source_review_rows = _build_source_review_rows()
    candidate_structural_cues = _make_candidate_structural_cues(source_review_rows)
    related_review_clusters = _make_clusters(
        review_item_rows, source_review_rows, candidate_structural_cues
    )
    provisional_review_rows = _make_provisional_rows(
        review_item_rows, source_review_rows, candidate_structural_cues
    )
    provisional_review_bundles = _make_bundles(provisional_review_rows, source_review_rows)

    workload_counts = Counter(row["workload_class"] for row in source_review_rows)
    review_required_source_ids = {
        row["source_row_id"]
        for row in source_review_rows
        if row["review_status"] == "review_required"
    }
    payload = {
        "version": ARTIFACT_VERSION,
        "source_handoff_version": checked_slice["version"],
        "review_item_rows": review_item_rows,
        "source_review_rows": source_review_rows,
        "related_review_clusters": related_review_clusters,
        "candidate_structural_cues": candidate_structural_cues,
        "provisional_review_rows": provisional_review_rows,
        "provisional_review_bundles": provisional_review_bundles,
        "summary": {
            "review_item_count": len(review_item_rows),
            "source_review_row_count": len(source_review_rows),
            "review_required_item_count": sum(
                1 for row in review_item_rows if row["review_status"] == "review_required"
            ),
            "related_review_cluster_count": len(related_review_clusters),
            "candidate_structural_cue_count": len(candidate_structural_cues),
            "provisional_review_row_count": len(provisional_review_rows),
            "provisional_review_bundle_count": len(provisional_review_bundles),
            "baseline_confirmation_count": workload_counts.get("baseline_confirmation", 0),
            "cluster_promotion_gap_count": workload_counts.get("cluster_promotion_gap", 0),
            "governance_gap_count": workload_counts.get("governance_gap", 0),
            "qualifier_drift_gap_count": workload_counts.get("qualifier_drift_gap", 0),
            "structural_contradiction_count": workload_counts.get(
                "structural_contradiction", 0
            ),
        },
    }
    payload["normalized_metrics_v1"] = compute_normalized_metrics_from_profile(
        profile=get_normalized_profile("wikidata"),
        artifact_id="wikidata_dense_structural_review_v1",
        lane_family="wikidata",
        lane_variant="dense",
        review_item_rows=review_item_rows,
        source_review_rows=source_review_rows,
        candidate_signal_count=sum(
            1
            for cue in candidate_structural_cues
            if cue["source_row_id"] in review_required_source_ids
        ),
        provisional_queue_row_count=len(provisional_review_rows),
        provisional_bundle_count=len(provisional_review_bundles),
    )

    return write_json_markdown_artifact(
        output_dir=output_dir,
        artifact_version=ARTIFACT_VERSION,
        payload=payload,
        summary_text=build_summary_markdown(payload),
    )


def build_summary_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Wikidata Dense Structural Review Summary",
        "",
        f"- Review items: {summary['review_item_count']}",
        f"- Source review rows: {summary['source_review_row_count']}",
        f"- Review-required items: {summary['review_required_item_count']}",
        f"- Related review clusters: {summary['related_review_cluster_count']}",
        f"- Candidate structural cues: {summary['candidate_structural_cue_count']}",
        f"- Provisional review rows: {summary['provisional_review_row_count']}",
        f"- Provisional review bundles: {summary['provisional_review_bundle_count']}",
        "",
        "## Workload Classes",
        "",
        f"- baseline_confirmation: {summary['baseline_confirmation_count']}",
        f"- cluster_promotion_gap: {summary['cluster_promotion_gap_count']}",
        f"- governance_gap: {summary['governance_gap_count']}",
        f"- qualifier_drift_gap: {summary['qualifier_drift_gap_count']}",
        f"- structural_contradiction: {summary['structural_contradiction_count']}",
    ]
    normalized_metrics = payload.get("normalized_metrics_v1", {})
    if isinstance(normalized_metrics, dict) and normalized_metrics:
        lines.extend(["", *render_normalized_metrics_markdown(normalized_metrics)])
    lines.extend(["", "## Top Provisional Review Bundles", ""])
    for bundle in payload["provisional_review_bundles"][:5]:
        lines.append(
            f"- #{bundle['bundle_rank']} {bundle['review_item_id']} with {bundle['anchor_count']} cues, "
            f"top score {bundle['top_priority_score']}."
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the dense Wikidata structural review artifact.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to write the dense review artifact into.",
    )
    args = parser.parse_args()
    print(json.dumps(build_dense_review_artifact(Path(args.output_dir).resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
