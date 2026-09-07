from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ontology.wikidata_nat_batch_acquisition_dispatch import dispatch_acquisition_plan
from src.ontology.wikidata_nat_batch_acquisition_plan import build_acquisition_plan
from src.ontology.wikidata_nat_batch_prerequisite_runner import build_batch_dry_run
from src.ontology.wikidata_nat_filtered_route_request import (
    FILTERED_ROUTE_RECEIPT_SCHEMA_VERSION,
    FILTERED_ROUTE_REQUEST_SCHEMA_VERSION,
    ITIR_ROUTE_BUILDER_COMMIT,
    ITIR_ROUTE_BUILDER_PATH,
    ITIR_ROUTE_BUILDER_REPO,
    build_filtered_route_request,
    validate_filtered_route_receipt,
)


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


def _plan() -> dict:
    batch = build_batch_dry_run(
        cohort_manifest=_load(MANIFEST_PATH),
        migration_packs=[_load(PACK_PATH)],
        source_revision_reference="fixture:nat-p5991-p14143",
    )
    return build_acquisition_plan(batch)


def _route_blocked_executor(_selector: dict) -> dict:
    return {
        "executor_id": "sensiblaw.nat_hf_selector.v0_1",
        "execution_outcome": "engine_unavailable",
        "executor_receipt": {
            "network_performed": True,
            "transport": "hf-object-fetch",
            "transport_status": "blocked_missing_node_route_index",
            "canonical_layout": True,
            "node_route_index": False,
            "manifest_version": "zelph-hf-layout/v2",
            "manifest_path": "wikidata-20260309-all/wikidata-20260309-all.hf-v2.json",
            "manifest_digest": "sha256:fixture-manifest",
            "manifest_revision": "fixture-revision",
        },
        "outputs": {},
    }


def _dispatch(plan: dict) -> dict:
    return dispatch_acquisition_plan(plan, selector_executor=_route_blocked_executor, max_tasks=4)


def test_filtered_route_request_recovers_exact_five_nat_qids() -> None:
    plan = _plan()
    request = build_filtered_route_request(plan, _dispatch(plan))
    assert request["schema_version"] == FILTERED_ROUTE_REQUEST_SCHEMA_VERSION
    assert request["qid_count"] == 5
    assert request["qids"] == [
        "Q10403939",
        "Q10416948",
        "Q10422059",
        "Q10651551",
        "Q56404383",
    ]
    assert request["filtered_request"] is True
    assert request["full_route_materialization_required"] is False
    assert request["network_performed"] is False
    assert request["source_support_paid"] is False


def test_qid_resolution_is_explicitly_two_stage_and_not_numeric_identity() -> None:
    plan = _plan()
    request = build_filtered_route_request(plan, _dispatch(plan))
    resolution = request["qid_resolution"]
    assert resolution["language"] == "wikidata"
    assert resolution["first_stage"] == "exact_name_to_zelph_node_id"
    assert resolution["first_stage_section"] == "nodeOfName"
    assert resolution["second_stage"] == "zelph_node_id_to_exact_chunk_membership"
    assert resolution["qid_is_not_assumed_to_equal_numeric_node_id"] is True


def test_request_pins_existing_itir_route_builder_as_producer() -> None:
    plan = _plan()
    request = build_filtered_route_request(plan, _dispatch(plan))
    assert request["producer"] == {
        "repository": ITIR_ROUTE_BUILDER_REPO,
        "commit": ITIR_ROUTE_BUILDER_COMMIT,
        "path": ITIR_ROUTE_BUILDER_PATH,
        "route_format": "zelph-node-route/v1",
    }


def test_request_rejects_non_route_blocked_dispatch() -> None:
    plan = _plan()
    dispatch = _dispatch(plan)
    dispatch["results"][0]["executor_receipt"]["transport_status"] = "manifest_fetch_failed"
    with pytest.raises(ValueError):
        build_filtered_route_request(plan, dispatch)


def test_route_receipt_validation_never_pays_source_support() -> None:
    plan = _plan()
    request = build_filtered_route_request(plan, _dispatch(plan))
    receipt = {
        "schema_version": FILTERED_ROUTE_RECEIPT_SCHEMA_VERSION,
        "source_request_ref": request["request_ref"],
        "receipt_ref": "nat-filtered-route-receipt:fixture",
        "route_format": "zelph-node-route/v1",
        "producer": {
            "repository": ITIR_ROUTE_BUILDER_REPO,
            "commit": ITIR_ROUTE_BUILDER_COMMIT,
        },
        "resolved_qids": request["qids"],
    }
    validated = validate_filtered_route_receipt(request, receipt)
    assert validated["receipt_valid"] is True
    assert validated["unresolved_qids"] == []
    assert validated["source_support_paid"] is False
    assert validated["consumer_verification_performed"] is False
    assert validated["semantic_promotion_performed"] is False
