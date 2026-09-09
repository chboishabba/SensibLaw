from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.policy.carriers.canonical import canonical_sha256


NAT_COVERAGE_RESIDUAL_SCHEMA_VERSION = "sl.nat_coverage_residual.v0_1"
NAT_BOUND_ACQUISITION_DEMAND_SCHEMA_VERSION = "sl.nat_bound_acquisition_demand.v0_1"
NAT_COVERAGE_RECOMPUTATION_SCHEMA_VERSION = "sl.nat_coverage_recomputation.v0_1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _text_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return sorted({_text(value) for value in values if _text(value)})


def build_target_property_coverage_residual(row: Mapping[str, Any]) -> dict[str, Any]:
    """Build the exact Nat Q/property coverage residual represented by one row.

    This is the runtime counterpart of
    DASHI.Interop.SensibLawNatCoverageAcquisitionDemandExact.  A grouped network
    request may carry many of these residuals, but sharing transport never merges
    their semantic/payment identity.
    """

    qid = _text(row.get("qid"))
    target_property = _text(row.get("target_property"))
    row_ref = _text(row.get("row_ref"))
    if not qid or not target_property or not row_ref:
        raise ValueError("Nat coverage residual requires row_ref, qid, and target_property")

    payload_without_ref = {
        "schema_version": NAT_COVERAGE_RESIDUAL_SCHEMA_VERSION,
        "source_row_ref": row_ref,
        "subject_qid": qid,
        "property": target_property,
        "coverage_status": "uninspected",
        "missing_coordinate": "targetPropertyFamily",
        "graph_revision_reference": _text(row.get("source_revision_reference")),
        "coverage_policy_reference": "Nat P5991->P14143 coverage policy",
        "consumer_reference": row_ref,
        "formal_producer_class": "empiricalEvidenceProducer",
        "runtime_required_producer": _text(row.get("required_producer")),
        "selector_class": _text(row.get("selector_class")),
    }
    payload = dict(payload_without_ref)
    payload["residual_ref"] = "nat-coverage-residual:" + canonical_sha256(payload_without_ref)
    return payload


def build_bound_coverage_demand(
    residual: Mapping[str, Any], *, task_ref: str, shared_execution_ref: str = ""
) -> dict[str, Any]:
    """Bind one acquisition demand to exactly one live residual.

    This is binding only.  It creates no coverage payment, consumer closure,
    migration authority, edit authority, or semantic promotion authority.
    """

    residual_ref = _text(residual.get("residual_ref"))
    qid = _text(residual.get("subject_qid"))
    prop = _text(residual.get("property"))
    if not residual_ref or not qid or not prop:
        raise ValueError("bound Nat acquisition demand requires an exact residual")

    payload_without_ref = {
        "schema_version": NAT_BOUND_ACQUISITION_DEMAND_SCHEMA_VERSION,
        "live_residual_ref": residual_ref,
        "selected_requirement": "inspect_target_property_family",
        "missing_coordinate": _text(residual.get("missing_coordinate")),
        "formal_producer_class": _text(residual.get("formal_producer_class")),
        "runtime_required_producer": _text(residual.get("runtime_required_producer")),
        "exact_subject_qid": qid,
        "exact_property": prop,
        "required_representation": (
            "native statement-family coverage or another representation explicitly "
            "certified complete for this exact Q/property query family"
        ),
        "task_ref": _text(task_ref),
        "shared_execution_ref": _text(shared_execution_ref),
        "candidate_only": True,
        "coverage_payment_claimed": False,
        "consumer_closure_claimed": False,
        "migration_authority": False,
        "edit_authority": False,
        "semantic_promotion_authority": False,
    }
    payload = dict(payload_without_ref)
    payload["demand_ref"] = "nat-bound-acquisition-demand:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def assess_acquisition_for_recomputation(
    residual: Mapping[str, Any], acquisition_result: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the post-acquisition state without confusing retrieval with payment."""

    residual_ref = _text(residual.get("residual_ref"))
    if not residual_ref:
        raise ValueError("coverage recomputation assessment requires residual_ref")

    execution_outcome = _text(acquisition_result.get("execution_outcome"))
    outputs = acquisition_result.get("outputs")
    outputs = outputs if isinstance(outputs, Mapping) else {}
    statement_snapshot = outputs.get("statement_snapshot")
    snapshot_present = isinstance(statement_snapshot, Mapping)

    if execution_outcome == "executed_with_output" and snapshot_present:
        observation_state = "candidate_evidence_observed_pending_recompute"
    elif execution_outcome == "executed_no_match":
        observation_state = "still_open_clean_transport_exhaustion_or_unresolved_identity"
    elif execution_outcome in {"engine_failed", "engine_unavailable"}:
        observation_state = "still_open_engine_failure"
    else:
        observation_state = "still_open_unclassified_acquisition_result"

    payload_without_ref = {
        "schema_version": NAT_COVERAGE_RECOMPUTATION_SCHEMA_VERSION,
        "live_residual_ref": residual_ref,
        "acquisition_result_ref": _text(acquisition_result.get("result_ref")),
        "execution_outcome": execution_outcome,
        "observation_state": observation_state,
        "statement_snapshot_present": snapshot_present,
        "coverage_recomputation_required": True,
        "coverage_payment_claimed": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "migration_authority": False,
    }
    payload = dict(payload_without_ref)
    payload["recomputation_ref"] = "nat-coverage-recomputation:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def bind_task_residuals(
    task: Mapping[str, Any], rows_by_ref: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    residuals: list[dict[str, Any]] = []
    demands: list[dict[str, Any]] = []
    task_ref = _text(task.get("task_ref"))
    for row_ref in _text_list(task.get("member_row_refs")):
        row = rows_by_ref.get(row_ref)
        if row is None:
            raise ValueError(f"Nat task references unknown row: {row_ref}")
        residual = build_target_property_coverage_residual(row)
        residuals.append(residual)
        demands.append(build_bound_coverage_demand(residual, task_ref=task_ref))
    residuals.sort(key=lambda item: _text(item.get("residual_ref")))
    demands.sort(key=lambda item: _text(item.get("demand_ref")))
    return residuals, demands


__all__ = [
    "NAT_BOUND_ACQUISITION_DEMAND_SCHEMA_VERSION",
    "NAT_COVERAGE_RECOMPUTATION_SCHEMA_VERSION",
    "NAT_COVERAGE_RESIDUAL_SCHEMA_VERSION",
    "assess_acquisition_for_recomputation",
    "bind_task_residuals",
    "build_bound_coverage_demand",
    "build_target_property_coverage_residual",
]
