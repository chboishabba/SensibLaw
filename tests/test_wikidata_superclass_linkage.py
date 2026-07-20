from __future__ import annotations

import json
from pathlib import Path

from src.ontology.nat import attach_receipt, load_fixture
from src.ontology.wikidata_superclass_linkage import (
    Q43229_PROFILE_ID,
    WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
    WIKIDATA_Q43229_SUPERCLASS_PRESSURE_REPORT_SCHEMA_VERSION,
    build_case,
    build_contract,
    build_report,
    build_world_model,
)
from src.policy.linkage_depth import audit_linkage_depth_case


def _load_fixture(name: str) -> dict:
    return json.loads((Path(__file__).resolve().parent / "fixtures" / "wikidata" / name).read_text(encoding="utf-8"))


def test_q43229_superclass_pressure_report_remains_receipt_free() -> None:
    report = build_report(
        review_bucket=_load_fixture("wikidata_nat_cohort_b_review_bucket_20260402.json"),
        operator_packet=_load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json"),
        operator_queue=_load_fixture("wikidata_nat_cohort_b_operator_queue_20260402.json"),
        operator_report=_load_fixture("wikidata_nat_cohort_b_operator_report_20260402.json"),
        batch_report=_load_fixture("wikidata_nat_cohort_b_operator_batch_report_20260402.json"),
    )

    assert report["schema_version"] == WIKIDATA_Q43229_SUPERCLASS_PRESSURE_REPORT_SCHEMA_VERSION
    assert report["target_instance_of_qid"] == "Q43229"
    assert report["summary"]["packet_row_count"] == 1
    assert report["summary"]["queue_row_count"] == 1
    assert "linkage_depth_receipt" not in report


def test_q43229_superclass_pressure_world_model_and_projections_reuse_shared_stack() -> None:
    world_model = build_world_model(
        review_bucket=_load_fixture("wikidata_nat_cohort_b_review_bucket_20260402.json"),
        operator_packet=_load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json"),
        operator_queue=_load_fixture("wikidata_nat_cohort_b_operator_queue_20260402.json"),
        operator_report=_load_fixture("wikidata_nat_cohort_b_operator_report_20260402.json"),
        batch_report=_load_fixture("wikidata_nat_cohort_b_operator_batch_report_20260402.json"),
    )
    report = build_report(
        review_bucket=_load_fixture("wikidata_nat_cohort_b_review_bucket_20260402.json"),
        operator_packet=_load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json"),
        operator_queue=_load_fixture("wikidata_nat_cohort_b_operator_queue_20260402.json"),
        operator_report=_load_fixture("wikidata_nat_cohort_b_operator_report_20260402.json"),
        batch_report=_load_fixture("wikidata_nat_cohort_b_operator_batch_report_20260402.json"),
    )

    assert world_model["lane_family"] == "nat"
    assert world_model["metadata"]["profile"]["profile_id"] == Q43229_PROFILE_ID
    assert report["projection"]["projection_kind"] == "report"
    assert report["review_surface"]["projection_kind"] == "review_surface"
    assert report["claim_table"]["projection_kind"] == "claim_table"
    assert report["linkage_case"]["projection_kind"] == "linkage_case"


def test_q43229_superclass_lane_wrapper_attaches_receipt() -> None:
    report = load_fixture(profile="q43229_superclass_pressure", with_receipt=True)

    receipt = report["linkage_depth_receipt"]
    assert receipt["contract"]["contract_id"] == WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID
    assert receipt["diagnostics"]["linkage_depth_status"] == "complete"
    assert receipt["diagnostics"]["typed_path_depth"] == 6
    assert receipt["diagnostics"]["candidate_vs_promoted_visibility"] is True
    assert receipt["diagnostics"]["visibility_requirements"]["counterexample_cone_visibility"]["values"] == [
        "complete"
    ]


def test_q43229_superclass_case_projects_adapter_composed_geometry() -> None:
    report = load_fixture(profile="q43229_superclass_pressure", with_receipt=False)

    case = build_case(report)
    audited = audit_linkage_depth_case(
        case,
        contract=build_contract(),
    )

    assert audited["linkage_depth_status"] == "complete"
    assert audited["typed_path_depth"] == 6
    assert case["case_source"] == "projected_world_model_artifact"
    assert audited["bridge_completeness"][-1]["source_layer"] == "review_surface"
    assert audited["bridge_completeness"][-1]["target_layer"] == "tranche_anchor"
    assert {
        node["layer"] for node in case["nodes"]
    } >= {
        "source_anchor",
        "statement_edge_candidate",
        "counterexample_cone",
        "pressure_surface",
        "repair_candidate",
        "review_surface",
        "tranche_anchor",
    }
    assert any(node["metadata"].get("class_lattice_pressure_visibility") == "complete" for node in case["nodes"])


def test_attach_q43229_superclass_receipt_wraps_existing_report() -> None:
    report = build_report(
        review_bucket=_load_fixture("wikidata_nat_cohort_b_review_bucket_20260402.json"),
        operator_packet=_load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json"),
        operator_queue=_load_fixture("wikidata_nat_cohort_b_operator_queue_20260402.json"),
        operator_report=_load_fixture("wikidata_nat_cohort_b_operator_report_20260402.json"),
        batch_report=_load_fixture("wikidata_nat_cohort_b_operator_batch_report_20260402.json"),
    )

    wrapped = attach_receipt(report, profile="q43229_superclass_pressure")

    assert "linkage_depth_receipt" in wrapped
    assert "linkage_depth_receipt" not in report
    assert wrapped["linkage_depth_receipt"]["case_id"] == "wikidata_q43229_superclass_pressure"
