#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.storage.repo_roots import repo_root, sensiblaw_root

REPO_ROOT = repo_root()
SENSIBLAW_ROOT = sensiblaw_root()
if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))

from scripts.build_wikidata_structural_handoff import _build_slice
from scripts.review_geometry_profiles import get_normalized_profile
from scripts.review_geometry_normalization import (
    compute_normalized_metrics_from_profile,
    render_normalized_metrics_markdown,
)
from src.policy.wikidata_structural_geometry import (
    build_checked_disjointness_cues,
    build_checked_disjointness_rows,
    build_checked_hotspot_cues,
    build_checked_hotspot_rows,
    build_checked_qualifier_drift_cues,
    build_checked_qualifier_drift_row,
)
from src.policy.wikidata_structural_io import write_json_markdown_artifact
try:
    from src.policy.wikidata_review_queue import (
        make_bundles as _make_bundles_impl,
        make_provisional_rows as _make_provisional_rows_impl,
        next_action_for_workload as _next_action_for_workload_impl,
    )
except ModuleNotFoundError:
    from policy.wikidata_review_queue import (
        make_bundles as _make_bundles_impl,
        make_provisional_rows as _make_provisional_rows_impl,
        next_action_for_workload as _next_action_for_workload_impl,
    )


ARTIFACT_VERSION = "wikidata_structural_review_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION


def _status_for_workload(workload_class: str) -> str:
    if workload_class == "baseline_confirmation":
        return "baseline"
    if workload_class == "cluster_promotion_gap":
        return "promoted"
    return "review_required"


def _next_action_for_workload(workload_class: str) -> str:
    return _next_action_for_workload_impl(workload_class)


