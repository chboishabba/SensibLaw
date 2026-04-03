import json
from pathlib import Path
import csv

import jsonschema
import yaml

from src.ontology.wikidata import (
    MIGRATION_PACK_SCHEMA_VERSION,
    SCHEMA_VERSION,
    SPLIT_PLAN_SCHEMA_VERSION,
    SOURCE_UNIT_SCHEMA_VERSION,
    WIKIDATA_REVIEW_PACKET_SCHEMA_VERSION,
    WIKIDATA_PHI_TEXT_BRIDGE_CASE_SCHEMA_VERSION,
    WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION,
    adapt_legacy_climate_text_source_to_source_units,
    attach_wikidata_phi_text_bridge,
    attach_wikidata_phi_text_bridge_from_observation_claim,
    attach_wikidata_phi_text_bridge_from_source_units,
    attach_wikidata_phi_text_bridge_from_revision_locked_climate_text,
    build_wikidata_review_packet,
    build_nat_cohort_c_population_scan,
    build_nat_cohort_c_population_scan_from_sparql_results,
    build_nat_cohort_c_population_scan_live,
    build_nat_cohort_c_operator_packet,
    build_observation_claim_payload_from_source_units,
    build_observation_claim_payload_from_revision_locked_climate_text_sources,
    build_wikidata_split_plan,
    build_wikidata_phi_text_bridge_case,
    build_wikidata_migration_pack,
    extract_phi_text_observations_from_observation_claim_payload,
    export_migration_pack_checked_safe_csv,
    export_migration_pack_openrefine_csv,
    project_wikidata_payload,
    verify_migration_pack_against_after_state,
)
from src.ontology.wikidata_grounding_depth import build_grounding_depth_summary


def _load_migration_pack_schema() -> dict:
    return yaml.safe_load(Path("schemas/sl.wikidata_migration_pack.v1.schema.yaml").read_text(encoding="utf-8"))


def _load_bridge_schema() -> dict:
    return yaml.safe_load(Path("schemas/sl.wikidata_phi_text_bridge_case.v1.schema.yaml").read_text(encoding="utf-8"))


def _load_climate_text_source_schema() -> dict:
    return yaml.safe_load(Path("schemas/sl.wikidata.climate_text_source.v1.schema.yaml").read_text(encoding="utf-8"))


def _load_source_unit_schema() -> dict:
    return yaml.safe_load(Path("schemas/sl.source_unit.v1.schema.yaml").read_text(encoding="utf-8"))


def _load_split_plan_schema() -> dict:
    return yaml.safe_load(Path("schemas/sl.wikidata_split_plan.v0_1.schema.yaml").read_text(encoding="utf-8"))


def _load_review_packet_schema() -> dict:
    return yaml.safe_load(Path("schemas/sl.wikidata_review_packet.v0_1.schema.yaml").read_text(encoding="utf-8"))


def _load_wiki_revision_source_unit_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wiki_revision_source_unit_fixture_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_wdu_sandbox_source_unit_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wiki_revision_nat_wdu_sandbox_p5991_p14143_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_lane_review_manifests_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_lane_review_manifests_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_c_branch_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_c_branch_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_c_population_scan_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_c_population_scan_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_seed_slice_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_seed_slice_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_shape_scan_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_shape_scan_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_review_only_export_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_review_only_export_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_split_plan_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_split_plan_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_classification_checkpoint_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_classification_checkpoint_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_review_packet_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_review_packet_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_review_packet_attachment_coverage_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_review_packet_attachment_coverage_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_review_packet_sidecar_fixture(qid: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / f"wikidata_nat_review_packet_{qid}_sidecar_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_grounding_depth_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_packets_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_live_discovery_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_live_discovery_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_live_tranche_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_live_tranche_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_checked_safe_hunt_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_checked_safe_hunt_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_gate_b_candidate_verification_run_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_gate_b_candidate_verification_run_20260403.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_project_wikidata_payload_reports_sccs_and_mixed_order() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q_ref",
                        "property": "P279",
                        "value": "Q_pleb",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc1", "P813": "2026-03-07"}],
                    },
                    {
                        "subject": "Q_pleb",
                        "property": "P279",
                        "value": "Q_ref",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc1"}],
                    },
                    {
                        "subject": "Q_alpha",
                        "property": "P31",
                        "value": "Q_writing_system",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc2"}],
                    },
                    {
                        "subject": "Q_alpha",
                        "property": "P279",
                        "value": "Q_symbol_system",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc2"}],
                    },
                    {
                        "subject": "Q_meta_child",
                        "property": "P31",
                        "value": "Q_meta_class",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc3"}],
                    },
                    {
                        "subject": "Q_meta_class",
                        "property": "P31",
                        "value": "Q_meta_super",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc3"}],
                    },
                ],
            },
            {
                "id": "t2",
                "statement_bundles": [
                    {
                        "subject": "Q_ref",
                        "property": "P279",
                        "value": "Q_pleb",
                        "rank": "deprecated",
                        "references": [{"P248": "Qsrc1", "P813": "2026-03-08"}],
                    },
                    {
                        "subject": "Q_pleb",
                        "property": "P279",
                        "value": "Q_ref",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc1"}],
                    },
                    {
                        "subject": "Q_alpha",
                        "property": "P31",
                        "value": "Q_writing_system",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc2"}],
                    },
                    {
                        "subject": "Q_alpha",
                        "property": "P279",
                        "value": "Q_symbol_system",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc2"}],
                    },
                ],
            },
        ]
    }

    report = project_wikidata_payload(payload)

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["bounded_slice"]["properties"] == ["P279", "P31"]
    assert report["windows"][0]["diagnostics"]["p279_sccs"][0]["members"] == ["Q_pleb", "Q_ref"]
    assert report["windows"][0]["diagnostics"]["mixed_order_nodes"][0]["qid"] == "Q_alpha"
    assert report["windows"][0]["diagnostics"]["metaclass_candidates"][0]["qid"] == "Q_meta_class"
    assert report["unstable_slots"][0]["slot_id"] == "Q_ref|P279"
    assert report["unstable_slots"][0]["tau_t1"] == 1
    assert report["unstable_slots"][0]["tau_t2"] == -1


def test_project_wikidata_payload_accepts_mapping_qualifiers() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P31",
                        "value": "Q2",
                        "rank": "preferred",
                        "qualifiers": {"P580": "1900", "P582": "1910"},
                        "references": [{"P248": ["Qsrc1", "Qsrc2"]}],
                    }
                ],
            }
        ]
    }

    report = project_wikidata_payload(payload)
    slot = report["windows"][0]["slots"][0]
    assert "P580" in slot["audit"][0]["qualifier_signature"]
    assert slot["sum_e"] == 3


def test_live_fixture_emits_mixed_order_and_nonzero_eii() -> None:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "live_p31_p279_slice_20260307.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    report = project_wikidata_payload(payload)

    assert report["windows"][0]["diagnostics"]["mixed_order_nodes"]
    assert report["windows"][0]["diagnostics"]["p279_sccs"]
    assert any(item["slot_id"] == "Q9779|P31" for item in report["unstable_slots"])
    assert any(
        node["qid"] == "Q21169592"
        for node in report["windows"][0]["diagnostics"]["mixed_order_nodes"]
    )
    unstable = next(item for item in report["unstable_slots"] if item["slot_id"] == "Q9779|P31")
    assert unstable["tau_t1"] == 1
    assert unstable["tau_t2"] == -1
    scc_member_sets = {
        tuple(entry["members"]) for entry in report["windows"][0]["diagnostics"]["p279_sccs"]
    }
    assert ("Q22652", "Q22698") in scc_member_sets
    assert ("Q188", "Q52040") in scc_member_sets


def test_qualifier_drift_fixture_emits_property_set_change() -> None:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "qualifier_drift_slice_20260307.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    report = project_wikidata_payload(payload, property_filter=("P166",))

    assert report["qualifier_drift"]
    drift = report["qualifier_drift"][0]
    assert drift["slot_id"] == "Qposthumous_case|P166"
    assert drift["qualifier_property_set_t1"] == ["P7452"]
    assert drift["qualifier_property_set_t2"] == ["P3831", "P585"]
    assert drift["severity"] == "high"


def test_real_imported_qualifier_slice_is_stable_baseline() -> None:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "real_qualifier_imported_slice_20260307.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    report = project_wikidata_payload(payload, property_filter=("P166",))

    assert report["qualifier_drift"] == []
    t1_slots = {
        slot["slot_id"]: slot for slot in report["windows"][0]["slots"]
    }
    assert t1_slots["Q28792860|P166"]["qualifier_property_set"] == ["P585"]
    assert t1_slots["Q1336181|P166"]["qualifier_property_set"] == [
        "P2241",
        "P585",
        "P7452",
    ]
    assert report["review_summary"]["qualifier_drift_counts"] == {
        "high": 0,
        "medium": 0,
        "low": 0,
    }


def test_project_wikidata_payload_reports_parthood_typing() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "QInstA",
                        "property": "P31",
                        "value": "QClassA",
                        "rank": "preferred",
                    },
                    {
                        "subject": "QInstB",
                        "property": "P31",
                        "value": "QClassA",
                        "rank": "preferred",
                    },
                    {
                        "subject": "QClassB",
                        "property": "P31",
                        "value": "QTop",
                        "rank": "preferred",
                    },
                    {
                        "subject": "QClassA",
                        "property": "P361",
                        "value": "QTop",
                        "rank": "preferred",
                    },
                    {
                        "subject": "QInstA",
                        "property": "P361",
                        "value": "QClassA",
                        "rank": "preferred",
                    },
                    {
                        "subject": "QInstA",
                        "property": "P527",
                        "value": "QInstB",
                        "rank": "preferred",
                    },
                    {
                        "subject": "QInstB",
                        "property": "P527",
                        "value": "QInstA",
                        "rank": "preferred",
                    },
                ],
            }
        ]
    }

    report = project_wikidata_payload(payload, property_filter=("P31", "P361", "P527"))
    diagnostics = report["windows"][0]["diagnostics"]["parthood_typing"]

    assert diagnostics["counts"]["class->class"] == 1
    assert diagnostics["counts"]["instance->class"] == 1
    assert diagnostics["counts"]["instance->instance"] == 2
    assert diagnostics["counts"]["mixed_redundant"] == 1

    assert {
        (
            row["subject_qid"],
            row["property_pid"],
            row["value_qid"],
            row["bucket"],
            row["classification"],
        )
        for row in diagnostics["classifications"]
    } == {
        ("QClassA", "P361", "QTop", "class->class", "certain"),
        ("QInstA", "P361", "QClassA", "instance->class", "certain"),
        ("QInstA", "P527", "QInstB", "instance->instance", "certain"),
        ("QInstB", "P527", "QInstA", "instance->instance", "certain"),
    }


