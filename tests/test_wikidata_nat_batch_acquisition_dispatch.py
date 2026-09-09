from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ontology.wikidata_nat_batch_acquisition_dispatch import (
    ACQUISITION_DISPATCH_SCHEMA_VERSION,
    dispatch_acquisition_plan,
)
from src.ontology.wikidata_nat_batch_acquisition_plan import build_acquisition_plan
from src.ontology.wikidata_nat_batch_prerequisite_runner import build_batch_dry_run


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "wikidata"
MANIFEST_PATH = FIXTURE_ROOT / "wikidata_nat_lane_review_manifests_20260401.json"
PACK_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "ontology"
    / "wikidata_migration_packs"
    / "p5991_p14143_climate_pilot_20260328"
    / "migration_pack.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _real_plan() -> dict:
    batch = build_batch_dry_run(
        cohort_manifest=_load(MANIFEST_PATH),
        migration_packs=[_load(PACK_PATH)],
        source_revision_reference="fixture:nat-p5991-p14143",
    )
    return build_acquisition_plan(batch)


def _complete_executor(selector: dict) -> dict:
    return {
        "executor_id": "test.complete-selector",
        "execution_outcome": "executed_with_output",
        "executor_receipt": {"network_performed": True, "transport": "fixture"},
        "outputs": {
            "statement_snapshot": {"qids": selector["qids"]},
            "qualifier_snaks": {"properties": selector["properties"]},
            "reference_snaks": {"properties": selector["properties"]},
            "source_revision_lineage": {"revision": "fixture"},
            "content_address": "sha256:fixture",
        },
    }


def test_dispatches_exact_current_four_tasks_without_paying_source_support() -> None:
    dispatch = dispatch_acquisition_plan(
        _real_plan(), selector_executor=_complete_executor, max_tasks=4
    )
    assert dispatch["schema_version"] == ACQUISITION_DISPATCH_SCHEMA_VERSION
    assert dispatch["dispatched_task_count"] == 4
    assert dispatch["counts_by_execution_outcome"] == {"executed_with_output": 4}
    assert dispatch["network_performed"] is True
    assert dispatch["edits_performed"] is False
    assert dispatch["consumer_verification_performed"] is False
    assert dispatch["semantic_promotion_performed"] is False
    assert dispatch["source_support_paid_count"] == 0
    assert all(result["prerequisite_paid"] is False for result in dispatch["results"])
    assert all(result["consumer_verification_performed"] is False for result in dispatch["results"])


def test_executor_output_keeps_p854_external_verification_obligation() -> None:
    dispatch = dispatch_acquisition_plan(
        _real_plan(), selector_executor=_complete_executor, max_tasks=4
    )
    for result in dispatch["results"]:
        obligations = result["external_reference_obligations"]
        assert any(
            item.get("reference_property") == "P854"
            and item.get("obligation")
            == "fetch_and_verify_external_reference_url_content"
            for item in obligations
        )
        assert result["prerequisite_paid"] is False


def test_missing_required_output_fails_contract_even_if_executor_says_success() -> None:
    def incomplete(selector: dict) -> dict:
        return {
            "executor_id": "test.incomplete-selector",
            "execution_outcome": "executed_with_output",
            "executor_receipt": {"network_performed": False},
            "outputs": {
                "statement_snapshot": {"qids": selector["qids"]},
                "reference_snaks": {},
            },
        }

    dispatch = dispatch_acquisition_plan(
        _real_plan(), selector_executor=incomplete, max_tasks=4
    )
    assert dispatch["counts_by_execution_outcome"] == {
        "failed_required_output_contract": 4
    }
    assert dispatch["network_performed"] is False
    assert all(result["missing_required_outputs"] for result in dispatch["results"])


def test_no_match_is_not_negative_evidence_or_payment() -> None:
    def no_match(_selector: dict) -> dict:
        return {
            "executor_id": "test.no-match-selector",
            "execution_outcome": "executed_no_match",
            "executor_receipt": {"network_performed": True},
            "outputs": {},
        }

    dispatch = dispatch_acquisition_plan(
        _real_plan(), selector_executor=no_match, max_tasks=4
    )
    assert dispatch["counts_by_execution_outcome"] == {"executed_no_match": 4}
    assert dispatch["source_support_paid_count"] == 0
    assert all(result["prerequisite_paid"] is False for result in dispatch["results"])


def test_dispatcher_refuses_plan_wider_than_explicit_bound() -> None:
    with pytest.raises(ValueError):
        dispatch_acquisition_plan(
            _real_plan(), selector_executor=_complete_executor, max_tasks=3
        )


def test_dispatch_receipt_is_content_addressed_and_deterministic_for_same_executor() -> None:
    left = dispatch_acquisition_plan(
        _real_plan(), selector_executor=_complete_executor, max_tasks=4
    )
    right = dispatch_acquisition_plan(
        _real_plan(), selector_executor=_complete_executor, max_tasks=4
    )
    assert left == right
    assert left["dispatch_ref"].startswith("nat-acquisition-dispatch:")
    assert all(
        result["result_ref"].startswith("nat-acquisition-result:")
        for result in left["results"]
    )
