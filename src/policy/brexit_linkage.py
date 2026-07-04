from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.linkage_adapters import (
    build_authority_adapter_fragment,
    build_claim_adapter_fragment,
    build_coalescence_adapter_fragment,
    build_document_adapter_fragment,
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
from src.sources.national_archives.brexit_national_archives_lane import (
    BREXIT_NATIONAL_ARCHIVES_WORLD_MODEL_SCHEMA_VERSION,
)

BREXIT_ARCHIVE_POLICY_INTENT_LINKAGE_CONTRACT_ID = "brexit_archive_policy_intent_linkage"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def build_contract() -> dict[str, Any]:
    return build_expected_layer_contract(
        contract_id=BREXIT_ARCHIVE_POLICY_INTENT_LINKAGE_CONTRACT_ID,
        domain="brexit_archive_policy_intent_linkage",
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
            "brexit_archive_record",
            "brexit_policy_intent_review_surface",
            "brexit_archive_authority_surface",
            "workflow_tranche_anchor",
        ],
        required_visibility_fields=[
            "candidate_vs_promoted_visibility",
            "archive_authority_visibility",
        ],
        notes=[
            "Brexit archive/policy-intent composes archive records, document containers, parsed intent surfaces, claim candidates, review, authority, and tranche fragments over the shared core.",
            "The national archives world-model report remains receipt-free; the wrapper attaches the linkage receipt.",
        ],
        linkage_policy={
            "native_spine": "brexit_archive_policy_intent",
            "promotion_policy": "review_only",
        },
    )