def test_build_wikidata_migration_pack_classifies_reference_and_qualifier_drift() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "100",
                        "rank": "preferred",
                        "qualifiers": {"P585": "2024"},
                        "references": [{"P248": "Qsrc1"}],
                    },
                    {
                        "subject": "Q2",
                        "property": "P5991",
                        "value": "200",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc1"}],
                    },
                ],
            },
            {
                "id": "t2",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "100",
                        "rank": "preferred",
                        "qualifiers": {"P585": "2024", "P7452": "Qreason"},
                        "references": [{"P248": "Qsrc1"}],
                    },
                    {
                        "subject": "Q2",
                        "property": "P5991",
                        "value": "200",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc1", "P813": "2026-03-28"}],
                    },
                    {
                        "subject": "Q3",
                        "property": "P5991",
                        "value": "300",
                        "rank": "preferred",
                        "references": [{"P248": "Qsrc2"}],
                    },
                ],
            },
        ]
    }

    report = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )

    assert report["schema_version"] == MIGRATION_PACK_SCHEMA_VERSION
    assert report["summary"]["candidate_count"] == 3
    by_entity = {item["entity_qid"]: item for item in report["candidates"]}
    assert by_entity["Q1"]["classification"] == "qualifier_drift"
    assert by_entity["Q1"]["qualifier_diff"]["status"] == "qualifier_drift"
    assert by_entity["Q2"]["classification"] == "reference_drift"
    assert by_entity["Q2"]["reference_diff"]["status"] == "reference_drift"
    assert by_entity["Q3"]["classification"] == "safe_with_reference_transfer"
    assert by_entity["Q3"]["claim_bundle_after"]["property"] == "P14143"


def test_build_wikidata_migration_pack_allows_normal_rank_when_evidence_exists() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "100",
                        "rank": "normal",
                        "references": [{"P248": "Qsrc"}],
                    }
                ],
            },
            {
                "id": "t2",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "100",
                        "rank": "normal",
                        "references": [{"P248": "Qsrc"}],
                    }
                ],
            },
        ]
    }

    report = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )

    assert report["summary"]["checked_safe_subset"] == [
        report["candidates"][0]["candidate_id"]
    ]
    assert report["candidates"][0]["classification"] == "safe_with_reference_transfer"
    assert report["candidates"][0]["action"] == "migrate_with_refs"
    assert report["candidates"][0]["split_axes"] == []


def test_build_wikidata_migration_pack_graduates_temporal_multi_value_cases_to_split_required() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "100",
                        "rank": "normal",
                        "qualifiers": {"P585": "2023"},
                        "references": [{"P248": "Qsrc"}],
                    }
                ],
            },
            {
                "id": "t2",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "100",
                        "rank": "normal",
                        "qualifiers": {"P585": "2023"},
                        "references": [{"P248": "Qsrc"}],
                    },
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "120",
                        "rank": "normal",
                        "qualifiers": {"P585": "2024"},
                        "references": [{"P248": "Qsrc"}],
                    },
                ],
            },
        ]
    }

    report = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )

    assert report["summary"]["counts_by_bucket"] == {"split_required": 2}
    for candidate in report["candidates"]:
        assert candidate["classification"] == "split_required"
        assert candidate["action"] == "split"
        assert "multi_value_slot" in candidate["reasons"]
        assert {"property": "__value__", "cardinality": 2, "source": "slot", "reason": "multi_value_slot"} in candidate["split_axes"]
        assert {"property": "P585", "cardinality": 2, "source": "slot", "reason": "multi_valued_dimension"} in candidate["split_axes"]
        assert candidate["text_evidence_refs"] == []
        assert candidate["bridge_case_ref"] is None
        assert candidate["pressure"] is None
        assert candidate["pressure_confidence"] is None
        assert candidate["pressure_summary"] is None
    assert report["bridge_cases"] == []
    jsonschema.validate(report, _load_migration_pack_schema())


def test_build_wikidata_phi_text_bridge_case_emits_split_pressure_for_temporal_text_slices() -> None:
    migration_pack = build_wikidata_migration_pack(
        {
            "windows": [
                {
                    "id": "t1",
                    "statement_bundles": [
                        {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {},
                            "references": [{"P248": "Qsrc"}],
                        }
                    ],
                }
            ]
        },
        source_property="P5991",
        target_property="P14143",
    )
    candidate = migration_pack["candidates"][0]

    bridge_case = build_wikidata_phi_text_bridge_case(
        candidate,
        text_observations=[
            {
                "observation_ref": "obs:1",
                "source_ref": "source:doc1",
                "anchors": [{"start": 0, "end": 10, "text": "2018 40"}],
                "subject": "Q1",
                "predicate": "annual_emissions",
                "object": "100",
                "qualifiers": {"P585": "2018"},
                "promotion_status": "promoted_true",
            },
            {
                "observation_ref": "obs:2",
                "source_ref": "source:doc1",
                "anchors": [{"start": 20, "end": 30, "text": "2019 60"}],
                "subject": "Q1",
                "predicate": "annual_emissions",
                "object": "100",
                "qualifiers": {"P585": "2019"},
                "promotion_status": "promoted_true",
            },
        ],
    )

    assert bridge_case["schema_version"] == WIKIDATA_PHI_TEXT_BRIDGE_CASE_SCHEMA_VERSION
    assert bridge_case["pressure"] == "split_pressure"
    assert bridge_case["comparison"]["missing_dimensions"]
    jsonschema.validate(bridge_case, _load_bridge_schema())


def test_build_wikidata_phi_text_bridge_case_treats_out_of_period_value_mismatch_as_split_pressure() -> None:
    migration_pack = build_wikidata_migration_pack(
        {
            "windows": [
                {
                    "id": "t1",
                    "statement_bundles": [
                        {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "852",
                            "rank": "normal",
                            "qualifiers": {
                                "P580": "+2023-01-01T00:00:00Z",
                                "P582": "+2023-12-31T00:00:00Z",
                            },
                            "references": [{"P248": "Qsrc"}],
                        }
                    ],
                }
            ]
        },
        source_property="P5991",
        target_property="P14143",
    )
    candidate = migration_pack["candidates"][0]

    bridge_case = build_wikidata_phi_text_bridge_case(
        candidate,
        text_observations=[
            {
                "observation_ref": "obs:2019",
                "source_ref": "source:doc1",
                "anchors": [{"start": 0, "end": 15, "text": "2019 scope 1 86"}],
                "subject": "Q1",
                "predicate": "annual_emissions",
                "object": "86",
                "qualifiers": {"P585": "2019"},
                "promotion_status": "promoted_true",
            }
        ],
    )

    assert bridge_case["pressure"] == "split_pressure"
    assert bridge_case["comparison"]["conflicts"] == []
    assert {
        "kind": "value_mismatch_outside_bundle_period",
        "detail": "text observation obs:2019 carries year(s) ['2019'] outside bundle year(s) ['2023']",
    } in bridge_case["comparison"]["missing_dimensions"]
    jsonschema.validate(bridge_case, _load_bridge_schema())


def test_build_wikidata_phi_text_bridge_case_treats_scope_mismatch_as_split_pressure() -> None:
    migration_pack = build_wikidata_migration_pack(
        {
            "windows": [
                {
                    "id": "t1",
                    "statement_bundles": [
                        {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "852",
                            "rank": "normal",
                            "qualifiers": {
                                "P518": "scope_2",
                                "P585": "2023",
                            },
                            "references": [{"P248": "Qsrc"}],
                        }
                    ],
                }
            ]
        },
        source_property="P5991",
        target_property="P14143",
    )
    candidate = migration_pack["candidates"][0]

    bridge_case = build_wikidata_phi_text_bridge_case(
        candidate,
        text_observations=[
            {
                "observation_ref": "obs:scope1",
                "source_ref": "source:doc1",
                "anchors": [{"start": 0, "end": 22, "text": "2023 scope 1 emissions"}],
                "subject": "Q1",
                "predicate": "annual_emissions",
                "object": "86",
                "qualifiers": {"P585": "2023", "P518": ["scope_1"]},
                "promotion_status": "promoted_true",
            }
        ],
    )

    assert bridge_case["pressure"] == "split_pressure"
    assert bridge_case["comparison"]["conflicts"] == []
    assert {
        "kind": "scope_dimension_mismatch",
        "detail": "text scope tag(s) ['scope_1'] do not match bundle scope value(s) ['scope_2']",
    } in bridge_case["comparison"]["missing_dimensions"]
    assert {
        "kind": "value_mismatch_outside_bundle_scope",
        "detail": "text observation obs:scope1 carries scope tag(s) ['scope_1'] outside bundle scope value(s) ['scope_2']",
    } in bridge_case["comparison"]["missing_dimensions"]
    jsonschema.validate(bridge_case, _load_bridge_schema())


def test_attach_wikidata_phi_text_bridge_enriches_migration_pack_additively() -> None:
    migration_pack = build_wikidata_migration_pack(
        {
            "windows": [
                {
                    "id": "t1",
                    "statement_bundles": [
                        {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {},
                            "references": [{"P248": "Qsrc"}],
                        }
                    ],
                }
            ]
        },
        source_property="P5991",
        target_property="P14143",
    )

    candidate_id = migration_pack["candidates"][0]["candidate_id"]
    enriched = attach_wikidata_phi_text_bridge(
        migration_pack,
        observations_by_candidate={
            candidate_id: [
                {
                    "observation_ref": "obs:contradiction",
                    "source_ref": "source:doc1",
                    "anchors": [{"start": 0, "end": 12, "text": "emissions 220"}],
                    "subject": "Q1",
                    "predicate": "annual_emissions",
                    "object": "220",
                    "qualifiers": {"P585": "2024"},
                    "promotion_status": "promoted_true",
                }
            ]
        },
    )

    candidate = enriched["candidates"][0]
    assert candidate["bridge_case_ref"] == "bridge://wikidata/Q1|P5991|1"
    assert candidate["text_evidence_refs"] == ["obs:contradiction"]
    assert candidate["pressure"] == "contradiction"
    assert candidate["pressure_confidence"] == 0.78
    assert "conflict" in candidate["pressure_summary"].lower()
    assert len(enriched["bridge_cases"]) == 1
    jsonschema.validate(enriched, _load_migration_pack_schema())


