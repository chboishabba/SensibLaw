from __future__ import annotations

import json
from pathlib import Path

from SensibLaw.src.fact_intake.au_review_bundle import (
    build_au_fact_review_bundle_world_model_report,
)
from SensibLaw.tests.test_au_fact_review_bundle import _prepare_au_fact_review_bundle_fixture
from SensibLaw.src.ontology.wikidata_nat_cohort_b_operator_packet import (
    build_nat_cohort_b_operator_packet_world_model_report,
)
from SensibLaw.src.reporting.world_model_lane_summary import (
    WORLD_MODEL_LANE_SUMMARY_SCHEMA_VERSION,
    build_lane_governance_snapshot,
    build_world_model_lane_summary,
)
from SensibLaw.src.sources.national_archives.brexit_national_archives_lane import (
    build_brexit_national_archives_world_model_report,
    fetch_brexit_archive_records,
)
from src.ontology.wikidata_nat_automation_graduation import build_nat_claim_convergence_report


def _load_nat_verification_runs_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_cohort_b_operator_packet_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_b_operator_packet_20260402.json"
        ).read_text(encoding="utf-8")
    )


def test_build_lane_governance_snapshot_maps_promoted_nat_report() -> None:
    report = build_nat_claim_convergence_report(_load_nat_verification_runs_fixture())
    snapshot = build_lane_governance_snapshot(report)

    assert snapshot["lane_name"] == report["family_id"]
    assert snapshot["promotion_gate_decision"] == "promote"
    assert snapshot["metrics"]["can_act_count"] == 2


def test_build_world_model_lane_summary_aggregates_rebound_lanes(monkeypatch, tmp_path: Path) -> None:
    def fake_get(_url: str, **_kwargs):
        raise RuntimeError("dialing blocked")

    monkeypatch.setattr(
        "SensibLaw.src.sources.national_archives.brexit_national_archives_lane.requests.get",
        fake_get,
    )

    nat_report = build_nat_claim_convergence_report(_load_nat_verification_runs_fixture())
    bundle, *_ = _prepare_au_fact_review_bundle_fixture(tmp_path)
    au_report = build_au_fact_review_bundle_world_model_report(bundle)
    brexit_report = build_brexit_national_archives_world_model_report(fetch_brexit_archive_records(limit=1))
    reviewer_report = build_nat_cohort_b_operator_packet_world_model_report(
        _load_cohort_b_operator_packet_fixture()
    )

    summary = build_world_model_lane_summary(
        [nat_report, au_report, brexit_report, reviewer_report]
    )

    assert summary["schema_version"] == WORLD_MODEL_LANE_SUMMARY_SCHEMA_VERSION
    assert summary["summary"]["lane_count"] == 4
    assert summary["summary"]["ready_lane_count"] >= 2
    assert summary["summary"]["total_authority_receipts"] >= 5
    assert "business_family_reconciled_low_qualifier_checked_safe_subset" in summary["governance_gate"]["ready_lanes"]
    assert summary["governance_gate"]["decision"] == "go"
