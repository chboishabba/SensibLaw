#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = REPO_ROOT / "SensibLaw"
if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))

from scripts.build_wikidata_structural_handoff import _build_slice


ARTIFACT_VERSION = "wikidata_structural_review_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION


def _workload_weight(workload_class: str) -> int:
    return {
        "structural_contradiction": 90,
        "governance_gap": 78,
        "qualifier_drift_gap": 72,
        "cluster_promotion_gap": 60,
        "baseline_confirmation": 25,
    }.get(workload_class, 10)


def _status_for_workload(workload_class: str) -> str:
    if workload_class == "baseline_confirmation":
        return "baseline"
    if workload_class == "cluster_promotion_gap":
        return "promoted"
    return "review_required"


def _next_action_for_workload(workload_class: str) -> str:
    return {
        "baseline_confirmation": "retain as checked baseline",
        "cluster_promotion_gap": "preserve as promoted structural exemplar",
        "governance_gap": "promote held hotspot pack through manifest governance",
        "qualifier_drift_gap": "inspect qualifier signature drift across revision windows",
        "structural_contradiction": "review contradiction culprits and preserve disjointness evidence",
    }.get(workload_class, "review structural evidence")


def _candidate_cue_priority(cue_kind: str) -> int:
    return {
        "violation_counts": 18,
        "pair_label": 14,
        "hold_reason": 13,
        "sample_question": 10,
        "qualifier_signature_delta": 12,
        "qualifier_property_set": 8,
        "source_artifact": 5,
        "property_pid": 4,
    }.get(cue_kind, 2)


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
        {
            "source_row_id": f"source:qualifier_drift:{drift['slot_id']}",
            "review_item_id": f"review:qualifier_drift:{drift['slot_id']}",
            "source_kind": "qualifier_drift_projection",
            "workload_class": "qualifier_drift_gap",
            "review_status": "review_required",
            "recommended_next_action": _next_action_for_workload("qualifier_drift_gap"),
            "source_path": drift["projection_path"],
            "text": (
                f"Qualifier drift for {drift['slot_id']} at severity={drift['severity']} "
                f"from {drift['from_window']} to {drift['to_window']}."
            ),
            "cue_payload": {
                "qualifier_signatures_t1": drift["qualifier_signatures_t1"],
                "qualifier_signatures_t2": drift["qualifier_signatures_t2"],
                "qualifier_property_set_t1": drift["qualifier_property_set_t1"],
                "qualifier_property_set_t2": drift["qualifier_property_set_t2"],
            },
        }
    )

    for pack in slice_payload["hotspot_governance"]["packs"]:
        workload_class = (
            "governance_gap" if pack.get("hold_reason") else "cluster_promotion_gap"
        )
        review_status = _status_for_workload(workload_class)
        rows.append(
            {
                "source_row_id": f"source:hotspot_pack:{pack['pack_id']}",
                "review_item_id": f"review:hotspot_pack:{pack['pack_id']}",
                "source_kind": "hotspot_pack_summary",
                "workload_class": workload_class,
                "review_status": review_status,
                "recommended_next_action": _next_action_for_workload(workload_class),
                "source_path": pack["source_artifacts"][0] if pack.get("source_artifacts") else None,
                "text": (
                    f"{pack['pack_id']} ({pack['hotspot_family']}) has {pack['cluster_count']} clusters "
                    f"and promotion_status={pack['promotion_status']}."
                ),
                "cue_payload": {
                    "hold_reason": pack.get("hold_reason"),
                    "source_artifacts": pack.get("source_artifacts", []),
                },
            }
        )
        for index, question in enumerate(pack.get("sample_questions", []), start=1):
            rows.append(
                {
                    "source_row_id": f"source:hotspot_pack_question:{pack['pack_id']}:{index}",
                    "review_item_id": f"review:hotspot_pack:{pack['pack_id']}",
                    "source_kind": "hotspot_sample_question",
                    "workload_class": workload_class,
                    "review_status": review_status,
                    "recommended_next_action": _next_action_for_workload(workload_class),
                    "source_path": pack["source_artifacts"][0] if pack.get("source_artifacts") else None,
                    "text": question,
                    "cue_payload": {"question_index": index},
                }
            )

    for case in slice_payload["disjointness_cases"]:
        workload_class = (
            "baseline_confirmation"
            if case["case_status"] == "baseline"
            else "structural_contradiction"
        )
        review_status = _status_for_workload(workload_class)
        for index, pair_label in enumerate(case["pair_labels"], start=1):
            rows.append(
                {
                    "source_row_id": f"source:disjointness_case:{case['case_id']}:{index}",
                    "review_item_id": f"review:disjointness_case:{case['case_id']}",
                    "source_kind": "disjointness_pair",
                    "workload_class": workload_class,
                    "review_status": review_status,
                    "recommended_next_action": _next_action_for_workload(workload_class),
                    "source_path": case["source_path"],
                    "text": pair_label,
                    "cue_payload": {
                        "pair_label": pair_label,
                        "subclass_violation_count": case["subclass_violation_count"],
                        "instance_violation_count": case["instance_violation_count"],
                    },
                }
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
            for signature in cue_payload.get("qualifier_signatures_t2", []):
                cues.append(
                    {
                        "cue_id": f"{row['source_row_id']}:signature:{len(cues)+1}",
                        "source_row_id": row["source_row_id"],
                        "review_item_id": row["review_item_id"],
                        "cue_kind": "qualifier_signature_delta",
                        "cue_value": signature,
                    }
                )
            cues.append(
                {
                    "cue_id": f"{row['source_row_id']}:property_set",
                    "source_row_id": row["source_row_id"],
                    "review_item_id": row["review_item_id"],
                    "cue_kind": "qualifier_property_set",
                    "cue_value": " -> ".join(
                        [
                            ",".join(cue_payload.get("qualifier_property_set_t1", [])) or "none",
                            ",".join(cue_payload.get("qualifier_property_set_t2", [])) or "none",
                        ]
                    ),
                }
            )
        elif row["source_kind"] == "hotspot_pack_summary":
            hold_reason = cue_payload.get("hold_reason")
            if hold_reason:
                cues.append(
                    {
                        "cue_id": f"{row['source_row_id']}:hold_reason",
                        "source_row_id": row["source_row_id"],
                        "review_item_id": row["review_item_id"],
                        "cue_kind": "hold_reason",
                        "cue_value": hold_reason,
                    }
                )
            for artifact in cue_payload.get("source_artifacts", []):
                cues.append(
                    {
                        "cue_id": f"{row['source_row_id']}:source_artifact:{len(cues)+1}",
                        "source_row_id": row["source_row_id"],
                        "review_item_id": row["review_item_id"],
                        "cue_kind": "source_artifact",
                        "cue_value": artifact,
                    }
                )
        elif row["source_kind"] == "hotspot_sample_question":
            cues.append(
                {
                    "cue_id": f"{row['source_row_id']}:sample_question",
                    "source_row_id": row["source_row_id"],
                    "review_item_id": row["review_item_id"],
                    "cue_kind": "sample_question",
                    "cue_value": row["text"],
                }
            )
        elif row["source_kind"] == "disjointness_pair":
            cues.append(
                {
                    "cue_id": f"{row['source_row_id']}:pair",
                    "source_row_id": row["source_row_id"],
                    "review_item_id": row["review_item_id"],
                    "cue_kind": "pair_label",
                    "cue_value": cue_payload["pair_label"],
                }
            )
            cues.append(
                {
                    "cue_id": f"{row['source_row_id']}:violations",
                    "source_row_id": row["source_row_id"],
                    "review_item_id": row["review_item_id"],
                    "cue_kind": "violation_counts",
                    "cue_value": (
                        f"subclass={cue_payload['subclass_violation_count']}, "
                        f"instance={cue_payload['instance_violation_count']}"
                    ),
                }
            )
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
    item_by_id = {row["review_item_id"]: row for row in review_items}
    source_by_id = {row["source_row_id"]: row for row in source_rows}
    rows: list[dict[str, Any]] = []
    for cue in candidate_cues:
        source_row = source_by_id[cue["source_row_id"]]
        review_item = item_by_id[cue["review_item_id"]]
        priority_score = _workload_weight(source_row["workload_class"]) + _candidate_cue_priority(
            cue["cue_kind"]
        )
        rows.append(
            {
                "provisional_review_id": f"prov:{cue['cue_id']}",
                "review_item_id": cue["review_item_id"],
                "source_row_id": cue["source_row_id"],
                "cue_id": cue["cue_id"],
                "cue_kind": cue["cue_kind"],
                "cue_value": cue["cue_value"],
                "workload_class": source_row["workload_class"],
                "recommended_next_action": review_item["recommended_next_action"],
                "priority_score": priority_score,
                "dedupe_key": f"{cue['review_item_id']}|{cue['cue_kind']}|{cue['cue_value']}",
            }
        )
    rows.sort(
        key=lambda row: (
            -row["priority_score"],
            row["review_item_id"],
            row["source_row_id"],
            row["cue_kind"],
            row["cue_value"],
        )
    )
    for index, row in enumerate(rows, start=1):
        row["priority_rank"] = index
    return rows


def _make_bundles(
    provisional_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    source_by_id = {row["source_row_id"]: row for row in source_rows}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in provisional_rows:
        grouped[row["review_item_id"]].append(row)

    bundles: list[dict[str, Any]] = []
    for review_item_id, rows in grouped.items():
        source_row_ids = sorted({row["source_row_id"] for row in rows})
        texts = [source_by_id[source_row_id]["text"] for source_row_id in source_row_ids]
        bundles.append(
            {
                "bundle_id": f"bundle:{review_item_id}",
                "review_item_id": review_item_id,
                "source_row_ids": source_row_ids,
                "source_texts": texts,
                "anchor_count": len(rows),
                "top_priority_score": max(row["priority_score"] for row in rows),
                "recommended_next_action": rows[0]["recommended_next_action"],
            }
        )
    bundles.sort(key=lambda row: (-row["top_priority_score"], -row["anchor_count"], row["bundle_id"]))
    for index, row in enumerate(bundles, start=1):
        row["bundle_rank"] = index
    return bundles


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

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    return {"artifact_path": str(artifact_path), "summary_path": str(summary_path)}


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
        "",
        "## Related Review Clusters",
        "",
    ]
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