def test_extract_phi_text_observations_from_observation_claim_payload_uses_real_contract_shape() -> None:
    payload = {
        "payload_version": "sl.observation_claim.contract.v1",
        "observations": [
            {
                "observation_id": "obs:1",
                "source_unit_id": "unit:1",
                "source_quote": "2018 emissions were 100.",
                "source_span": {"start_char": 0, "end_char": 24},
                "evidence_refs": [{"span_ref": "unit:1:0-24", "ref_type": "text_span"}],
                "status": "active",
                "canonicality": "verified",
                "payload_version": "sl.observation_claim.contract.v1",
                "hash": "obs-hash-1",
                "asserted_at": "2026-03-28T00:00:00Z",
                "observed_at": "2018",
            },
            {
                "observation_id": "obs:2",
                "source_unit_id": "unit:1",
                "source_quote": "2019 emissions were 100.",
                "source_span": {"start_char": 30, "end_char": 54},
                "evidence_refs": [{"span_ref": "unit:1:30-54", "ref_type": "text_span"}],
                "status": "active",
                "canonicality": "adjudicated",
                "payload_version": "sl.observation_claim.contract.v1",
                "hash": "obs-hash-2",
                "asserted_at": "2026-03-28T00:00:00Z",
                "observed_at": "2019",
            },
        ],
        "claims": [
            {
                "claim_id": "claim:1",
                "observation_id": "obs:1",
                "predicate": "annual_emissions",
                "subject_id": "Q1",
                "object_id": "100",
                "subject_type": "entity",
                "object_type": "quantity",
                "norm_id": None,
                "posture": "asserted",
                "evidence_quality": "high",
                "confidence": 0.92,
                "claim_created_at": "2026-03-28T00:00:00Z",
                "claim_updated_at": "2026-03-28T00:00:00Z",
                "evidence_links": ["link:1"],
                "hash": "claim-hash-1",
            },
            {
                "claim_id": "claim:2",
                "observation_id": "obs:2",
                "predicate": "annual_emissions",
                "subject_id": "Q1",
                "object_id": "100",
                "subject_type": "entity",
                "object_type": "quantity",
                "norm_id": None,
                "posture": "asserted",
                "evidence_quality": "high",
                "confidence": 0.95,
                "claim_created_at": "2026-03-28T00:00:00Z",
                "claim_updated_at": "2026-03-28T00:00:00Z",
                "evidence_links": ["link:2"],
                "hash": "claim-hash-2",
            },
        ],
        "evidence_links": [
            {"link_id": "link:1", "claim_id": "claim:1", "link_kind": "supporting", "link_hash": "lh1"},
            {"link_id": "link:2", "claim_id": "claim:2", "link_kind": "supporting", "link_hash": "lh2"},
        ],
    }

    observations = extract_phi_text_observations_from_observation_claim_payload(
        payload,
        subject_id="Q1",
        predicate_allowlist=("annual_emissions",),
    )

    assert len(observations) == 2
    assert observations[0]["promotion_status"] == "promoted_true"
    assert observations[0]["source_ref"] == "unit:1"
    assert observations[0]["qualifiers"]["P585"] == "2018"


def test_extract_phi_text_observations_from_observation_claim_payload_carries_scope_tags_from_evidence_links() -> None:
    payload = {
        "payload_version": "sl.observation_claim.contract.v1",
        "observations": [
            {
                "observation_id": "obs:1",
                "source_unit_id": "unit:1",
                "source_quote": "2018 scope 1 emissions were 100.",
                "source_span": {"start_char": 0, "end_char": 32},
                "evidence_refs": [{"span_ref": "unit:1:0-32", "ref_type": "text_span"}],
                "status": "active",
                "canonicality": "verified",
                "payload_version": "sl.observation_claim.contract.v1",
                "hash": "obs-hash-1",
                "asserted_at": "2026-03-28T00:00:00Z",
                "observed_at": "2018",
            }
        ],
        "claims": [
            {
                "claim_id": "claim:1",
                "observation_id": "obs:1",
                "predicate": "annual_emissions",
                "subject_id": "Q1",
                "object_id": "100",
                "subject_type": "entity",
                "object_type": "quantity",
                "norm_id": None,
                "posture": "asserted",
                "evidence_quality": "high",
                "confidence": 0.92,
                "claim_created_at": "2026-03-28T00:00:00Z",
                "claim_updated_at": "2026-03-28T00:00:00Z",
                "evidence_links": ["link:1"],
                "hash": "claim-hash-1",
            }
        ],
        "evidence_links": [
            {
                "link_id": "link:1",
                "claim_id": "claim:1",
                "link_kind": "supporting",
                "trace_refs": ["scope_tag:scope_1"],
                "link_hash": "lh1",
            }
        ],
    }

    observations = extract_phi_text_observations_from_observation_claim_payload(
        payload,
        subject_id="Q1",
        predicate_allowlist=("annual_emissions",),
    )

    assert observations == [
        {
            "observation_ref": "claim:1",
            "source_ref": "unit:1",
            "anchors": [{"start": 0, "end": 32, "text": "2018 scope 1 emissions were 100."}],
            "subject": "Q1",
            "predicate": "annual_emissions",
            "object": "100",
            "qualifiers": {"P585": "2018", "P518": ["scope_1"]},
            "promotion_status": "promoted_true",
        }
    ]


def test_attach_wikidata_phi_text_bridge_from_observation_claim_uses_real_producer() -> None:
    migration_pack = build_wikidata_migration_pack(
        {
            "windows": [
                {
                    "id": "t1",
                    "statement_bundles": [
                        {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {},
                            "references": [{"P248": "Qsrc"}],
                        }
                    ],
                }
            ]
        },
        source_property="P5991",
        target_property="P14143",
    )

    observation_claim_payload = {
        "payload_version": "sl.observation_claim.contract.v1",
        "observations": [
            {
                "observation_id": "obs:1",
                "source_unit_id": "unit:1",
                "source_quote": "2018 emissions were 100.",
                "source_span": {"start_char": 0, "end_char": 24},
                "evidence_refs": [{"span_ref": "unit:1:0-24", "ref_type": "text_span"}],
                "status": "active",
                "canonicality": "verified",
                "payload_version": "sl.observation_claim.contract.v1",
                "hash": "obs-hash-1",
                "asserted_at": "2026-03-28T00:00:00Z",
                "observed_at": "2018",
            },
            {
                "observation_id": "obs:2",
                "source_unit_id": "unit:1",
                "source_quote": "2019 emissions were 100.",
                "source_span": {"start_char": 30, "end_char": 54},
                "evidence_refs": [{"span_ref": "unit:1:30-54", "ref_type": "text_span"}],
                "status": "active",
                "canonicality": "verified",
                "payload_version": "sl.observation_claim.contract.v1",
                "hash": "obs-hash-2",
                "asserted_at": "2026-03-28T00:00:00Z",
                "observed_at": "2019",
            },
        ],
        "claims": [
            {
                "claim_id": "claim:1",
                "observation_id": "obs:1",
                "predicate": "annual_emissions",
                "subject_id": "Q1",
                "object_id": "100",
                "subject_type": "entity",
                "object_type": "quantity",
                "norm_id": None,
                "posture": "asserted",
                "evidence_quality": "high",
                "confidence": 0.92,
                "claim_created_at": "2026-03-28T00:00:00Z",
                "claim_updated_at": "2026-03-28T00:00:00Z",
                "evidence_links": ["link:1"],
                "hash": "claim-hash-1",
            },
            {
                "claim_id": "claim:2",
                "observation_id": "obs:2",
                "predicate": "annual_emissions",
                "subject_id": "Q1",
                "object_id": "100",
                "subject_type": "entity",
                "object_type": "quantity",
                "norm_id": None,
                "posture": "asserted",
                "evidence_quality": "high",
                "confidence": 0.95,
                "claim_created_at": "2026-03-28T00:00:00Z",
                "claim_updated_at": "2026-03-28T00:00:00Z",
                "evidence_links": ["link:2"],
                "hash": "claim-hash-2",
            },
        ],
        "evidence_links": [
            {"link_id": "link:1", "claim_id": "claim:1", "link_kind": "supporting", "link_hash": "lh1"},
            {"link_id": "link:2", "claim_id": "claim:2", "link_kind": "supporting", "link_hash": "lh2"},
        ],
    }

    enriched = attach_wikidata_phi_text_bridge_from_observation_claim(
        migration_pack,
        observation_claim_payload=observation_claim_payload,
        predicate_allowlist=("annual_emissions",),
    )

    candidate = enriched["candidates"][0]
    assert candidate["pressure"] == "split_pressure"
    assert candidate["text_evidence_refs"] == ["claim:1", "claim:2"]
    assert len(enriched["bridge_cases"]) == 1
    jsonschema.validate(enriched, _load_migration_pack_schema())


