from __future__ import annotations

from src.ontology.wikidata_nat_batch_acquisition_plan import (
    ACQUISITION_PLAN_SCHEMA_VERSION,
    ACQUISITION_TASK_SCHEMA_VERSION,
)
from src.ontology.wikidata_nat_batch_shared_acquisition_dispatch import (
    dispatch_shared_acquisition_plan,
)


def _task(task_ref: str, qids: list[str]) -> dict:
    return {
        "schema_version": ACQUISITION_TASK_SCHEMA_VERSION,
        "task_ref": task_ref,
        "source_group_ref": "group:" + task_ref,
        "source_signature_ref": "sig:" + task_ref,
        "target_prerequisite": "source_support",
        "required_producer": "acquire_source_support",
        "mechanism": "look",
        "selector_class": "zelph_hf_selector",
        "member_row_refs": ["row:" + task_ref],
        "external_reference_obligations": [
            {
                "reference_property": "P854",
                "obligation": "fetch_and_verify_external_reference_url_content",
                "mechanism": "external_source_acquisition",
                "candidate_only": True,
            }
        ],
        "wikidata_selector_request": {
            "operations": ["node_route_selection", "partial_loading"],
            "qids": qids,
            "properties": ["P5991", "P14143", "P854"],
            "required_outputs": [
                "statement_snapshot",
                "qualifier_snaks",
                "reference_snaks",
                "source_revision_lineage",
                "content_address",
            ],
            "candidate_only": True,
            "full_reasoning_required": False,
        },
        "dispatch_status": "planned_not_dispatched",
    }


def _plan() -> dict:
    return {
        "schema_version": ACQUISITION_PLAN_SCHEMA_VERSION,
        "plan_ref": "plan:test",
        "source_batch_ref": "batch:test",
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "source_cohort": "business_family_reconciled",
        "materialized_row_count": 57,
        "planned_task_count": 2,
        "tasks": [
            _task("task:a", ["Q10403939", "Q10422059"]),
            _task("task:b", ["Q10416948", "Q10651551", "Q56404383"]),
        ],
        "network_performed": False,
        "edits_performed": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
    }


def _shared_outputs(qids: list[str]) -> dict:
    return {
        "statement_snapshot": {qid: {"claims": {}} for qid in qids},
        "qualifier_snaks": {qid: {} for qid in qids},
        "reference_snaks": {qid: {} for qid in qids},
        "source_revision_lineage": {qid: {"revid": 1} for qid in qids},
        "content_address": "sha256:shared",
    }


def test_shared_dispatch_calls_executor_once_for_union_and_projects_per_task() -> None:
    calls: list[dict] = []

    def executor(selector: dict) -> dict:
        calls.append(selector)
        qids = list(selector["qids"])
        return {
            "executor_id": "fixture.shared",
            "execution_outcome": "executed_with_output",
            "executor_receipt": {"network_performed": True},
            "outputs": _shared_outputs(qids),
        }

    result = dispatch_shared_acquisition_plan(
        _plan(), selector_executor=executor, max_tasks=4
    )
    assert len(calls) == 1
    assert calls[0]["qids"] == [
        "Q10403939",
        "Q10416948",
        "Q10422059",
        "Q10651551",
        "Q56404383",
    ]
    assert result["executor_call_count"] == 1
    assert result["projection_count"] == 2
    assert result["network_performed"] is True
    assert result["source_support_paid_count"] == 0
    assert result["counts_by_execution_outcome"] == {"executed_with_output": 2}
    assert all(p["qids_covered_by_shared_union"] for p in result["projections"])
    assert all(p["source_support_paid"] is False for p in result["projections"])
    assert all(
        p["consumer_verification_required"] is True for p in result["projections"]
    )

    outputs_by_task = {
        item["task_ref"]: item["outputs"]["statement_snapshot"]
        for item in result["results"]
    }
    assert sorted(outputs_by_task["task:a"]) == ["Q10403939", "Q10422059"]
    assert sorted(outputs_by_task["task:b"]) == [
        "Q10416948",
        "Q10651551",
        "Q56404383",
    ]


def test_shared_engine_failure_projects_failure_without_payment() -> None:
    calls = 0

    def executor(_selector: dict) -> dict:
        nonlocal calls
        calls += 1
        return {
            "executor_id": "fixture.failed",
            "execution_outcome": "engine_failed",
            "executor_receipt": {
                "network_performed": True,
                "transport_status": "zelph_binary_manifest_incompatible",
            },
            "outputs": {},
        }

    result = dispatch_shared_acquisition_plan(
        _plan(), selector_executor=executor, max_tasks=4
    )
    assert calls == 1
    assert result["counts_by_execution_outcome"] == {"engine_failed": 2}
    assert all(item["prerequisite_paid"] is False for item in result["results"])
    assert all(item["outputs"] == {} for item in result["results"])
