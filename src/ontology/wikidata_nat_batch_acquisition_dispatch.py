from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from src.ontology.wikidata_nat_batch_acquisition_plan import (
    ACQUISITION_PLAN_SCHEMA_VERSION,
    ACQUISITION_TASK_SCHEMA_VERSION,
)
from src.policy.carriers.canonical import canonical_sha256


ACQUISITION_DISPATCH_SCHEMA_VERSION = "sl.nat_batch_acquisition_dispatch.v0_1"
ACQUISITION_RESULT_SCHEMA_VERSION = "sl.nat_batch_acquisition_result.v0_1"

SelectorExecutor = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return sorted({_text(value) for value in values if _text(value)})


def _require_plan(plan: Mapping[str, Any], *, max_tasks: int) -> list[Mapping[str, Any]]:
    if _text(plan.get("schema_version")) != ACQUISITION_PLAN_SCHEMA_VERSION:
        raise ValueError("unsupported Nat acquisition-plan schema")
    if bool(plan.get("network_performed")):
        raise ValueError("plan already claims network activity")
    if bool(plan.get("edits_performed")):
        raise ValueError("plan already claims edits")
    if bool(plan.get("consumer_verification_performed")):
        raise ValueError("plan already claims consumer verification")
    if bool(plan.get("semantic_promotion_performed")):
        raise ValueError("plan already claims semantic promotion")

    tasks = plan.get("tasks")
    if not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes, bytearray)):
        raise ValueError("acquisition plan must contain tasks")
    normalized = [task for task in tasks if isinstance(task, Mapping)]
    if len(normalized) != len(tasks):
        raise ValueError("acquisition plan contains non-object tasks")
    if len(normalized) > max_tasks:
        raise ValueError(
            f"bounded dispatcher refuses {len(normalized)} tasks; max_tasks={max_tasks}"
        )
    return normalized


def _require_bounded_task(task: Mapping[str, Any]) -> Mapping[str, Any]:
    if _text(task.get("schema_version")) != ACQUISITION_TASK_SCHEMA_VERSION:
        raise ValueError("unsupported Nat acquisition-task schema")
    if _text(task.get("dispatch_status")) != "planned_not_dispatched":
        raise ValueError("task is not in planned_not_dispatched state")
    if _text(task.get("target_prerequisite")) != "source_support":
        raise ValueError("bounded dispatcher currently accepts source_support tasks only")
    if _text(task.get("required_producer")) != "acquire_source_support":
        raise ValueError("bounded dispatcher requires acquire_source_support producer")
    if _text(task.get("mechanism")) != "look":
        raise ValueError("bounded dispatcher accepts Look tasks only")
    if _text(task.get("selector_class")) != "zelph_hf_selector":
        raise ValueError("bounded dispatcher accepts Zelph/HF selector tasks only")

    selector = _as_mapping(task.get("wikidata_selector_request"))
    if not selector:
        raise ValueError("task missing wikidata_selector_request")
    if not bool(selector.get("candidate_only")):
        raise ValueError("selector request must remain candidate_only")
    if bool(selector.get("full_reasoning_required")):
        raise ValueError("bounded selector dispatch cannot request full reasoning")

    qids = _text_list(selector.get("qids"))
    properties = _text_list(selector.get("properties"))
    required_outputs = _text_list(selector.get("required_outputs"))
    operations = _text_list(selector.get("operations"))
    if not qids:
        raise ValueError("selector request must name at least one QID")
    if not properties:
        raise ValueError("selector request must name at least one property")
    if not required_outputs:
        raise ValueError("selector request must name required outputs")
    if not operations:
        raise ValueError("selector request must name bounded operations")

    return selector