def test_build_observation_claim_payload_from_revision_locked_climate_text_sources_extracts_year_value_rows() -> None:
    climate_text_payload = {
        "schema_version": WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION,
        "sources": [
            {
                "source_id": "climate-src:1",
                "entity_qid": "Q1",
                "source_unit_id": "unit:q1:r1",
                "revision_id": "123",
                "revision_timestamp": "2026-03-28T00:00:00Z",
                "text": (
                    "Carbon footprint 2018: 100 tCO2e\n"
                    "Carbon footprint 2019: 100 tCO2e\n"
                    "General note without a climate value\n"
                ),
            }
        ],
    }

    jsonschema.validate(climate_text_payload, _load_climate_text_source_schema())
    observation_claim_payload = build_observation_claim_payload_from_revision_locked_climate_text_sources(
        climate_text_payload
    )

    contract_schema = yaml.safe_load(
        Path("schemas/sl.observation_claim.contract.v1.schema.yaml").read_text(encoding="utf-8")
    )
    jsonschema.validate(observation_claim_payload, contract_schema)

    assert observation_claim_payload["payload_version"] == "sl.observation_claim.contract.v1"
    assert len(observation_claim_payload["observations"]) == 2
    assert [row["observed_at"] for row in observation_claim_payload["observations"]] == ["2018", "2019"]
    assert [row["object_id"] for row in observation_claim_payload["claims"]] == ["100", "100"]
    trace_refs = [row["trace_refs"] for row in observation_claim_payload["evidence_links"]]
    assert trace_refs == [
        ["revision:123", "source:climate-src:1"],
        ["revision:123", "source:climate-src:1"],
    ]


def test_adapt_legacy_climate_text_source_to_source_units_is_schema_valid() -> None:
    climate_text_payload = {
        "schema_version": WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION,
        "sources": [
            {
                "source_id": "climate-src:1",
                "entity_qid": "Q1",
                "source_unit_id": "unit:q1:r1",
                "revision_id": "123",
                "revision_timestamp": "2026-03-28T00:00:00Z",
                "source_url": "https://example.test/report.pdf",
                "title": "Report",
                "text": "Carbon footprint 2018: 100 tCO2e\n",
            }
        ],
    }

    payload = adapt_legacy_climate_text_source_to_source_units(climate_text_payload)

    assert payload["schema_version"] == SOURCE_UNIT_SCHEMA_VERSION
    assert payload["source_units"][0]["revision"]["retrieval_method"] == "pdf_snapshot"
    assert payload["source_units"][0]["origin"]["source_type"] == "pdf"
    assert payload["source_units"][0]["metadata"] == {}
    jsonschema.validate(payload, _load_source_unit_schema())


def test_build_observation_claim_payload_from_source_units_extracts_html_snapshot_rows() -> None:
    source_unit_payload = {
        "schema_version": SOURCE_UNIT_SCHEMA_VERSION,
        "source_units": [
            {
                "source_id": "html-src:1",
                "entity_qid": "Q1",
                "source_unit_id": "unit:q1:html1",
                "revision": {
                    "revision_id": "snapshot:1",
                    "revision_timestamp": "2026-03-28T00:00:00Z",
                    "retrieval_method": "html_snapshot",
                },
                "origin": {
                    "source_type": "html",
                    "source_url": "https://example.test/esg",
                    "title": "ESG snapshot",
                },
                "content": {
                    "format": "text",
                    "text": "In 2018 emissions were 400 tCO2e.\nIn 2019 emissions were 600 tCO2e.\n",
                },
                "anchors": [],
                "metadata": {},
            }
        ],
    }

    jsonschema.validate(source_unit_payload, _load_source_unit_schema())
    observation_claim_payload = build_observation_claim_payload_from_source_units(source_unit_payload)

    contract_schema = yaml.safe_load(
        Path("schemas/sl.observation_claim.contract.v1.schema.yaml").read_text(encoding="utf-8")
    )
    jsonschema.validate(observation_claim_payload, contract_schema)

    assert [row["observed_at"] for row in observation_claim_payload["observations"]] == ["2018", "2019"]
    assert [row["object_id"] for row in observation_claim_payload["claims"]] == ["400", "600"]


def test_build_observation_claim_payload_from_source_units_carries_scope_tags_from_metadata() -> None:
    source_unit_payload = {
        "schema_version": SOURCE_UNIT_SCHEMA_VERSION,
        "source_units": [
            {
                "source_id": "html-src:1",
                "entity_qid": "Q1",
                "source_unit_id": "unit:q1:html1",
                "revision": {
                    "revision_id": "snapshot:1",
                    "revision_timestamp": "2026-03-28T00:00:00Z",
                    "retrieval_method": "wiki_revision",
                },
                "origin": {
                    "source_type": "wiki",
                    "source_url": "https://en.wikipedia.org/wiki/Example",
                    "title": "Example revision",
                },
                "content": {
                    "format": "text",
                    "text": "In 2018 emissions were 100 tCO2e.\n",
                },
                "anchors": [],
                "metadata": {"scope_tags": ["scope_1"]},
            }
        ],
    }

    observation_claim_payload = build_observation_claim_payload_from_source_units(source_unit_payload)

    assert observation_claim_payload["evidence_links"][0]["trace_refs"] == [
        "revision:snapshot:1",
        "source:html-src:1",
        "scope_tag:scope_1",
    ]


def test_wiki_revision_source_unit_fixture_is_schema_valid() -> None:
    payload = _load_wiki_revision_source_unit_fixture()

    jsonschema.validate(payload, _load_source_unit_schema())
    source_unit = payload["source_units"][0]
    assert source_unit["revision"]["retrieval_method"] == "wiki_revision"
    assert source_unit["origin"]["source_type"] == "wiki"


def test_nat_wdu_sandbox_source_unit_fixture_is_schema_valid() -> None:
    payload = _load_nat_wdu_sandbox_source_unit_fixture()

    jsonschema.validate(payload, _load_source_unit_schema())
    source_unit = payload["source_units"][0]
    assert source_unit["revision"]["retrieval_method"] == "wiki_revision"
    assert source_unit["origin"]["source_type"] == "wiki"
    assert source_unit["metadata"]["migration_source_property"] == "P5991"
    assert source_unit["metadata"]["migration_target_property"] == "P14143"
    assert [anchor["label"] for anchor in source_unit["anchors"]] == [
        "migration_goal",
        "cohort_business_family",
        "expected_qualifier_family",
        "expected_reference_family",
        "query_anchor",
    ]


def test_nat_lane_review_manifests_fixture_pins_five_cohorts_and_progress_model() -> None:
    payload = _load_nat_lane_review_manifests_fixture()

    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["source_property"] == "P5991"
    assert payload["target_property"] == "P14143"
    assert [cohort["cohort_id"] for cohort in payload["cohorts"]] == [
        "business_family_reconciled",
        "other_reconciled_instance_of",
        "non_ghg_protocol_or_missing_p459",
        "missing_instance_of",
        "unreconciled_instance_of",
    ]
    assert payload["expected_qualifier_properties"] == [
        "P459",
        "P3831",
        "P585",
        "P580",
        "P582",
        "P518",
        "P7452",
    ]
    assert payload["expected_reference_properties"] == [
        "P854",
        "P1065",
        "P813",
        "P1476",
        "P2960",
    ]
    assert payload["summary"]["current_progress_count"] == 7
    assert payload["summary"]["total_progress_count"] == 8
    assert payload["summary"]["current_progress_ratio"] == 0.875
    assert payload["summary"]["next_priority_cohort"] == "business_family_reconciled"


def test_nat_lane_review_manifests_fixture_keeps_business_family_population_pinned() -> None:
    payload = _load_nat_lane_review_manifests_fixture()

    cohorts = {cohort["cohort_id"]: cohort for cohort in payload["cohorts"]}
    assert cohorts["business_family_reconciled"]["population"] == 37665
    assert cohorts["missing_instance_of"]["population"] == 1395
    assert cohorts["unreconciled_instance_of"]["population"] == 142
    assert cohorts["other_reconciled_instance_of"]["population"] is None
    assert cohorts["non_ghg_protocol_or_missing_p459"]["population"] is None
    assert all(cohort["status"] == "manifest_pinned" for cohort in payload["cohorts"])


def test_nat_cohort_c_branch_fixture_pins_non_ghg_or_missing_p459_branch_state() -> None:
    payload = _load_nat_cohort_c_branch_fixture()

    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["cohort_id"] == "non_ghg_protocol_or_missing_p459"
    assert payload["status"] == "branch_pinned"
    assert payload["selection_rule"] == "determination method or standard (P459) is missing or not GHG protocol"
    assert payload["risk_level"] == "high"
    assert payload["population"] is None
    assert payload["next_gate"] == "review_first_population_scan"
    assert payload["expected_qualifier_properties"] == [
        "P459",
        "P3831",
        "P585",
        "P580",
        "P582",
        "P518",
        "P7452",
    ]
    assert payload["expected_reference_properties"] == [
        "P854",
        "P1065",
        "P813",
        "P1476",
        "P2960",
    ]


def test_nat_cohort_c_population_scan_helper_normalizes_review_first_candidates() -> None:
    payload = _load_nat_cohort_c_population_scan_fixture()

    scan = build_nat_cohort_c_population_scan(payload)

    assert scan["cohort_id"] == "non_ghg_protocol_or_missing_p459"
    assert scan["scan_status"] == "review_first_population_scan_ready"
    assert scan["next_gate"] == "review_first_population_scan"
    assert scan["summary"] == {
        "candidate_count": 3,
        "p459_status_counts": {"missing": 2, "non_GHG_protocol": 1},
        "review_first": True,
        "policy_risk": "high",
    }
    assert [candidate["qid"] for candidate in scan["sample_candidates"]] == [
        "Q30938280",
        "Q731938",
        "Q1785637",
    ]


def test_nat_cohort_c_live_population_scan_result_normalizer_groups_statement_rows() -> None:
    sparql_payload = {
        "results": {
            "bindings": [
                {
                    "item": {"value": "https://www.wikidata.org/entity/Q1"},
                    "itemLabel": {"value": "Example One"},
                    "statement": {"value": "https://www.wikidata.org/entity/statement/Q1-abc"},
                    "qualifier_pid": {"value": "P580"},
                },
                {
                    "item": {"value": "https://www.wikidata.org/entity/Q1"},
                    "itemLabel": {"value": "Example One"},
                    "statement": {"value": "https://www.wikidata.org/entity/statement/Q1-abc"},
                    "qualifier_pid": {"value": "P582"},
                },
                {
                    "item": {"value": "https://www.wikidata.org/entity/Q2"},
                    "itemLabel": {"value": "Example Two"},
                    "statement": {"value": "https://www.wikidata.org/entity/statement/Q2-def"},
                    "p459": {"value": "https://www.wikidata.org/entity/Q999"},
                    "p459Label": {"value": "Alt standard"},
                    "qualifier_pid": {"value": "P518"},
                },
            ]
        }
    }

    scan = build_nat_cohort_c_population_scan_from_sparql_results(sparql_payload)

    assert scan["scan_status"] == "live_population_scan_preview"
    assert scan["summary"] == {
        "candidate_count": 2,
        "p459_status_counts": {"missing": 1, "non_GHG_protocol": 1},
        "review_first": True,
        "policy_risk": "high",
    }
    assert scan["sample_candidates"][0]["qid"] == "Q1"
    assert scan["sample_candidates"][0]["p459_status"] == "missing"
    assert scan["sample_candidates"][0]["qualifier_properties"] == ["P580", "P582"]
    assert scan["sample_candidates"][1]["qid"] == "Q2"
    assert scan["sample_candidates"][1]["p459_status"] == "non_GHG_protocol"


