import json
from pathlib import Path

from src.ontology.wikidata_disjointness import (
    DISJOINTNESS_REPORT_SCHEMA_VERSION,
    project_wikidata_disjointness_payload,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wikidata"
    / "disjointness_p2738_pilot_pack_v1"
    / "slice.json"
)
REAL_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wikidata"
    / "disjointness_p2738_nucleon_real_pack_v1"
    / "slice.json"
)
REAL_CONTRADICTION_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wikidata"
    / "disjointness_p2738_fixed_construction_real_pack_v1"
    / "slice.json"
)
REAL_INSTANCE_CONTRADICTION_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wikidata"
    / "disjointness_p2738_working_fluid_real_pack_v1"
    / "slice.json"
)


def test_project_wikidata_disjointness_payload_reports_pairs_violations_and_culprits() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    report = project_wikidata_disjointness_payload(payload)

    assert report["schema_version"] == DISJOINTNESS_REPORT_SCHEMA_VERSION
    assert report["source_window_id"] == "t1"
    assert report["bounded_slice"]["properties"] == ["P2738", "P11260", "P279", "P31"]
    assert report["review_summary"] == {
        "disjoint_pair_count": 1,
        "subclass_violation_count": 2,
        "instance_violation_count": 2,
        "culprit_class_count": 1,
        "culprit_item_count": 1,
    }
    assert report["disjoint_pairs"] == [
        {
            "holder_label": "transport family",
            "holder_qid": "QTransportFamily",
            "left_label": "land transport mode",
            "left_qid": "QLandMode",
            "pair_id": "QTransportFamily:QLandMode:QWaterMode",
            "property_pid": "P2738",
            "qualifier_pid": "P11260",
            "right_label": "water transport mode",
            "right_qid": "QWaterMode",
            "statement_value": "QTransportMode",
        }
    ]
    assert [row["qid"] for row in report["subclass_violations"]] == [
        "QAmphibiousVehicle",
        "QHovercraft",
    ]
    assert [row["qid"] for row in report["culprit_classes"]] == ["QAmphibiousVehicle"]
    culprit = report["culprit_classes"][0]
    assert culprit["downstream_subclass_violation_count"] == 1
    assert culprit["downstream_instance_violation_count"] == 1
    hovercraft = report["subclass_violations"][1]
    assert hovercraft["explained_by_culprit_class_qid"] == "QAmphibiousVehicle"
    assert [row["qid"] for row in report["instance_violations"]] == [
        "QDuckBoat",
        "QJetSkiCar",
    ]
    assert report["instance_violations"][0]["explained_by_culprit_class_qid"] == "QAmphibiousVehicle"
    assert report["instance_violations"][1]["explained_by_culprit_class_qid"] is None
    assert [row["qid"] for row in report["culprit_items"]] == ["QJetSkiCar"]


def test_project_wikidata_disjointness_payload_requires_single_window() -> None:
    payload = {
        "windows": [
            {"id": "t1", "statement_bundles": []},
            {"id": "t2", "statement_bundles": []},
        ]
    }

    try:
        project_wikidata_disjointness_payload(payload)
    except ValueError as exc:
        assert "exactly one window" in str(exc)
    else:
        raise AssertionError("expected ValueError for multi-window disjointness slice")


def test_real_nucleon_disjointness_pack_is_stable_zero_violation_baseline() -> None:
    payload = json.loads(REAL_FIXTURE_PATH.read_text(encoding="utf-8"))

    report = project_wikidata_disjointness_payload(payload)

    assert report["source_window_id"] == "real_2026_03_25"
    assert report["review_summary"] == {
        "disjoint_pair_count": 1,
        "subclass_violation_count": 0,
        "instance_violation_count": 0,
        "culprit_class_count": 0,
        "culprit_item_count": 0,
    }
    assert report["disjoint_pairs"] == [
        {
            "holder_label": "nucleon",
            "holder_qid": "Q102165",
            "left_label": "proton",
            "left_qid": "Q2294",
            "pair_id": "Q102165:Q2294:Q2348",
            "property_pid": "P2738",
            "qualifier_pid": "P11260",
            "right_label": "neutron",
            "right_qid": "Q2348",
            "statement_value": "Q23766486",
        }
    ]
    assert report["subclass_violations"] == []
    assert report["instance_violations"] == []


def test_real_fixed_construction_pack_reports_real_subclass_contradiction() -> None:
    payload = json.loads(REAL_CONTRADICTION_FIXTURE_PATH.read_text(encoding="utf-8"))

    report = project_wikidata_disjointness_payload(payload)

    assert report["source_window_id"] == "real_fixed_construction_2026_03_25"
    assert report["review_summary"] == {
        "disjoint_pair_count": 1,
        "subclass_violation_count": 4,
        "instance_violation_count": 0,
        "culprit_class_count": 1,
        "culprit_item_count": 0,
    }
    assert [row["qid"] for row in report["subclass_violations"]] == [
        "Q2131593",
        "Q27096213",
        "Q618123",
        "Q811430",
    ]
    culprit = report["culprit_classes"][0]
    assert culprit["qid"] == "Q27096213"
    assert culprit["downstream_subclass_violation_count"] == 3
    assert culprit["downstream_instance_violation_count"] == 0
    downstream = next(row for row in report["subclass_violations"] if row["qid"] == "Q811430")
    assert downstream["explained_by_culprit_class_qid"] == "Q27096213"


def test_real_working_fluid_pack_reports_real_instance_contradiction() -> None:
    payload = json.loads(REAL_INSTANCE_CONTRADICTION_FIXTURE_PATH.read_text(encoding="utf-8"))

    report = project_wikidata_disjointness_payload(payload)

    assert report["source_window_id"] == "real_working_fluid_2026_03_25"
    assert report["review_summary"] == {
        "disjoint_pair_count": 1,
        "subclass_violation_count": 0,
        "instance_violation_count": 1,
        "culprit_class_count": 0,
        "culprit_item_count": 1,
    }
    assert report["subclass_violations"] == []
    assert [row["qid"] for row in report["instance_violations"]] == ["Q217236"]
    assert report["instance_violations"][0]["explained_by_culprit_class_qid"] is None
    assert [row["qid"] for row in report["culprit_items"]] == ["Q217236"]
