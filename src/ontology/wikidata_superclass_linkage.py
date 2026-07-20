from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from src.policy.linkage_adapters import (
    build_collection_adapter_fragment,
    build_projection_adapter_fragment,
    build_source_adapter_fragment,
    build_tranche_adapter_fragment,
    merge_linkage_fragments,
)
from src.policy.linkage_depth import (
    LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION,
    build_expected_layer_contract,
    build_linkage_depth_case,
    build_linkage_depth_receipt,
)
from src.policy.linkage_case_inputs import require_case_from_projection_artifact
from src.policy.world_model import (
    build_state_node,
    build_world_model as build_candidate_world_model,
)
from src.policy.world_model_profiles import build_profile
from src.policy.world_model_projections import (
    project_claim_table,
    project_linkage_case,
    project_report as project_world_model_report,
    project_review_surface,
)

WIKIDATA_Q43229_SUPERCLASS_PRESSURE_REPORT_SCHEMA_VERSION = (
    "sl.wikidata_q43229_superclass_pressure_report.v0_1"
)
WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID = (
    "wikidata_q43229_superclass_pressure_linkage"
)
Q43229_TARGET_QID = "Q43229"
Q43229_LANE_FAMILY = "nat"
Q43229_PROFILE_ID = "q43229_superclass_pressure"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    seen: list[str] = []
    for item in value:
        text = _text(item)
        if text and text not in seen:
            seen.append(text)
    return seen


def _row_key(row: Mapping[str, Any]) -> str:
    return _text(row.get("row_id")) or _text(row.get("queue_item_id")) or _text(row.get("packet_id"))


def _q43229_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if _text(row.get("instance_of_qid")) != Q43229_TARGET_QID:
            continue
        row_id = _row_key(row)
        if not row_id or row_id in seen:
            continue
        seen.add(row_id)
        filtered.append(dict(row))
    return filtered


def _q43229_rows_by_field(rows: Sequence[Mapping[str, Any]], *, key_field: str) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if _text(row.get("instance_of_qid")) != Q43229_TARGET_QID:
            continue
        row_key = _text(row.get(key_field)) or _row_key(row)
        if not row_key or row_key in seen:
            continue
        seen.add(row_key)
        filtered.append(dict(row))
    return filtered