def test_nat_cohort_c_live_population_scan_returns_fail_closed_when_query_fails(monkeypatch) -> None:
    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.ontology.wikidata._http_get_json", _raise)

    payload = build_nat_cohort_c_population_scan_live(row_limit=3, timeout_seconds=1)

    assert payload["scan_status"] == "live_population_scan_unavailable"
    assert payload["summary"] == {
        "candidate_count": 0,
        "p459_status_counts": {},
        "review_first": True,
        "policy_risk": "high",
    }
    assert payload["failures"][0]["stage"] == "live_query"


def test_nat_cohort_c_operator_packet_wraps_scan_payload_with_hold_or_review_decision() -> None:
    review_scan = _load_nat_cohort_c_population_scan_fixture()
    review_packet = build_nat_cohort_c_operator_packet(review_scan)
    assert review_packet["decision"] == "review"
    assert review_packet["governance"] == {
        "automation_allowed": False,
        "fail_closed": True,
        "live_query_unavailable": False,
    }
    assert review_packet["triage_prompts"][0].startswith("Review the candidate P459 status split")

    unavailable_scan = {
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "non_ghg_protocol_or_missing_p459",
        "scan_status": "live_population_scan_unavailable",
        "summary": {"p459_status_counts": {}, "review_first": True, "policy_risk": "high"},
        "sample_candidates": [],
        "notes": ["The live preview helper is fail-closed when the Wikidata query endpoint is unavailable."],
    }
    unavailable_packet = build_nat_cohort_c_operator_packet(unavailable_scan)
    assert unavailable_packet["decision"] == "hold"
    assert unavailable_packet["governance"]["live_query_unavailable"] is True
    assert unavailable_packet["triage_prompts"][0].startswith("Live query was unavailable")


def test_nat_cohort_a_seed_slice_fixture_pins_business_family_subset_materialization() -> None:
    payload = _load_nat_cohort_a_seed_slice_fixture()

    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["cohort_id"] == "business_family_reconciled"
    assert payload["status"] == "seed_slice_materialized"
    assert payload["instance_of_anchor"] == "Q4830453"
    assert payload["entity_qids"] == ["Q10403939", "Q10422059"]
    assert payload["candidate_span"]["candidate_count"] == 53
    assert payload["candidate_span"]["first_candidate_id"] == "Q10403939|P5991|1"
    assert payload["candidate_span"]["last_candidate_id"] == "Q10422059|P5991|29"
    assert payload["classification_counts"] == {"split_required": 53}
    assert payload["requires_review_count"] == 53
    assert payload["checked_safe_subset"] == []


def test_nat_cohort_a_shape_scan_fixture_is_shape_clean_against_nat_expectations() -> None:
    payload = _load_nat_cohort_a_shape_scan_fixture()

    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["cohort_id"] == "business_family_reconciled"
    assert payload["status"] == "shape_scan_completed"
    assert payload["candidate_count"] == 53
    assert payload["actual_qualifier_properties"] == [
        "P3831",
        "P459",
        "P518",
        "P580",
        "P582",
    ]
    assert payload["actual_reference_properties"] == ["P854"]
    assert payload["unexpected_qualifier_properties"] == []
    assert payload["unexpected_reference_properties"] == []
    assert payload["qualifier_occurrence_counts"] == {
        "P3831": 49,
        "P459": 53,
        "P518": 33,
        "P580": 53,
        "P582": 53,
    }
    assert payload["reference_occurrence_counts"] == {"P854": 53}
    assert payload["summary"] == {
        "shape_clean": True,
        "next_gate": "broader_cohort_classification",
    }


def test_nat_cohort_a_review_only_export_fixture_pins_review_csv_summary() -> None:
    payload = _load_nat_cohort_a_review_only_export_fixture()

    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["cohort_id"] == "business_family_reconciled"
    assert payload["status"] == "review_only_export_completed"
    assert payload["row_count"] == 53
    assert payload["counts_by_bucket"] == {"split_required": 53}
    assert payload["checked_safe_subset"] == []
    assert payload["export_scope"] == "review_only_openrefine_rows"

    csv_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_review_only_export_20260401.csv"
    )
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert len(rows) == 53
    assert {row["classification"] for row in rows} == {"split_required"}
    assert {row["action"] for row in rows} == {"split"}
    assert {row["requires_review"] for row in rows} == {"true"}


def test_nat_cohort_a_split_plan_fixture_pins_two_review_only_slot_plans() -> None:
    payload = _load_nat_cohort_a_split_plan_fixture()

    jsonschema.validate(payload, _load_split_plan_schema())
    assert payload["summary"]["plan_count"] == 2
    assert payload["summary"]["counts_by_status"] == {"structurally_decomposable": 2}
    assert {plan["entity_qid"] for plan in payload["plans"]} == {"Q10403939", "Q10422059"}
    assert all(plan["suggested_action"] == "review_structured_split" for plan in payload["plans"])


def test_nat_review_packet_fixture_is_schema_valid() -> None:
    payload = _load_nat_review_packet_fixture()

    jsonschema.validate(payload, _load_review_packet_schema())
    assert payload["schema_version"] == WIKIDATA_REVIEW_PACKET_SCHEMA_VERSION
    assert payload["parsed_page"]["headings"] == ["tasks", "done", "to do", "queries"]
    assert payload["parsed_page"]["task_buckets"]["done"] == [
        "is there any documentation or protocol on how to make this kind of migrations? Asked Jan and Wikiproject onthology",
        "get the units wip query",
    ]
    assert payload["parsed_page"]["query_rows"] == [
        "https://w.wiki/KR5d all carbon footprint statements. 57835 results on march 27th"
    ]
    assert payload["split_review_context"]["split_plan_id"] == "split://Q10403939|P5991"
    assert payload["page_signals"]["query_links"] == ["https://w.wiki/KR5d"]
    assert payload["page_signals"]["expected_reference_properties"] == [
        "P1065",
        "P1476",
        "P2960",
        "P813",
        "P854",
    ]


def test_build_wikidata_review_packet_attaches_nat_source_unit_to_split_plan() -> None:
    payload = build_wikidata_review_packet(
        source_unit_payload=_load_nat_wdu_sandbox_source_unit_fixture(),
        split_plan_payload=_load_nat_cohort_a_split_plan_fixture(),
        split_plan_id="split://Q10403939|P5991",
    )

    jsonschema.validate(payload, _load_review_packet_schema())
    assert payload["schema_version"] == WIKIDATA_REVIEW_PACKET_SCHEMA_VERSION
    assert payload["review_entity_qid"] == "Q10403939"
    assert payload["source_surface"]["revision"]["retrieval_method"] == "wiki_revision"
    assert payload["parsed_page"]["headings"] == ["tasks", "done", "to do", "queries"]
    assert len(payload["parsed_page"]["task_buckets"]["todo"]) == 15
    assert len(payload["parsed_page"]["cohort_task_lines"]) == 8
    assert payload["split_review_context"]["proposed_bundle_count"] == 24
    assert payload["page_signals"]["expected_qualifier_properties"] == [
        "P3831",
        "P459",
        "P518",
        "P580",
        "P582",
        "P585",
        "P7452",
    ]
    assert len(payload["follow_receipts"]) == 1
    assert payload["follow_receipts"][0]["url"] == "https://w.wiki/KR5d"
    assert payload["follow_receipts"][0]["extracted_evidence"] == [
        "query_row: https://w.wiki/KR5d all carbon footprint statements. 57835 results on march 27th"
    ]
    assert payload["reviewer_view"]["recommended_next_step"] == "review_structured_split"
    assert "use_todo_bucket_as_review_checklist" in payload["reviewer_view"]["decision_focus"]
    assert "page_open_questions" in payload["reviewer_view"]["uncertainty_flags"]
    assert "no_follow_receipts" not in payload["reviewer_view"]["uncertainty_flags"]


def test_build_wikidata_review_packet_captures_grounding_gap_signal() -> None:
    payload = build_wikidata_review_packet(
        source_unit_payload=_load_nat_wdu_sandbox_source_unit_fixture(),
        split_plan_payload=_load_nat_cohort_a_split_plan_fixture(),
        split_plan_id="split://Q10403939|P5991",
        grounding_depth_summary=build_grounding_depth_summary(
            fixture=_load_nat_grounding_depth_fixture()
        ),
    )

    assert "grounding_gap_class=grounded" in payload["reviewer_view"]["uncertainty_flags"]
    assert payload["reviewer_view"]["recommended_next_step"] == "review_structured_split"


def test_build_wikidata_review_packet_overrides_next_step_for_live_receipt_review() -> None:
    live_follow_results = [
        {
            "result_rows": [
                {
                    "qid": "Q10403939",
                    "plan_id": "hard_grounding_packet:1",
                    "target_ref": "review-packet:5bae90b4fcb444f6",
                    "status": "fetched",
                    "chosen_source_class": "named_revision_locked_source",
                    "evidence": {
                        "source_class": "named_revision_locked_source",
                        "revision_source": {
                            "label": "Akademiska Hus",
                            "revision_url": "https://www.wikidata.org/w/index.php?title=Q10403939&oldid=2419926147",
                        },
                    },
                }
            ]
        }
    ]
    payload = build_wikidata_review_packet(
        source_unit_payload=_load_nat_wdu_sandbox_source_unit_fixture(),
        split_plan_payload=_load_nat_cohort_a_split_plan_fixture(),
        split_plan_id="split://Q10403939|P5991",
        grounding_depth_summary=build_grounding_depth_summary(
            fixture=_load_nat_grounding_depth_fixture(),
            live_follow_results=live_follow_results,
        ),
    )

    assert payload["reviewer_view"]["recommended_next_step"] == "review_live_follow_receipts"
    assert "review_live_follow_receipts" in payload["reviewer_view"]["decision_focus"]
    assert "live_receipts_ready_for_review" in payload["reviewer_view"]["uncertainty_flags"]
    assert "live_follow_receipts=1" in payload["reviewer_view"]["uncertainty_flags"]


