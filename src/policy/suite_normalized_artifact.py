from __future__ import annotations

from typing import Any, Mapping, Sequence

from .compiler_contract import normalize_promoted_outcomes


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

    return {
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


def build_gwb_public_review_normalized_artifact(
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
        hold_scope="bounded_follow_or_review_of_open_gwb_public_review_pressure",
        abstain_scope="bounded_manual_review_of_open_gwb_public_review_pressure",
        abstain_stop_condition="stop after explicit abstain confirmation or new bounded evidence",
        hold_stop_condition="stop when open review or legal-follow pressure is cleared",
    )

    source_family = str(evidence_bundle.get("source_family") or "gwb_public_review").strip()
    item_label = str(evidence_bundle.get("item_label") or "source_row").strip()
    source_ref = str(source_input.get("path") or artifact_id).strip()
    return {
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


def build_gwb_broader_review_normalized_artifact(
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
        hold_scope="bounded_follow_or_review_of_open_gwb_broader_review_pressure",
        abstain_scope="bounded_manual_review_of_open_gwb_broader_review_pressure",
        abstain_stop_condition="stop after explicit abstain confirmation or new bounded evidence",
        hold_stop_condition="stop when open review, archive-follow, or legal-follow pressure is cleared",
    )

    source_family = str(evidence_bundle.get("source_family") or "gwb_broader_review").strip()
    item_label = str(evidence_bundle.get("item_label") or "source_row").strip()
    source_ref = str(source_input.get("path") or artifact_id).strip()
    return {
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
