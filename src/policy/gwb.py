from __future__ import annotations

from typing import Any, Mapping
from src.policy.world_model_runtime import (
    attach_receipt as _attach_receipt,
    build_world_model as _build_world_model_from_input,
    project_report as _project_report,
)


def attach_receipt(artifact: Mapping[str, Any], *, profile: str = "broader_review") -> dict[str, Any]:
    return _attach_receipt(artifact)


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_world_model(payload_or_conn: Any, *, profile: str = "broader_review", run_id: str | None = None) -> dict[str, Any]:
    if profile == "broader_review":
        return _build_world_model_from_input(payload_or_conn)
    if profile in {"semantic", "narrative_timeline"}:
        if not run_id:
            raise ValueError("gwb narrative_timeline world model requires run_id")
        # Compat wrapper: call the lane-specific builder directly.
        # The public API (build_world_model(data)) discovers adapters from
        # content — but this wrapper accepts sqlite3 connections which
        # cannot be content-sniffed. Lane wrappers are compat shims.
        from src.policy.gwb_narrative_world_model import (
            build_world_model as _build_gwb_narrative_world_model,
        )
        from src.policy.world_model import normalize_world_model
        from copy import deepcopy

        wm = _build_gwb_narrative_world_model(payload_or_conn, run_id=run_id)
        model = normalize_world_model(wm)
        metadata = deepcopy(dict(model.get("metadata") or {}))
        metadata["runtime_adapter"] = "gwb_narrative_timeline"
        model["metadata"] = metadata
        return model
    raise ValueError(f"unsupported gwb world-model profile: {profile}")


def build_report(
    payload_or_conn: Any,
    *,
    profile: str = "broader_review",
    run_id: str | None = None,
    with_receipt: bool = False,
) -> dict[str, Any]:
    report = _project_report(build_world_model(payload_or_conn, profile=profile, run_id=run_id))
    if not with_receipt:
        return report
    return _attach_receipt(report)


def build_semantic_report(conn: Any, *, run_id: str, with_receipt: bool = False) -> dict[str, Any]:
    return build_report(conn, profile="narrative_timeline", run_id=run_id, with_receipt=with_receipt)


__all__ = [
    "attach_receipt",
    "build_report",
    "build_world_model",
]
