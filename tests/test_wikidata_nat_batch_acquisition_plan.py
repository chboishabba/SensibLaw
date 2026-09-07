from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ontology.wikidata_nat_batch_acquisition_plan import (
    ACQUISITION_PLAN_SCHEMA_VERSION,
    build_acquisition_plan,
)
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


def _real_batch() -> dict:
    return build_batch_dry_run(
        cohort_manifest=_load(MANIFEST_PATH),
        migration_packs=[_load(PACK_PATH)],
        source_revision_reference="fixture:nat-p5991-p14143",
    )


def test_plan_preserves_batch_counts_and_performs_no_dispatch() -> None:
    batch = _real_batch()
    plan = build_acquisition_plan(batch)
    assert plan["schema_version"] == ACQUISITION_PLAN_SCHEMA_VERSION
    assert plan["source_batch_ref"] == batch["batch_ref"]
    assert plan["source_population"] == 37665
    assert plan["materialized_row_count"] == batch["materialized_row_count"]
    assert plan["planned_task_count"] == batch["work_group_count"]
    assert plan["planned_member_count"] == batch["row_count"]
    assert plan["network_performed"] is False
    assert plan["edits_performed"] is False
    assert plan["consumer_verification_performed"] is False
    assert plan["semantic_promotion_performed"] is False


def test_every_current_task_is_bounded_source_support_look_work() -> None:
    plan = build_acquisition_plan(_real_batch())
    assert plan["tasks"]
    for task in plan["tasks"]:
        assert task["target_prerequisite"] == "source_support"
        assert task["required_producer"] == "acquire_source_support"
        assert task["mechanism"] == "look"
        assert task["selector_class"] == "zelph_hf_selector"
        assert task["dispatch_status"] == "planned_not_dispatched"
        selector = task["wikidata_selector_request"]
        assert selector["candidate_only"] is True
        assert selector["full_reasoning_required"] is False
        assert "statement_snapshot" in selector["required_outputs"]
        assert "reference_snaks" in selector["required_outputs"]
        assert "source_revision_lineage" in selector["required_outputs"]


def test_p854_creates_external_source_obligation_not_payment() -> None:
    plan = build_acquisition_plan(_real_batch())
    p854_tasks = [
        task for task in plan["tasks"] if "P854" in task["reference_properties"]
    ]
    assert p854_tasks
    for task in p854_tasks:
        obligations = task["external_reference_obligations"]
        assert any(
            item["reference_property"] == "P854"
            and item["obligation"] == "fetch_and_verify_external_reference_url_content"
            for item in obligations
        )
        policy = task["payment_policy"]
        assert policy["wikidata_selector_output_alone_pays_source_support"] is False
        assert policy["external_reference_presence_alone_pays_source_support"] is False
        assert policy["consumer_verification_required"] is True
        assert policy["semantic_promotion_allowed"] is False
        assert policy["edit_authority"] is False


def test_plan_is_content_addressed_and_deterministic() -> None:
    batch = _real_batch()
    left = build_acquisition_plan(batch)
    right = build_acquisition_plan(batch)
    assert left == right
    assert left["plan_ref"].startswith("nat-acquisition-plan:")
    assert all(task["task_ref"].startswith("nat-acquisition-task:") for task in left["tasks"])


def test_planner_rejects_non_dry_or_promoted_batch() -> None:
    batch = _real_batch()
    batch["network_performed"] = True
    with pytest.raises(ValueError):
        build_acquisition_plan(batch)
