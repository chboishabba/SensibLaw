from __future__ import annotations

import src.ontology.wikidata_linkage_depth as wikidata_linkage_depth
from scripts.build_gwb_broader_review import build_gwb_broader_review
from src.policy.gwb_lane_receipts import (
    build_gwb_broader_review_world_model_report_with_linkage_receipt,
)
from src.policy.gwb_linkage_depth import (
    GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID,
    build_gwb_broader_review_linkage_case,
)
from src.policy.au_lane_receipts import attach_au_fact_review_bundle_linkage_receipt
from src.policy.au_linkage_depth import (
    AU_FACT_REVIEW_BUNDLE_LINKAGE_CONTRACT_ID,
    build_au_fact_review_bundle_linkage_case,
)
from src.policy.linkage_depth import build_linkage_depth_audit
from src.ontology.wikidata_linkage_depth import (
    LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION,
    audit_linkage_depth_case,
    build_dog_soft_stitch_linkage_case,
    build_climate_review_linkage_case,
    build_disjointness_report_linkage_case,
    build_sensiblaw_pnf_wd_linkage_contract,
    build_wikidata_disjointness_review_linkage_contract,
    build_wikidata_linkage_depth_audit,
)
from src.ontology.wikidata import build_wikidata_climate_review_demonstrator
from src.ontology.wikidata_disjointness import (
    load_disjointness_slice,
    project_wikidata_disjointness_payload,
)
from src.ontology.wikidata_lane_receipts import (
    load_q43229_superclass_pressure_report_with_linkage_receipt,
    load_climate_review_demonstrator_with_linkage_receipt,
    load_disjointness_report_with_linkage_receipt,
)
from src.ontology.wikidata_superclass_linkage import (
    WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
    build_wikidata_q43229_superclass_pressure_linkage_case,
)
from src.policy.brexit_linkage import (
    BREXIT_ARCHIVE_POLICY_INTENT_LINKAGE_CONTRACT_ID,
    build_brexit_archive_policy_intent_linkage_case,
)
from src.sources.national_archives.brexit_lane_receipts import (
    build_brexit_national_archives_world_model_report_with_linkage_receipt,
)
from src.sources.national_archives.brexit_national_archives_lane import normalized_archive_records
from tests.test_au_fact_review_bundle import _prepare_au_fact_review_bundle_fixture


def test_expected_layer_contract_matches_phase_e_contract_shape() -> None:
    contract = build_sensiblaw_pnf_wd_linkage_contract()

    assert contract["schema_version"] == "sl.expected_layer_contract.v0_1"
    assert contract["contract_id"] == "sensiblaw_pnf_wd_linkage"
    assert contract["expected_layers"] == [
        "token_span",
        "sentence_document",
        "sentence_pnf",
        "document_pnf",
        "entity_topic_candidate",
        "wd_lexical_or_semantic_candidate",
        "zelph_wd_review_surface",
        "review_packet_tranche",
    ]
    assert contract["required_bridges"] == [
        ["token_span", "sentence_document"],
        ["sentence_document", "sentence_pnf"],
        ["sentence_pnf", "document_pnf"],
        ["document_pnf", "entity_topic_candidate"],
        ["entity_topic_candidate", "wd_lexical_or_semantic_candidate"],
        ["wd_lexical_or_semantic_candidate", "zelph_wd_review_surface"],
        ["zelph_wd_review_surface", "review_packet_tranche"],
    ]
    assert contract["minimum_depth"] == 7


