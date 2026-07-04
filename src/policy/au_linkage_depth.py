from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from src.fact_intake.au_review_bundle import AU_FACT_REVIEW_BUNDLE_WORLD_MODEL_SCHEMA_VERSION
from src.policy.linkage_depth import (
    LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION,
    build_expected_layer_contract,
    build_linkage_depth_case,
    build_linkage_depth_receipt,
)

AU_FACT_REVIEW_BUNDLE_LINKAGE_CONTRACT_ID = "au_fact_review_bundle_linkage"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _metadata_flag(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    text = _text(value)
    return text or None


def build_au_fact_review_bundle_linkage_contract() -> dict[str, Any]:
    return build_expected_layer_contract(
        contract_id=AU_FACT_REVIEW_BUNDLE_LINKAGE_CONTRACT_ID,
        domain="au_fact_review_bundle_linkage",
        anchor_kind="source_anchor",
        expected_layers=[
            "source_anchor",
            "legal_text_or_event_anchor",
            "provision_or_legal_ref_container",
            "parsed_legal_support_surface",
            "legal_claim_candidate",
            "authority_surface",
            "review_surface",
            "tranche_anchor",
        ],
        required_bridges=[
            ["source_anchor", "legal_text_or_event_anchor"],
            ["legal_text_or_event_anchor", "provision_or_legal_ref_container"],
            ["provision_or_legal_ref_container", "parsed_legal_support_surface"],
            ["parsed_legal_support_surface", "legal_claim_candidate"],
            ["legal_claim_candidate", "authority_surface"],
            ["authority_surface", "review_surface"],
            ["review_surface", "tranche_anchor"],
        ],
        terminal_anchor="tranche_anchor",
        required_authority_boundaries=[
            "au_source_document",
            "au_legal_reference_context",
            "au_authority_visibility_surface",
            "au_fact_review_bundle",
            "workflow_tranche_anchor",
        ],
        required_visibility_fields=[
            "authority_boundary_visibility",
            "instrument_or_jurisdiction_visible",
            "candidate_vs_promoted_visibility",
        ],
        notes=[
            "AU proves legal authority depth rather than only queue reachability.",
            "The lane stays receipt-free until the wrapper attaches the linkage-depth receipt.",
        ],
        linkage_policy={
            "native_spine": "au_legal_authority",
            "wd_bridge_requirement": "optional",
        },
    )


def _source_row_index(review_bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(row.get("source_id")): row
        for row in _mapping_rows(review_bundle.get("sources"))
        if _text(row.get("source_id"))
    }


def _event_index(review_bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(row.get("event_id")): row
        for row in _mapping_rows(review_bundle.get("events"))
        if _text(row.get("event_id"))
    }


def _authority_queue_by_event(review_bundle: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    operator_views = review_bundle.get("operator_views") if isinstance(review_bundle.get("operator_views"), Mapping) else {}
    authority_follow = operator_views.get("authority_follow") if isinstance(operator_views.get("authority_follow"), Mapping) else {}
    queue: dict[str, list[Mapping[str, Any]]] = {}
    for row in _mapping_rows(authority_follow.get("queue")):
        event_id = _text(row.get("event_id") or row.get("item_id"))
        if event_id:
            queue.setdefault(event_id, []).append(row)
    return queue


def _legal_queue_by_event(review_bundle: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    operator_views = review_bundle.get("operator_views") if isinstance(review_bundle.get("operator_views"), Mapping) else {}
    legal_follow = operator_views.get("legal_follow_graph") if isinstance(operator_views.get("legal_follow_graph"), Mapping) else {}
    queue: dict[str, list[Mapping[str, Any]]] = {}
    for row in _mapping_rows(legal_follow.get("queue")):
        event_id = _text(row.get("event_id"))
        if event_id:
            queue.setdefault(event_id, []).append(row)
    return queue


def _workflow_anchor_metadata(review_bundle: Mapping[str, Any]) -> dict[str, Any]:
    workflow_summary = review_bundle.get("workflow_summary") if isinstance(review_bundle.get("workflow_summary"), Mapping) else {}
    promotion_gate = review_bundle.get("promotion_gate") if isinstance(review_bundle.get("promotion_gate"), Mapping) else {}
    return {
        "workflow_stage": _text(workflow_summary.get("stage")),
        "recommended_view": _text(workflow_summary.get("recommended_view")),
        "gate_decision": _text(promotion_gate.get("decision")),
        "authority_surface": "workflow_tranche_anchor",
    }


def _build_case_payload(review_bundle: Mapping[str, Any]) -> dict[str, Any]:
    if str(review_bundle.get("version") or "").strip() != "fact.review.bundle.v1":
        raise ValueError("AU linkage case requires fact review bundle payload")

    run = review_bundle.get("run") if isinstance(review_bundle.get("run"), Mapping) else {}
    workflow_summary = review_bundle.get("workflow_summary") if isinstance(review_bundle.get("workflow_summary"), Mapping) else {}
    operator_workflow_surface = (
        review_bundle.get("operator_workflow_surface")
        if isinstance(review_bundle.get("operator_workflow_surface"), Mapping)
        else {}
    )
    review_queue = _mapping_rows(review_bundle.get("review_queue"))
    if not review_queue:
        raise ValueError("AU linkage case requires review queue rows")

    fact_run_id = _text(run.get("fact_run_id"))
    semantic_run_id = _text(run.get("semantic_run_id"))
    artifact_id = fact_run_id or semantic_run_id or "au_fact_review_bundle"
    source_rows = _source_row_index(review_bundle)
    event_rows = _event_index(review_bundle)
    authority_by_event = _authority_queue_by_event(review_bundle)
    legal_by_event = _legal_queue_by_event(review_bundle)
    source_documents = _mapping_rows(review_bundle.get("source_documents"))

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    anchor_ids: list[str] = []

    def add_node(node_id: str, *, layer: str, label: str, metadata: Mapping[str, Any]) -> None:
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "layer": layer,
                "label": label,
                "metadata": dict(metadata),
            }
        )

    def add_edge(source: str, target: str, *, kind: str, metadata: Mapping[str, Any]) -> None:
        edge_key = (source, target, kind)
        if edge_key in seen_edges:
            return
        seen_edges.add(edge_key)
        edges.append(
            {
                "source": source,
                "target": target,
                "kind": kind,
                "metadata": dict(metadata),
            }
        )

    review_surface_id = f"au_fact_review_bundle:{artifact_id}"
    tranche_anchor_id = f"workflow_tranche_anchor:{artifact_id}"
    add_node(
        review_surface_id,
        layer="review_surface",
        label=f"AU fact-review bundle {artifact_id}",
        metadata={
            "artifact_id": artifact_id,
            "semantic_run_id": semantic_run_id,
            "recommended_view": _text(workflow_summary.get("recommended_view")),
            "review_queue_count": len(review_queue),
            "authority_surface": "au_fact_review_bundle",
            "candidate_vs_promoted_visibility": True,
        },
    )
    add_node(
        tranche_anchor_id,
        layer="tranche_anchor",
        label=f"workflow tranche anchor {artifact_id}",
        metadata=_workflow_anchor_metadata(review_bundle),
    )
    add_edge(
        review_surface_id,
        tranche_anchor_id,
        kind="workflow_tranche_projection",
        metadata={
            "from_layer": "review_surface",
            "to_layer": "tranche_anchor",
            "authority_surface": "workflow_tranche_anchor",
            "promotion_status": _text((review_bundle.get("promotion_gate") or {}).get("decision")) or "audit",
        },
    )

    for row in review_queue:
        fact_id = _text(row.get("fact_id"))
        if not fact_id:
            continue
        event_ids = [_text(value) for value in row.get("event_ids", []) if _text(value)]
        if not event_ids:
            continue
        source_ids = [_text(value) for value in row.get("source_ids", []) if _text(value)]
        candidate_node_id = f"au_legal_claim_candidate:{fact_id}"
        authority_node_id = f"au_authority_surface:{fact_id}"
        visibility_state = "complete"

        add_node(
            candidate_node_id,
            layer="legal_claim_candidate",
            label=f"AU legal claim candidate {fact_id}",
            metadata={
                "fact_id": fact_id,
                "candidate_status": _text(row.get("candidate_status")),
                "policy_outcomes": [value for value in row.get("policy_outcomes", []) if _text(value)],
                "reason_codes": [value for value in row.get("reason_codes", []) if _text(value)],
                "legal_procedural_predicates": [
                    value for value in row.get("legal_procedural_predicates", []) if _text(value)
                ],
                "candidate_vs_promoted_visibility": bool(_text(row.get("candidate_status")) and row.get("policy_outcomes")),
            },
        )
        add_edge(
            authority_node_id,
            review_surface_id,
            kind="review_bundle_projection",
            metadata={
                "from_layer": "authority_surface",
                "to_layer": "review_surface",
                "authority_surface": "au_fact_review_bundle",
            },
        )

        for source_id in source_ids or [f"source_missing:{fact_id}"]:
            source_row = source_rows.get(source_id, {})
            source_document_id = _text(source_row.get("source_document_id"))
            source_anchor_id = f"source_anchor:{source_id}"
            if source_anchor_id not in anchor_ids:
                anchor_ids.append(source_anchor_id)
            add_node(
                source_anchor_id,
                layer="source_anchor",
                label=f"AU source anchor {source_id}",
                metadata={
                    "source_id": source_id,
                    "source_document_id": source_document_id,
                    "source_type": _text(source_row.get("source_type")),
                    "projection_mode": _text(source_row.get("projection_mode")),
                    "authority_surface": "au_source_document",
                },
            )
            for event_id in event_ids:
                event_row = event_rows.get(event_id, {})
                event_anchor_id = f"au_event_anchor:{fact_id}:{event_id}"
                authority_rows = authority_by_event.get(_text((event_row.get("source_event_ids") or [event_id])[0])) or authority_by_event.get(event_id) or []
                legal_rows = legal_by_event.get(_text((event_row.get("source_event_ids") or [event_id])[0])) or legal_by_event.get(event_id) or []
                provision_node_id = f"au_legal_ref_container:{fact_id}:{event_id}"
                parsed_node_id = f"au_parsed_legal_support:{fact_id}:{event_id}"

                authority_titles = sorted(
                    {
                        _text(value)
                        for authority_row in authority_rows
                        for value in authority_row.get("authority_titles", [])
                        if _text(value)
                    }
                )
                legal_refs = sorted(
                    {
                        _text(value)
                        for authority_row in authority_rows
                        for value in authority_row.get("legal_refs", [])
                        if _text(value)
                    }
                )
                jurisdiction_keys = sorted(
                    {
                        _text(key)
                        for authority_row in authority_rows
                        for key in (authority_row.get("jurisdiction_hint_counts") or {}).keys()
                        if _text(key)
                    }
                )
                instrument_keys = sorted(
                    {
                        _text(key)
                        for authority_row in authority_rows
                        for key in (authority_row.get("instrument_kind_counts") or {}).keys()
                        if _text(key)
                    }
                )
                citation_count = sum(
                    len(authority_row.get("candidate_citation_details", []))
                    for authority_row in authority_rows
                    if isinstance(authority_row.get("candidate_citation_details"), Sequence)
                )
                legal_route_targets = sorted(
                    {
                        _text(legal_row.get("route_target"))
                        for legal_row in legal_rows
                        if _text(legal_row.get("route_target"))
                    }
                )
                source_event_ids = [
                    _text(value)
                    for value in event_row.get("source_event_ids", [])
                    if _text(value)
                ]
                instrument_or_jurisdiction_visible = bool(jurisdiction_keys or instrument_keys)

                add_node(
                    event_anchor_id,
                    layer="legal_text_or_event_anchor",
                    label=f"AU legal/event anchor {event_id}",
                    metadata={
                        "event_id": event_id,
                        "event_type": _text(event_row.get("event_type")),
                        "source_event_ids": source_event_ids,
                        "source_document_id": source_document_id,
                        "authority_surface": "au_source_document",
                    },
                )
                add_node(
                    provision_node_id,
                    layer="provision_or_legal_ref_container",
                    label=f"AU legal ref container {fact_id}:{event_id}",
                    metadata={
                        "fact_id": fact_id,
                        "event_id": event_id,
                        "authority_titles": authority_titles,
                        "legal_refs": legal_refs,
                        "citation_count": citation_count,
                        "jurisdiction_keys": jurisdiction_keys,
                        "instrument_keys": instrument_keys,
                        "authority_surface": "au_legal_reference_context",
                        "instrument_or_jurisdiction_visible": instrument_or_jurisdiction_visible,
                    },
                )
                add_node(
                    parsed_node_id,
                    layer="parsed_legal_support_surface",
                    label=f"AU parsed legal support {fact_id}:{event_id}",
                    metadata={
                        "fact_id": fact_id,
                        "event_id": event_id,
                        "legal_route_targets": legal_route_targets,
                        "authority_title_count": len(authority_titles),
                        "legal_ref_count": len(legal_refs),
                        "citation_count": citation_count,
                        "jurisdiction_keys": jurisdiction_keys,
                        "instrument_keys": instrument_keys,
                        "instrument_or_jurisdiction_visible": instrument_or_jurisdiction_visible,
                        "authority_surface": "au_legal_reference_context",
                    },
                )
                add_edge(
                    source_anchor_id,
                    event_anchor_id,
                    kind="source_event_projection",
                    metadata={
                        "from_layer": "source_anchor",
                        "to_layer": "legal_text_or_event_anchor",
                        "authority_surface": "au_source_document",
                    },
                )
                add_edge(
                    event_anchor_id,
                    provision_node_id,
                    kind="event_legal_context_projection",
                    metadata={
                        "from_layer": "legal_text_or_event_anchor",
                        "to_layer": "provision_or_legal_ref_container",
                        "authority_surface": "au_legal_reference_context",
                    },
                )
                add_edge(
                    provision_node_id,
                    parsed_node_id,
                    kind="legal_context_parse_projection",
                    metadata={
                        "from_layer": "provision_or_legal_ref_container",
                        "to_layer": "parsed_legal_support_surface",
                        "authority_surface": "au_legal_reference_context",
                    },
                )
                add_edge(
                    parsed_node_id,
                    candidate_node_id,
                    kind="parsed_claim_projection",
                    metadata={
                        "from_layer": "parsed_legal_support_surface",
                        "to_layer": "legal_claim_candidate",
                        "authority_surface": "au_legal_reference_context",
                    },
                )

        supporting_document_count = len(source_documents)
        authority_visibility = bool(
            operator_workflow_surface
            and _text((review_bundle.get("workflow_summary") or {}).get("recommended_view"))
        )
        instrument_or_jurisdiction_visible = any(
            bool(
                (authority_row.get("jurisdiction_hint_counts") if isinstance(authority_row.get("jurisdiction_hint_counts"), Mapping) else {})
                or (authority_row.get("instrument_kind_counts") if isinstance(authority_row.get("instrument_kind_counts"), Mapping) else {})
            )
            for event_id in event_ids
            for authority_row in authority_by_event.get(event_id, [])
        )
        add_node(
            authority_node_id,
            layer="authority_surface",
            label=f"AU authority surface {fact_id}",
            metadata={
                "fact_id": fact_id,
                "recommended_view": _text(workflow_summary.get("recommended_view")),
                "review_stage": _text(workflow_summary.get("stage")),
                "supporting_document_count": supporting_document_count,
                "authority_boundary_visibility": visibility_state if authority_visibility else "partial",
                "instrument_or_jurisdiction_visible": _metadata_flag(instrument_or_jurisdiction_visible),
                "candidate_vs_promoted_visibility": True,
                "authority_surface": "au_authority_visibility_surface",
            },
        )
        add_edge(
            candidate_node_id,
            authority_node_id,
            kind="authority_review_projection",
            metadata={
                "from_layer": "legal_claim_candidate",
                "to_layer": "authority_surface",
                "authority_surface": "au_authority_visibility_surface",
                "candidate_vs_promoted_visibility": True,
            },
        )

    return build_linkage_depth_case(
        case_id="au_fact_review_bundle",
        case_kind="legal_authority_fixture",
        lane_id="au",
        contract_id=AU_FACT_REVIEW_BUNDLE_LINKAGE_CONTRACT_ID,
        case_source="emitted_bridge_artifact",
        notes=[
            "AU fact-review bundle preserves source, legal context, claim-candidate, authority, review, and tranche depth.",
            "The receipt is attached at lane level so the underlying bundle builder stays receipt-free.",
        ],
        expected_anchor_ids=anchor_ids,
        expected_terminal_ids=[tranche_anchor_id],
        nodes=nodes,
        edges=edges,
        contract=build_au_fact_review_bundle_linkage_contract(),
    )


def build_au_fact_review_bundle_linkage_case(review_bundle: Mapping[str, Any]) -> dict[str, Any]:
    receipt = review_bundle.get("linkage_depth_receipt") if isinstance(review_bundle, Mapping) else None
    if isinstance(receipt, Mapping) and _text(receipt.get("schema_version")) == LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION:
        return build_linkage_depth_case(
            case_id=_text(receipt.get("case_id")) or "au_fact_review_bundle",
            case_kind="legal_authority_fixture",
            contract_id=_text((receipt.get("contract") or {}).get("contract_id")) or AU_FACT_REVIEW_BUNDLE_LINKAGE_CONTRACT_ID,
            expected_anchor_ids=receipt.get("expected_anchor_ids", []),
            expected_terminal_ids=receipt.get("expected_terminal_ids", []),
            nodes=receipt.get("nodes", []),
            edges=receipt.get("edges", []),
            lane_id=_text(receipt.get("lane_id")) or "au",
            case_source=_text(receipt.get("source_mode")) or "emitted_bridge_artifact",
            notes=["AU fact-review linkage case loaded from the emitted lane receipt."],
            contract=receipt.get("contract") if isinstance(receipt.get("contract"), Mapping) else build_au_fact_review_bundle_linkage_contract(),
        )
    return _build_case_payload(review_bundle)


def build_au_fact_review_bundle_linkage_receipt(
    review_bundle: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract_payload = dict(contract) if isinstance(contract, Mapping) else build_au_fact_review_bundle_linkage_contract()
    case_payload = _build_case_payload(review_bundle)
    receipt = build_linkage_depth_receipt(
        case=case_payload,
        contract=contract_payload,
        source_mode="emitted_bridge_artifact",
        notes=[
            "Lane-level linkage receipt for the AU fact-review bundle.",
            "The shared core audits authority-boundary and jurisdiction/instrument visibility through open metadata checks.",
        ],
    )
    receipt["contract"] = deepcopy(contract_payload)
    return receipt


def build_au_fact_review_bundle_world_model_report_with_linkage_receipt(
    review_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    from src.fact_intake.au_review_bundle import build_au_fact_review_bundle_world_model_report

    report = build_au_fact_review_bundle_world_model_report(review_bundle)
    artifact = deepcopy(dict(report))
    artifact["linkage_depth_receipt"] = build_au_fact_review_bundle_linkage_receipt(review_bundle)
    return artifact


__all__ = [
    "AU_FACT_REVIEW_BUNDLE_LINKAGE_CONTRACT_ID",
    "build_au_fact_review_bundle_linkage_case",
    "build_au_fact_review_bundle_linkage_contract",
    "build_au_fact_review_bundle_linkage_receipt",
    "build_au_fact_review_bundle_world_model_report_with_linkage_receipt",
]
