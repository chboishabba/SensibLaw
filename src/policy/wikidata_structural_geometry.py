from __future__ import annotations

from typing import Any


def build_checked_qualifier_drift_row(
    *,
    drift: dict[str, Any],
    recommended_next_action: str,
) -> dict[str, Any]:
    slot_id = str(drift["slot_id"])
    return {
        "source_row_id": f"source:qualifier_drift:{slot_id}",
        "review_item_id": f"review:qualifier_drift:{slot_id}",
        "source_kind": "qualifier_drift_projection",
        "workload_class": "qualifier_drift_gap",
        "review_status": "review_required",
        "recommended_next_action": recommended_next_action,
        "source_path": drift["projection_path"],
        "text": (
            f"Qualifier drift for {slot_id} at severity={drift['severity']} "
            f"from {drift['from_window']} to {drift['to_window']}."
        ),
        "cue_payload": {
            "qualifier_signatures_t1": drift["qualifier_signatures_t1"],
            "qualifier_signatures_t2": drift["qualifier_signatures_t2"],
            "qualifier_property_set_t1": drift["qualifier_property_set_t1"],
            "qualifier_property_set_t2": drift["qualifier_property_set_t2"],
        },
    }


def build_checked_qualifier_drift_cues(row: dict[str, Any]) -> list[dict[str, Any]]:
    cue_payload = row.get("cue_payload") or {}
    cues: list[dict[str, Any]] = []
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
    return cues


def build_dense_qualifier_drift_row(
    *,
    drift_row: dict[str, Any],
    review_item_id: str,
    source_path: str,
    recommended_next_action: str,
) -> dict[str, Any]:
    slot_id = str(drift_row["slot_id"])
    return {
        "source_row_id": f"source:dense:qualifier_drift:{slot_id}",
        "review_item_id": review_item_id,
        "source_kind": "qualifier_drift_summary",
        "workload_class": "qualifier_drift_gap",
        "review_status": "review_required",
        "recommended_next_action": recommended_next_action,
        "source_path": source_path,
        "text": (
            f"{slot_id} drift from {drift_row['from_window']} to "
            f"{drift_row['to_window']} at severity={drift_row['severity']}."
        ),
        "cue_payload": {
            "qualifier_signatures_t1": drift_row.get("qualifier_signatures_t1", []),
            "qualifier_signatures_t2": drift_row.get("qualifier_signatures_t2", []),
            "qualifier_property_set_t1": drift_row.get("qualifier_property_set_t1", []),
            "qualifier_property_set_t2": drift_row.get("qualifier_property_set_t2", []),
        },
    }


def build_dense_qualifier_drift_cues(row: dict[str, Any]) -> list[dict[str, Any]]:
    cue_payload = row.get("cue_payload") or {}
    cues: list[dict[str, Any]] = []
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
    return cues


def build_checked_hotspot_rows(
    *,
    pack: dict[str, Any],
    workload_class: str,
    review_status: str,
    recommended_next_action: str,
) -> list[dict[str, Any]]:
    pack_id = str(pack["pack_id"])
    source_path = pack["source_artifacts"][0] if pack.get("source_artifacts") else None
    rows = [
        {
            "source_row_id": f"source:hotspot_pack:{pack_id}",
            "review_item_id": f"review:hotspot_pack:{pack_id}",
            "source_kind": "hotspot_pack_summary",
            "workload_class": workload_class,
            "review_status": review_status,
            "recommended_next_action": recommended_next_action,
            "source_path": source_path,
            "text": (
                f"{pack_id} ({pack['hotspot_family']}) has {pack['cluster_count']} clusters "
                f"and promotion_status={pack['promotion_status']}."
            ),
            "cue_payload": {
                "hold_reason": pack.get("hold_reason"),
                "source_artifacts": pack.get("source_artifacts", []),
            },
        }
    ]
    for index, question in enumerate(pack.get("sample_questions", []), start=1):
        rows.append(
            {
                "source_row_id": f"source:hotspot_pack_question:{pack_id}:{index}",
                "review_item_id": f"review:hotspot_pack:{pack_id}",
                "source_kind": "hotspot_sample_question",
                "workload_class": workload_class,
                "review_status": review_status,
                "recommended_next_action": recommended_next_action,
                "source_path": source_path,
                "text": question,
                "cue_payload": {"question_index": index},
            }
        )
    return rows


def build_checked_hotspot_cues(row: dict[str, Any]) -> list[dict[str, Any]]:
    cue_payload = row.get("cue_payload") or {}
    if row["source_kind"] == "hotspot_pack_summary":
        cues: list[dict[str, Any]] = []
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
        return cues
    if row["source_kind"] == "hotspot_sample_question":
        return [
            {
                "cue_id": f"{row['source_row_id']}:sample_question",
                "source_row_id": row["source_row_id"],
                "review_item_id": row["review_item_id"],
                "cue_kind": "sample_question",
                "cue_value": row["text"],
            }
        ]
    return []


