from __future__ import annotations

from src.ontology.wikidata_nat_batch_acquisition_plan import (
    ACQUISITION_PLAN_SCHEMA_VERSION,
    ACQUISITION_TASK_SCHEMA_VERSION,
)
from src.ontology.wikidata_nat_batch_shared_acquisition_dispatch import (
    dispatch_shared_acquisition_plan,
)


def _coverage_residual(index: int, qid: str) -> dict:
    return {
        "residual_ref": f"nat-coverage-residual:test:{index:02d}",
        "subject_qid": qid,
        "property": "P14143",
        "coverage_status": "uninspected",
        "missing_coordinate": "targetPropertyFamily",
        "graph_revision_reference": "revision:test",
        "consumer_reference": f"row:test:{index:02d}",
        "formal_producer_class": "empiricalEvidenceProducer",
    }


def _task(
    task_ref: str,
    qids: list[str],
    *,
    residuals: list[dict] | None = None,
) -> dict:
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
        "live_coverage_residuals": list(residuals or []),
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


def _plan_with_57_residuals() -> dict:
    qids_a = ["Q10403939", "Q10422059"]
    qids_b = ["Q10416948", "Q10651551", "Q56404383"]
    residuals = [
        _coverage_residual(
            index,
            (qids_a + qids_b)[index % 5],
        )
        for index in range(57)
    ]
    task_a_residuals = [
        residual
        for residual in residuals
        if residual["subject_qid"] in set(qids_a)
    ]
    task_b_residuals = [
        residual
        for residual in residuals
        if residual["subject_qid"] in set(qids_b)
    ]
    return {
        "schema_version": ACQUISITION_PLAN_SCHEMA_VERSION,
        "plan_ref": "plan:57-residuals",
        "source_batch_ref": "batch:57-residuals",
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "source_cohort": "business_family_reconciled",
        "materialized_row_count": 57,
        "planned_task_count": 2,
        "planned_live_coverage_residual_count": 57,
        "tasks": [
            _task("task:a", qids_a, residuals=task_a_residuals),
            _task("task:b", qids_b, residuals=task_b_residuals),
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


def test_shared_dispatch_fans_one_execution_back_to_57_exact_residuals() -> None:
    calls: list[dict] = []

    def executor(selector: dict) -> dict:
        calls.append(selector)
        qids = list(selector["qids"])
        return {
            "executor_id": "fixture.57-residuals",
            "execution_outcome": "executed_with_output",
            "executor_receipt": {"network_performed": True},
            "outputs": _shared_outputs(qids),
        }

    result = dispatch_shared_acquisition_plan(
        _plan_with_57_residuals(), selector_executor=executor, max_tasks=4
    )

    assert len(calls) == 1
    assert result["executor_call_count"] == 1
    assert result["materialized_row_count"] == 57
    assert result["planned_live_coverage_residual_count"] == 57
    assert result["residual_recomputation_count"] == 57
    assert result["ternary_admissibility_projection_count"] == 57
    assert result["coverage_residual_paid_count"] == 57
    assert result["coverage_residual_still_open_count"] == 0
    assert result["source_support_paid_count"] == 0
    assert result["consumer_verification_performed"] is False
    assert result["semantic_promotion_performed"] is False

    recomputation_by_ref = {
        item["live_residual_ref"]: item
        for item in result["residual_recomputations"]
    }
    assert len(recomputation_by_ref) == 57
    assert all(
        item["coverage_coordinate_paid"] is True
        for item in recomputation_by_ref.values()
    )
    assert all(
        item["property_family_status"] == "absent"
        for item in recomputation_by_ref.values()
    )
    assert all(
        item["source_support_paid"] is False
        for item in recomputation_by_ref.values()
    )
    assert all(
        item["rank_visibility_evaluated"] is False
        and item["qualifier_constraints_evaluated"] is False
        and item["property_scope_evaluated"] is False
        and item["property_engine_derivability_evaluated"] is False
        for item in recomputation_by_ref.values()
    )

    ternary_by_source = {
        item["source_recomputation_ref"]: item
        for item in result["ternary_admissibility_projections"]
    }
    assert len(ternary_by_source) == 57
    assert all(item["dimension"] == 10 for item in ternary_by_source.values())
    assert all(
        item["axis_trits"]["native_family_coverage"] == 1
        and item["axis_trits"]["rank_visibility"] == 0
        and item["axis_trits"]["qualifier_constraints"] == 0
        and item["axis_trits"]["property_scope"] == 0
        and item["axis_trits"]["property_derivability"] == 0
        and item["axis_trits"]["source_support"] == 0
        and item["axis_trits"]["authority"] == 0
        and item["axis_trits"]["semantic_correspondence"] == 0
        for item in ternary_by_source.values()
    )
    assert all(
        len(item["base369_nine_trits"]) == 9
        and set(item["base369_nine_trits"]) <= {-1, 0, 1}
        for item in ternary_by_source.values()
    )


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