def test_build_wikidata_review_packet_honors_explicit_empty_follow_receipts() -> None:
    payload = build_wikidata_review_packet(
        source_unit_payload=_load_nat_wdu_sandbox_source_unit_fixture(),
        split_plan_payload=_load_nat_cohort_a_split_plan_fixture(),
        split_plan_id="split://Q10403939|P5991",
        follow_receipts=[],
    )

    assert payload["follow_receipts"] == []
    assert "no_follow_receipts" in payload["reviewer_view"]["uncertainty_flags"]


def test_build_wikidata_review_packet_semantic_sidecar_includes_anchor_and_split_context_units() -> None:
    payload = build_wikidata_review_packet(
        source_unit_payload=_load_nat_wdu_sandbox_source_unit_fixture(),
        split_plan_payload=_load_nat_cohort_a_split_plan_fixture(),
        split_plan_id="split://Q10403939|P5991",
        include_semantic_decomposition=True,
    )

    semantic = payload["semantic_decomposition"]
    unit_types = {unit["unit_type"] for unit in semantic["candidate_units"]}
    assert "follow_receipt_surface" in unit_types
    assert "anchor_surface" in unit_types
    assert "split_context_surface" in unit_types
    assert "missing_evidence_surface" in unit_types
    assert "split_axis_surface" in unit_types
    assert "anchor_refs_not_promoted_to_grounded_claims" in semantic["missing_evidence"]
    assert "split_context_not_lifted_into_semantic_decision_graph" in semantic["missing_evidence"]


def test_nat_review_packet_attachment_coverage_fixture_expands_to_fifteen_rows() -> None:
    payload = _load_nat_review_packet_attachment_coverage_fixture()

    assert payload["packetized_split_rows"] == 15
    assert payload["packetized_split_row_ids"] == [
        "Q10403939|P5991",
        "Q10422059|P5991",
        "Q188326|P5991",
        "Q3356220|P5991",
        "Q52825|P5991",
        "Q862811|P5991",
        "Q10425193|P5991",
        "Q10601765|P5991",
        "Q30938280|P5991",
        "Q47508289|P5991",
        "Q731938|P5991",
        "Q10416948|P5991",
        "Q56404383|P5991",
        "Q1785637|P5991",
        "Q738421|P5991",
    ]
    assert len(payload["packet_slots"]) == 15
    assert payload["ready_for_reviewers"][-1] == "Coverage index showing 15 / 53 packetized rows"


def test_nat_review_packet_sidecar_fixtures_include_follow_receipts_and_semantic_layers() -> None:
    for qid, expected_step in [
        ("Q10416948", "review_structured_split"),
        ("Q56404383", "review_only"),
    ]:
        payload = _load_nat_review_packet_sidecar_fixture(qid)
        assert payload["follow_receipts"]
        assert payload["semantic_decomposition"]["separate_from_parsed_page"] is True
        assert payload["semantic_decomposition"]["candidate_units"]
        unit_types = {
            unit["unit_type"] for unit in payload["semantic_decomposition"]["candidate_units"]
        }
        assert "follow_receipt_surface" in unit_types
        assert "anchor_surface" in unit_types
        assert "split_context_surface" in unit_types
        assert "missing_evidence_surface" in unit_types
        merged_split_axes = payload["split_review_context"]["merged_split_axes"]
        if merged_split_axes:
            assert "split_axis_surface" in unit_types
        assert payload["reviewer_view"]["recommended_next_step"] == expected_step


def test_nat_cohort_a_classification_checkpoint_fixture_pins_split_required_seed_state() -> None:
    payload = _load_nat_cohort_a_classification_checkpoint_fixture()

    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["cohort_id"] == "business_family_reconciled"
    assert payload["status"] == "classification_checkpoint_completed"
    assert payload["classification_scope"] == "materialized_bounded_cohort"
    assert payload["entity_qids"] == ["Q10403939", "Q10422059"]
    assert payload["candidate_count"] == 53
    assert payload["counts_by_classification"] == {"split_required": 53}
    assert payload["counts_by_action"] == {"split": 53}
    assert payload["requires_review"] == {"true": 53, "false": 0}
    assert payload["checked_safe_subset"] == []
    assert payload["summary"] == {
        "classification_ready_for_export_gate": True,
        "migration_ready": False,
        "next_gate": "checked_safe_or_review_only_export",
    }


def test_nat_cohort_a_live_discovery_fixture_pins_ranked_business_family_shortlist() -> None:
    payload = _load_nat_cohort_a_live_discovery_fixture()

    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["cohort_id"] == "business_family_reconciled"
    assert payload["status"] == "live_discovery_completed"
    assert payload["source_property"] == "P5991"
    assert payload["target_property"] == "P14143"
    assert payload["cohort_rule"]["instance_of_any"] == [
        "Q4830453",
        "Q6881511",
        "Q891723",
    ]
    assert payload["summary"]["discovered_row_count"] == 12
    assert payload["summary"]["selected_live_tranche_count"] == 4
    assert payload["summary"]["selected_live_tranche_qids"] == [
        "Q30938280",
        "Q731938",
        "Q1785637",
        "Q738421",
    ]
    assert payload["discovered_rows"][0] == {
        "qid": "Q30938280",
        "label": "Essity",
        "statement_count": 14,
        "qualifier_count": 9,
        "selected_for_live_tranche": True,
    }
    assert sum(1 for row in payload["discovered_rows"] if row["selected_for_live_tranche"]) == 4


def test_nat_cohort_a_live_tranche_fixture_pins_fail_closed_live_expansion_result() -> None:
    payload = _load_nat_cohort_a_live_tranche_fixture()

    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["cohort_id"] == "business_family_reconciled"
    assert payload["status"] == "live_tranche_materialized"
    assert payload["source_discovery_fixture"] == "wikidata_nat_cohort_a_live_discovery_20260401.json"
    assert payload["qids"] == ["Q30938280", "Q731938", "Q1785637", "Q738421"]
    assert payload["candidate_count"] == 188
    assert payload["checked_safe_subset_count"] == 0
    assert payload["requires_review_count"] == 188
    assert payload["counts_by_bucket"] == {"split_required": 188}
    assert payload["openrefine_row_count"] == 188
    assert payload["split_plan_summary"] == {
        "plan_count": 4,
        "counts_by_status": {"structurally_decomposable": 4},
    }
    assert payload["summary"] == {
        "nat_progress_count": 7,
        "nat_total_count": 8,
        "nat_progress_ratio": 0.875,
        "promoted_subset_found": False,
        "next_recommendation": "targeted_checked_safe_hunt_or_branch_to_cohort_c",
    }


def test_nat_cohort_a_checked_safe_hunt_fixture_pins_bounded_checked_safe_subset() -> None:
    payload = _load_nat_cohort_a_checked_safe_hunt_fixture()

    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["cohort_id"] == "business_family_reconciled"
    assert payload["status"] == "checked_safe_hunt_completed"
    assert payload["qids"] == ["Q1068745", "Q1489170"]
    assert payload["candidate_count"] == 2
    assert payload["checked_safe_subset_count"] == 2
    assert payload["requires_review_count"] == 0
    assert payload["counts_by_bucket"] == {"safe_with_reference_transfer": 2}
    assert payload["checked_safe_subset"] == ["Q1068745|P5991|1", "Q1489170|P5991|1"]
    assert payload["counts_by_action"] == {"migrate_with_refs": 2}
    assert payload["summary"] == {
        "nat_progress_count": 7,
        "nat_total_count": 8,
        "nat_progress_ratio": 0.875,
        "promoted_subset_found": True,
        "next_recommendation": "run_post_edit_verification_on_bounded_promoted_subset",
    }


def test_build_observation_claim_payload_from_wiki_revision_source_unit_fixture() -> None:
    payload = _load_wiki_revision_source_unit_fixture()

    observation_claim_payload = build_observation_claim_payload_from_source_units(payload)

    assert observation_claim_payload["payload_version"] == "sl.observation_claim.contract.v1"
    assert [row["observed_at"] for row in observation_claim_payload["observations"]] == ["2023"]
    assert [row["object_id"] for row in observation_claim_payload["claims"]] == ["86"]
    assert observation_claim_payload["evidence_links"][0]["trace_refs"] == [
        "revision:987654321",
        "source:wikipedia:example_corp:rev:20260401",
        "scope_tag:scope_1",
    ]


def test_attach_wikidata_phi_text_bridge_from_revision_locked_climate_text_builds_observation_claim_and_bridge() -> None:
    migration_pack = build_wikidata_migration_pack(
        {
            "windows": [
                {
                    "id": "t1",
                    "statement_bundles": [
                        {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "100",
                            "rank": "normal",
                            "references": [{"P248": "Qsrc"}],
                        }
                    ],
                }
            ]
        },
        source_property="P5991",
        target_property="P14143",
    )
    climate_text_payload = {
        "schema_version": WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION,
        "sources": [
            {
                "source_id": "climate-src:1",
                "entity_qid": "Q1",
                "source_unit_id": "unit:q1:r1",
                "revision_id": "123",
                "revision_timestamp": "2026-03-28T00:00:00Z",
                "text": "Carbon footprint 2018: 100 tCO2e\nCarbon footprint 2019: 100 tCO2e\n",
            }
        ],
    }

    enriched, observation_claim_payload = attach_wikidata_phi_text_bridge_from_revision_locked_climate_text(
        migration_pack,
        climate_text_payload=climate_text_payload,
    )

    candidate = enriched["candidates"][0]
    assert candidate["pressure"] == "split_pressure"
    assert len(candidate["text_evidence_refs"]) == 2
    assert len(enriched["bridge_cases"]) == 1
    assert len(observation_claim_payload["observations"]) == 2
    jsonschema.validate(enriched, _load_migration_pack_schema())


