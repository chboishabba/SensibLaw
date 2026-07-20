from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.linkage_depth import (
    LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION,
    build_linkage_depth_case,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def case_from_receipt(
    receipt: Mapping[str, Any],
    *,
    case_kind: str,
    default_case_id: str,
    default_lane_id: str,
    default_contract: Mapping[str, Any],
    default_contract_id: str,
    default_notes: Sequence[str] = (),
    default_case_source: str = "emitted_bridge_artifact",
) -> dict[str, Any] | None:
    if not isinstance(receipt, Mapping) or _text(receipt.get("schema_version")) != LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION:
        return None
    contract = receipt.get("contract") if isinstance(receipt.get("contract"), Mapping) else default_contract
    return build_linkage_depth_case(
        case_id=_text(receipt.get("case_id")) or default_case_id,
        case_kind=case_kind,
        lane_id=_text(receipt.get("lane_id")) or default_lane_id,
        contract_id=_text((receipt.get("contract") or {}).get("contract_id")) or default_contract_id,
        case_source=_text(receipt.get("source_mode")) or default_case_source,
        notes=[_text(value) for value in default_notes if _text(value)],
        expected_anchor_ids=receipt.get("expected_anchor_ids", []),
        expected_terminal_ids=receipt.get("expected_terminal_ids", []),
        nodes=receipt.get("nodes", []),
        edges=receipt.get("edges", []),
        contract=contract,
    )


def case_from_linkage_projection(
    projection: Mapping[str, Any],
    *,
    case_kind: str,
    default_case_id: str,
    default_lane_id: str,
    default_contract: Mapping[str, Any],
    default_contract_id: str,
    default_notes: Sequence[str] = (),
    default_case_source: str = "projected_world_model_artifact",
) -> dict[str, Any] | None:
    if not isinstance(projection, Mapping) or _text(projection.get("projection_kind")) != "linkage_case":
        return None
    payload = projection.get("payload") if isinstance(projection.get("payload"), Mapping) else {}
    source_model = projection.get("source_model") if isinstance(projection.get("source_model"), Mapping) else {}
    metadata = projection.get("metadata") if isinstance(projection.get("metadata"), Mapping) else {}
    contract = default_contract
    return build_linkage_depth_case(
        case_id=_text(payload.get("case_id")) or default_case_id,
        case_kind=case_kind,
        lane_id=_text(metadata.get("lane_id")) or default_lane_id or _text(source_model.get("lane_family")),
        contract_id=_text(payload.get("contract_id")) or default_contract_id,
        case_source=default_case_source,
        notes=[_text(value) for value in payload.get("notes", []) if _text(value)]
        or [_text(value) for value in default_notes if _text(value)],
        expected_anchor_ids=payload.get("expected_anchor_ids", []),
        expected_terminal_ids=payload.get("expected_terminal_ids", []),
        nodes=payload.get("nodes", []),
        edges=payload.get("edges", []),
        contract=contract,
    )


def require_case_from_projection_artifact(
    artifact: Mapping[str, Any],
    *,
    case_kind: str,
    default_case_id: str,
    default_lane_id: str,
    default_contract: Mapping[str, Any],
    default_contract_id: str,
    default_notes: Sequence[str] = (),
    default_case_source: str = "projected_world_model_artifact",
) -> dict[str, Any]:
    if not isinstance(artifact, Mapping):
        raise ValueError("linkage receipt attachment requires projected artifact mapping")
    case = case_from_linkage_projection(
        artifact.get("linkage_case"),
        case_kind=case_kind,
        default_case_id=default_case_id,
        default_lane_id=default_lane_id,
        default_contract=default_contract,
        default_contract_id=default_contract_id,
        default_notes=default_notes,
        default_case_source=default_case_source,
    )
    if case is None:
        raise ValueError(
            "linkage receipt attachment requires a linkage_case projection; "
            "project_linkage_case(...) must run before attach_receipt(...)"
        )
    return case


__all__ = [
    "case_from_linkage_projection",
    "case_from_receipt",
    "require_case_from_projection_artifact",
]
