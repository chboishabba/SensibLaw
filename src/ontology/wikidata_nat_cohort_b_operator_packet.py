from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from src.models.action_policy import ACTION_POLICY_SCHEMA_VERSION
from src.models.convergence import CONVERGENCE_SCHEMA_VERSION
from src.models.conflict import CONFLICT_SCHEMA_VERSION
from src.models.nat_claim import NAT_CLAIM_SCHEMA_VERSION
from src.models.temporal import TEMPORAL_SCHEMA_VERSION
from src.policy.linkage_adapters import (
    build_collection_adapter_fragment,
    build_projection_adapter_fragment,
    build_source_adapter_fragment,
    build_tranche_adapter_fragment,
    merge_linkage_fragments,
)
from src.policy.linkage_depth import build_linkage_depth_case
from src.policy.world_model import build_world_model as build_candidate_world_model
from src.policy.world_model_adapters import (
    ClaimStateRecordMapping,
    build_authority_surface_rows,
    build_claim_state_records,
)
from src.policy.world_model_profiles import build_profile
from src.policy.world_model_projections import (
    project_claim_table,
    project_linkage_case,
    project_report as project_world_model_report,
    project_review_surface,
)

WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_b_operator_packet.v0_1"
)
WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_WORLD_MODEL_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_b_operator_packet_world_model.v0_1"
)
NAT_COHORT_B_OPERATOR_PACKET_LINKAGE_CONTRACT_ID = (
    "wikidata_nat_cohort_b_operator_packet_review_linkage"
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return sorted({_stringify(item) for item in value if _stringify(item)})


def _normalize_review_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("review_bucket_rows", [])
    if not isinstance(rows, list):
        raise ValueError("review bucket payload requires review_bucket_rows list")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("review bucket rows must be objects")
        variance_flags = _string_list(row.get("variance_flags", []))
        normalized.append(
            {
                "row_id": _stringify(row.get("row_id")),
                "entity_qid": _stringify(row.get("entity_qid")),
                "instance_of_qid": _stringify(row.get("instance_of_qid")),
                "variance_flags": variance_flags,
                "reviewer_questions": _string_list(row.get("reviewer_questions", [])),
            }
        )
    normalized.sort(
        key=lambda item: (-len(item["variance_flags"]), item["instance_of_qid"], item["row_id"])
    )
    return normalized


def _variance_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for flag in row.get("variance_flags", []):
            key = _stringify(flag)
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _triage_prompts(*, decision: str, counts: Mapping[str, int], violations: Sequence[Mapping[str, Any]]) -> list[str]:
    if decision == "hold":
        if violations:
            return [
                "Payload violated the Cohort B contract; remove out-of-lane rows and retry.",
                "Do not produce operator review packets for rows with unreconciled or business-family instance-of classes.",
            ]
        return [
            "No valid Cohort B rows were available; hold and refresh bounded candidate materialization.",
        ]

    prompts = [
        "Review highest-variance Cohort B rows first; keep lane review-only.",
        "Confirm class-local semantics before any migration-equivalence judgment.",
    ]
    if counts.get("unexpected_qualifier_properties", 0) > 0:
        prompts.append("Inspect unexpected qualifier properties as potential class-specific semantics.")
    if counts.get("unexpected_reference_properties", 0) > 0:
        prompts.append("Inspect unexpected reference properties for citation-shape drift.")
    if counts.get("mixed_temporal_qualifier_resolution", 0) > 0:
        prompts.append("Resolve temporal qualifier-mode mixing before downstream decisions.")
    return prompts


def build_nat_cohort_b_operator_packet(
    review_bucket_payload: Mapping[str, Any],
    *,
    max_rows: int = 5,
) -> dict[str, Any]:
    if not isinstance(review_bucket_payload, Mapping):
        raise ValueError("Cohort B operator packet requires review bucket payload object")
    if _stringify(review_bucket_payload.get("cohort_id")) != "cohort_b_reconciled_non_business":
        raise ValueError("Cohort B operator packet requires cohort_b_reconciled_non_business payload")

    source_decision = _stringify(review_bucket_payload.get("decision")) or "hold"
    if source_decision not in {"review_only", "hold"}:
        raise ValueError("review bucket decision must be review_only or hold")

    violations = [
        {"row_id": _stringify(item.get("row_id")), "violation": _stringify(item.get("violation"))}
        for item in review_bucket_payload.get("contract_violations", [])
        if isinstance(item, Mapping)
    ]
    rows = _normalize_review_rows(review_bucket_payload)
    if source_decision == "hold" and rows:
        raise ValueError("hold review bucket payload must not contain review rows")

    packet_decision = "review" if source_decision == "review_only" and rows else "hold"
    if packet_decision == "hold":
        selected_rows: list[dict[str, Any]] = []
    else:
        selected_rows = rows[: max(0, max_rows)]

    counts = _variance_counts(selected_rows if selected_rows else rows)
    packet_id = hashlib.sha1(
        json.dumps(
            {
                "lane_id": _stringify(review_bucket_payload.get("lane_id")),
                "cohort_id": "cohort_b_reconciled_non_business",
                "packet_decision": packet_decision,
                "row_ids": [row["row_id"] for row in selected_rows],
                "violation_keys": [item["violation"] for item in violations],
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "schema_version": WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION,
        "packet_id": f"operator-packet:{packet_id}",
        "lane_id": _stringify(review_bucket_payload.get("lane_id")),
        "cohort_id": "cohort_b_reconciled_non_business",
        "decision": packet_decision,
        "source_bucket_decision": source_decision,
        "triage_prompts": _triage_prompts(
            decision=packet_decision,
            counts=counts,
            violations=violations,
        ),
        "selected_rows": selected_rows,
        "summary": {
            "selected_row_count": len(selected_rows),
            "source_review_row_count": len(rows),
            "contract_violation_count": len(violations),
            "variance_flag_counts": counts,
            "review_first": True,
        },
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
            "requires_human_review": True,
        },
        "contract_violations": violations,
        "non_claims": [
            "operator review packet only",
            "not migration execution",
            "not cross-cohort routing",
        ],
    }


def _packet_context(operator_packet: Mapping[str, Any]) -> dict[str, Any]:
    packet_id = _stringify(operator_packet.get("packet_id"))
    lane_id = _stringify(operator_packet.get("lane_id"))
    cohort_id = _stringify(operator_packet.get("cohort_id"))
    return {
        "packet_id": packet_id,
        "lane_id": lane_id,
        "cohort_id": cohort_id,
    }


def build_nat_cohort_b_operator_packet_world_model(
    operator_packet: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(operator_packet, Mapping):
        raise ValueError("world model requires operator packet object")
    if _stringify(operator_packet.get("schema_version")) != WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION:
        raise ValueError("world model requires Cohort B operator packet payload")

    context = _packet_context(operator_packet)
    selected_rows = operator_packet.get("selected_rows", [])
    if not isinstance(selected_rows, Sequence) or isinstance(selected_rows, (str, bytes, bytearray)):
        selected_rows = []

    mapping = ClaimStateRecordMapping(
        claim_id="row_id",
        candidate_id="row_id",
        cohort_id=lambda _row, ctx: ctx["cohort_id"],
        canonical_form=lambda row, ctx: {
            "subject": _stringify(row.get("entity_qid")),
            "property": "instance_of_review",
            "value": _stringify(row.get("instance_of_qid")),
            "qualifiers": {
                "variance_flags": _string_list(row.get("variance_flags", [])),
                "reviewer_questions": _string_list(row.get("reviewer_questions", [])),
            },
            "references": [],
            "window_id": ctx["packet_id"],
        },
        source_family=lambda _row, _ctx: "reviewer_packet",
        authority_level=lambda _row, _ctx: "review_packet",
        claim_status=lambda _row, _ctx: "REVIEW_ONLY",
        evidence_status=lambda _row, _ctx: "review_only",
        root_artifact_id=lambda _row, ctx: ctx["packet_id"],
        source_property=lambda _row, _ctx: "review_packet",
        target_property=lambda _row, _ctx: "review_packet",
        state_basis=lambda _row, _ctx: "review_packet",
        nat_claim_state=lambda _row, _ctx: "review_claim",
        provenance_chain=lambda row, ctx: {
            "packet_id": ctx["packet_id"],
            "lane_id": ctx["lane_id"],
            "cohort_id": ctx["cohort_id"],
            "entity_qid": _stringify(row.get("entity_qid")),
            "instance_of_qid": _stringify(row.get("instance_of_qid")),
        },
    )
    claims = build_claim_state_records(
        [row for row in selected_rows if isinstance(row, Mapping)],
        family_id=context["lane_id"],
        mapping=mapping,
        context=context,
    )
    profile = build_profile(
        profile_id="nat_cohort_b_operator_packet",
        lane_family="nat",
        source_kinds=["wikidata_operator_packet"],
        authority_surfaces=[
            "review_packet",
            "operator_review_surface",
            "workflow_tranche_anchor",
        ],
        promotion_policy="review_only",
        default_projection_kinds=["report", "claim_table", "review_surface", "linkage_case"],
        metadata={"lane_id": context["lane_id"], "cohort_id": context["cohort_id"]},
    )
    summary = {
        "claim_count": len(claims),
        "must_review_count": sum(
            1 for claim in claims if _stringify(claim.get("action_policy", {}).get("actionability")) == "must_review"
        ),
        "must_abstain_count": sum(
            1 for claim in claims if _stringify(claim.get("action_policy", {}).get("actionability")) == "must_abstain"
        ),
    }
    return build_candidate_world_model(
        model_id=context["packet_id"] or "nat_cohort_b_operator_packet",
        lane_family="nat",
        model_status="candidate",
        source_mode="wikidata_operator_packet_review",
        claims=claims,
        authority_surfaces=build_authority_surface_rows(profile["authority_surfaces"]),
        summary=summary,
        metadata={
            "profile": profile,
            "packet_id": context["packet_id"],
            "lane_id": context["lane_id"],
            "cohort_id": context["cohort_id"],
            "decision": _stringify(operator_packet.get("decision")) or "hold",
            "triage_prompts": _string_list(operator_packet.get("triage_prompts")),
            "governance": dict(operator_packet.get("governance"))
            if isinstance(operator_packet.get("governance"), Mapping)
            else {},
            "selected_rows": [dict(row) for row in selected_rows if isinstance(row, Mapping)],
        },
    )


def _build_linkage_projection(world_model: Mapping[str, Any]) -> dict[str, Any]:
    metadata = world_model.get("metadata") if isinstance(world_model.get("metadata"), Mapping) else {}
    selected_rows = metadata.get("selected_rows") if isinstance(metadata.get("selected_rows"), Sequence) else []
    packet_id = _stringify(metadata.get("packet_id")) or "operator-packet"
    lane_id = _stringify(metadata.get("lane_id")) or "nat"
    review_surface_id = f"operator_review_surface:{packet_id}"
    tranche_anchor_id = f"workflow_tranche_anchor:{packet_id}"
    review_node_ids: list[str] = []
    fragments: list[dict[str, Any]] = []

    for row in selected_rows:
        if not isinstance(row, Mapping):
            continue
        row_id = _stringify(row.get("row_id"))
        if not row_id:
            continue
        source_anchor_id = f"source_anchor:{row_id}"
        review_candidate_id = f"review_candidate:{row_id}"
        review_node_ids.append(review_candidate_id)
        fragments.append(
            build_source_adapter_fragment(
                anchor_id=source_anchor_id,
                label=f"Wikidata operator packet source anchor {row_id}",
                metadata={
                    "row_id": row_id,
                    "entity_qid": _stringify(row.get("entity_qid")),
                    "instance_of_qid": _stringify(row.get("instance_of_qid")),
                },
                target_id=review_candidate_id,
                edge_kind="review_candidate_projection",
                edge_metadata={
                    "from_layer": "source_anchor",
                    "to_layer": "review_surface",
                    "authority_surface": "review_packet",
                    "promotion_status": "review_only",
                },
            )
        )
        fragments.append(
            build_projection_adapter_fragment(
                layer="review_surface",
                node_id=review_candidate_id,
                label=f"Wikidata operator review candidate {row_id}",
                metadata={
                    "row_id": row_id,
                    "variance_flags": _string_list(row.get("variance_flags")),
                    "candidate_vs_promoted_visibility": True,
                },
                target_id=review_surface_id,
                edge_kind="operator_review_projection",
                edge_metadata={
                    "from_layer": "review_surface",
                    "to_layer": "authority_surface",
                    "authority_surface": "operator_review_surface",
                    "promotion_status": "review_only",
                },
            )
        )

    fragments.append(
        build_collection_adapter_fragment(
            layer="authority_surface",
            node_id=review_surface_id,
            label=f"Wikidata operator review surface {packet_id}",
            metadata={
                "lane_id": lane_id,
                "packet_id": packet_id,
                "review_row_count": len(review_node_ids),
                "authority_surface": "operator_review_surface",
            },
            upstream_node_ids=review_node_ids,
            edge_kind="operator_review_projection",
            edge_metadata={
                "from_layer": "review_surface",
                "to_layer": "authority_surface",
                "authority_surface": "operator_review_surface",
                "promotion_status": "review_only",
            },
        )
    )
    fragments.append(
        build_tranche_adapter_fragment(
            node_id=tranche_anchor_id,
            label=f"Wikidata operator tranche anchor {packet_id}",
            metadata={
                "packet_id": packet_id,
                "lane_id": lane_id,
                "authority_surface": "workflow_tranche_anchor",
            },
            upstream_node_ids=[review_surface_id],
            edge_kind="workflow_tranche_projection",
            edge_metadata={
                "from_layer": "authority_surface",
                "to_layer": "tranche_anchor",
                "authority_surface": "workflow_tranche_anchor",
                "promotion_status": "review_only",
            },
        )
    )
    merged = merge_linkage_fragments(*fragments)
    case = build_linkage_depth_case(
        case_id="nat_cohort_b_operator_packet",
        case_kind="wd_operator_review_fixture",
        lane_id=lane_id,
        contract_id=NAT_COHORT_B_OPERATOR_PACKET_LINKAGE_CONTRACT_ID,
        case_source="projected_world_model_artifact",
        notes=[
            "Cohort B operator packet is projected through the shared world-model/projection stack.",
            "This compatibility surface preserves source anchor, review candidate, authority surface, and tranche depth.",
        ],
        expected_anchor_ids=merged.get("expected_anchor_ids", []),
        expected_terminal_ids=[tranche_anchor_id],
        nodes=merged.get("nodes", []),
        edges=merged.get("edges", []),
    )
    return project_linkage_case(
        world_model,
        case_id=case["case_id"],
        contract_id=NAT_COHORT_B_OPERATOR_PACKET_LINKAGE_CONTRACT_ID,
        nodes=case["nodes"],
        edges=case["edges"],
        expected_anchor_ids=case["expected_anchor_ids"],
        expected_terminal_ids=case["expected_terminal_ids"],
        notes=case["notes"],
        metadata={
            "projection_role": "linkage_case",
            "lane_id": lane_id,
            "contract_id": NAT_COHORT_B_OPERATOR_PACKET_LINKAGE_CONTRACT_ID,
        },
    )


def build_nat_cohort_b_operator_packet_world_model_report(
    operator_packet: Mapping[str, Any],
) -> dict[str, Any]:
    world_model = build_nat_cohort_b_operator_packet_world_model(operator_packet)
    metadata = world_model.get("metadata") if isinstance(world_model.get("metadata"), Mapping) else {}
    lane_id = _stringify(metadata.get("lane_id"))
    packet_id = _stringify(metadata.get("packet_id"))
    claim_table = project_claim_table(
        world_model,
        claim_rows=world_model.get("claims"),
        metadata={"profile_id": "nat_cohort_b_operator_packet"},
    )
    review_surface = project_review_surface(
        world_model,
        review_rows=metadata.get("selected_rows") if isinstance(metadata.get("selected_rows"), Sequence) else [],
        workflow_summary={
            "decision": _stringify(metadata.get("decision")) or "hold",
            "review_first": True,
        },
        metadata={"profile_id": "nat_cohort_b_operator_packet"},
    )
    linkage_case = _build_linkage_projection(world_model)
    return project_world_model_report(
        world_model,
        schema_version=WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_WORLD_MODEL_SCHEMA_VERSION,
        artifact_id=packet_id,
        lane_id=lane_id,
        family_id="nat_cohort_b_operator_packet",
        workflow_summary=review_surface["payload"]["workflow_summary"],
        claims=world_model.get("claims"),
        summary=world_model.get("summary") if isinstance(world_model.get("summary"), Mapping) else None,
        projection_metadata={"profile_id": "nat_cohort_b_operator_packet"},
        extra_fields={
            "claim_schema_version": NAT_CLAIM_SCHEMA_VERSION,
            "convergence_schema_version": CONVERGENCE_SCHEMA_VERSION,
            "temporal_schema_version": TEMPORAL_SCHEMA_VERSION,
            "conflict_schema_version": CONFLICT_SCHEMA_VERSION,
            "action_policy_schema_version": ACTION_POLICY_SCHEMA_VERSION,
            "packet_id": packet_id,
            "cohort_id": _stringify(metadata.get("cohort_id")),
            "decision": _stringify(metadata.get("decision")) or "hold",
            "triage_prompts": _string_list(metadata.get("triage_prompts")),
            "governance": dict(metadata.get("governance")) if isinstance(metadata.get("governance"), Mapping) else {},
            "review_surface": review_surface,
            "claim_table": claim_table,
            "linkage_case": linkage_case,
        },
    )


__all__ = [
    "WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION",
    "WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_WORLD_MODEL_SCHEMA_VERSION",
    "build_nat_cohort_b_operator_packet",
    "build_nat_cohort_b_operator_packet_world_model",
    "build_nat_cohort_b_operator_packet_world_model_report",
]