def test_attach_wikidata_phi_text_bridge_from_source_units_builds_observation_claim_and_bridge() -> None:
    migration_pack = build_wikidata_migration_pack(
        {
            "windows": [
                {
                    "id": "t1",
                    "statement_bundles": [
                        {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "100",
                            "rank": "normal",
                            "references": [{"P248": "Qsrc"}],
                        }
                    ],
                }
            ]
        },
        source_property="P5991",
        target_property="P14143",
    )
    source_unit_payload = {
        "schema_version": SOURCE_UNIT_SCHEMA_VERSION,
        "source_units": [
            {
                "source_id": "html-src:1",
                "entity_qid": "Q1",
                "source_unit_id": "unit:q1:html1",
                "revision": {
                    "revision_id": "snapshot:1",
                    "revision_timestamp": "2026-03-28T00:00:00Z",
                    "retrieval_method": "html_snapshot",
                },
                "origin": {
                    "source_type": "html",
                    "source_url": "https://example.test/esg",
                    "title": "ESG snapshot",
                },
                "content": {
                    "format": "text",
                    "text": "In 2018 emissions were 100 tCO2e.\nIn 2019 emissions were 100 tCO2e.\n",
                },
                "anchors": [],
                "metadata": {},
            }
        ],
    }

    enriched, observation_claim_payload = attach_wikidata_phi_text_bridge_from_source_units(
        migration_pack,
        source_unit_payload=source_unit_payload,
    )

    candidate = enriched["candidates"][0]
    assert candidate["pressure"] == "split_pressure"
    assert len(candidate["text_evidence_refs"]) == 2
    assert len(enriched["bridge_cases"]) == 1
    assert len(observation_claim_payload["observations"]) == 2
    jsonschema.validate(enriched, _load_migration_pack_schema())


def test_attach_wikidata_phi_text_bridge_from_source_units_uses_scope_tags_for_scope_pressure() -> None:
    migration_pack = build_wikidata_migration_pack(
        {
            "windows": [
                {
                    "id": "t1",
                    "statement_bundles": [
                        {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "852",
                            "rank": "normal",
                            "qualifiers": {"P518": "scope_2", "P585": "2023"},
                            "references": [{"P248": "Qsrc"}],
                        }
                    ],
                }
            ]
        },
        source_property="P5991",
        target_property="P14143",
    )
    source_unit_payload = {
        "schema_version": SOURCE_UNIT_SCHEMA_VERSION,
        "source_units": [
            {
                "source_id": "wiki-src:1",
                "entity_qid": "Q1",
                "source_unit_id": "unit:q1:wiki1",
                "revision": {
                    "revision_id": "rev:1",
                    "revision_timestamp": "2026-03-28T00:00:00Z",
                    "retrieval_method": "wiki_revision",
                },
                "origin": {
                    "source_type": "wiki",
                    "source_url": "https://en.wikipedia.org/wiki/Example",
                    "title": "Example revision",
                },
                "content": {
                    "format": "text",
                    "text": "In 2023 scope 1 emissions were 86 tCO2e.\n",
                },
                "anchors": [],
                "metadata": {"scope_tags": ["scope_1"]},
            }
        ],
    }

    enriched, observation_claim_payload = attach_wikidata_phi_text_bridge_from_source_units(
        migration_pack,
        source_unit_payload=source_unit_payload,
    )

    candidate = enriched["candidates"][0]
    assert candidate["pressure"] == "split_pressure"
    assert len(enriched["bridge_cases"]) == 1
    assert enriched["bridge_cases"][0]["comparison"]["conflicts"] == []
    assert {
        "kind": "scope_dimension_mismatch",
        "detail": "text scope tag(s) ['scope_1'] do not match bundle scope value(s) ['scope_2']",
    } in enriched["bridge_cases"][0]["comparison"]["missing_dimensions"]
    assert observation_claim_payload["evidence_links"][0]["trace_refs"][-1] == "scope_tag:scope_1"


def test_attach_wikidata_phi_text_bridge_from_wiki_revision_source_unit_fixture() -> None:
    migration_pack = build_wikidata_migration_pack(
        {
            "windows": [
                {
                    "id": "t1",
                    "statement_bundles": [
                        {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "852",
                            "rank": "normal",
                            "qualifiers": {"P518": "scope_2", "P585": "2023"},
                            "references": [{"P248": "Qsrc"}],
                        }
                    ],
                }
            ]
        },
        source_property="P5991",
        target_property="P14143",
    )
    source_unit_payload = _load_wiki_revision_source_unit_fixture()

    enriched, observation_claim_payload = attach_wikidata_phi_text_bridge_from_source_units(
        migration_pack,
        source_unit_payload=source_unit_payload,
    )

    candidate = enriched["candidates"][0]
    assert candidate["pressure"] == "split_pressure"
    assert candidate["text_evidence_refs"]
    assert len(enriched["bridge_cases"]) == 1
    assert enriched["bridge_cases"][0]["comparison"]["conflicts"] == []
    assert {
        "kind": "scope_dimension_mismatch",
        "detail": "text scope tag(s) ['scope_1'] do not match bundle scope value(s) ['scope_2']",
    } in enriched["bridge_cases"][0]["comparison"]["missing_dimensions"]
    assert observation_claim_payload["evidence_links"][0]["source_unit_id"] == "unit:wikipedia:example_corp:rev:20260401:lead"


def test_export_migration_pack_openrefine_csv_writes_flat_review_rows(tmp_path: Path) -> None:
    migration_pack = {
        "target_property": "P14143",
        "candidates": [
            {
                "candidate_id": "Q1|P5991|1",
                "entity_qid": "Q1",
                "slot_id": "Q1|P5991",
                "statement_index": 1,
                "classification": "safe_with_reference_transfer",
                "action": "migrate_with_refs",
                "confidence": 0.9,
                "requires_review": False,
                "reasons": [],
                "split_axes": [],
                "claim_bundle_before": {
                    "property": "P5991",
                    "value": "100",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2024"]},
                    "references": [{"P248": ["Qsrc"]}],
                },
                "qualifier_diff": {"status": "unchanged", "severity": None},
                "reference_diff": {"status": "unchanged", "severity": None},
            },
            {
                "candidate_id": "Q2|P5991|1",
                "entity_qid": "Q2",
                "slot_id": "Q2|P5991",
                "statement_index": 1,
                "classification": "reference_drift",
                "action": "review",
                "confidence": 0.45,
                "requires_review": True,
                "reasons": ["reference_drift:high"],
                "split_axes": [],
                "claim_bundle_before": {
                    "property": "P5991",
                    "value": "200",
                    "rank": "normal",
                    "qualifiers": {},
                    "references": [{"P248": ["Qsrc"]}],
                },
                "qualifier_diff": {"status": "unchanged", "severity": None},
                "reference_diff": {"status": "reference_drift", "severity": "high"},
            },
        ],
    }
    out_path = tmp_path / "migration_pack_openrefine.csv"

    report = export_migration_pack_openrefine_csv(migration_pack, output_path=str(out_path))

    rows = list(csv.DictReader(out_path.open(encoding="utf-8")))
    assert report["row_count"] == 2
    assert report["counts_by_bucket"] == {
        "safe_with_reference_transfer": 1,
        "reference_drift": 1,
    }
    assert rows[0]["entity_qid"] == "Q1"
    assert rows[0]["action"] == "migrate_with_refs"
    assert rows[0]["suggested_action"] == "migrate_with_refs"
    assert rows[0]["split_axis_count"] == "0"
    assert rows[0]["qualifier_count"] == "1"
    assert rows[1]["entity_qid"] == "Q2"
    assert rows[1]["suggested_action"] == "review"
    assert rows[1]["split_axis_properties"] == ""
    assert rows[1]["reference_drift"] == "true"
    assert rows[1]["reason_codes"] == "reference_drift:high"


def test_export_migration_pack_checked_safe_csv_only_writes_safe_rows(tmp_path: Path) -> None:
    migration_pack = {
        "target_property": "P14143",
        "candidates": [
            {
                "candidate_id": "Q1|P5991|1",
                "entity_qid": "Q1",
                "slot_id": "Q1|P5991",
                "statement_index": 1,
                "classification": "safe_with_reference_transfer",
                "action": "migrate_with_refs",
                "claim_bundle_before": {
                    "property": "P5991",
                    "value": "100",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2024"]},
                    "references": [{"P248": ["Qsrc"]}],
                },
                "claim_bundle_after": {
                    "property": "P14143",
                    "value": "100",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2024"]},
                    "references": [{"P248": ["Qsrc"]}],
                },
            },
            {
                "candidate_id": "Q2|P5991|1",
                "entity_qid": "Q2",
                "slot_id": "Q2|P5991",
                "statement_index": 1,
                "classification": "split_required",
                "action": "split",
                "claim_bundle_before": {
                    "property": "P5991",
                    "value": "200",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2024"]},
                    "references": [{"P248": ["Qsrc"]}],
                },
                "claim_bundle_after": {
                    "property": "P14143",
                    "value": "200",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2024"]},
                    "references": [{"P248": ["Qsrc"]}],
                },
            },
        ],
    }
    out_path = tmp_path / "migration_pack_checked_safe.csv"

    report = export_migration_pack_checked_safe_csv(migration_pack, output_path=str(out_path))

    rows = list(csv.DictReader(out_path.open(encoding="utf-8")))
    assert report["row_count"] == 1
    assert report["export_scope"] == "checked_safe_subset_only"
    assert report["counts_by_bucket"] == {"safe_with_reference_transfer": 1}
    assert rows[0]["candidate_id"] == "Q1|P5991|1"
    assert rows[0]["action"] == "migrate_with_refs"
    assert rows[0]["to_property"] == "P14143"
    assert '"P585": ["2024"]' in rows[0]["qualifiers_json"]