def _normalize_executor_result(
    *,
    task: Mapping[str, Any],
    selector: Mapping[str, Any],
    raw_result: Mapping[str, Any],
) -> dict[str, Any]:
    required_outputs = _text_list(selector.get("required_outputs"))
    output_payload = _as_mapping(raw_result.get("outputs"))
    emitted_outputs = sorted(
        key
        for key in required_outputs
        if key in output_payload and output_payload[key] is not None
    )
    missing_outputs = sorted(set(required_outputs) - set(emitted_outputs))

    raw_outcome = _text(raw_result.get("execution_outcome"))
    if raw_outcome in {"engine_unavailable", "engine_failed"}:
        execution_outcome = raw_outcome
    elif raw_outcome == "executed_no_match":
        execution_outcome = "executed_no_match"
    elif missing_outputs:
        execution_outcome = "failed_required_output_contract"
    elif raw_outcome in {"executed_with_output", "ok", "success"} or output_payload:
        execution_outcome = "executed_with_output"
    else:
        execution_outcome = "executed_no_match"

    executor_receipt = dict(_as_mapping(raw_result.get("executor_receipt")))
    result_without_ref = {
        "schema_version": ACQUISITION_RESULT_SCHEMA_VERSION,
        "task_ref": _text(task.get("task_ref")),
        "source_group_ref": _text(task.get("source_group_ref")),
        "source_signature_ref": _text(task.get("source_signature_ref")),
        "target_prerequisite": _text(task.get("target_prerequisite")),
        "selector_class": _text(task.get("selector_class")),
        "selector_request_digest": canonical_sha256(selector),
        "executor_id": _text(raw_result.get("executor_id"))
        or "unspecified_selector_executor",
        "execution_outcome": execution_outcome,
        "required_outputs": required_outputs,
        "emitted_outputs": emitted_outputs,
        "missing_required_outputs": missing_outputs,
        "outputs": dict(output_payload),
        "executor_receipt": executor_receipt,
        "network_performed": bool(executor_receipt.get("network_performed", False)),
        "external_reference_obligations": list(
            task.get("external_reference_obligations") or []
        ),
        "member_row_refs": _text_list(task.get("member_row_refs")),
        "candidate_only": True,
        "consumer_verification_performed": False,
        "prerequisite_paid": False,
        "semantic_promotion_performed": False,
        "edits_performed": False,
    }
    result = dict(result_without_ref)
    result["result_ref"] = "nat-acquisition-result:" + canonical_sha256(
        result_without_ref
    )
    return result


def dispatch_acquisition_plan(
    plan: Mapping[str, Any],
    *,
    selector_executor: SelectorExecutor,
    max_tasks: int = 4,
) -> dict[str, Any]:
    """Execute only the bounded selector tasks from a validated Nat plan.

    The dispatcher normalizes transport results into execution receipts. It does
    not verify external P854/P248 sources, pay source_support, edit Wikidata, or
    promote semantics. Those remain downstream consumer obligations.
    """

    tasks = _require_plan(plan, max_tasks=max_tasks)
    results: list[dict[str, Any]] = []
    for task in tasks:
        selector = _require_bounded_task(task)
        raw_result = selector_executor(selector)
        if not isinstance(raw_result, Mapping):
            raise ValueError("selector executor must return a mapping receipt")
        results.append(
            _normalize_executor_result(
                task=task,
                selector=selector,
                raw_result=raw_result,
            )
        )

    results.sort(key=lambda result: _text(result.get("result_ref")))
    counts = Counter(_text(result.get("execution_outcome")) for result in results)
    payload_without_ref = {
        "schema_version": ACQUISITION_DISPATCH_SCHEMA_VERSION,
        "source_plan_ref": _text(plan.get("plan_ref")),
        "source_batch_ref": _text(plan.get("source_batch_ref")),
        "lane_id": _text(plan.get("lane_id")),
        "source_cohort": _text(plan.get("source_cohort")),
        "materialized_row_count": plan.get("materialized_row_count"),
        "planned_task_count": plan.get("planned_task_count"),
        "dispatched_task_count": len(results),
        "counts_by_execution_outcome": dict(sorted(counts.items())),
        "results": results,
        "network_performed": any(
            bool(result.get("network_performed")) for result in results
        ),
        "edits_performed": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "source_support_paid_count": 0,
    }
    payload = dict(payload_without_ref)
    payload["dispatch_ref"] = "nat-acquisition-dispatch:" + canonical_sha256(
        payload_without_ref
    )
    return payload


__all__ = [
    "ACQUISITION_DISPATCH_SCHEMA_VERSION",
    "ACQUISITION_RESULT_SCHEMA_VERSION",
    "SelectorExecutor",
    "dispatch_acquisition_plan",
]
