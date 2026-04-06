from __future__ import annotations

from typing import Any, Mapping, Sequence

from .compiler_contract import normalize_promoted_outcomes
from .diagnostic_graph_metrics import (
    build_graph_diagnostics,
    build_graph_revision_stability,
)


SUITE_NORMALIZED_ARTIFACT_SCHEMA_VERSION = "itir.normalized.artifact.v1"


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _nonempty_strings(values: Sequence[Any]) -> list[str]:
    seen: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.append(text)
    return seen


def _normalize_text_ref(candidate: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(candidate, Mapping):
        return None
    text_id = str(candidate.get("text_id") or "").strip()
    envelope_id = str(candidate.get("envelope_id") or "").strip()
    segment_ids = _nonempty_strings(candidate.get("segment_ids") or [])
    if not segment_ids:
        segment_id = str(candidate.get("segment_id") or "").strip()
        if segment_id:
            segment_ids = [segment_id]

    normalized: dict[str, Any] = {}
    if text_id:
        normalized["text_id"] = text_id
    if envelope_id:
        normalized["envelope_id"] = envelope_id
    if segment_ids:
        normalized["segment_ids"] = segment_ids
    return normalized or None


def _extract_text_ref(*candidates: Mapping[str, Any] | None) -> dict[str, Any] | None:
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        explicit = candidate.get("text_ref") if isinstance(candidate.get("text_ref"), Mapping) else candidate
        normalized = _normalize_text_ref(explicit)
        if normalized:
            return normalized
    return None


def _normalize_typing_deficit_signal(
    signal: Mapping[str, Any],
    *,
    default_source: str,
) -> dict[str, Any]:
    normalized = dict(signal)
    normalized.setdefault("signal_id", f"{default_source}:{len(str(normalized))}")
    normalized.setdefault("source", default_source)
    normalized.setdefault("signal_kind", "missing_instance_of_typing_deficit")
    return normalized


def build_suite_graph_diagnostics(
    *,
    graph_payload: Mapping[str, Any],
    source_artifact_id: str,
    source_lane: str,
    substrate_kind: str,
    projection_role: str,
    graph_version: str | None = None,
    cone_seed_node_kinds: Sequence[str],
    cone_allowed_edge_types: Sequence[str],
    cone_max_depth: int,
    baseline_graph_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    # Normalized artifacts own diagnostic attachment, but diagnostics stay derived-only.
    # Revision stability is omitted unless a caller supplies an explicit baseline pair.
    diagnostics = build_graph_diagnostics(
        graph_payload=graph_payload,
        source_artifact_id=source_artifact_id,
        source_lane=source_lane,
        substrate_kind=substrate_kind,
        projection_role=projection_role,
        graph_version=graph_version,
        cone_seed_node_kinds=cone_seed_node_kinds,
        cone_allowed_edge_types=cone_allowed_edge_types,
        cone_max_depth=cone_max_depth,
    )
    if isinstance(baseline_graph_diagnostics, Mapping):
        diagnostics["revision_stability"] = build_graph_revision_stability(
            baseline_diagnostics=baseline_graph_diagnostics,
            candidate_diagnostics=diagnostics,
        )
    return diagnostics


def _derive_unresolved_pressure(
    *,
    gate_decision: str,
    gate_reason: str,
    hold_scope: str,
    abstain_scope: str,
    abstain_stop_condition: str,
    hold_stop_condition: str,
) -> tuple[str, dict[str, Any] | None]:
    if gate_decision == "promote":
        return "none", None
    if gate_decision == "abstain":
        return "abstain", {
            "trigger": gate_reason or "no_promoted_outcomes",
            "scope": abstain_scope,
            "stop_condition": abstain_stop_condition,
        }
    return "hold", {
        "trigger": gate_reason or "mixed_promote_review_or_abstain_pressure",
        "scope": hold_scope,
        "stop_condition": hold_stop_condition,
    }


def build_au_fact_review_bundle_normalized_artifact(
    *,
    semantic_run_id: str,
    workflow_kind: str | None,
    compiler_contract: Mapping[str, Any],
    promotion_gate: Mapping[str, Any],
    source_documents: Sequence[Mapping[str, Any]],
    typing_deficit_signals: Sequence[Mapping[str, Any]] | None = None,
    graph_payload: Mapping[str, Any] | None = None,
    baseline_graph_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_bundle = (
        compiler_contract.get("evidence_bundle")
        if isinstance(compiler_contract.get("evidence_bundle"), Mapping)
        else {}
    )
    promoted_outcomes = normalize_promoted_outcomes(
        compiler_contract.get("promoted_outcomes")
        if isinstance(compiler_contract.get("promoted_outcomes"), Mapping)
        else None
    )
    gate_decision = str(promotion_gate.get("decision") or "").strip()
    gate_reason = str(promotion_gate.get("reason") or "").strip()

    review_count = _int(promoted_outcomes.get("review_count"))
    abstained_count = _int(promoted_outcomes.get("abstained_count"))
    unresolved_pressure_status, follow_obligation = _derive_unresolved_pressure(
        gate_decision=gate_decision,
        gate_reason=gate_reason,
        hold_scope="bounded_follow_or_review_of_open_au_fact_review_pressure",
        abstain_scope="bounded_manual_review_of_open_au_fact_review_pressure",
        abstain_stop_condition="stop after explicit abstain confirmation or new bounded evidence",
        hold_stop_condition="stop when open review or abstain pressure is cleared",
    )

    upstream_artifact_ids = _nonempty_strings(
        [
            semantic_run_id,
            *[
                row.get("doc_id")
                or row.get("source_document_id")
                or row.get("path")
                or row.get("label")
                for row in source_documents
                if isinstance(row, Mapping)
            ],
        ]
    )
    source_family = str(evidence_bundle.get("source_family") or "au_fact_review_bundle").strip()
    item_label = str(evidence_bundle.get("item_label") or "fact").strip()
    normalized_signals = [
        _normalize_typing_deficit_signal(signal, default_source="au")
        for signal in typing_deficit_signals or []
        if isinstance(signal, Mapping)
    ]
    text_ref = _extract_text_ref(
        *[row for row in source_documents if isinstance(row, Mapping)],
    )

    artifact = {
        "schema_version": SUITE_NORMALIZED_ARTIFACT_SCHEMA_VERSION,
        "artifact_role": "derived_product",
        "artifact_id": f"au.fact_review_bundle:{semantic_run_id}",
        "canonical_identity": {
            "identity_class": "fact_review_run",
            "identity_key": semantic_run_id,
            "aliases": [f"au:{source_family}", "au_fact_review_bundle"],
        },
        "provenance_anchor": {
            "source_system": "SensibLaw",
            "source_artifact_id": semantic_run_id,
            "anchor_kind": "semantic_run_id",
            "anchor_ref": "semantic_context.suite_normalized_artifact",
        },
        "context_envelope_ref": {
            "envelope_id": semantic_run_id,
            "envelope_kind": workflow_kind or "au_semantic",
        },
        "authority": {
            "authority_class": "derived_inspection",
            "derived": True,
            "promotion_receipt_ref": None,
        },
        "lineage": {
            "upstream_artifact_ids": upstream_artifact_ids,
            "profile_version": str(compiler_contract.get("schema_version") or ""),
        },
        "follow_obligation": follow_obligation,
        "unresolved_pressure_status": unresolved_pressure_status,
        "summary": {
            "lane": str(compiler_contract.get("lane") or "au"),
            "source_family": source_family,
            "item_label": item_label,
            "source_count": _int(evidence_bundle.get("source_count")),
            "item_count": _int(evidence_bundle.get("item_count")),
            "promoted_count": _int(promoted_outcomes.get("promoted_count")),
            "review_count": review_count,
            "abstained_count": abstained_count,
            "product_ref": str(promotion_gate.get("product_ref") or "au_fact_review_bundle"),
            "gate_decision": gate_decision,
        },
        "typing_deficit_signals": normalized_signals,
    }
    if text_ref:
        artifact["text_ref"] = text_ref
    if isinstance(graph_payload, Mapping):
        artifact["graph_diagnostics"] = build_suite_graph_diagnostics(
            graph_payload=graph_payload,
            source_artifact_id=semantic_run_id,
            source_lane=str(compiler_contract.get("lane") or "au"),
            substrate_kind="legal_follow_graph",
            projection_role="suite_normalized_artifact",
            graph_version=str(graph_payload.get("version") or ""),
            cone_seed_node_kinds=("event",),
            cone_allowed_edge_types=(
                "mentions_authority_title",
                "mentions_legal_ref",
                "mentions_case_ref",
                "mentions_supporting_legislation",
                "mentions_cited_instrument",
                "mentions_citation",
            ),
            cone_max_depth=1,
            baseline_graph_diagnostics=baseline_graph_diagnostics,
        )
    return artifact


def build_gwb_public_review_normalized_artifact(
    *,
    artifact_id: str,
    compiler_contract: Mapping[str, Any],
    promotion_gate: Mapping[str, Any],
    source_input: Mapping[str, Any],
    workflow_summary: Mapping[str, Any],
    graph_payload: Mapping[str, Any] | None = None,
    baseline_graph_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_bundle = (
        compiler_contract.get("evidence_bundle")
        if isinstance(compiler_contract.get("evidence_bundle"), Mapping)
        else {}
    )
    promoted_outcomes = normalize_promoted_outcomes(
        compiler_contract.get("promoted_outcomes")
        if isinstance(compiler_contract.get("promoted_outcomes"), Mapping)
        else None
    )
    gate_decision = str(promotion_gate.get("decision") or "").strip()
    gate_reason = str(promotion_gate.get("reason") or "").strip()
    workflow_stage = str(workflow_summary.get("stage") or "").strip()
    recommended_view = str(workflow_summary.get("recommended_view") or "").strip()
    unresolved_pressure_status, follow_obligation = _derive_unresolved_pressure(
        gate_decision=gate_decision,
        gate_reason=gate_reason,
        hold_scope="bounded_follow_or_review_of_open_gwb_public_review_pressure",
        abstain_scope="bounded_manual_review_of_open_gwb_public_review_pressure",
        abstain_stop_condition="stop after explicit abstain confirmation or new bounded evidence",
        hold_stop_condition="stop when open review or legal-follow pressure is cleared",
    )

    source_family = str(evidence_bundle.get("source_family") or "gwb_public_review").strip()
    item_label = str(evidence_bundle.get("item_label") or "source_row").strip()
    source_ref = str(source_input.get("path") or artifact_id).strip()
    text_ref = _extract_text_ref(source_input)
    artifact = {
        "schema_version": SUITE_NORMALIZED_ARTIFACT_SCHEMA_VERSION,
        "artifact_role": "derived_product",
        "artifact_id": f"gwb.public_review:{artifact_id}",
        "canonical_identity": {
            "identity_class": "gwb_review_run",
            "identity_key": artifact_id,
            "aliases": [f"gwb:{source_family}", artifact_id],
        },
        "provenance_anchor": {
            "source_system": "SensibLaw",
            "source_artifact_id": source_ref,
            "anchor_kind": "gwb_public_review",
            "anchor_ref": "suite_normalized_artifact",
        },
        "context_envelope_ref": {
            "envelope_id": artifact_id,
            "envelope_kind": "gwb_public_review",
        },
        "authority": {
            "authority_class": "derived_inspection",
            "derived": True,
            "promotion_receipt_ref": None,
        },
        "lineage": {
            "upstream_artifact_ids": [source_ref],
            "profile_version": str(compiler_contract.get("schema_version") or ""),
        },
        "follow_obligation": follow_obligation,
        "unresolved_pressure_status": unresolved_pressure_status,
        "summary": {
            "lane": str(compiler_contract.get("lane") or "gwb"),
            "source_family": source_family,
            "item_label": item_label,
            "source_count": _int(evidence_bundle.get("source_count")),
            "item_count": _int(evidence_bundle.get("item_count")),
            "promoted_count": _int(promoted_outcomes.get("promoted_count")),
            "review_count": _int(promoted_outcomes.get("review_count")),
            "abstained_count": _int(promoted_outcomes.get("abstained_count")),
            "product_ref": str(promotion_gate.get("product_ref") or artifact_id),
            "gate_decision": gate_decision,
            "workflow_stage": workflow_stage,
            "recommended_view": recommended_view,
        },
    }
    if text_ref:
        artifact["text_ref"] = text_ref
    if isinstance(graph_payload, Mapping):
        artifact["graph_diagnostics"] = build_suite_graph_diagnostics(
            graph_payload=graph_payload,
            source_artifact_id=source_ref,
            source_lane=str(compiler_contract.get("lane") or "gwb"),
            substrate_kind="legal_follow_graph",
            projection_role="suite_normalized_artifact",
            graph_version=str(graph_payload.get("version") or ""),
            cone_seed_node_kinds=("seed_lane",),
            cone_allowed_edge_types=("supports_source_row", "follows_source"),
            cone_max_depth=2,
            baseline_graph_diagnostics=baseline_graph_diagnostics,
        )
    return artifact


def build_gwb_broader_review_normalized_artifact(
    *,
    artifact_id: str,
    compiler_contract: Mapping[str, Any],
    promotion_gate: Mapping[str, Any],
    source_input: Mapping[str, Any],
    workflow_summary: Mapping[str, Any],
    graph_payload: Mapping[str, Any] | None = None,
    baseline_graph_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_bundle = (
        compiler_contract.get("evidence_bundle")
        if isinstance(compiler_contract.get("evidence_bundle"), Mapping)
        else {}
    )
    promoted_outcomes = normalize_promoted_outcomes(
        compiler_contract.get("promoted_outcomes")
        if isinstance(compiler_contract.get("promoted_outcomes"), Mapping)
        else None
    )
    gate_decision = str(promotion_gate.get("decision") or "").strip()
    gate_reason = str(promotion_gate.get("reason") or "").strip()
    workflow_stage = str(workflow_summary.get("stage") or "").strip()
    recommended_view = str(workflow_summary.get("recommended_view") or "").strip()
    unresolved_pressure_status, follow_obligation = _derive_unresolved_pressure(
        gate_decision=gate_decision,
        gate_reason=gate_reason,
        hold_scope="bounded_follow_or_review_of_open_gwb_broader_review_pressure",
        abstain_scope="bounded_manual_review_of_open_gwb_broader_review_pressure",
        abstain_stop_condition="stop after explicit abstain confirmation or new bounded evidence",
        hold_stop_condition="stop when open review, archive-follow, or legal-follow pressure is cleared",
    )

    source_family = str(evidence_bundle.get("source_family") or "gwb_broader_review").strip()
    item_label = str(evidence_bundle.get("item_label") or "source_row").strip()
    source_ref = str(source_input.get("path") or artifact_id).strip()
    text_ref = _extract_text_ref(source_input)
    artifact = {
        "schema_version": SUITE_NORMALIZED_ARTIFACT_SCHEMA_VERSION,
        "artifact_role": "derived_product",
        "artifact_id": f"gwb.broader_review:{artifact_id}",
        "canonical_identity": {
            "identity_class": "gwb_review_run",
            "identity_key": artifact_id,
            "aliases": [f"gwb:{source_family}", artifact_id],
        },
        "provenance_anchor": {
            "source_system": "SensibLaw",
            "source_artifact_id": source_ref,
            "anchor_kind": "gwb_broader_review",
            "anchor_ref": "suite_normalized_artifact",
        },
        "context_envelope_ref": {
            "envelope_id": artifact_id,
            "envelope_kind": "gwb_broader_review",
        },
        "authority": {
            "authority_class": "derived_inspection",
            "derived": True,
            "promotion_receipt_ref": None,
        },
        "lineage": {
            "upstream_artifact_ids": [source_ref],
            "profile_version": str(compiler_contract.get("schema_version") or ""),
        },
        "follow_obligation": follow_obligation,
        "unresolved_pressure_status": unresolved_pressure_status,
        "summary": {
            "lane": str(compiler_contract.get("lane") or "gwb"),
            "source_family": source_family,
            "item_label": item_label,
            "source_count": _int(evidence_bundle.get("source_count")),
            "item_count": _int(evidence_bundle.get("item_count")),
            "promoted_count": _int(promoted_outcomes.get("promoted_count")),
            "review_count": _int(promoted_outcomes.get("review_count")),
            "abstained_count": _int(promoted_outcomes.get("abstained_count")),
            "product_ref": str(promotion_gate.get("product_ref") or artifact_id),
            "gate_decision": gate_decision,
            "workflow_stage": workflow_stage,
            "recommended_view": recommended_view,
        },
    }
    if text_ref:
        artifact["text_ref"] = text_ref
    if isinstance(graph_payload, Mapping):
        artifact["graph_diagnostics"] = build_suite_graph_diagnostics(
            graph_payload=graph_payload,
            source_artifact_id=source_ref,
            source_lane=str(compiler_contract.get("lane") or "gwb"),
            substrate_kind="legal_follow_graph",
            projection_role="suite_normalized_artifact",
            graph_version=str(graph_payload.get("version") or ""),
            cone_seed_node_kinds=("seed_lane",),
            cone_allowed_edge_types=("supports_source_row", "follows_source"),
            cone_max_depth=2,
            baseline_graph_diagnostics=baseline_graph_diagnostics,
        )
    return artifact


def build_affidavit_coverage_review_normalized_artifact(
    *,
    artifact_id: str,
    compiler_contract: Mapping[str, Any],
    promotion_gate: Mapping[str, Any],
    source_input: Mapping[str, Any],
    workflow_summary: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_bundle = (
        compiler_contract.get("evidence_bundle")
        if isinstance(compiler_contract.get("evidence_bundle"), Mapping)
        else {}
    )
    promoted_outcomes = normalize_promoted_outcomes(
        compiler_contract.get("promoted_outcomes")
        if isinstance(compiler_contract.get("promoted_outcomes"), Mapping)
        else None
    )
    gate_decision = str(promotion_gate.get("decision") or "").strip()
    gate_reason = str(promotion_gate.get("reason") or "").strip()
    workflow_stage = str(workflow_summary.get("stage") or "").strip()
    recommended_view = str(workflow_summary.get("recommended_view") or "").strip()
    unresolved_pressure_status, follow_obligation = _derive_unresolved_pressure(
        gate_decision=gate_decision,
        gate_reason=gate_reason,
        hold_scope="bounded_follow_or_review_of_open_affidavit_coverage_review_pressure",
        abstain_scope="bounded_manual_review_of_open_affidavit_coverage_review_pressure",
        abstain_stop_condition="stop after explicit abstain confirmation or new bounded evidence",
        hold_stop_condition="stop when open review or abstain pressure is cleared",
    )

    source_family = str(evidence_bundle.get("source_family") or "affidavit_coverage_review").strip()
    item_label = str(evidence_bundle.get("item_label") or "affidavit_proposition").strip()
    source_ref = str(source_input.get("path") or artifact_id).strip()
    artifact = {
        "schema_version": SUITE_NORMALIZED_ARTIFACT_SCHEMA_VERSION,
        "artifact_role": "derived_product",
        "artifact_id": f"affidavit.coverage_review:{artifact_id}",
        "canonical_identity": {
            "identity_class": "affidavit_review_run",
            "identity_key": artifact_id,
            "aliases": [f"affidavit:{source_family}", artifact_id],
        },
        "provenance_anchor": {
            "source_system": "SensibLaw",
            "source_artifact_id": source_ref,
            "anchor_kind": "affidavit_coverage_review",
            "anchor_ref": "suite_normalized_artifact",
        },
        "context_envelope_ref": {
            "envelope_id": artifact_id,
            "envelope_kind": "affidavit_coverage_review",
        },
        "authority": {
            "authority_class": "derived_inspection",
            "derived": True,
            "promotion_receipt_ref": None,
        },
        "lineage": {
            "upstream_artifact_ids": [source_ref],
            "profile_version": str(compiler_contract.get("schema_version") or ""),
        },
        "follow_obligation": follow_obligation,
        "unresolved_pressure_status": unresolved_pressure_status,
        "summary": {
            "lane": str(compiler_contract.get("lane") or "affidavit"),
            "source_family": source_family,
            "item_label": item_label,
            "source_count": _int(evidence_bundle.get("source_count")),
            "item_count": _int(evidence_bundle.get("item_count")),
            "promoted_count": _int(promoted_outcomes.get("promoted_count")),
            "review_count": _int(promoted_outcomes.get("review_count")),
            "abstained_count": _int(promoted_outcomes.get("abstained_count")),
            "product_ref": str(promotion_gate.get("product_ref") or artifact_id),
            "gate_decision": gate_decision,
            "workflow_stage": workflow_stage,
            "recommended_view": recommended_view,
        },
    }
    text_ref = _extract_text_ref(source_input)
    if text_ref:
        artifact["text_ref"] = text_ref
    return artifact