def build_report(
    *,
    review_bucket: Mapping[str, Any],
    operator_packet: Mapping[str, Any],
    operator_queue: Mapping[str, Any],
    operator_report: Mapping[str, Any],
    batch_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return project_report(
        build_world_model(
            review_bucket=review_bucket,
            operator_packet=operator_packet,
            operator_queue=operator_queue,
            operator_report=operator_report,
            batch_report=batch_report,
        )
    )


def build_world_model(
    *,
    review_bucket: Mapping[str, Any],
    operator_packet: Mapping[str, Any],
    operator_queue: Mapping[str, Any],
    operator_report: Mapping[str, Any],
    batch_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    lane_id = _text(operator_packet.get("lane_id")) or _text(operator_report.get("lane_id"))
    packet_id = _text(operator_packet.get("packet_id"))
    report_id = _text(operator_report.get("report_id"))
    cohort_id = _text(operator_packet.get("cohort_id")) or _text(operator_report.get("cohort_id"))

    packet_rows = _q43229_rows(_mapping_rows(operator_packet.get("selected_rows")))
    bucket_rows = _q43229_rows(_mapping_rows(review_bucket.get("candidates")))
    queue_payload = (
        operator_queue.get("queue_items")
        if isinstance(operator_queue.get("queue_items"), Sequence)
        else operator_queue.get("queue", {}).get("queue_items")
        if isinstance(operator_queue.get("queue"), Mapping)
        else []
    )
    queue_rows = _q43229_rows_by_field(_mapping_rows(queue_payload), key_field="queue_item_id")
    report_rows = _q43229_rows_by_field(_mapping_rows(operator_report.get("examples")), key_field="queue_item_id")

    if not packet_rows:
        raise ValueError("Q43229 superclass-pressure report requires at least one packet row for Q43229")

    case_rows = []
    if isinstance(batch_report, Mapping):
        for row in _mapping_rows(batch_report.get("case_summaries")):
            if packet_id and _text(row.get("packet_id")) == packet_id:
                case_rows.append(dict(row))

    decision = _text(operator_packet.get("decision")) or _text(operator_report.get("report_status")) or "review"
    governance = (
        dict(operator_report.get("governance"))
        if isinstance(operator_report.get("governance"), Mapping)
        else dict(operator_packet.get("governance"))
        if isinstance(operator_packet.get("governance"), Mapping)
        else {}
    )
    summary = {
        "packet_row_count": len(packet_rows),
        "review_bucket_row_count": len(bucket_rows),
        "queue_row_count": len(queue_rows),
        "report_row_count": len(report_rows),
        "case_count": len(case_rows),
        "review_first": bool(operator_packet.get("summary", {}).get("review_first"))
        or bool(operator_report.get("summary", {}).get("review_first")),
        "variance_flag_counts": dict(operator_report.get("summary", {}).get("variance_flag_counts", {}))
        if isinstance(operator_report.get("summary"), Mapping)
        else dict(operator_packet.get("summary", {}).get("variance_flag_counts", {}))
        if isinstance(operator_packet.get("summary"), Mapping)
        else {},
        "priority_counts": dict(operator_report.get("summary", {}).get("priority_counts", {}))
        if isinstance(operator_report.get("summary"), Mapping)
        else {},
    }
    claims = [
        build_state_node(
            node_id=f"claim:{_row_key(row)}",
            node_kind="statement_edge_candidate",
            label=f"Superclass-pressure candidate {_row_key(row)}",
            status="candidate",
            source_anchor_ids=[f"wd_source_anchor:{_row_key(row)}"],
            authority_surface="wd_source_discussion",
            promotion_status="candidate_only",
            metadata={
                "row_id": _text(row.get("row_id")),
                "entity_qid": _text(row.get("entity_qid")),
                "instance_of_qid": _text(row.get("instance_of_qid")),
                "variance_flags": _string_list(row.get("variance_flags")),
                "reviewer_questions": _string_list(row.get("reviewer_questions")),
                "candidate_vs_promoted_visibility": True,
            },
        )
        for row in packet_rows
        if _row_key(row)
    ]
    authority_surfaces = [
        build_state_node(
            node_id=f"authority:{name}",
            node_kind="authority_surface",
            label=name.replace("_", " "),
            status="reviewed",
            authority_surface=name,
            promotion_status="review_only",
        )
        for name in (
            "wd_source_discussion",
            "wd_class_lattice_pressure_surface",
            "wd_community_review_surface",
            "workflow_tranche_anchor",
        )
    ]
    profile = build_profile(
        profile_id=Q43229_PROFILE_ID,
        lane_family=Q43229_LANE_FAMILY,
        source_kinds=[
            "wikidata_review_bucket",
            "wikidata_operator_packet",
            "wikidata_operator_queue",
            "wikidata_operator_report",
        ],
        authority_surfaces=[
            "wd_source_discussion",
            "wd_class_lattice_pressure_surface",
            "wd_community_review_surface",
            "workflow_tranche_anchor",
        ],
        external_bridges=["wikidata"],
        promotion_policy="review_only",
        default_projection_kinds=["report", "claim_table", "review_surface", "linkage_case"],
        metadata={"target_instance_of_qid": Q43229_TARGET_QID},
    )
    return build_candidate_world_model(
        model_id=packet_id or report_id or Q43229_PROFILE_ID,
        lane_family=Q43229_LANE_FAMILY,
        model_status="candidate",
        source_mode="bounded_wikidata_review_artifacts",
        claims=claims,
        authority_surfaces=authority_surfaces,
        summary=summary,
        metadata={
            "profile": profile,
            "profile_id": Q43229_PROFILE_ID,
            "lane_id": lane_id,
            "cohort_id": cohort_id,
            "target_instance_of_qid": Q43229_TARGET_QID,
            "packet_id": packet_id,
            "report_id": report_id,
            "batch_status": _text(batch_report.get("batch_status")) if isinstance(batch_report, Mapping) else "",
            "decision": decision,
            "governance": governance,
            "packet_rows": packet_rows,
            "review_bucket_rows": bucket_rows,
            "queue_rows": queue_rows,
            "report_rows": report_rows,
            "case_rows": case_rows,
            "triage_prompts": _string_list(operator_packet.get("triage_prompts")),
            "recommendations": _string_list(operator_report.get("recommendations")),
        },
    )


def _report_payload_from_world_model(world_model: Mapping[str, Any]) -> dict[str, Any]:
    metadata = world_model.get("metadata") if isinstance(world_model.get("metadata"), Mapping) else {}
    summary = world_model.get("summary") if isinstance(world_model.get("summary"), Mapping) else {}
    return {
        "schema_version": WIKIDATA_Q43229_SUPERCLASS_PRESSURE_REPORT_SCHEMA_VERSION,
        "lane_id": _text(metadata.get("lane_id")),
        "cohort_id": _text(metadata.get("cohort_id")),
        "target_instance_of_qid": _text(metadata.get("target_instance_of_qid")) or Q43229_TARGET_QID,
        "packet_id": _text(metadata.get("packet_id")),
        "report_id": _text(metadata.get("report_id")),
        "batch_status": _text(metadata.get("batch_status")),
        "decision": _text(metadata.get("decision")) or "review",
        "governance": dict(metadata.get("governance")) if isinstance(metadata.get("governance"), Mapping) else {},
        "packet_rows": [dict(row) for row in _mapping_rows(metadata.get("packet_rows"))],
        "review_bucket_rows": [dict(row) for row in _mapping_rows(metadata.get("review_bucket_rows"))],
        "queue_rows": [dict(row) for row in _mapping_rows(metadata.get("queue_rows"))],
        "report_rows": [dict(row) for row in _mapping_rows(metadata.get("report_rows"))],
        "case_rows": [dict(row) for row in _mapping_rows(metadata.get("case_rows"))],
        "triage_prompts": _string_list(metadata.get("triage_prompts")),
        "recommendations": _string_list(metadata.get("recommendations")),
        "summary": dict(summary),
    }


def _build_linkage_projection(world_model: Mapping[str, Any]) -> dict[str, Any]:
    case = _build_q43229_superclass_pressure_case_payload(_report_payload_from_world_model(world_model))
    return project_linkage_case(
        world_model,
        case_id=case["case_id"],
        contract_id=WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
        nodes=case["nodes"],
        edges=case["edges"],
        expected_anchor_ids=case["expected_anchor_ids"],
        expected_terminal_ids=case["expected_terminal_ids"],
        notes=case["notes"],
        metadata={
            "projection_role": "linkage_case",
            "contract_id": WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
        },
    )


def project_report(world_model: Mapping[str, Any]) -> dict[str, Any]:
    model = world_model if isinstance(world_model, Mapping) else {}
    metadata = model.get("metadata") if isinstance(model.get("metadata"), Mapping) else {}
    summary = model.get("summary") if isinstance(model.get("summary"), Mapping) else {}
    report_payload = _report_payload_from_world_model(model)
    review_surface = project_review_surface(
        model,
        review_rows=report_payload["report_rows"],
        workflow_summary={
            "decision": report_payload["decision"],
            "review_first": bool(summary.get("review_first")),
            "priority_counts": dict(summary.get("priority_counts", {})),
        },
        summary={"review_row_count": len(report_payload["report_rows"])},
        metadata={"profile_id": Q43229_PROFILE_ID},
    )
    claim_table = project_claim_table(
        model,
        claim_rows=model.get("claims"),
        summary={"row_count": len(model.get("claims", []))},
        metadata={"profile_id": Q43229_PROFILE_ID},
    )
    linkage_case = _build_linkage_projection(model)
    return project_world_model_report(
        model,
        schema_version=WIKIDATA_Q43229_SUPERCLASS_PRESSURE_REPORT_SCHEMA_VERSION,
        artifact_id=report_payload["report_id"] or report_payload["packet_id"] or model.get("model_id"),
        lane_id=report_payload["lane_id"] or Q43229_LANE_FAMILY,
        family_id=Q43229_PROFILE_ID,
        promotion_gate={
            "decision": report_payload["decision"],
            "reason": "q43229_superclass_pressure_review_only",
            "requires_human_review": True,
        },
        workflow_summary=review_surface["payload"]["workflow_summary"],
        claims=model.get("claims"),
        summary=summary,
        projection_metadata={"profile_id": Q43229_PROFILE_ID},
        extra_fields={
            "cohort_id": report_payload["cohort_id"],
            "target_instance_of_qid": report_payload["target_instance_of_qid"],
            "packet_id": report_payload["packet_id"],
            "report_id": report_payload["report_id"],
            "batch_status": report_payload["batch_status"],
            "decision": report_payload["decision"],
            "governance": report_payload["governance"],
            "packet_rows": report_payload["packet_rows"],
            "review_bucket_rows": report_payload["review_bucket_rows"],
            "queue_rows": report_payload["queue_rows"],
            "report_rows": report_payload["report_rows"],
            "case_rows": report_payload["case_rows"],
            "triage_prompts": report_payload["triage_prompts"],
            "recommendations": report_payload["recommendations"],
            "review_surface": review_surface,
            "claim_table": claim_table,
            "linkage_case": linkage_case,
        },
    )


def build_contract() -> dict[str, Any]:
    return build_expected_layer_contract(
        contract_id=WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
        domain="wikidata_q43229_superclass_pressure",
        anchor_kind="source_anchor",
        expected_layers=[
            "source_anchor",
            "statement_edge_candidate",
            "counterexample_cone",
            "pressure_surface",
            "repair_candidate",
            "review_surface",
            "tranche_anchor",
        ],
        required_bridges=[
            ["source_anchor", "statement_edge_candidate"],
            ["statement_edge_candidate", "counterexample_cone"],
            ["counterexample_cone", "pressure_surface"],
            ["pressure_surface", "repair_candidate"],
            ["repair_candidate", "review_surface"],
            ["review_surface", "tranche_anchor"],
        ],
        terminal_anchor="tranche_anchor",
        required_authority_boundaries=[
            "wd_source_discussion",
            "wd_class_lattice_pressure_surface",
            "wd_community_review_surface",
            "workflow_tranche_anchor",
        ],
        required_visibility_fields=[
            "candidate_vs_promoted_visibility",
            "counterexample_cone_visibility",
            "class_lattice_pressure_visibility",
        ],
        notes=[
            "Q43229 projects a structural-pressure lane from existing Cohort B review artifacts.",
            "The adapter kit emits source, statement, cone, pressure, repair, review, and tranche fragments without widening the shared audit core.",
        ],
        linkage_policy={
            "native_spine": "wd_structural_pressure_review",
            "promotion_policy": "review_only",
            "repair_surface": "candidate_only",
        },
    )


def _bucket_row_index(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(row.get("row_id")): row
        for row in _mapping_rows(report.get("review_bucket_rows"))
        if _text(row.get("row_id"))
    }


def _queue_row_index(report: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    by_row_id: dict[str, list[Mapping[str, Any]]] = {}
    for row in _mapping_rows(report.get("queue_rows")):
        row_id = _text(row.get("row_id"))
        if row_id:
            by_row_id.setdefault(row_id, []).append(row)
    return by_row_id


def _report_row_index(report: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    by_row_id: dict[str, list[Mapping[str, Any]]] = {}
    for row in _mapping_rows(report.get("report_rows")):
        row_id = _text(row.get("row_id"))
        if row_id:
            by_row_id.setdefault(row_id, []).append(row)
    return by_row_id


def _build_q43229_superclass_pressure_case_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    if _text(report.get("schema_version")) != WIKIDATA_Q43229_SUPERCLASS_PRESSURE_REPORT_SCHEMA_VERSION:
        raise ValueError("Q43229 superclass-pressure linkage case requires superclass-pressure report payload")

    packet_rows = _mapping_rows(report.get("packet_rows"))
    if not packet_rows:
        raise ValueError("Q43229 superclass-pressure linkage case requires packet rows")

    packet_id = _text(report.get("packet_id")) or "packet"
    report_id = _text(report.get("report_id")) or packet_id
    lane_id = _text(report.get("lane_id")) or "wikidata"
    bucket_index = _bucket_row_index(report)
    queue_index = _queue_row_index(report)
    report_index = _report_row_index(report)
    pressure_node_id = f"class_lattice_pressure:{Q43229_TARGET_QID}:{packet_id}"
    review_node_id = f"community_review_surface:{report_id}"
    tranche_node_id = f"workflow_tranche_anchor:{report_id}"
    repair_node_ids: list[str] = []
    counterexample_node_ids: list[str] = []
    fragments = []

    for row in packet_rows:
        row_id = _text(row.get("row_id"))
        entity_qid = _text(row.get("entity_qid"))
        if not row_id:
            continue
        bucket_row = bucket_index.get(row_id, {})
        queue_rows = queue_index.get(row_id, [])
        report_rows = report_index.get(row_id, [])
        source_anchor_id = f"wd_source_anchor:{row_id}"
        statement_node_id = f"statement_edge_candidate:{row_id}"
        counterexample_node_id = f"counterexample_cone:{row_id}"
        repair_node_id = f"repair_candidate:{row_id}"
        repair_node_ids.append(repair_node_id)
        counterexample_node_ids.append(counterexample_node_id)

        fragments.append(
            build_source_adapter_fragment(
                anchor_id=source_anchor_id,
                label=f"Wikidata source discussion anchor {row_id}",
                metadata={
                    "row_id": row_id,
                    "entity_qid": entity_qid,
                    "instance_of_qid": Q43229_TARGET_QID,
                    "reviewer_questions": _string_list(row.get("reviewer_questions")),
                },
                target_id=statement_node_id,
                edge_kind="statement_edge_projection",
                edge_metadata={
                    "from_layer": "source_anchor",
                    "to_layer": "statement_edge_candidate",
                    "authority_surface": "wd_source_discussion",
                },
            )
        )
        fragments.append(
            build_projection_adapter_fragment(
                layer="statement_edge_candidate",
                node_id=statement_node_id,
                label=f"Wikidata statement edge candidate {row_id}",
                metadata={
                    "row_id": row_id,
                    "entity_qid": entity_qid,
                    "instance_of_qid": Q43229_TARGET_QID,
                    "variance_flags": _string_list(row.get("variance_flags")),
                    "candidate_vs_promoted_visibility": True,
                },
                target_id=counterexample_node_id,
                edge_kind="counterexample_cone_projection",
                edge_metadata={
                    "from_layer": "statement_edge_candidate",
                    "to_layer": "counterexample_cone",
                    "authority_surface": "wd_source_discussion",
                },
            )
        )
        fragments.append(
            build_projection_adapter_fragment(
                layer="counterexample_cone",
                node_id=counterexample_node_id,
                label=f"Wikidata counterexample cone {row_id}",
                metadata={
                    "row_id": row_id,
                    "entity_qid": entity_qid,
                    "qualifier_properties": _string_list(bucket_row.get("qualifier_properties")),
                    "reference_properties": _string_list(bucket_row.get("reference_properties")),
                    "queue_item_ids": [_text(q.get("queue_item_id")) for q in queue_rows if _text(q.get("queue_item_id"))],
                    "priorities": [_text(q.get("priority")) for q in queue_rows if _text(q.get("priority"))],
                    "counterexample_cone_visibility": "complete" if bucket_row else "partial",
                },
                target_id=pressure_node_id,
                edge_kind="class_lattice_pressure_projection",
                edge_metadata={
                    "from_layer": "counterexample_cone",
                    "to_layer": "pressure_surface",
                    "authority_surface": "wd_class_lattice_pressure_surface",
                },
            )
        )
        fragments.append(
            build_projection_adapter_fragment(
                layer="repair_candidate",
                node_id=repair_node_id,
                label=f"Wikidata repair candidate {row_id}",
                metadata={
                    "row_id": row_id,
                    "entity_qid": entity_qid,
                    "instance_of_qid": Q43229_TARGET_QID,
                    "recommendations": _string_list(report.get("recommendations")),
                    "triage_prompts": _string_list(report.get("triage_prompts")),
                    "report_priorities": [_text(r.get("priority")) for r in report_rows if _text(r.get("priority"))],
                    "candidate_vs_promoted_visibility": True,
                },
                source_id=pressure_node_id,
                source_edge_kind="repair_candidate_projection",
                source_edge_metadata={
                    "from_layer": "pressure_surface",
                    "to_layer": "repair_candidate",
                    "authority_surface": "wd_class_lattice_pressure_surface",
                },
                target_id=review_node_id,
                edge_kind="community_review_projection",
                edge_metadata={
                    "from_layer": "repair_candidate",
                    "to_layer": "review_surface",
                    "authority_surface": "wd_community_review_surface",
                    "promotion_status": "candidate_only",
                },
            )
        )

    if not repair_node_ids:
        raise ValueError("Q43229 superclass-pressure linkage case requires at least one repair candidate")

    fragments.append(
        build_collection_adapter_fragment(
            layer="pressure_surface",
            node_id=pressure_node_id,
            label=f"Wikidata class lattice pressure surface {Q43229_TARGET_QID}",
            metadata={
                "instance_of_qid": Q43229_TARGET_QID,
                "packet_id": packet_id,
                "queue_row_count": len(_mapping_rows(report.get("queue_rows"))),
                "review_first": bool(report.get("summary", {}).get("review_first")),
                "variance_flag_counts": dict(report.get("summary", {}).get("variance_flag_counts", {})),
                "class_lattice_pressure_visibility": "complete" if counterexample_node_ids else "partial",
            },
            upstream_node_ids=counterexample_node_ids,
            edge_kind="class_lattice_pressure_projection",
            edge_metadata={
                "from_layer": "counterexample_cone",
                "to_layer": "pressure_surface",
                "authority_surface": "wd_class_lattice_pressure_surface",
            },
        )
    )
    fragments.append(
        build_collection_adapter_fragment(
            layer="review_surface",
            node_id=review_node_id,
            label=f"Wikidata community review surface {report_id}",
            metadata={
                "report_id": report_id,
                "lane_id": lane_id,
                "recommendations": _string_list(report.get("recommendations")),
                "review_row_count": len(_mapping_rows(report.get("report_rows"))),
                "candidate_vs_promoted_visibility": True,
            },
            upstream_node_ids=repair_node_ids,
            edge_kind="community_review_projection",
            edge_metadata={
                "from_layer": "repair_candidate",
                "to_layer": "review_surface",
                "authority_surface": "wd_community_review_surface",
                "promotion_status": "review_only",
            },
        )
    )
    fragments.append(
        build_tranche_adapter_fragment(
            node_id=tranche_node_id,
            label=f"Wikidata workflow tranche anchor {report_id}",
            metadata={
                "report_id": report_id,
                "packet_id": packet_id,
                "batch_status": _text(report.get("batch_status")),
                "decision": _text(report.get("decision")),
                "authority_surface": "workflow_tranche_anchor",
            },
            upstream_node_ids=[review_node_id],
            edge_kind="workflow_tranche_projection",
            edge_metadata={
                "from_layer": "review_surface",
                "to_layer": "tranche_anchor",
                "authority_surface": "workflow_tranche_anchor",
                "promotion_status": "review_only",
            },
        )
    )

    fragment = merge_linkage_fragments(*fragments)
    return build_linkage_depth_case(
        case_id="wikidata_q43229_superclass_pressure",
        case_kind="wd_structural_pressure_fixture",
        lane_id=lane_id,
        contract_id=WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
        case_source="emitted_bridge_artifact",
        notes=[
            "Q43229 superclass pressure is projected from Cohort B review bucket, packet, queue, and report artifacts.",
            "The lane remains review-only while preserving statement, cone, pressure, repair, and community review depth.",
        ],
        expected_anchor_ids=fragment.get("expected_anchor_ids", []),
        expected_terminal_ids=[tranche_node_id],
        nodes=fragment.get("nodes", []),
        edges=fragment.get("edges", []),
        contract=build_contract(),
    )


def build_case(report: Mapping[str, Any]) -> dict[str, Any]:
    receipt = report.get("linkage_depth_receipt") if isinstance(report, Mapping) else None
    if isinstance(receipt, Mapping) and _text(receipt.get("schema_version")) == LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION:
        return build_linkage_depth_case(
            case_id=_text(receipt.get("case_id")) or "wikidata_q43229_superclass_pressure",
            case_kind="wd_structural_pressure_fixture",
            contract_id=_text((receipt.get("contract") or {}).get("contract_id"))
            or WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
            expected_anchor_ids=receipt.get("expected_anchor_ids", []),
            expected_terminal_ids=receipt.get("expected_terminal_ids", []),
            nodes=receipt.get("nodes", []),
            edges=receipt.get("edges", []),
            lane_id=_text(receipt.get("lane_id")) or "wikidata",
            case_source=_text(receipt.get("source_mode")) or "emitted_bridge_artifact",
            notes=["Q43229 superclass pressure case loaded from emitted lane receipt."],
            contract=receipt.get("contract")
            if isinstance(receipt.get("contract"), Mapping)
            else build_contract(),
        )
    linkage_projection = report.get("linkage_case") if isinstance(report, Mapping) else None
    if (
        isinstance(linkage_projection, Mapping)
        and _text(linkage_projection.get("projection_kind")) == "linkage_case"
    ):
        payload = linkage_projection.get("payload") if isinstance(linkage_projection.get("payload"), Mapping) else {}
        return build_linkage_depth_case(
            case_id=_text(payload.get("case_id")) or "wikidata_q43229_superclass_pressure",
            case_kind="wd_structural_pressure_fixture",
            contract_id=_text(payload.get("contract_id")) or WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
            expected_anchor_ids=payload.get("expected_anchor_ids", []),
            expected_terminal_ids=payload.get("expected_terminal_ids", []),
            nodes=payload.get("nodes", []),
            edges=payload.get("edges", []),
            lane_id=_text((linkage_projection.get("source_model") or {}).get("lane_family")) or Q43229_LANE_FAMILY,
            case_source="projected_world_model_artifact",
            notes=payload.get("notes", []),
            contract=build_contract(),
        )
    return _build_q43229_superclass_pressure_case_payload(report)


def build_receipt(
    report: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract_payload = (
        dict(contract)
        if isinstance(contract, Mapping)
        else build_contract()
    )
    case = require_case_from_projection_artifact(
        report,
        case_kind="wd_structural_pressure_fixture",
        default_case_id="wikidata_q43229_superclass_pressure",
        default_lane_id=Q43229_LANE_FAMILY,
        default_contract=contract_payload,
        default_contract_id=WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
        default_notes=["Q43229 superclass-pressure case loaded from the projected linkage surface."],
    )
    return build_linkage_depth_receipt(
        case=case,
        contract=contract_payload,
        receipt_id=f"linkage_depth:{case['case_id']}",
        source_mode="emitted_bridge_artifact",
        notes=[
            "Q43229 superclass-pressure receipt is attached only at the lane wrapper boundary.",
        ],
    )


__all__ = [
    "Q43229_TARGET_QID",
    "Q43229_PROFILE_ID",
    "WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID",
    "WIKIDATA_Q43229_SUPERCLASS_PRESSURE_REPORT_SCHEMA_VERSION",
    "build_case",
    "build_contract",
    "build_receipt",
    "build_report",
    "build_world_model",
    "project_report",
]