def test_verify_migration_pack_against_after_state_reports_verified_and_missing() -> None:
    migration_pack = {
        "source_property": "P5991",
        "target_property": "P14143",
        "candidates": [
            {
                "candidate_id": "Q1|P5991|1",
                "entity_qid": "Q1",
                "classification": "safe_with_reference_transfer",
                "action": "migrate_with_refs",
                "claim_bundle_before": {
                    "subject": "Q1",
                    "property": "P5991",
                    "value": "100",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2024"]},
                    "references": [{"P248": ["Qsrc"]}],
                    "window_id": "t1",
                },
                "claim_bundle_after": {
                    "subject": "Q1",
                    "property": "P14143",
                    "value": "100",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2024"]},
                    "references": [{"P248": ["Qsrc"]}],
                    "window_id": "t1",
                },
            },
            {
                "candidate_id": "Q2|P5991|1",
                "entity_qid": "Q2",
                "classification": "safe_equivalent",
                "action": "migrate",
                "claim_bundle_before": {
                    "subject": "Q2",
                    "property": "P5991",
                    "value": "200",
                    "rank": "normal",
                    "qualifiers": {},
                    "references": [],
                    "window_id": "t1",
                },
                "claim_bundle_after": {
                    "subject": "Q2",
                    "property": "P14143",
                    "value": "200",
                    "rank": "normal",
                    "qualifiers": {},
                    "references": [],
                    "window_id": "t1",
                },
            },
            {
                "candidate_id": "Q3|P5991|1",
                "entity_qid": "Q3",
                "classification": "split_required",
                "action": "split",
                "claim_bundle_before": {
                    "subject": "Q3",
                    "property": "P5991",
                    "value": "300",
                    "rank": "normal",
                    "qualifiers": {},
                    "references": [],
                    "window_id": "t1",
                },
                "claim_bundle_after": {
                    "subject": "Q3",
                    "property": "P14143",
                    "value": "300",
                    "rank": "normal",
                    "qualifiers": {},
                    "references": [],
                    "window_id": "t1",
                },
            },
        ],
    }
    after_payload = {
        "windows": [
            {
                "id": "after",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P14143",
                        "value": "100",
                        "rank": "normal",
                        "qualifiers": {"P585": "2024"},
                        "references": [{"P248": "Qsrc"}],
                    },
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "100",
                        "rank": "normal",
                        "qualifiers": {"P585": "2024"},
                        "references": [{"P248": "Qsrc"}],
                    },
                ],
            }
        ]
    }

    report = verify_migration_pack_against_after_state(migration_pack, after_payload)

    assert report["verification_scope"] == "checked_safe_subset_only"
    assert report["summary"]["verified_candidate_count"] == 2
    assert report["summary"]["counts_by_status"] == {"verified": 1, "target_missing": 1}
    by_id = {row["candidate_id"]: row for row in report["rows"]}
    assert by_id["Q1|P5991|1"]["status"] == "verified"
    assert by_id["Q1|P5991|1"]["source_still_present"] is True
    assert by_id["Q2|P5991|1"]["status"] == "target_missing"
    assert "Q3|P5991|1" not in by_id


def test_verify_nat_cohort_a_gate_b_candidate_verification_run_reports_two_verified_rows() -> None:
    payload = _load_nat_cohort_a_gate_b_candidate_verification_run_fixture()

    report = verify_migration_pack_against_after_state(
        payload["migration_pack"],
        payload["after_payload"],
    )

    assert report["verification_scope"] == "checked_safe_subset_only"
    assert report["summary"]["verified_candidate_count"] == payload["expected_summary"]["verified_candidate_count"]
    assert report["summary"]["counts_by_status"] == payload["expected_summary"]["counts_by_status"]
    by_id = {row["candidate_id"]: row for row in report["rows"]}
    assert by_id["Q1068745|P5991|1"]["status"] == "verified"
    assert by_id["Q1068745|P5991|1"]["source_still_present"] is True
    assert by_id["Q1489170|P5991|1"]["status"] == "verified"
    assert by_id["Q1489170|P5991|1"]["source_still_present"] is True


def test_verify_nat_cohort_a_gate_b_candidate_verification_runs_ready_reports_two_clean_runs() -> None:
    payload = _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()

    assert len(payload["runs"]) == payload["expected_summary"]["run_count"]

    for run in payload["runs"]:
        report = verify_migration_pack_against_after_state(
            run["migration_pack"],
            run["after_payload"],
        )
        assert report["verification_scope"] == "checked_safe_subset_only"
        assert report["summary"]["verified_candidate_count"] == payload["expected_summary"]["verified_candidate_count_per_run"]
        assert report["summary"]["counts_by_status"] == payload["expected_summary"]["counts_by_status"]
        by_id = {row["candidate_id"]: row for row in report["rows"]}
        assert by_id["Q1068745|P5991|1"]["status"] == "verified"
        assert by_id["Q1068745|P5991|1"]["source_still_present"] is True
        assert by_id["Q1489170|P5991|1"]["status"] == "verified"
        assert by_id["Q1489170|P5991|1"]["source_still_present"] is True


def test_build_wikidata_split_plan_emits_structural_plan_for_split_rows() -> None:
    migration_pack = {
        "source_property": "P5991",
        "target_property": "P14143",
        "candidates": [
            {
                "candidate_id": "Q1|P5991|1",
                "entity_qid": "Q1",
                "slot_id": "Q1|P5991",
                "statement_index": 1,
                "classification": "split_required",
                "action": "split",
                "split_axes": [
                    {"property": "__value__", "cardinality": 2, "source": "slot", "reason": "multi_value_slot"},
                    {"property": "P585", "cardinality": 2, "source": "slot", "reason": "multi_valued_dimension"},
                ],
                "claim_bundle_before": {
                    "subject": "Q1",
                    "property": "P5991",
                    "value": "100",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2023"]},
                    "references": [{"P248": ["Qsrc"]}],
                    "window_id": "t1",
                },
                "claim_bundle_after": {
                    "subject": "Q1",
                    "property": "P14143",
                    "value": "100",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2023"]},
                    "references": [{"P248": ["Qsrc"]}],
                    "window_id": "t1",
                },
            },
            {
                "candidate_id": "Q1|P5991|2",
                "entity_qid": "Q1",
                "slot_id": "Q1|P5991",
                "statement_index": 2,
                "classification": "split_required",
                "action": "split",
                "split_axes": [
                    {"property": "__value__", "cardinality": 2, "source": "slot", "reason": "multi_value_slot"},
                    {"property": "P585", "cardinality": 2, "source": "slot", "reason": "multi_valued_dimension"},
                ],
                "claim_bundle_before": {
                    "subject": "Q1",
                    "property": "P5991",
                    "value": "120",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2024"]},
                    "references": [{"P248": ["Qsrc"]}],
                    "window_id": "t1",
                },
                "claim_bundle_after": {
                    "subject": "Q1",
                    "property": "P14143",
                    "value": "120",
                    "rank": "normal",
                    "qualifiers": {"P585": ["2024"]},
                    "references": [{"P248": ["Qsrc"]}],
                    "window_id": "t1",
                },
            },
        ],
    }

    report = build_wikidata_split_plan(migration_pack)

    assert report["schema_version"] == SPLIT_PLAN_SCHEMA_VERSION
    assert report["summary"]["counts_by_status"] == {"structurally_decomposable": 1}
    plan = report["plans"][0]
    assert plan["status"] == "structurally_decomposable"
    assert plan["suggested_action"] == "review_structured_split"
    assert plan["proposed_bundle_count"] == 2
    assert plan["reference_propagation"] == "exact"
    assert plan["qualifier_propagation"] == "exact"
    jsonschema.validate(report, _load_split_plan_schema())


def test_project_wikidata_payload_reports_pilot_pack_parthood_typing() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "parthood_pilot_pack_20260308"
    )
    payload = json.loads((fixture_root / "slice.json").read_text(encoding="utf-8"))
    expected = json.loads((fixture_root / "projection.json").read_text(encoding="utf-8"))

    report = project_wikidata_payload(payload, property_filter=("P31", "P361", "P527"))

    assert report["windows"][0]["diagnostics"]["parthood_typing"] == expected["parthood_typing"]
    assert any(
        row["inverse_relation"] == "cross_property_expected"
        for row in report["windows"][0]["diagnostics"]["parthood_typing"]["classifications"]
    )


def test_project_wikidata_payload_reports_imported_pack_parthood_typing() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "parthood_imported_pack_20260308"
    )
    payload = json.loads((fixture_root / "slice.json").read_text(encoding="utf-8"))
    expected = json.loads((fixture_root / "projection.json").read_text(encoding="utf-8"))

    report = project_wikidata_payload(payload, property_filter=("P31", "P361", "P527"))

    assert (
        report["windows"][0]["diagnostics"]["parthood_typing"]
        == expected["parthood_typing"]
    )
    assert report["windows"][0]["diagnostics"]["parthood_typing"]["counts"][
        "cross_property_inverse"
    ] == 2


def test_repo_pinned_live_qualifier_drift_case_matches_materialized_projection() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "q100104196_p166_2277985537_2277985693"
    )
    payload = json.loads((fixture_root / "slice.json").read_text(encoding="utf-8"))
    expected = json.loads((fixture_root / "projection.json").read_text(encoding="utf-8"))

    report = project_wikidata_payload(payload, property_filter=("P166",))

    assert report["qualifier_drift"] == expected["qualifier_drift"]
    assert report["qualifier_drift"][0]["slot_id"] == "Q100104196|P166"
    assert report["qualifier_drift"][0]["severity"] == "medium"
    assert report["qualifier_drift"][0]["qualifier_property_set_t1"] == ["P585"]
    assert report["qualifier_drift"][0]["qualifier_property_set_t2"] == ["P585"]


def test_repo_pinned_second_live_qualifier_drift_case_matches_materialized_projection() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "q100152461_p54_2456615151_2456615274"
    )
    payload = json.loads((fixture_root / "slice.json").read_text(encoding="utf-8"))
    expected = json.loads((fixture_root / "projection.json").read_text(encoding="utf-8"))

    report = project_wikidata_payload(payload, property_filter=("P54",))

    assert report["qualifier_drift"] == expected["qualifier_drift"]
    assert report["qualifier_drift"][0]["slot_id"] == "Q100152461|P54"
    assert report["qualifier_drift"][0]["severity"] == "medium"
    assert report["qualifier_drift"][0]["qualifier_property_set_t1"] == ["P580", "P582"]
    assert report["qualifier_drift"][0]["qualifier_property_set_t2"] == ["P580", "P582"]
