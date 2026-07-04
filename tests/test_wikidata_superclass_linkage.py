from __future__ import annotations

import json
from pathlib import Path

from src.ontology.wikidata_lane_receipts import (
    attach_wikidata_q43229_superclass_pressure_linkage_receipt,
    load_q43229_superclass_pressure_report_with_linkage_receipt,
)
from src.ontology.wikidata_superclass_linkage import (
    WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
    WIKIDATA_Q43229_SUPERCLASS_PRESSURE_REPORT_SCHEMA_VERSION,
    build_wikidata_q43229_superclass_pressure_linkage_case,
    build_wikidata_q43229_superclass_pressure_linkage_contract,
    build_wikidata_q43229_superclass_pressure_report,
)
from src.policy.linkage_depth import audit_linkage_depth_case


def _load_fixture(name: str) -> dict:
    return json.loads((Path(__file__).resolve().parent / "fixtures" / "wikidata" / name).read_text(encoding="utf-8"))


def test_q43229_superclass_pressure_report_remains_receipt_free() -> None:
    report = build_wikidata_q43229_superclass_pressure_report(
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


def test_q43229_superclass_lane_wrapper_attaches_receipt() -> None:
    report = load_q43229_superclass_pressure_report_with_linkage_receipt()

    receipt = report["linkage_depth_receipt"]
    assert receipt["contract"]["contract_id"] == WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID
    assert receipt["diagnostics"]["linkage_depth_status"] == "complete"
    assert receipt["diagnostics"]["typed_path_depth"] == 6
    assert receipt["diagnostics"]["candidate_vs_promoted_visibility"] is True
    assert receipt["diagnostics"]["visibility_requirements"]["counterexample_cone_visibility"]["values"] == [
        "complete"
    ]


def test_q43229_superclass_case_projects_adapter_composed_geometry() -> None:
    report = load_q43229_superclass_pressure_report_with_linkage_receipt()

    case = build_wikidata_q43229_superclass_pressure_linkage_case(report)
    audited = audit_linkage_depth_case(
        case,
        contract=build_wikidata_q43229_superclass_pressure_linkage_contract(),
    )

    assert audited["linkage_depth_status"] == "complete"
    assert audited["typed_path_depth"] == 6
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
    report = build_wikidata_q43229_superclass_pressure_report(
        review_bucket=_load_fixture("wikidata_nat_cohort_b_review_bucket_20260402.json"),
        operator_packet=_load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json"),
        operator_queue=_load_fixture("wikidata_nat_cohort_b_operator_queue_20260402.json"),
        operator_report=_load_fixture("wikidata_nat_cohort_b_operator_report_20260402.json"),
        batch_report=_load_fixture("wikidata_nat_cohort_b_operator_batch_report_20260402.json"),
    )

    wrapped = attach_wikidata_q43229_superclass_pressure_linkage_receipt(report)

    assert "linkage_depth_receipt" in wrapped
    assert "linkage_depth_receipt" not in report
    assert wrapped["linkage_depth_receipt"]["case_id"] == "wikidata_q43229_superclass_pressure"