def test_wikidata_linkage_depth_audit_passes_synthetic_and_real_cases() -> None:
    audit = build_wikidata_linkage_depth_audit()

    assert audit["schema_version"] == "sl.wikidata_linkage_depth_audit.v0_1"
    assert audit["summary"] == {
        "case_count": 3,
        "complete_case_count": 3,
        "complete_case_ids": [
            "dog_soft_stitch",
            "climate_review_demonstrator",
            "disjointness_report",
        ],
        "role_erasure_case_count": 0,
        "role_erasure_case_ids": [],
        "anchor_failure_case_count": 0,
        "anchor_failure_case_ids": [],
        "wd_soft_stitch_case_count": 2,
        "wd_soft_stitch_case_ids": [
            "dog_soft_stitch",
            "climate_review_demonstrator",
        ],
        "emitted_artifact_case_count": 2,
        "contract_ids": [
            "sensiblaw_pnf_wd_linkage",
            "wikidata_disjointness_review_linkage",
        ],
        "primary_owner": "linkage_depth_projection_diagnostics",
    }
    by_id = {row["case_id"]: row for row in audit["cases"]}
    assert by_id["dog_soft_stitch"]["typed_path_depth"] == 7
    assert by_id["dog_soft_stitch"]["wd_promotion_blocked"] is True
    assert by_id["climate_review_demonstrator"]["lane_id"] == "climate_review_demonstrator"
    assert by_id["climate_review_demonstrator"]["case_source"] == "emitted_bridge_artifact"
    assert by_id["climate_review_demonstrator"]["linkage_depth_status"] == "complete"
    assert by_id["climate_review_demonstrator"]["anchor_to_tranche_reachability"]["anchor_count"] == 3
    assert by_id["climate_review_demonstrator"]["collapse_origin"] == "none"
    assert by_id["disjointness_report"]["contract_id"] == "wikidata_disjointness_review_linkage"
    assert by_id["disjointness_report"]["case_source"] == "emitted_bridge_artifact"
    assert by_id["disjointness_report"]["typed_path_depth"] == 6
    assert by_id["disjointness_report"]["wd_soft_stitch_present"] is False
    assert by_id["disjointness_report"]["anchor_to_tranche_reachability"]["anchor_count"] == 1


def test_climate_review_demonstrator_emits_linkage_depth_receipt() -> None:
    report = load_climate_review_demonstrator_with_linkage_receipt()

    receipt = report["linkage_depth_receipt"]
    assert receipt["schema_version"] == LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION
    assert receipt["artifact_type"] == "linkage_depth_receipt"
    assert receipt["source_mode"] == "emitted_bridge_artifact"
    assert receipt["contract"]["contract_id"] == "sensiblaw_pnf_wd_linkage"
    assert receipt["diagnostics"]["linkage_depth_status"] == "complete"
    assert receipt["diagnostics"]["wd_promotion_blocked"] is True
    assert receipt["diagnostics"]["anchor_to_tranche_reachability"]["all_reachable"] is True
    assert any(
        edge["metadata"]["promotion_status"] == "blocked"
        for edge in receipt["edges"]
        if edge["kind"] == "wd_soft_stitch"
    )


def test_disjointness_report_emits_linkage_depth_receipt() -> None:
    report = load_disjointness_report_with_linkage_receipt()

    receipt = report["linkage_depth_receipt"]
    contract = build_wikidata_disjointness_review_linkage_contract()
    assert receipt["schema_version"] == LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION
    assert receipt["artifact_type"] == "linkage_depth_receipt"
    assert receipt["source_mode"] == "emitted_bridge_artifact"
    assert receipt["contract"]["contract_id"] == contract["contract_id"]
    assert receipt["diagnostics"]["linkage_depth_status"] == "complete"
    assert receipt["diagnostics"]["wd_soft_stitch_present"] is False
    assert receipt["diagnostics"]["anchor_to_tranche_reachability"]["all_reachable"] is True
    assert [
        edge["kind"]
        for edge in receipt["edges"]
    ] == [
        "window_statement_bundle_projection",
        "pair_extraction",
        "contradiction_candidate_projection",
        "semantic_wd_candidate",
        "review_surface_projection",
        "review_packet_projection",
    ]


def test_generic_climate_demonstrator_remains_receipt_free() -> None:
    from src.ontology.wikidata_lane_receipts import _read_json, _sensiblaw_root

    root = _sensiblaw_root()
    climate_root = (
        root
        / "data"
        / "ontology"
        / "wikidata_migration_packs"
        / "p5991_p14143_climate_pilot_20260328"
    )
    fixture_root = root / "tests" / "fixtures" / "wikidata"
    report = build_wikidata_climate_review_demonstrator(
        _read_json(climate_root / "migration_pack.json"),
        climate_text_payload=_read_json(
            climate_root / "climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json"
        ),
        review_packet=_read_json(fixture_root / "wikidata_nat_review_packet_20260401.json"),
    )

    assert "linkage_depth_receipt" not in report


