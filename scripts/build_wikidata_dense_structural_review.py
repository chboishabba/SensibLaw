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
    _make_bundles,
    _make_clusters,
    _make_provisional_rows,
    _make_review_items,
)


ARTIFACT_VERSION = "wikidata_dense_structural_review_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def _label_for(label_map: dict[str, Any], qid: str | None) -> str:
    if not qid:
        return "unknown"
    return str(label_map.get(qid) or qid)


def _build_source_review_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    checked_slice = _build_slice()
    baseline_payload = _load_json(QUALIFIER_BASELINE_PATH)
    drift_projection = _load_json(QUALIFIER_DRIFT_PROJECTION_PATH)
    hotspot_manifest = _load_json(HOTSPOT_MANIFEST_PATH)
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
                    "recommended_next_action": "retain as checked baseline",
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
            {
                "source_row_id": f"source:dense:qualifier_drift:{drift_row['slot_id']}",
                "review_item_id": drift_item_id,
                "source_kind": "qualifier_drift_summary",
                "workload_class": "qualifier_drift_gap",
                "review_status": "review_required",
                "recommended_next_action": "inspect qualifier signature drift across revision windows",
                "source_path": _relative(QUALIFIER_DRIFT_PROJECTION_PATH),
                "text": (
                    f"{drift_row['slot_id']} drift from {drift_row['from_window']} to "
                    f"{drift_row['to_window']} at severity={drift_row['severity']}."
                ),
                "cue_payload": {
                    "qualifier_signatures_t1": drift_row.get("qualifier_signatures_t1", []),
                    "qualifier_signatures_t2": drift_row.get("qualifier_signatures_t2", []),
                    "qualifier_property_set_t1": drift_row.get("qualifier_property_set_t1", []),
                    "qualifier_property_set_t2": drift_row.get("qualifier_property_set_t2", []),
                },
            }
        )

    for pack in hotspot_manifest.get("entries", []):
        pack_id = pack.get("pack_id")
        if pack_id not in checked_slice["hotspot_governance"]["selected_pack_ids"]:
            continue
        workload_class = "governance_gap" if pack.get("promotion_status") != "promoted" else "cluster_promotion_gap"
        review_status = "review_required" if workload_class == "governance_gap" else "promoted"
        item_id = f"review:hotspot_pack:{pack_id}"
        rows.append(
            {
                "source_row_id": f"source:dense:hotspot_pack:{pack_id}",
                "review_item_id": item_id,
                "source_kind": "hotspot_pack_summary",
                "workload_class": workload_class,
                "review_status": review_status,
                "recommended_next_action": (
                    "promote held hotspot pack through manifest governance"
                    if workload_class == "governance_gap"
                    else "preserve as promoted structural exemplar"
                ),
                "source_path": _relative(HOTSPOT_MANIFEST_PATH),
                "text": f"{pack_id} focuses on {','.join(pack.get('focus_qids', []))}.",
                "cue_payload": {
                    "hold_reason": pack.get("hold_reason") or pack.get("status"),
                    "focus_qids": pack.get("focus_qids", []),
                    "candidate_cluster_families": pack.get("candidate_cluster_families", []),
                    "source_artifacts": pack.get("source_artifacts", []),
                },
            }
        )
        for index, qid in enumerate(pack.get("focus_qids", []), start=1):
            rows.append(
                {
                    "source_row_id": f"source:dense:hotspot_focus:{pack_id}:{index}",
                    "review_item_id": item_id,
                    "source_kind": "hotspot_focus_qid",
                    "workload_class": workload_class,
                    "review_status": review_status,
                    "recommended_next_action": (
                        "promote held hotspot pack through manifest governance"
                        if workload_class == "governance_gap"
                        else "preserve as promoted structural exemplar"
                    ),
                    "source_path": _relative(HOTSPOT_MANIFEST_PATH),
                    "text": f"Focus QID {qid}",
                    "cue_payload": {"focus_qid": qid},
                }
            )
        for index, family in enumerate(pack.get("candidate_cluster_families", []), start=1):
            rows.append(
                {
                    "source_row_id": f"source:dense:hotspot_cluster_family:{pack_id}:{index}",
                    "review_item_id": item_id,
                    "source_kind": "hotspot_cluster_family",
                    "workload_class": workload_class,
                    "review_status": review_status,
                    "recommended_next_action": (
                        "promote held hotspot pack through manifest governance"
                        if workload_class == "governance_gap"
                        else "preserve as promoted structural exemplar"
                    ),
                    "source_path": _relative(HOTSPOT_MANIFEST_PATH),
                    "text": family,
                    "cue_payload": {"cluster_family": family},
                }
            )

    for case_id, path in DISJOINTNESS_CASE_PATHS.items():
        payload = _load_json(path)
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
                    {
                        "source_row_id": f"source:dense:disjointness:{case_id}:{index}",
                        "review_item_id": review_item_id,
                        "source_kind": "disjointness_statement_bundle",
                        "workload_class": workload_class,
                        "review_status": review_status,
                        "recommended_next_action": (
                            "review contradiction culprits and preserve disjointness evidence"
                            if workload_class == "structural_contradiction"
                            else "retain as checked baseline"
                        ),
                        "source_path": _relative(path),
                        "text": text,
                        "cue_payload": {
                            "subject": subject,
                            "value": value,
                            "property": bundle.get("property"),
                            "qualifier_keys": sorted((bundle.get("qualifiers") or {}).keys()),
                        },
                    }
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
            for signature in payload.get("qualifier_signatures_t2", []):
                cues.append(
                    {
                        "cue_id": f"{row['source_row_id']}:signature:{len(cues)+1}",
                        "source_row_id": row["source_row_id"],
                        "review_item_id": row["review_item_id"],
                        "cue_kind": "qualifier_signature_delta",
                        "cue_value": signature,
                    }
                )
        elif row["source_kind"] == "hotspot_pack_summary":
            for qid in payload.get("focus_qids", []):
                cues.append(
                    {
                        "cue_id": f"{row['source_row_id']}:focus_qid:{qid}",
                        "source_row_id": row["source_row_id"],
                        "review_item_id": row["review_item_id"],
                        "cue_kind": "focus_qid",
                        "cue_value": qid,
                    }
                )
            for family in payload.get("candidate_cluster_families", []):
                cues.append(
                    {
                        "cue_id": f"{row['source_row_id']}:cluster_family:{family}",
                        "source_row_id": row["source_row_id"],
                        "review_item_id": row["review_item_id"],
                        "cue_kind": "cluster_family",
                        "cue_value": family,
                    }
                )
        elif row["source_kind"] in {"hotspot_focus_qid", "hotspot_cluster_family"}:
            cue_key = "focus_qid" if "focus_qid" in payload else "cluster_family"
            cues.append(
                {
                    "cue_id": f"{row['source_row_id']}:{cue_key}",
                    "source_row_id": row["source_row_id"],
                    "review_item_id": row["review_item_id"],
                    "cue_kind": cue_key,
                    "cue_value": payload[cue_key],
                }
            )
        elif row["source_kind"] == "disjointness_statement_bundle":
            cues.append(
                {
                    "cue_id": f"{row['source_row_id']}:property",
                    "source_row_id": row["source_row_id"],
                    "review_item_id": row["review_item_id"],
                    "cue_kind": "property_pid",
                    "cue_value": payload["property"],
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

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    return {"artifact_path": str(artifact_path), "summary_path": str(summary_path)}


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
        "",
        "## Top Provisional Review Bundles",
        "",
    ]
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
