from __future__ import annotations

from src.policy.brexit_linkage import (
    BREXIT_ARCHIVE_POLICY_INTENT_LINKAGE_CONTRACT_ID,
    build_brexit_archive_policy_intent_linkage_case,
    build_brexit_archive_policy_intent_linkage_contract,
)
from src.policy.linkage_depth import audit_linkage_depth_case
from src.sources.national_archives.brexit_lane_receipts import (
    attach_brexit_archive_policy_intent_linkage_receipt,
    build_brexit_national_archives_world_model_report_with_linkage_receipt,
)
from src.sources.national_archives.brexit_national_archives_lane import (
    build_brexit_national_archives_world_model_report,
    normalized_archive_records,
)


def test_brexit_archive_world_model_builder_remains_receipt_free() -> None:
    report = build_brexit_national_archives_world_model_report(normalized_archive_records())

    assert report["lane_id"] == "brexit_national_archives_policy_intent"
    assert report["summary"]["claim_count"] == 2
    assert "linkage_depth_receipt" not in report


def test_brexit_archive_lane_wrapper_attaches_receipt() -> None:
    report = build_brexit_national_archives_world_model_report_with_linkage_receipt(
        normalized_archive_records()
    )

    receipt = report["linkage_depth_receipt"]
    assert receipt["contract"]["contract_id"] == BREXIT_ARCHIVE_POLICY_INTENT_LINKAGE_CONTRACT_ID
    assert receipt["diagnostics"]["linkage_depth_status"] == "complete"
    assert receipt["diagnostics"]["typed_path_depth"] == 6
    assert receipt["diagnostics"]["candidate_vs_promoted_visibility"] is True
    assert receipt["diagnostics"]["visibility_requirements"]["archive_authority_visibility"]["values"] == [
        "complete"
    ]


def test_brexit_archive_case_projects_adapter_geometry() -> None:
    report = build_brexit_national_archives_world_model_report_with_linkage_receipt(
        normalized_archive_records()
    )

    case = build_brexit_archive_policy_intent_linkage_case(report)
    audited = audit_linkage_depth_case(
        case,
        contract=build_brexit_archive_policy_intent_linkage_contract(),
    )

    assert audited["linkage_depth_status"] == "complete"
    assert audited["typed_path_depth"] == 6
    assert {
        node["layer"] for node in case["nodes"]
    } >= {
        "source_anchor",
        "source_container",
        "parsed_form",
        "domain_candidate",
        "review_surface",
        "authority_surface",
        "tranche_anchor",
    }
    assert any(node["metadata"].get("archive_authority_visibility") == "complete" for node in case["nodes"])


def test_attach_brexit_archive_receipt_wraps_existing_report() -> None:
    report = build_brexit_national_archives_world_model_report(normalized_archive_records())

    wrapped = attach_brexit_archive_policy_intent_linkage_receipt(report)

    assert "linkage_depth_receipt" in wrapped
    assert "linkage_depth_receipt" not in report
    assert wrapped["linkage_depth_receipt"]["case_id"] == "brexit_archive_policy_intent"
