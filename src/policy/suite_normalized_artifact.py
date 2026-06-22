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


_TRANSPORT_REVIEW_PACKET_EXCLUDED_FIELDS = {
    "body",
    "char_end",
    "char_start",
    "content",
    "diagnostic",
    "diagnostics",
    "end",
    "excerpt",
    "excerpt_text",
    "full_receipt",
    "full_receipts",
    "full_text",
    "graph_diagnostics",
    "logs",
    "message",
    "object_uri",
    "object_uris",
    "object_url",
    "object_urls",
    "raw_text",
    "receipt",
    "receipts",
    "span",
    "span_end",
    "span_start",
    "spans",
    "start",
    "text",
    "token_end",
    "token_start",
    "sink_uri",
    "sink_uris",
    "sink_url",
    "sink_urls",
    "trace",
    "transport_object_uri",
    "transport_object_uris",
    "transport_sink_uri",
    "transport_sink_uris",
}


def _strip_transport_review_packet_fields(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in _TRANSPORT_REVIEW_PACKET_EXCLUDED_FIELDS:
                continue
            normalized[key_text] = _strip_transport_review_packet_fields(item)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_strip_transport_review_packet_fields(item) for item in value]
    return value


def _normalize_transport_projection_refs(values: Sequence[Any]) -> list[str]:
    return _nonempty_strings(values)


def _optional_projection_count(
    *sources: Mapping[str, Any],
    keys: Sequence[str],
) -> int | None:
    for source in sources:
        for key in keys:
            if key in source:
                return _int(source.get(key))
    return None


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
        if isinstance(graph_payload.get("pressure"), Mapping):
            artifact["legal_follow_pressure"] = dict(graph_payload.get("pressure") or {})
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


def _strip_sink_uri_fields(value: Any) -> Any:
    return _strip_transport_review_packet_fields(value)


def _build_transport_review_packet_projection(
    *,
    artifact_id: str,
    artifact_revision: str,
    artifact_class: str,
    selectors: Sequence[Any],
    selected_shard_ids: Sequence[str],
    selected_sections: Sequence[str],
    upstream_artifact_ids: Sequence[str],
    build_provenance: Mapping[str, Any] | None,
    source_system: str,
) -> dict[str, Any]:
    provenance_source = dict(build_provenance) if isinstance(build_provenance, Mapping) else {}
    normalized_selectors = [
        _strip_transport_review_packet_fields(selector)
        for selector in selectors
        if isinstance(selector, Mapping)
    ]
    candidate_facts = [
        {"fact_kind": "selected_shard", "fact_ref": shard_id}
        for shard_id in selected_shard_ids
    ]
    candidate_facts.extend(
        {"fact_kind": "selected_section", "fact_ref": section_id}
        for section_id in selected_sections
    )
    candidate_refs = _normalize_transport_projection_refs(
        [selector.get("selector_id") for selector in selectors if isinstance(selector, Mapping)]
    )
    provenance_refs = _normalize_transport_projection_refs(
        [
            *upstream_artifact_ids,
            artifact_id,
            artifact_revision,
            provenance_source.get("build_id"),
            provenance_source.get("source_run_id"),
            provenance_source.get("source_artifact_id"),
            provenance_source.get("anchor_ref"),
            "semantic_context.suite_normalized_artifact",
        ]
    )
    citation_refs = _normalize_transport_projection_refs(
        [
            *candidate_refs,
            *[
                ref
                for selector in selectors
                if isinstance(selector, Mapping)
                for ref in (
                    [selector.get("citation_ref")]
                    + (
                        list(selector.get("citation_refs"))
                        if isinstance(selector.get("citation_refs"), Sequence)
                        and not isinstance(selector.get("citation_refs"), (str, bytes, bytearray))
                        else []
                    )
                    + (
                        list(selector.get("provenance_refs"))
                        if isinstance(selector.get("provenance_refs"), Sequence)
                        and not isinstance(selector.get("provenance_refs"), (str, bytes, bytearray))
                        else []
                    )
                )
            ],
        ]
    )
    support_count = _optional_projection_count(
        provenance_source,
        *[selector for selector in selectors if isinstance(selector, Mapping)],
        keys=("support_count", "supported_count", "supporting_count"),
    )
    contradiction_count = _optional_projection_count(
        provenance_source,
        *[selector for selector in selectors if isinstance(selector, Mapping)],
        keys=(
            "contradiction_count",
            "contradicted_count",
            "contradicting_count",
            "counter_count",
            "opposition_count",
        ),
    )
    projection: dict[str, Any] = {
        "authority_label": "transport_view",
        "authority_boundary": {
            "authority_class": "transport_view",
            "candidate_only": True,
            "derived": True,
            "partial_view": True,
            "transport_only": True,
            "complete_closure": False,
            "excludes": [
                "raw_text",
                "full_receipts",
                "spans",
                "sink/object_uris",
                "bulky_diagnostics",
            ],
        },
        "candidate_facts": candidate_facts,
        "candidate_refs": candidate_refs,
        "route_selectors": normalized_selectors,
        "citations": citation_refs,
        "provenance_refs": provenance_refs,
        "artifact_ref": artifact_id,
        "artifact_revision": artifact_revision,
        "artifact_class": artifact_class,
        "source_system": source_system,
    }
    if support_count is not None:
        projection["support_count"] = support_count
    if contradiction_count is not None:
        projection["contradiction_count"] = contradiction_count
    return projection