def build_dense_hotspot_rows(
    *,
    pack: dict[str, Any],
    item_id: str,
    workload_class: str,
    review_status: str,
    recommended_next_action: str,
    source_path: str,
) -> list[dict[str, Any]]:
    pack_id = str(pack["pack_id"])
    rows = [
        {
            "source_row_id": f"source:dense:hotspot_pack:{pack_id}",
            "review_item_id": item_id,
            "source_kind": "hotspot_pack_summary",
            "workload_class": workload_class,
            "review_status": review_status,
            "recommended_next_action": recommended_next_action,
            "source_path": source_path,
            "text": f"{pack_id} focuses on {','.join(pack.get('focus_qids', []))}.",
            "cue_payload": {
                "hold_reason": pack.get("hold_reason") or pack.get("status"),
                "focus_qids": pack.get("focus_qids", []),
                "candidate_cluster_families": pack.get("candidate_cluster_families", []),
                "source_artifacts": pack.get("source_artifacts", []),
            },
        }
    ]
    for index, qid in enumerate(pack.get("focus_qids", []), start=1):
        rows.append(
            {
                "source_row_id": f"source:dense:hotspot_focus:{pack_id}:{index}",
                "review_item_id": item_id,
                "source_kind": "hotspot_focus_qid",
                "workload_class": workload_class,
                "review_status": review_status,
                "recommended_next_action": recommended_next_action,
                "source_path": source_path,
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
                "recommended_next_action": recommended_next_action,
                "source_path": source_path,
                "text": family,
                "cue_payload": {"cluster_family": family},
            }
        )
    return rows


def build_dense_hotspot_cues(row: dict[str, Any]) -> list[dict[str, Any]]:
    payload = row.get("cue_payload") or {}
    if row["source_kind"] == "hotspot_pack_summary":
        cues: list[dict[str, Any]] = []
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
        return cues
    if row["source_kind"] in {"hotspot_focus_qid", "hotspot_cluster_family"}:
        cue_key = "focus_qid" if "focus_qid" in payload else "cluster_family"
        return [
            {
                "cue_id": f"{row['source_row_id']}:{cue_key}",
                "source_row_id": row["source_row_id"],
                "review_item_id": row["review_item_id"],
                "cue_kind": cue_key,
                "cue_value": payload[cue_key],
            }
        ]
    return []


def build_checked_disjointness_rows(
    *,
    case: dict[str, Any],
    workload_class: str,
    review_status: str,
    recommended_next_action: str,
) -> list[dict[str, Any]]:
    case_id = str(case["case_id"])
    rows: list[dict[str, Any]] = []
    for index, pair_label in enumerate(case["pair_labels"], start=1):
        rows.append(
            {
                "source_row_id": f"source:disjointness_case:{case_id}:{index}",
                "review_item_id": f"review:disjointness_case:{case_id}",
                "source_kind": "disjointness_pair",
                "workload_class": workload_class,
                "review_status": review_status,
                "recommended_next_action": recommended_next_action,
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


def build_checked_disjointness_cues(row: dict[str, Any]) -> list[dict[str, Any]]:
    cue_payload = row.get("cue_payload") or {}
    return [
        {
            "cue_id": f"{row['source_row_id']}:pair",
            "source_row_id": row["source_row_id"],
            "review_item_id": row["review_item_id"],
            "cue_kind": "pair_label",
            "cue_value": cue_payload["pair_label"],
        },
        {
            "cue_id": f"{row['source_row_id']}:violations",
            "source_row_id": row["source_row_id"],
            "review_item_id": row["review_item_id"],
            "cue_kind": "violation_counts",
            "cue_value": (
                f"subclass={cue_payload['subclass_violation_count']}, "
                f"instance={cue_payload['instance_violation_count']}"
            ),
        },
    ]


def build_dense_disjointness_row(
    *,
    case_id: str,
    review_item_id: str,
    workload_class: str,
    review_status: str,
    recommended_next_action: str,
    source_path: str,
    index: int,
    text: str,
    subject: str,
    value: str,
    property_pid: str,
    qualifier_keys: list[str],
) -> dict[str, Any]:
    return {
        "source_row_id": f"source:dense:disjointness:{case_id}:{index}",
        "review_item_id": review_item_id,
        "source_kind": "disjointness_statement_bundle",
        "workload_class": workload_class,
        "review_status": review_status,
        "recommended_next_action": recommended_next_action,
        "source_path": source_path,
        "text": text,
        "cue_payload": {
            "subject": subject,
            "value": value,
            "property": property_pid,
            "qualifier_keys": qualifier_keys,
        },
    }


def build_dense_disjointness_cues(row: dict[str, Any]) -> list[dict[str, Any]]:
    payload = row.get("cue_payload") or {}
    cues = [
        {
            "cue_id": f"{row['source_row_id']}:property",
            "source_row_id": row["source_row_id"],
            "review_item_id": row["review_item_id"],
            "cue_kind": "property_pid",
            "cue_value": payload["property"],
        }
    ]
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


__all__ = [
    "build_checked_disjointness_cues",
    "build_checked_disjointness_rows",
    "build_checked_hotspot_cues",
    "build_checked_hotspot_rows",
    "build_checked_qualifier_drift_cues",
    "build_checked_qualifier_drift_row",
    "build_dense_disjointness_cues",
    "build_dense_disjointness_row",
    "build_dense_hotspot_cues",
    "build_dense_hotspot_rows",
    "build_dense_qualifier_drift_cues",
    "build_dense_qualifier_drift_row",
]