def _make_review_items(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    qualifier_core = slice_payload["qualifier_core"]
    baseline = qualifier_core["baseline"]
    drift = qualifier_core["drift_case"]

    items.append(
        {
            "review_item_id": "review:qualifier_baseline",
            "review_kind": "qualifier_baseline",
            "title": "Qualifier-bearing import baseline",
            "review_status": "baseline",
            "workload_class": "baseline_confirmation",
            "recommended_next_action": _next_action_for_workload("baseline_confirmation"),
            "source_paths": [baseline["source_path"]],
            "evidence_summary": (
                f"{baseline['statement_count']} statements across {baseline['window_count']} windows "
                f"for {', '.join(baseline['property_pids'])}"
            ),
        }
    )
    items.append(
        {
            "review_item_id": f"review:qualifier_drift:{drift['slot_id']}",
            "review_kind": "qualifier_drift_case",
            "title": f"Qualifier drift case {drift['slot_id']}",
            "review_status": "review_required",
            "workload_class": "qualifier_drift_gap",
            "recommended_next_action": _next_action_for_workload("qualifier_drift_gap"),
            "source_paths": [drift["source_slice_path"], drift["projection_path"]],
            "evidence_summary": (
                f"severity={drift['severity']} from {drift['from_window']} to {drift['to_window']}"
            ),
        }
    )

    for pack in slice_payload["hotspot_governance"]["packs"]:
        workload_class = (
            "governance_gap" if pack.get("hold_reason") else "cluster_promotion_gap"
        )
        items.append(
            {
                "review_item_id": f"review:hotspot_pack:{pack['pack_id']}",
                "review_kind": "hotspot_pack",
                "title": f"Hotspot pack {pack['pack_id']}",
                "review_status": _status_for_workload(workload_class),
                "workload_class": workload_class,
                "recommended_next_action": _next_action_for_workload(workload_class),
                "source_paths": list(pack.get("source_artifacts", [])),
                "evidence_summary": (
                    f"{pack['hotspot_family']} with {pack['cluster_count']} generated clusters"
                ),
            }
        )

    for case in slice_payload["disjointness_cases"]:
        workload_class = (
            "baseline_confirmation"
            if case["case_status"] == "baseline"
            else "structural_contradiction"
        )
        items.append(
            {
                "review_item_id": f"review:disjointness_case:{case['case_id']}",
                "review_kind": "disjointness_case",
                "title": f"Disjointness case {case['case_id']}",
                "review_status": _status_for_workload(workload_class),
                "workload_class": workload_class,
                "recommended_next_action": _next_action_for_workload(workload_class),
                "source_paths": [case["source_path"]],
                "evidence_summary": ", ".join(case["pair_labels"]),
            }
        )
    return items


def _make_source_rows(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    qualifier_core = slice_payload["qualifier_core"]
    baseline = qualifier_core["baseline"]
    drift = qualifier_core["drift_case"]

    for pid in baseline["property_pids"]:
        rows.append(
            {
                "source_row_id": f"source:qualifier_baseline:{pid}",
                "review_item_id": "review:qualifier_baseline",
                "source_kind": "qualifier_baseline_property",
                "workload_class": "baseline_confirmation",
                "review_status": "baseline",
                "recommended_next_action": _next_action_for_workload("baseline_confirmation"),
                "source_path": baseline["source_path"],
                "text": f"Property {pid} preserved across importer baseline windows.",
                "cue_payload": {
                    "property_pid": pid,
                    "statement_count": baseline["statement_count"],
                    "window_count": baseline["window_count"],
                },
            }
        )

    rows.append(
        build_checked_qualifier_drift_row(
            drift=drift,
            recommended_next_action=_next_action_for_workload("qualifier_drift_gap"),
        )
    )

    for pack in slice_payload["hotspot_governance"]["packs"]:
        workload_class = (
            "governance_gap" if pack.get("hold_reason") else "cluster_promotion_gap"
        )
        review_status = _status_for_workload(workload_class)
        rows.extend(
            build_checked_hotspot_rows(
                pack=pack,
                workload_class=workload_class,
                review_status=review_status,
                recommended_next_action=_next_action_for_workload(workload_class),
            )
        )

    for case in slice_payload["disjointness_cases"]:
        workload_class = (
            "baseline_confirmation"
            if case["case_status"] == "baseline"
            else "structural_contradiction"
        )
        review_status = _status_for_workload(workload_class)
        rows.extend(
            build_checked_disjointness_rows(
                case=case,
                workload_class=workload_class,
                review_status=review_status,
                recommended_next_action=_next_action_for_workload(workload_class),
            )
        )
    return rows


def _make_candidate_cues(
    slice_payload: dict[str, Any], source_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for row in source_rows:
        cue_payload = row.get("cue_payload") or {}
        if row["source_kind"] == "qualifier_baseline_property":
            cues.append(
                {
                    "cue_id": f"{row['source_row_id']}:property",
                    "source_row_id": row["source_row_id"],
                    "review_item_id": row["review_item_id"],
                    "cue_kind": "property_pid",
                    "cue_value": cue_payload["property_pid"],
                }
            )
        elif row["source_kind"] == "qualifier_drift_projection":
            cues.extend(build_checked_qualifier_drift_cues(row))
        elif row["source_kind"] in {"hotspot_pack_summary", "hotspot_sample_question"}:
            cues.extend(build_checked_hotspot_cues(row))
        elif row["source_kind"] == "disjointness_pair":
            cues.extend(build_checked_disjointness_cues(row))
    return cues


def _make_clusters(
    review_items: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    candidate_cues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items_by_id = {row["review_item_id"]: row for row in review_items}
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_cues: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in source_rows:
        if row["review_status"] == "review_required":
            grouped_rows[row["review_item_id"]].append(row)
    for cue in candidate_cues:
        if cue["review_item_id"] in grouped_rows:
            grouped_cues[cue["review_item_id"]].append(cue)

    clusters: list[dict[str, Any]] = []
    for review_item_id, rows in grouped_rows.items():
        item = items_by_id[review_item_id]
        rollup = Counter(row["workload_class"] for row in rows)
        cue_kind_rollup = Counter(cue["cue_kind"] for cue in grouped_cues[review_item_id])
        clusters.append(
            {
                "cluster_id": f"cluster:{review_item_id}",
                "review_item_id": review_item_id,
                "title": item["title"],
                "review_row_count": len(rows),
                "workload_class_rollup": dict(sorted(rollup.items())),
                "dominant_workload_class": max(rollup, key=rollup.get),
                "recommended_next_action": item["recommended_next_action"],
                "candidate_cue_count": len(grouped_cues[review_item_id]),
                "candidate_cue_rollup": dict(sorted(cue_kind_rollup.items())),
                "source_row_ids": [row["source_row_id"] for row in rows],
            }
        )
    clusters.sort(key=lambda row: (-row["review_row_count"], row["cluster_id"]))
    return clusters


def _make_provisional_rows(
    review_items: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    candidate_cues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _make_provisional_rows_impl(review_items, source_rows, candidate_cues)


def _make_bundles(
    provisional_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return _make_bundles_impl(provisional_rows, source_rows)


def build_review_artifact(output_dir: Path) -> dict[str, Any]:
    slice_payload = _build_slice()
    review_item_rows = _make_review_items(slice_payload)
    source_review_rows = _make_source_rows(slice_payload)
    candidate_structural_cues = _make_candidate_cues(slice_payload, source_review_rows)
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
        "source_handoff_version": slice_payload["version"],
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
        artifact_id="wikidata_checked_structural_review_v1",
        lane_family="wikidata",
        lane_variant="checked",
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
        "# Wikidata Structural Review Summary",
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
    lines.extend(["", "## Related Review Clusters", ""])
    for cluster in payload["related_review_clusters"]:
        rollup_text = ", ".join(
            f"{key} ({value})" for key, value in sorted(cluster["candidate_cue_rollup"].items())
        )
        lines.extend(
            [
                (
                    f"- {cluster['title']}: {cluster['review_row_count']} review rows, "
                    f"{cluster['dominant_workload_class']}, cues={rollup_text or 'none'}."
                ),
                f"  recommended action: {cluster['recommended_next_action']}",
            ]
        )
    lines.extend(["", "## Top Provisional Review Bundles", ""])
    for bundle in payload["provisional_review_bundles"][:5]:
        lines.append(
            f"- #{bundle['bundle_rank']} {bundle['review_item_id']} with {bundle['anchor_count']} cues, "
            f"top score {bundle['top_priority_score']}."
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the checked Wikidata structural review artifact.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to write the checked review artifact into.",
    )
    args = parser.parse_args()
    print(json.dumps(build_review_artifact(Path(args.output_dir).resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
