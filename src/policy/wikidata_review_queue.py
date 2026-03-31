"""Shared Wikidata structural review queue helpers."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def workload_weight(workload_class: str) -> int:
    return {
        "structural_contradiction": 90,
        "governance_gap": 78,
        "qualifier_drift_gap": 72,
        "cluster_promotion_gap": 60,
        "baseline_confirmation": 25,
    }.get(workload_class, 10)


def next_action_for_workload(workload_class: str) -> str:
    return {
        "baseline_confirmation": "retain as checked baseline",
        "cluster_promotion_gap": "preserve as promoted structural exemplar",
        "governance_gap": "promote held hotspot pack through manifest governance",
        "qualifier_drift_gap": "inspect qualifier signature drift across revision windows",
        "structural_contradiction": "review contradiction culprits and preserve disjointness evidence",
    }.get(workload_class, "review structural evidence")


def candidate_cue_priority(cue_kind: str) -> int:
    return {
        "violation_counts": 18,
        "pair_label": 14,
        "hold_reason": 13,
        "qualifier_signature_delta": 12,
        "sample_question": 10,
        "qualifier_property_set": 8,
        "source_artifact": 5,
        "property_pid": 4,
    }.get(cue_kind, 2)


def make_provisional_rows(
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
        priority_score = workload_weight(source_row["workload_class"]) + candidate_cue_priority(cue["cue_kind"])
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


def make_bundles(
    provisional_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
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


__all__ = [
    "candidate_cue_priority",
    "make_bundles",
    "make_provisional_rows",
    "next_action_for_workload",
    "workload_weight",
]
