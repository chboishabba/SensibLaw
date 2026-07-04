from __future__ import annotations

from typing import Any, Mapping

from src.policy.linkage_adapters import (
    build_authority_adapter_fragment,
    build_claim_adapter_fragment,
    build_coalescence_adapter_fragment,
    build_document_adapter_fragment,
    build_external_bridge_adapter_fragment,
    build_parse_adapter_fragment,
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

GWB_NARRATIVE_TIMELINE_LINKAGE_CONTRACT_ID = "gwb_narrative_timeline_linkage"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _source_family_for_document(document_id: str) -> str:
    lowered = document_id.casefold()
    if lowered.startswith("wikidata:") or "wikidata.org" in lowered:
        return "wikidata_item"
    if "wikipedia.org" in lowered:
        return "wikipedia_article"
    if ".pdf" in lowered:
        return "book_pdf"
    return "timeline_source"


def _is_external_source(document_id: str) -> bool:
    lowered = document_id.casefold()
    return lowered.startswith("wikidata:") or "wikidata.org" in lowered or "wikipedia.org" in lowered


def build_contract() -> dict[str, Any]:
    return build_expected_layer_contract(
        contract_id=GWB_NARRATIVE_TIMELINE_LINKAGE_CONTRACT_ID,
        domain="gwb_narrative_timeline_linkage",
        anchor_kind="source_anchor",
        expected_layers=[
            "source_anchor",
            "source_container",
            "parsed_form",
            "domain_candidate",
            "review_surface",
            "authority_surface",
            "tranche_anchor",
        ],
        required_bridges=[
            ["source_anchor", "source_container"],
            ["source_container", "parsed_form"],
            ["parsed_form", "domain_candidate"],
            ["domain_candidate", "review_surface"],
            ["review_surface", "authority_surface"],
            ["authority_surface", "tranche_anchor"],
        ],
        terminal_anchor="tranche_anchor",
        required_authority_boundaries=[
            "gwb_narrative_review_surface",
            "workflow_tranche_anchor",
        ],
        required_visibility_fields=[
            "candidate_vs_promoted_visibility",
            "cross_source_provenance_visibility",
        ],
        notes=[
            "GWB narrative/timeline composition is built from generic source, document, parse, claim, coalescence, authority, and tranche adapters.",
            "Multiple heterogeneous sources may coalesce into one review surface without requiring a WD bridge.",
        ],
        linkage_policy={
            "native_spine": "gwb_semantic_timeline",
            "cross_source_coalescence": "required",
            "wd_bridge_requirement": "optional_enrichment",
        },
    )


def _build_case_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    run_id = _text(report.get("run_id"))
    if not run_id:
        raise ValueError("GWB narrative/timeline linkage case requires semantic report run_id")

    per_event = _mapping_rows(report.get("per_event"))
    if not per_event:
        raise ValueError("GWB narrative/timeline linkage case requires per_event semantic rows")

    source_documents = {
        _text(row.get("sourceDocumentId")): row
        for row in _mapping_rows(report.get("source_documents"))
        if _text(row.get("sourceDocumentId"))
    }

    review_node_id = f"narrative_timeline_surface:{run_id}"
    authority_node_id = f"operator_review_surface:{run_id}"
    tranche_node_id = f"workflow_tranche_anchor:{run_id}"
    candidate_node_ids: list[str] = []
    fragments = []

    for event in per_event:
        event_id = _text(event.get("event_id"))
        source_document_id = _text(event.get("source_document_id")) or _text(event.get("source_id"))
        relation_rows = _mapping_rows(event.get("relation_candidates"))
        if not event_id or not source_document_id or not relation_rows:
            continue

        document = source_documents.get(source_document_id, {})
        source_anchor_id = f"source_anchor:{event_id}"
        document_node_id = f"source_document:{source_document_id}"
        parse_node_id = f"timeline_event_parse:{event_id}"

        fragments.append(
            build_source_adapter_fragment(
                anchor_id=source_anchor_id,
                label=f"GWB source anchor {event_id}",
                metadata={
                    "event_id": event_id,
                    "source_document_id": source_document_id,
                    "source_family": _source_family_for_document(source_document_id),
                },
                target_id=document_node_id,
                edge_kind="source_document_projection",
                edge_metadata={
                    "from_layer": "source_anchor",
                    "to_layer": "source_container",
                    "source_family": _source_family_for_document(source_document_id),
                },
            )
        )
        fragments.append(
            build_document_adapter_fragment(
                node_id=document_node_id,
                label=f"GWB source document {document.get('title') or source_document_id}",
                metadata={
                    "source_document_id": source_document_id,
                    "source_type": _text(document.get("sourceType")) or _source_family_for_document(source_document_id),
                    "event_count": int(document.get("eventCount", 0) or 0),
                    "source_family": _source_family_for_document(source_document_id),
                },
                target_id=parse_node_id,
                edge_kind="timeline_event_projection",
                edge_metadata={
                    "from_layer": "source_container",
                    "to_layer": "parsed_form",
                    "event_id": event_id,
                },
            )
        )
        fragments.append(
            build_parse_adapter_fragment(
                node_id=parse_node_id,
                label=f"GWB timeline event parse {event_id}",
                metadata={
                    "event_id": event_id,
                    "event_section": _text(event.get("section")),
                    "source_document_id": source_document_id,
                    "source_char_start": event.get("source_char_start"),
                    "source_char_end": event.get("source_char_end"),
                },
            )
        )

        for relation in relation_rows:
            candidate_id = _text(relation.get("candidate_id"))
            if not candidate_id:
                continue
            relation_node_id = f"relation_candidate:{event_id}:{candidate_id}"
            candidate_node_ids.append(relation_node_id)
            fragments.append(
                build_claim_adapter_fragment(
                    node_id=relation_node_id,
                    label=f"GWB relation candidate {relation.get('display_label') or relation.get('predicate_key') or candidate_id}",
                    metadata={
                        "event_id": event_id,
                        "candidate_id": candidate_id,
                        "predicate_key": _text(relation.get("predicate_key")),
                        "promotion_status": _text(relation.get("promotion_status")),
                        "semantic_basis": _text(relation.get("semantic_basis")),
                        "candidate_vs_promoted_visibility": True,
                    },
                    source_id=parse_node_id,
                    source_edge_kind="event_candidate_projection",
                    source_edge_metadata={
                        "from_layer": "parsed_form",
                        "to_layer": "domain_candidate",
                        "event_id": event_id,
                    },
                    target_id=review_node_id,
                    edge_kind="narrative_coalescence_projection",
                    edge_metadata={
                        "from_layer": "domain_candidate",
                        "to_layer": "review_surface",
                        "event_id": event_id,
                        "promotion_status": _text(relation.get("promotion_status")) or "candidate",
                    },
                )
            )

        if _is_external_source(source_document_id):
            fragments.append(
                build_external_bridge_adapter_fragment(
                    node_id=f"external_source:{source_document_id}",
                    label=f"GWB external source {source_document_id}",
                    metadata={
                        "source_document_id": source_document_id,
                        "bridge_type": _source_family_for_document(source_document_id),
                    },
                    upstream_node_ids=[document_node_id],
                    edge_kind="optional_external_enrichment",
                    edge_metadata={
                        "from_layer": "source_container",
                        "to_layer": "external_candidate",
                    },
                )
            )

    if not candidate_node_ids:
        raise ValueError("GWB narrative/timeline linkage case requires at least one event candidate")

    source_document_count = len(source_documents)
    promoted_count = len(_mapping_rows(report.get("promoted_relations")))
    candidate_only_count = len(_mapping_rows(report.get("candidate_only_relations")))
    cross_source_visibility = "complete" if source_document_count > 1 else "partial"

    fragments.append(
        build_coalescence_adapter_fragment(
            node_id=review_node_id,
            label=f"GWB narrative/timeline coalescence surface {run_id}",
            metadata={
                "run_id": run_id,
                "source_document_count": source_document_count,
                "event_count": len(per_event),
                "promoted_relation_count": promoted_count,
                "candidate_only_relation_count": candidate_only_count,
                "diagnostic_flags": {
                    "candidate_vs_promoted_visibility": True,
                    "cross_source_provenance_visibility": cross_source_visibility,
                },
            },
            upstream_node_ids=candidate_node_ids,
            edge_kind="narrative_coalescence_projection",
            edge_metadata={
                "from_layer": "domain_candidate",
                "to_layer": "review_surface",
            },
        )
    )
    fragments.append(
        build_authority_adapter_fragment(
            node_id=authority_node_id,
            label=f"GWB narrative review authority surface {run_id}",
            metadata={
                "run_id": run_id,
                "authority_surface": "gwb_narrative_review_surface",
                "review_family": "gwb_semantic_timeline",
                "diagnostic_flags": {
                    "candidate_vs_promoted_visibility": True,
                    "cross_source_provenance_visibility": cross_source_visibility,
                },
            },
            upstream_node_ids=[review_node_id],
            edge_kind="operator_review_projection",
            edge_metadata={
                "from_layer": "review_surface",
                "to_layer": "authority_surface",
                "authority_surface": "gwb_narrative_review_surface",
            },
        )
    )
    fragments.append(
        build_tranche_adapter_fragment(
            node_id=tranche_node_id,
            label=f"GWB workflow/tranche anchor {run_id}",
            metadata={
                "run_id": run_id,
                "authority_surface": "workflow_tranche_anchor",
                "workflow_stage": "semantic_review",
            },
            upstream_node_ids=[authority_node_id],
            edge_kind="workflow_tranche_projection",
            edge_metadata={
                "from_layer": "authority_surface",
                "to_layer": "tranche_anchor",
                "authority_surface": "workflow_tranche_anchor",
            },
        )
    )

    merged = merge_linkage_fragments(*fragments)
    return build_linkage_depth_case(
        case_id="gwb_narrative_timeline",
        case_kind="narrative_timeline_fixture",
        lane_id="gwb",
        contract_id=GWB_NARRATIVE_TIMELINE_LINKAGE_CONTRACT_ID,
        case_source="emitted_bridge_artifact",
        notes=[
            "GWB narrative/timeline linkage is composed from generic adapter fragments rather than lane-specific audit logic.",
            "The receipt preserves source document provenance, event parse depth, relation candidate status, and coalesced review/tranche reachability.",
            *merged.get("notes", []),
        ],
        expected_anchor_ids=merged.get("expected_anchor_ids", []),
        expected_terminal_ids=merged.get("expected_terminal_ids", []),
        nodes=merged.get("nodes", []),
        edges=merged.get("edges", []),
        contract=build_contract(),
    )


def build_case(report: Mapping[str, Any]) -> dict[str, Any]:
    receipt = report.get("linkage_depth_receipt") if isinstance(report, Mapping) else None
    if isinstance(receipt, Mapping) and _text(receipt.get("schema_version")) == LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION:
        return build_linkage_depth_case(
            case_id=_text(receipt.get("case_id")) or "gwb_narrative_timeline",
            case_kind="narrative_timeline_fixture",
            contract_id=_text((receipt.get("contract") or {}).get("contract_id")) or GWB_NARRATIVE_TIMELINE_LINKAGE_CONTRACT_ID,
            expected_anchor_ids=receipt.get("expected_anchor_ids", []),
            expected_terminal_ids=receipt.get("expected_terminal_ids", []),
            nodes=receipt.get("nodes", []),
            edges=receipt.get("edges", []),
            lane_id=_text(receipt.get("lane_id")) or "gwb",
            case_source=_text(receipt.get("source_mode")) or "emitted_bridge_artifact",
            notes=["GWB narrative/timeline case loaded from the emitted lane receipt."],
            contract=receipt.get("contract") if isinstance(receipt.get("contract"), Mapping) else build_contract(),
        )
    return _build_case_payload(report)


def build_receipt(
    report: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract_payload = dict(contract) if isinstance(contract, Mapping) else build_contract()
    case_payload = _build_case_payload(report)
    return build_linkage_depth_receipt(
        case=case_payload,
        contract=contract_payload,
        receipt_id=f"linkage_depth:gwb_narrative_timeline:{_text(report.get('run_id'))}",
        source_mode="emitted_bridge_artifact",
        notes=[
            "GWB narrative/timeline lane receipt attached at the semantic report boundary.",
        ],
    )


__all__ = [
    "GWB_NARRATIVE_TIMELINE_LINKAGE_CONTRACT_ID",
    "build_case",
    "build_contract",
    "build_receipt",
]