def test_generic_disjointness_report_remains_receipt_free() -> None:
    from src.ontology.wikidata_lane_receipts import _sensiblaw_root

    root = _sensiblaw_root()
    report = project_wikidata_disjointness_payload(
        load_disjointness_slice(
            root
            / "tests"
            / "fixtures"
            / "wikidata"
            / "disjointness_p2738_fixed_construction_real_pack_v1"
            / "slice.json"
        )
    )

    assert "linkage_depth_receipt" not in report


def test_linkage_depth_audit_detects_projection_collapse_when_pnf_bridge_is_removed() -> None:
    contract = build_sensiblaw_pnf_wd_linkage_contract()
    case = build_dog_soft_stitch_linkage_case()
    case["edges"] = [
        row
        for row in case["edges"]
        if not (
            row["source"] == "sentence_document:dog"
            and row["target"] == "sentence_pnf:dog"
        )
    ]

    audited = audit_linkage_depth_case(case, contract=contract)

    assert audited["linkage_depth_status"] == "shallow"
    assert audited["typed_path_depth"] == 1
    assert audited["anchor_to_tranche_reachability"]["all_reachable"] is False
    assert audited["collapse_origin"] == "projection"
    assert audited["collapse_points"] == [
        {
            "anchor_id": "token_span:dog",
            "after_layer": "sentence_document",
            "missing_layer": "sentence_pnf",
            "missing_bridge": "sentence_document->sentence_pnf",
        }
    ]


def test_shared_core_audits_mixed_wd_gwb_and_au_contracts(tmp_path) -> None:
    gwb_result = build_gwb_broader_review(tmp_path / "gwb-out")
    import json
    from pathlib import Path

    payload = json.loads(Path(gwb_result["artifact_path"]).read_text(encoding="utf-8"))
    gwb_report = build_gwb_broader_review_world_model_report_with_linkage_receipt(payload)
    au_bundle, _, _, _ = _prepare_au_fact_review_bundle_fixture(tmp_path / "au-fixture")
    au_bundle = attach_au_fact_review_bundle_linkage_receipt(au_bundle)

    audit = build_linkage_depth_audit(
        cases=[
            build_climate_review_linkage_case(),
            build_disjointness_report_linkage_case(),
            build_gwb_broader_review_linkage_case(gwb_report),
            build_au_fact_review_bundle_linkage_case(au_bundle),
        ],
        audit_scope="mixed_wd_gwb_au_linkage_depth",
    )

    assert audit["schema_version"] == "sl.linkage_depth_audit.v0_1"
    assert audit["summary"]["case_count"] == 4
    assert audit["summary"]["complete_case_count"] == 4
    assert audit["summary"]["contract_ids"] == [
        AU_FACT_REVIEW_BUNDLE_LINKAGE_CONTRACT_ID,
        GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID,
        "sensiblaw_pnf_wd_linkage",
        "wikidata_disjointness_review_linkage",
    ]
    by_id = {row["case_id"]: row for row in audit["cases"]}
    assert by_id["au_fact_review_bundle"]["contract_id"] == AU_FACT_REVIEW_BUNDLE_LINKAGE_CONTRACT_ID
    assert by_id["au_fact_review_bundle"]["typed_path_depth"] == 7
    assert by_id["au_fact_review_bundle"]["authority_boundary_visibility"] == "complete"
    assert by_id["gwb_broader_review"]["contract_id"] == GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID
    assert by_id["gwb_broader_review"]["typed_path_depth"] == 5
    assert by_id["gwb_broader_review"]["wd_soft_stitch_present"] is False