def _normalize_zelph_selector(selector: Any) -> Any:
    if isinstance(selector, Mapping):
        normalized = dict(_strip_transport_review_packet_fields(selector))
        normalized.pop("support_count", None)
        normalized.pop("contradiction_count", None)
        normalized.pop("supported_count", None)
        normalized.pop("contradicted_count", None)
        normalized.pop("contradicting_count", None)
        normalized.pop("counter_count", None)
        normalized.pop("opposition_count", None)
        return normalized
    return selector


def _nonempty_texts(values: Sequence[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            normalized.append(text)
    return normalized


def build_zelph_shard_transport_normalized_artifact(
    *,
    artifact_id: str,
    artifact_revision: str,
    artifact_class: str,
    selectors: Sequence[Any],
    selected_shard_ids: Sequence[Any],
    selected_sections: Sequence[Any],
    upstream_artifact_ids: Sequence[Any] | None = None,
    build_provenance: Mapping[str, Any] | None = None,
    source_system: str = "Zelph-HF",
) -> dict[str, Any]:
    normalized_selectors = [_normalize_zelph_selector(selector) for selector in selectors]
    normalized_shard_ids = _nonempty_texts(selected_shard_ids)
    normalized_sections = _nonempty_texts(selected_sections)
    normalized_upstream_artifact_ids = _nonempty_texts(upstream_artifact_ids or [])
    normalized_build_provenance = (
        _strip_transport_review_packet_fields(build_provenance) if isinstance(build_provenance, Mapping) else None
    )
    review_packet_projection = _build_transport_review_packet_projection(
        artifact_id=artifact_id,
        artifact_revision=artifact_revision,
        artifact_class=artifact_class,
        selectors=selectors,
        selected_shard_ids=normalized_shard_ids,
        selected_sections=normalized_sections,
        upstream_artifact_ids=normalized_upstream_artifact_ids,
        build_provenance=build_provenance,
        source_system=source_system or "Zelph-HF",
    )

    artifact = {
        "schema_version": SUITE_NORMALIZED_ARTIFACT_SCHEMA_VERSION,
        "artifact_role": "transport_view",
        "artifact_id": artifact_id,
        "canonical_identity": {
            "identity_class": "zelph_shard_transport",
            "identity_key": f"{artifact_class}:{artifact_id}:{artifact_revision}",
            "aliases": [
                artifact_id,
                artifact_revision,
                artifact_class,
            ],
        },
        "provenance_anchor": {
            "source_system": source_system or "Zelph-HF",
            "source_artifact_id": artifact_id,
            "anchor_kind": "zelph_shard_transport",
            "anchor_ref": "semantic_context.suite_normalized_artifact",
        },
        "context_envelope_ref": {
            "envelope_id": artifact_id,
            "envelope_kind": "zelph_shard_transport",
        },
        "authority": {
            "authority_class": "transport_view",
            "candidate": True,
            "derived": True,
            "transport_only": True,
            "promotion_receipt_ref": None,
        },
        "non_authority_flags": {
            "truth_authority": False,
            "promotion_authority": False,
            "transport_authority": False,
        },
        "lineage": {
            "upstream_artifact_ids": normalized_upstream_artifact_ids,
            "build_provenance": normalized_build_provenance or {},
            "artifact_revision": artifact_revision,
            "artifact_class": artifact_class,
        },
        "invariants": {
            "partial_view": True,
            "subset_of_artifact": True,
            "complete_closure": False,
            "truth_authority": False,
            "promotion_authority": False,
        },
        "selectors": normalized_selectors,
        "route_selectors": normalized_selectors,
        "selected_shard_ids": normalized_shard_ids,
        "selected_sections": normalized_sections,
        "review_packet_projection": review_packet_projection,
        "summary": {
            "artifact_class": artifact_class,
            "artifact_revision": artifact_revision,
            "source_system": source_system or "Zelph-HF",
            "partial_view": True,
            "partial_load": True,
            "candidate_only": True,
            "selector_count": len(normalized_selectors),
            "route_selector_count": len(normalized_selectors),
            "selected_shard_count": len(normalized_shard_ids),
            "selected_section_count": len(normalized_sections),
        },
    }
    return artifact
