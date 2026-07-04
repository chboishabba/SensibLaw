from __future__ import annotations

from typing import Any, Mapping

from src.fact_intake.au_review_bundle import build_au_fact_review_bundle as _build_bundle
from src.policy.au_linkage_depth import build_receipt as _build_receipt
from src.policy.au_world_model import build_report as _build_projected_report
from src.policy.au_world_model import build_world_model as _build_world_model_from_bundle
from src.policy.linkage_workflows import attach_receipt as _attach_receipt
from src.policy.linkage_workflows import build_report as _build_with_workflow


def attach_receipt(artifact: Mapping[str, Any]) -> dict[str, Any]:
    source_artifact = artifact
    if not isinstance(artifact.get("linkage_case"), Mapping):
        source_artifact = _build_projected_report(dict(artifact))
    return _attach_receipt(source_artifact, receipt_builder=_build_receipt)


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
    return _build_world_model_from_bundle(bundle)


def build_report(
    conn: Any,
    *,
    fact_run_id: str,
    semantic_report: Mapping[str, Any],
    source_events: list[Mapping[str, Any]] | None = None,
    with_receipt: bool = False,
) -> dict[str, Any]:
    return _build_with_workflow(
        report_builder=lambda *args, **kwargs: _build_projected_report(
            _build_bundle_artifact(*args, **kwargs),
        ),
        report_kwargs={
            "conn": conn,
            "fact_run_id": fact_run_id,
            "semantic_report": semantic_report,
            "source_events": source_events,
        },
        receipt_builder=_build_receipt,
        with_receipt=with_receipt,
    )


__all__ = [
    "attach_receipt",
    "build_report",
    "build_world_model",
]