def test_shared_core_audits_mixed_wd_gwb_au_q43229_and_brexit_contracts(tmp_path) -> None:
    gwb_result = build_gwb_broader_review(tmp_path / "gwb-out")
    import json
    from pathlib import Path

    payload = json.loads(Path(gwb_result["artifact_path"]).read_text(encoding="utf-8"))
    gwb_report = build_gwb_broader_review_world_model_report_with_linkage_receipt(payload)
    au_bundle, _, _, _ = _prepare_au_fact_review_bundle_fixture(tmp_path / "au-fixture")
    au_bundle = attach_au_fact_review_bundle_linkage_receipt(au_bundle)
    q43229_report = load_q43229_superclass_pressure_report_with_linkage_receipt()
    brexit_report = build_brexit_national_archives_world_model_report_with_linkage_receipt(
        normalized_archive_records()
    )

    audit = build_linkage_depth_audit(
        cases=[
            build_climate_review_linkage_case(),
            build_disjointness_report_linkage_case(),
            build_gwb_broader_review_linkage_case(gwb_report),
            build_au_fact_review_bundle_linkage_case(au_bundle),
            build_wikidata_q43229_superclass_pressure_linkage_case(q43229_report),
            build_brexit_archive_policy_intent_linkage_case(brexit_report),
        ],
        audit_scope="mixed_wd_gwb_au_q43229_brexit_linkage_depth",
    )

    assert audit["summary"]["case_count"] == 6
    assert audit["summary"]["complete_case_count"] == 6
    assert set(audit["summary"]["contract_ids"]) == {
        AU_FACT_REVIEW_BUNDLE_LINKAGE_CONTRACT_ID,
        BREXIT_ARCHIVE_POLICY_INTENT_LINKAGE_CONTRACT_ID,
        GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID,
        WIKIDATA_Q43229_SUPERCLASS_PRESSURE_LINKAGE_CONTRACT_ID,
        "sensiblaw_pnf_wd_linkage",
        "wikidata_disjointness_review_linkage",
    }
    by_id = {row["case_id"]: row for row in audit["cases"]}
    assert by_id["wikidata_q43229_superclass_pressure"]["typed_path_depth"] == 6
    assert by_id["wikidata_q43229_superclass_pressure"]["candidate_vs_promoted_visibility"] is True
    assert by_id["brexit_archive_policy_intent"]["typed_path_depth"] == 6
    assert by_id["brexit_archive_policy_intent"]["visibility_requirements"]["archive_authority_visibility"][
        "values"
    ] == ["complete"]


def test_wikidata_linkage_depth_wrapper_uses_shared_core(monkeypatch) -> None:
    def _fake_build_linkage_depth_audit(*, cases, contracts=None, audit_scope="linkage_depth", schema_version="", next_actions=(), primary_owner=""):
        assert len(cases) == 1
        assert cases[0]["case_id"] == "dog_soft_stitch"
        assert audit_scope == "bounded_pnf_x_zelph_wd_linkage_depth"
        return {
            "schema_version": schema_version,
            "audit_scope": audit_scope,
            "contracts": contracts or [],
            "summary": {
                "case_count": 1,
                "complete_case_count": 1,
                "complete_case_ids": ["dog_soft_stitch"],
                "role_erasure_case_count": 0,
                "role_erasure_case_ids": [],
                "anchor_failure_case_count": 0,
                "anchor_failure_case_ids": [],
                "wd_soft_stitch_case_count": 1,
                "wd_soft_stitch_case_ids": ["dog_soft_stitch"],
                "emitted_artifact_case_count": 0,
                "contract_ids": ["sensiblaw_pnf_wd_linkage"],
                "primary_owner": "linkage_depth_projection_diagnostics",
            },
            "cases": [{"case_id": "dog_soft_stitch"}],
            "next_actions": list(next_actions),
        }

    monkeypatch.setattr(wikidata_linkage_depth, "build_linkage_depth_audit", _fake_build_linkage_depth_audit)

    report = wikidata_linkage_depth.build_wikidata_linkage_depth_audit(case_id="dog_soft_stitch")

    assert report["schema_version"] == "sl.wikidata_linkage_depth_audit.v0_1"
    assert report["summary"]["complete_case_ids"] == ["dog_soft_stitch"]
