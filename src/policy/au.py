from __future__ import annotations

from typing import Any, Mapping

from src.fact_intake.au_review_bundle import build_au_fact_review_bundle as _build_bundle
from src.policy.world_model_runtime import (
    attach_receipt as _attach_receipt,
    build_world_model as _build_world_model_from_input,
    project_report as _project_report,
)


def attach_receipt(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return _attach_receipt(artifact)


def _build_bundle_artifact(
    conn: Any,
    *,
    fact_run_id: str,
    semantic_report: Mapping[str, Any],
    source_events: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return dict(
        _build_bundle(
            conn,
            fact_run_id=fact_run_id,
            semantic_report=semantic_report,
            source_events=source_events,
        )
    )


def build_world_model(
    conn: Any,
    *,
    fact_run_id: str,
    semantic_report: Mapping[str, Any],
    source_events: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    bundle = _build_bundle_artifact(
        conn,
        fact_run_id=fact_run_id,
        semantic_report=semantic_report,
        source_events=source_events,
    )
    return _build_world_model_from_input(bundle)


def build_report(
    conn: Any,
    *,
    fact_run_id: str,
    semantic_report: Mapping[str, Any],
    source_events: list[Mapping[str, Any]] | None = None,
    with_receipt: bool = False,
) -> dict[str, Any]:
    report = _project_report(
        build_world_model(
            conn,
            fact_run_id=fact_run_id,
            semantic_report=semantic_report,
            source_events=source_events,
        )
    )
    if not with_receipt:
        return report
    return _attach_receipt(report)


__all__ = [
    "attach_receipt",
    "build_report",
    "build_world_model",
]
