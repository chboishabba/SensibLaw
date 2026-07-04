from __future__ import annotations

from typing import Any, Mapping

from src.policy.gwb_broader_review_world_model import (
    build_report as _build_broader_review_report,
    build_world_model as _build_broader_review_world_model,
)
from src.policy.gwb_linkage_depth import build_receipt as _build_broader_review_receipt
from src.policy.gwb_narrative_world_model import (
    build_report as _build_narrative_report,
    build_world_model as _build_narrative_world_model,
)
from src.policy.gwb_narrative_linkage import build_receipt as _build_narrative_receipt
from src.policy.linkage_workflows import attach_receipt as _attach_receipt
from src.policy.linkage_workflows import build_report as _build_report


def attach_receipt(artifact: Mapping[str, Any], *, profile: str = "broader_review") -> dict[str, Any]:
    builders = {
        "broader_review": _build_broader_review_receipt,
        "semantic": _build_narrative_receipt,
        "narrative_timeline": _build_narrative_receipt,
    }
    try:
        receipt_builder = builders[profile]
    except KeyError as exc:
        raise ValueError(f"unsupported gwb receipt profile: {profile}") from exc
    source_artifact = artifact
    if not isinstance(artifact.get("linkage_case"), Mapping):
        try:
            if profile == "broader_review":
                source_artifact = _build_broader_review_report(dict(artifact))
            else:
                source_artifact = _build_narrative_report(dict(artifact), run_id=artifact.get("run_id"))
        except ValueError as exc:
            raise ValueError(
                "linkage receipt attachment requires a linkage_case projection; "
                "project_linkage_case(...) must run before attach_receipt(...)"
            ) from exc
    return _attach_receipt(source_artifact, receipt_builder=receipt_builder)


def build_world_model(payload_or_conn: Any, *, profile: str = "broader_review", run_id: str | None = None) -> dict[str, Any]:
    if profile == "broader_review":
        return _build_broader_review_world_model(payload_or_conn)
    if profile in {"semantic", "narrative_timeline"}:
        if not run_id:
            raise ValueError("gwb narrative_timeline world model requires run_id")
        return _build_narrative_world_model(payload_or_conn, run_id=run_id)
    raise ValueError(f"unsupported gwb world-model profile: {profile}")


def build_report(
    payload_or_conn: Any,
    *,
    profile: str = "broader_review",
    run_id: str | None = None,
    with_receipt: bool = False,
) -> dict[str, Any]:
    if profile in {"semantic", "narrative_timeline"}:
        if not run_id:
            raise ValueError("gwb narrative_timeline report requires run_id")
        return _build_report(
            report_builder=_build_narrative_report,
            report_args=(payload_or_conn,),
            report_kwargs={"run_id": run_id},
            receipt_builder=_build_narrative_receipt,
            with_receipt=with_receipt,
        )
    payload = payload_or_conn
    return _build_report(
        report_builder=_build_broader_review_report,
        report_args=(payload,),
        receipt_builder=_build_broader_review_receipt,
        with_receipt=with_receipt,
    )


def build_semantic_report(conn: Any, *, run_id: str, with_receipt: bool = False) -> dict[str, Any]:
    return build_report(conn, profile="narrative_timeline", run_id=run_id, with_receipt=with_receipt)


__all__ = [
    "attach_receipt",
    "build_report",
    "build_world_model",
]
