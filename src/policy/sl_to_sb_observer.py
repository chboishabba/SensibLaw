from __future__ import annotations

from typing import Any, Mapping, Sequence


SL_TO_SB_ISO_RUN_OBSERVER_CONTRACT_VERSION = "sl.sl_to_sb_iso_run_observer_contract.v0_1"
SL_TO_SB_ISO_RUN_OBSERVER_KIND = "sensiblaw_iso_run_v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _nonempty_strings(values: Sequence[Any]) -> list[str]:
    seen: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.append(text)
    return seen


def _bounded_casey_refs(values: Sequence[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    allowed = (
        "workspace_id",
        "operation_id",
        "operation_kind",
        "build_id",
        "tree_id",
        "selection_digest",
        "receipt_hash",
    )
    refs: list[dict[str, str]] = []
    for item in values or []:
        if not isinstance(item, Mapping):
            continue
        normalized = {field: _text(item.get(field)) for field in allowed if _text(item.get(field))}
        if normalized:
            refs.append(normalized)
    return refs


def _bounded_output_refs(values: Sequence[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    allowed = ("artifact_id", "artifact_role", "ref_kind", "ref")
    refs: list[dict[str, str]] = []
    for item in values or []:
        if not isinstance(item, Mapping):
            continue
        normalized = {field: _text(item.get(field)) for field in allowed if _text(item.get(field))}
        if normalized:
            refs.append(normalized)
    return refs


def build_sl_to_sb_iso_run_observer_payload(
    *,
    suite_normalized_artifact: Mapping[str, Any],
    state_date: str | None = None,
    sb_state_id: str | None = None,
    output_refs: Sequence[Mapping[str, Any]] | None = None,
    casey_observer_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a bounded SL -> SB observer overlay for ISO-style runs."""

    artifact_id = _text(suite_normalized_artifact.get("artifact_id"))
    if not artifact_id:
        raise ValueError("SL->SB ISO run observer payload requires artifact_id")

    supplied_state_date = _text(state_date)
    supplied_sb_state_id = _text(sb_state_id)
    if not supplied_state_date and not supplied_sb_state_id:
        raise ValueError("SL->SB ISO run observer payload requires state_date or sb_state_id")

    context_envelope_ref = (
        suite_normalized_artifact.get("context_envelope_ref")
        if isinstance(suite_normalized_artifact.get("context_envelope_ref"), Mapping)
        else {}
    )
    provenance_anchor = (
        suite_normalized_artifact.get("provenance_anchor")
        if isinstance(suite_normalized_artifact.get("provenance_anchor"), Mapping)
        else {}
    )
    lineage = suite_normalized_artifact.get("lineage") if isinstance(suite_normalized_artifact.get("lineage"), Mapping) else {}
    text_ref = suite_normalized_artifact.get("text_ref") if isinstance(suite_normalized_artifact.get("text_ref"), Mapping) else {}

    run_id = _text(context_envelope_ref.get("envelope_id")) or artifact_id
    source_artifact_id = _text(provenance_anchor.get("source_artifact_id")) or artifact_id
    follow_obligation = (
        dict(suite_normalized_artifact.get("follow_obligation"))
        if isinstance(suite_normalized_artifact.get("follow_obligation"), Mapping)
        else None
    )
    legal_follow_pressure = (
        dict(suite_normalized_artifact.get("legal_follow_pressure"))
        if isinstance(suite_normalized_artifact.get("legal_follow_pressure"), Mapping)
        else None
    )
    unresolved_pressure_status = _text(suite_normalized_artifact.get("unresolved_pressure_status")) or "none"
    lineage_refs = _nonempty_strings(lineage.get("upstream_artifact_ids") or [])
    source_artifact_refs = _nonempty_strings([source_artifact_id, artifact_id])

    payload: dict[str, Any] = {
        "activity_event_id": f"sl-iso-run:{run_id}",
        "annotation_id": f"obs:sl_iso_run:{run_id}",
        "provenance": {
            "source": "SensibLaw",
            "run_id": run_id,
            "source_artifact_id": source_artifact_id,
            "contract_version": SL_TO_SB_ISO_RUN_OBSERVER_CONTRACT_VERSION,
        },
        "observer_kind": SL_TO_SB_ISO_RUN_OBSERVER_KIND,
        "status": "linked",
        "confidence": "high",
        "run_id": run_id,
        "artifact_refs": source_artifact_refs,
        "output_refs": [
            {
                "artifact_id": artifact_id,
                "artifact_role": _text(suite_normalized_artifact.get("artifact_role")) or "derived_product",
                "ref_kind": "suite_normalized_artifact",
                "ref": "semantic_context.suite_normalized_artifact",
            },
            *_bounded_output_refs(output_refs),
        ],
        "follow_obligation": follow_obligation,
        "legal_follow_pressure": legal_follow_pressure,
        "unresolved_pressure_status": unresolved_pressure_status,
        "lineage_refs": lineage_refs,
        "source_artifact_refs": source_artifact_refs,
    }
    if supplied_sb_state_id:
        payload["sb_state_id"] = supplied_sb_state_id
    if supplied_state_date:
        payload["state_date"] = supplied_state_date
    if text_ref:
        payload["provenance"]["text_id"] = _text(text_ref.get("text_id"))
    bounded_casey_refs = _bounded_casey_refs(casey_observer_refs)
    if bounded_casey_refs:
        payload["casey_observer_refs"] = bounded_casey_refs
    return payload


__all__ = [
    "SL_TO_SB_ISO_RUN_OBSERVER_CONTRACT_VERSION",
    "SL_TO_SB_ISO_RUN_OBSERVER_KIND",
    "build_sl_to_sb_iso_run_observer_payload",
]
