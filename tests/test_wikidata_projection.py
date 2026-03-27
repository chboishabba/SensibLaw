import json
from pathlib import Path

from src.ontology.wikidata import (
    MIGRATION_PACK_SCHEMA_VERSION,
    SCHEMA_VERSION,
    build_wikidata_migration_pack,
    project_wikidata_payload,
)


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
