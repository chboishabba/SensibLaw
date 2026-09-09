from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from src.ontology.wikidata_nat_batch_acquisition_dispatch import (
    SelectorExecutor,
    _as_mapping,
    _normalize_executor_result,
    _require_bounded_task,
    _require_plan,
    _text,
    _text_list,
)
from src.ontology.wikidata_nat_residual_bound_acquisition import (
    assess_acquisition_for_recomputation,
)
from src.ontology.wikidata_nat_ternary_admissibility import (
    build_nat_ternary_admissibility_projection,
)
from src.policy.carriers.canonical import canonical_sha256


SHARED_DISPATCH_SCHEMA_VERSION = "sl.nat_batch_shared_acquisition_dispatch.v0_1"
SHARED_EXECUTION_SCHEMA_VERSION = "sl.nat_shared_acquisition_execution.v0_1"
SHARED_PROJECTION_SCHEMA_VERSION = "sl.nat_shared_acquisition_projection.v0_1"

QID_KEYED_OUTPUTS = {
    "statement_snapshot",
    "qualifier_snaks",
    "reference_snaks",
    "source_revision_lineage",
}


def _union_text_lists(values: Sequence[Sequence[str]]) -> list[str]:
    return sorted({item for group in values for item in _text_list(group)})


def _shared_selector(selectors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not selectors:
        raise ValueError("shared acquisition requires at least one selector")
    return {
        "candidate_only": True,
        "full_reasoning_required": False,
        "operations": _union_text_lists(
            [selector.get("operations") or [] for selector in selectors]
        ),
        "qids": _union_text_lists([selector.get("qids") or [] for selector in selectors]),
        "properties": _union_text_lists(
            [selector.get("properties") or [] for selector in selectors]
        ),
        "required_outputs": _union_text_lists(
            [selector.get("required_outputs") or [] for selector in selectors]
        ),
        "shared_execution": True,
    }


def _project_outputs(
    outputs: Mapping[str, Any], task_qids: Sequence[str]
) -> dict[str, Any]:
    qid_set = set(_text_list(task_qids))
    projected: dict[str, Any] = {}
    for key, value in outputs.items():
        if key == "content_address":
            continue
        if key in QID_KEYED_OUTPUTS and isinstance(value, Mapping):
            projected[key] = {
                qid: value[qid]
                for qid in sorted(qid_set)
                if qid in value
            }
        else:
            projected[key] = value
    projected["content_address"] = "sha256:" + canonical_sha256(projected)
    return projected


def _task_residuals(task: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = task.get("live_coverage_residuals")
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    residuals = [value for value in values if isinstance(value, Mapping)]
    residuals.sort(key=lambda item: _text(item.get("residual_ref")))
    return residuals


def dispatch_shared_acquisition_plan(
    plan: Mapping[str, Any],
    *,
    selector_executor: SelectorExecutor,
    max_tasks: int = 4,
) -> dict[str, Any]:
    """Coalesce bounded Nat acquisition tasks into one transport execution.

    The union execution is an I/O optimisation only. Each planned task receives
    a deterministic QID-scoped projection which is normalized by the existing
    per-task result contract. The result is then projected again to each exact
    live Nat coverage residual carried by that task. Retrieval alone never pays
    a residual; payment of the narrow Q/property coverage coordinate can occur
    only in the explicit residual-local recomputation step.

    Each recomputation additionally receives a balanced-ternary N-dimensional
    admissibility projection. That is a representation/inspection surface only:
    its selected nine-axis chart fits the existing Base369 T^9 carrier, but it
    creates no Monster action, source authority, or semantic promotion.
    """

    tasks = _require_plan(plan, max_tasks=max_tasks)
    selectors = [_require_bounded_task(task) for task in tasks]
    shared_selector = _shared_selector(selectors)

    raw_shared = selector_executor(shared_selector)
    if not isinstance(raw_shared, Mapping):
        raise ValueError("selector executor must return a mapping receipt")

    shared_executor_receipt = dict(_as_mapping(raw_shared.get("executor_receipt")))
    shared_outputs = dict(_as_mapping(raw_shared.get("outputs")))
    shared_without_ref = {
        "schema_version": SHARED_EXECUTION_SCHEMA_VERSION,
        "source_plan_ref": _text(plan.get("plan_ref")),
        "selector_request_digest": canonical_sha256(shared_selector),
        "selector": shared_selector,
        "executor_id": _text(raw_shared.get("executor_id"))
        or "unspecified_selector_executor",
        "execution_outcome": _text(raw_shared.get("execution_outcome")),
        "executor_receipt": shared_executor_receipt,
        "output_content_address": _text(shared_outputs.get("content_address")),
        "network_performed": bool(
            shared_executor_receipt.get("network_performed", False)
        ),
        "consumer_verification_performed": False,
        "source_support_paid": False,
        "semantic_promotion_performed": False,
        "edits_performed": False,
    }
    shared_execution = dict(shared_without_ref)
    shared_execution["shared_execution_ref"] = (
        "nat-shared-acquisition-execution:" + canonical_sha256(shared_without_ref)
    )

    results: list[dict[str, Any]] = []
    projections: list[dict[str, Any]] = []
    residual_recomputations: list[dict[str, Any]] = []
    ternary_admissibility_projections: list[dict[str, Any]] = []
    for task, selector in zip(tasks, selectors):
        task_qids = _text_list(selector.get("qids"))
        task_properties = _text_list(selector.get("properties"))
        projected_outputs = _project_outputs(shared_outputs, task_qids) if shared_outputs else {}
        task_residuals = _task_residuals(task)
        task_residual_refs = [
            _text(residual.get("residual_ref"))
            for residual in task_residuals
            if _text(residual.get("residual_ref"))
        ]
        task_demand_refs = sorted(
            {
                _text(demand.get("demand_ref"))
                for demand in (task.get("bound_acquisition_demands") or [])
                if isinstance(demand, Mapping) and _text(demand.get("demand_ref"))
            }
        )
        projection_without_ref = {
            "schema_version": SHARED_PROJECTION_SCHEMA_VERSION,
            "task_ref": _text(task.get("task_ref")),
            "shared_execution_ref": shared_execution["shared_execution_ref"],
            "projection_qids": task_qids,
            "projection_properties": task_properties,
            "shared_union_qids": _text_list(shared_selector.get("qids")),
            "qids_covered_by_shared_union": set(task_qids).issubset(
                set(_text_list(shared_selector.get("qids")))
            ),
            "live_coverage_residual_refs": task_residual_refs,
            "bound_acquisition_demand_refs": task_demand_refs,
            "consumer_verification_required": True,
            "coverage_recomputation_required": bool(task_residual_refs),
            "source_support_paid": False,
            "semantic_promotion_performed": False,
        }
        projection = dict(projection_without_ref)
        projection["projection_ref"] = (
            "nat-shared-acquisition-projection:"
            + canonical_sha256(projection_without_ref)
        )
        projections.append(projection)

        projected_receipt = dict(shared_executor_receipt)
        projected_receipt.update(
            {
                "shared_execution_ref": shared_execution["shared_execution_ref"],
                "shared_projection_ref": projection["projection_ref"],
                "shared_union_qids": _text_list(shared_selector.get("qids")),
                "projection_qids": task_qids,
                "projection_properties": task_properties,
                "live_coverage_residual_refs": task_residual_refs,
                "consumer_verification_performed": False,
                "source_support_paid": False,
                "semantic_promotion_performed": False,
                "edits_performed": False,
            }
        )
        projected_raw = {
            "executor_id": _text(raw_shared.get("executor_id")),
            "execution_outcome": _text(raw_shared.get("execution_outcome")),
            "executor_receipt": projected_receipt,
            "outputs": projected_outputs,
        }
        normalized = _normalize_executor_result(
            task=task,
            selector=selector,
            raw_result=projected_raw,
        )
        normalized["shared_execution_ref"] = shared_execution["shared_execution_ref"]
        normalized["shared_projection_ref"] = projection["projection_ref"]

        task_recomputations: list[dict[str, Any]] = []
        task_ternary_projections: list[dict[str, Any]] = []
        for residual in task_residuals:
            recomputation = assess_acquisition_for_recomputation(residual, normalized)
            ternary_projection = build_nat_ternary_admissibility_projection(recomputation)
            recomputation["ternary_admissibility_projection_ref"] = ternary_projection[
                "projection_ref"
            ]
            task_recomputations.append(recomputation)
            task_ternary_projections.append(ternary_projection)

        task_recomputations.sort(key=lambda item: _text(item.get("recomputation_ref")))
        task_ternary_projections.sort(key=lambda item: _text(item.get("projection_ref")))
        task_paid_count = sum(
            1 for item in task_recomputations if bool(item.get("coverage_coordinate_paid"))
        )
        normalized["live_coverage_residual_refs"] = task_residual_refs
        normalized["coverage_recomputations"] = task_recomputations
        normalized["coverage_recomputation_count"] = len(task_recomputations)
        normalized["coverage_coordinate_paid_count"] = task_paid_count
        normalized["coverage_coordinate_still_open_count"] = (
            len(task_recomputations) - task_paid_count
        )
        normalized["ternary_admissibility_projections"] = task_ternary_projections
        normalized["ternary_admissibility_projection_count"] = len(
            task_ternary_projections
        )
        normalized["retrieval_result_alone_pays_live_residual"] = False
        residual_recomputations.extend(task_recomputations)
        ternary_admissibility_projections.extend(task_ternary_projections)
        results.append(normalized)

    results.sort(key=lambda result: _text(result.get("result_ref")))
    projections.sort(key=lambda item: _text(item.get("projection_ref")))
    residual_recomputations.sort(key=lambda item: _text(item.get("recomputation_ref")))
    ternary_admissibility_projections.sort(
        key=lambda item: _text(item.get("projection_ref"))
    )
    counts = Counter(_text(result.get("execution_outcome")) for result in results)
    coverage_paid_count = sum(
        1 for item in residual_recomputations if bool(item.get("coverage_coordinate_paid"))
    )

    payload_without_ref = {
        "schema_version": SHARED_DISPATCH_SCHEMA_VERSION,
        "source_plan_ref": _text(plan.get("plan_ref")),
        "source_batch_ref": _text(plan.get("source_batch_ref")),
        "lane_id": _text(plan.get("lane_id")),
        "source_cohort": _text(plan.get("source_cohort")),
        "materialized_row_count": plan.get("materialized_row_count"),
        "planned_task_count": plan.get("planned_task_count"),
        "planned_live_coverage_residual_count": plan.get(
            "planned_live_coverage_residual_count", 0
        ),
        "executor_call_count": 1,
        "shared_execution": shared_execution,
        "projection_count": len(projections),
        "projections": projections,
        "results": results,
        "residual_recomputation_count": len(residual_recomputations),
        "residual_recomputations": residual_recomputations,
        "ternary_admissibility_projection_count": len(
            ternary_admissibility_projections
        ),
        "ternary_admissibility_projections": ternary_admissibility_projections,
        "counts_by_execution_outcome": dict(sorted(counts.items())),
        "network_performed": bool(shared_execution.get("network_performed")),
        "consumer_verification_performed": False,
        "source_support_paid_count": 0,
        "coverage_residual_paid_count": coverage_paid_count,
        "coverage_residual_still_open_count": (
            len(residual_recomputations) - coverage_paid_count
        ),
        "semantic_promotion_performed": False,
        "edits_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["dispatch_ref"] = "nat-shared-acquisition-dispatch:" + canonical_sha256(
        payload_without_ref
    )
    return payload


__all__ = [
    "SHARED_DISPATCH_SCHEMA_VERSION",
    "SHARED_EXECUTION_SCHEMA_VERSION",
    "SHARED_PROJECTION_SCHEMA_VERSION",
    "dispatch_shared_acquisition_plan",
]