def _build_brexit_archive_policy_intent_case_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    if _text(report.get("schema_version")) != BREXIT_NATIONAL_ARCHIVES_WORLD_MODEL_SCHEMA_VERSION:
        raise ValueError("Brexit archive policy-intent linkage case requires national archives world-model report")

    claims = _mapping_rows(report.get("claims"))
    if not claims:
        raise ValueError("Brexit archive policy-intent linkage case requires at least one claim")

    lane_id = _text(report.get("lane_id")) or "brexit_national_archives_policy_intent"
    artifact_id = f"{lane_id}:{int(report.get('summary', {}).get('claim_count', 0) or 0)}"
    review_node_id = f"brexit_policy_intent_review_surface:{artifact_id}"
    authority_node_id = f"brexit_archive_authority_surface:{artifact_id}"
    tranche_node_id = f"workflow_tranche_anchor:{artifact_id}"
    candidate_node_ids: list[str] = []
    review_authority_roles: list[str] = []
    fragments = []

    for claim in claims:
        claim_id = _text(claim.get("claim_id"))
        canonical_form = claim.get("canonical_form") if isinstance(claim.get("canonical_form"), Mapping) else {}
        qualifiers = canonical_form.get("qualifiers") if isinstance(canonical_form.get("qualifiers"), Mapping) else {}
        evidence_paths = _mapping_rows(claim.get("evidence_paths"))
        evidence = evidence_paths[0] if evidence_paths else {}
        doc_id = _text(canonical_form.get("subject")) or claim_id
        source_anchor_id = f"archive_source_anchor:{doc_id}"
        document_node_id = f"archive_document:{doc_id}"
        parse_node_id = f"archive_intent_parse:{doc_id}"
        candidate_node_id = f"archive_policy_candidate:{doc_id}"
        candidate_node_ids.append(candidate_node_id)
        authority_role = _text(qualifiers.get("authority_role"))
        if authority_role and authority_role not in review_authority_roles:
            review_authority_roles.append(authority_role)

        fragments.append(
            build_source_adapter_fragment(
                anchor_id=source_anchor_id,
                label=f"Brexit archive source anchor {doc_id}",
                metadata={
                    "doc_id": doc_id,
                    "collection": _text(qualifiers.get("collection")),
                    "anchor_date": _text(qualifiers.get("anchor_date")),
                    "source_url": _text((canonical_form.get("references") or [{}])[0].get("source_url", [""])[0])
                    if isinstance((canonical_form.get("references") or [{}])[0], Mapping)
                    else "",
                },
                target_id=document_node_id,
                edge_kind="archive_document_projection",
                edge_metadata={
                    "from_layer": "source_anchor",
                    "to_layer": "source_container",
                    "authority_surface": "brexit_archive_record",
                },
            )
        )
        fragments.append(
            build_document_adapter_fragment(
                node_id=document_node_id,
                label=f"Brexit archive document {doc_id}",
                metadata={
                    "doc_id": doc_id,
                    "collection": _text(qualifiers.get("collection")),
                    "authority_role": authority_role,
                    "intent_tags": list(qualifiers.get("intent_tags", []))
                    if isinstance(qualifiers.get("intent_tags"), Sequence)
                    else [],
                },
                target_id=parse_node_id,
                edge_kind="archive_intent_parse_projection",
                edge_metadata={
                    "from_layer": "source_container",
                    "to_layer": "parsed_form",
                    "authority_surface": "brexit_archive_record",
                },
            )
        )
        fragments.append(
            build_parse_adapter_fragment(
                node_id=parse_node_id,
                label=f"Brexit archive intent parse {doc_id}",
                metadata={
                    "doc_id": doc_id,
                    "title": _text(canonical_form.get("value")),
                    "authority_role": authority_role,
                    "intent_tags": list(qualifiers.get("intent_tags", []))
                    if isinstance(qualifiers.get("intent_tags"), Sequence)
                    else [],
                },
                target_id=candidate_node_id,
                edge_kind="archive_claim_candidate_projection",
                edge_metadata={
                    "from_layer": "parsed_form",
                    "to_layer": "domain_candidate",
                    "authority_surface": "brexit_archive_record",
                },
            )
        )
        fragments.append(
            build_claim_adapter_fragment(
                node_id=candidate_node_id,
                label=f"Brexit policy intent claim candidate {doc_id}",
                metadata={
                    "doc_id": doc_id,
                    "claim_id": claim_id,
                    "claim_status": _text(claim.get("status")),
                    "actionability": _text((claim.get("action_policy") or {}).get("actionability")),
                    "candidate_vs_promoted_visibility": True,
                },
                target_id=review_node_id,
                edge_kind="policy_intent_review_projection",
                edge_metadata={
                    "from_layer": "domain_candidate",
                    "to_layer": "review_surface",
                    "authority_surface": "brexit_policy_intent_review_surface",
                    "promotion_status": _text(claim.get("status")) or "review_only",
                },
            )
        )

    if not candidate_node_ids:
        raise ValueError("Brexit archive policy-intent linkage case requires at least one policy candidate")

    fragments.append(
        build_coalescence_adapter_fragment(
            node_id=review_node_id,
            label=f"Brexit policy intent review surface {artifact_id}",
            metadata={
                "lane_id": lane_id,
                "claim_count": len(claims),
                "must_review_count": int(report.get("summary", {}).get("must_review_count", 0) or 0),
                "candidate_vs_promoted_visibility": True,
            },
            upstream_node_ids=candidate_node_ids,
            edge_kind="policy_intent_review_projection",
            edge_metadata={
                "from_layer": "domain_candidate",
                "to_layer": "review_surface",
                "authority_surface": "brexit_policy_intent_review_surface",
                "promotion_status": "review_only",
            },
        )
    )
    fragments.append(
        build_authority_adapter_fragment(
            node_id=authority_node_id,
            label=f"Brexit archive authority surface {artifact_id}",
            metadata={
                "lane_id": lane_id,
                "authority_roles": review_authority_roles,
                "live_fetch_count": int(report.get("summary", {}).get("live_fetch_count", 0) or 0),
                "archive_authority_visibility": "complete" if review_authority_roles else "partial",
            },
            upstream_node_ids=[review_node_id],
            edge_kind="archive_authority_projection",
            edge_metadata={
                "from_layer": "review_surface",
                "to_layer": "authority_surface",
                "authority_surface": "brexit_archive_authority_surface",
            },
        )
    )
    fragments.append(
        build_tranche_adapter_fragment(
            node_id=tranche_node_id,
            label=f"Brexit workflow tranche anchor {artifact_id}",
            metadata={
                "lane_id": lane_id,
                "claim_count": len(claims),
                "must_review_count": int(report.get("summary", {}).get("must_review_count", 0) or 0),
                "authority_surface": "workflow_tranche_anchor",
            },
            upstream_node_ids=[authority_node_id],
            edge_kind="workflow_tranche_projection",
            edge_metadata={
                "from_layer": "authority_surface",
                "to_layer": "tranche_anchor",
                "authority_surface": "workflow_tranche_anchor",
                "promotion_status": "review_only",
            },
        )
    )

    fragment = merge_linkage_fragments(*fragments)
    return build_linkage_depth_case(
        case_id="brexit_archive_policy_intent",
        case_kind="archive_policy_fixture",
        lane_id=lane_id,
        contract_id=BREXIT_ARCHIVE_POLICY_INTENT_LINKAGE_CONTRACT_ID,
        case_source="emitted_bridge_artifact",
        notes=[
            "Brexit archive/policy-intent receipt composes archive provenance, intent parse, candidate, review, authority, and tranche layers over the shared core.",
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
            case_id=_text(receipt.get("case_id")) or "brexit_archive_policy_intent",
            case_kind="archive_policy_fixture",
            contract_id=_text((receipt.get("contract") or {}).get("contract_id"))
            or BREXIT_ARCHIVE_POLICY_INTENT_LINKAGE_CONTRACT_ID,
            expected_anchor_ids=receipt.get("expected_anchor_ids", []),
            expected_terminal_ids=receipt.get("expected_terminal_ids", []),
            nodes=receipt.get("nodes", []),
            edges=receipt.get("edges", []),
            lane_id=_text(receipt.get("lane_id")) or "brexit_national_archives_policy_intent",
            case_source=_text(receipt.get("source_mode")) or "emitted_bridge_artifact",
            notes=["Brexit archive policy-intent case loaded from emitted lane receipt."],
            contract=receipt.get("contract")
            if isinstance(receipt.get("contract"), Mapping)
            else build_contract(),
        )
    return _build_brexit_archive_policy_intent_case_payload(report)


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
    case = build_case(report)
    return build_linkage_depth_receipt(
        case=case,
        contract=contract_payload,
        receipt_id=f"linkage_depth:{case['case_id']}",
        source_mode="emitted_bridge_artifact",
        notes=[
            "Brexit archive/policy-intent receipt is attached only by the lane wrapper.",
        ],
    )


__all__ = [
    "BREXIT_ARCHIVE_POLICY_INTENT_LINKAGE_CONTRACT_ID",
    "build_case",
    "build_contract",
    "build_receipt",
]
