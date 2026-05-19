import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cli import __main__ as cli_main
from src.ontology.wikidata_change_review import (
    CHANGE_REVIEW_PACKET_SCHEMA_VERSION,
    CHANGE_REVIEW_REPORT_SCHEMA_VERSION,
    build_change_review_report,
    build_change_review_report_from_path,
    load_change_review_packet,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wikidata"
    / "q27968055_change_review_packet.json"
)
MEREOLOGY_TEMPORAL_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wikidata"
    / "change_review_mereology_temporal_packet.json"
)
SCHEMA_DIR = ROOT / "schemas"


def _schema(name: str) -> dict:
    return yaml.safe_load((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_change_review_packet_loads() -> None:
    packet = load_change_review_packet(FIXTURE)

    assert packet["schema_version"] == CHANGE_REVIEW_PACKET_SCHEMA_VERSION
    assert packet["focus_item"] == "Q27968055"
    assert packet["authority_policy"] == "review_only"
    assert [candidate["id"] for candidate in packet["candidate_repairs"]] == [
        "keep_current",
        "remove_p279_q3331189",
        "remove_p279_q1656682",
        "test_weaker_p279_q24017414",
        "hold_for_class_order_review",
        "hold_upstream_abstract_obligation",
    ]


def test_change_review_report_compares_each_candidate_review_only() -> None:
    report = build_change_review_report_from_path(FIXTURE)

    assert report["schema_version"] == CHANGE_REVIEW_REPORT_SCHEMA_VERSION
    assert report["focus_item"] == "Q27968055"
    assert report["authority_policy"] == "review_only"
    assert report["edit_authority"] is False
    assert report["assumptions"]["no_live_wikidata_write"] is True
    assert report["check_coverage"]["status"] == "complete"
    assert report["check_coverage"]["run"] == [
        "subclass_consistency",
        "class_order_pressure",
        "metaclass_pressure",
        "disjointness",
    ]
    assert report["check_coverage"]["deferred"] == [
        {
            "family": "downstream_use",
            "reason": "upstream-reference index intake is not implemented in v0",
        },
        {
            "family": "minimality",
            "reason": "candidate minimality ranking is not implemented in v0",
        },
    ]
    assert len(report["candidate_reports"]) == 6

    by_id = {candidate["candidate_id"]: candidate for candidate in report["candidate_reports"]}
    assert by_id["hold_for_class_order_review"]["disposition"] == "held"
    assert by_id["hold_for_class_order_review"]["edit_authority"] is False
    assert by_id["remove_p279_q3331189"]["disposition"] == "checked_safe_reviewable"
    assert by_id["remove_p279_q3331189"]["candidate_blocker_count"] <= report["baseline"]["blocker_count"]
    assert by_id["remove_p279_q3331189"]["mutation_summary"]["applied_in_memory_only"] is True


def test_change_review_reports_upstream_abstract_obligation_candidate_review_only() -> None:
    packet = load_change_review_packet(FIXTURE)
    candidate_packet = {
        candidate["id"]: candidate for candidate in packet["candidate_repairs"]
    }["hold_upstream_abstract_obligation"]
    report = build_change_review_report(packet)
    by_id = {candidate["candidate_id"]: candidate for candidate in report["candidate_reports"]}
    candidate = by_id["hold_upstream_abstract_obligation"]

    assert "subject" not in candidate_packet
    assert "property" not in candidate_packet
    assert "value" not in candidate_packet
    assert "statement" not in candidate_packet
    assert "match" not in candidate_packet
    assert "replacement" not in candidate_packet
    assert candidate["disposition"] == "held"
    assert candidate["authority_policy"] == "review_only"
    assert candidate["edit_authority"] is False
    assert candidate["candidate_obligation"] is True
    assert candidate["promotion_required"] is True
    assert candidate["obligation_type"] == candidate_packet["obligation_type"]
    assert candidate["obligation_payload"] == candidate_packet["obligation_payload"]
    assert candidate["obligation_payload"]["qid_pid_assignment"] == "not_implied"


def test_change_review_reports_q27968055_pressure_attribution_review_only() -> None:
    report = build_change_review_report_from_path(FIXTURE)
    by_id = {candidate["candidate_id"]: candidate for candidate in report["candidate_reports"]}

    assert report["edit_authority"] is False
    assert report["pressure_attribution_surface"] == [
        "downstream",
        "local",
        "sibling",
        "upstream",
    ]
    assert "upstream_inheritance_pressure" in report["pressure_attribution"]
    assert by_id["keep_current"]["review_reasons"] == [
        "held_same_depth_split_required",
        "held_upstream_ontology_pressure",
    ]

    remove_q3331189 = by_id["remove_p279_q3331189"]
    assert remove_q3331189["disposition"] == "checked_safe_reviewable"
    assert remove_q3331189["edit_authority"] is False
    assert remove_q3331189["pressure_delta"]["local_statement_pressure"] == -1
    assert remove_q3331189["pressure_delta"]["upstream_inheritance_pressure"] == -1
    assert "held_upstream_ontology_pressure" in remove_q3331189["review_reasons"]
    assert remove_q3331189["held_reasons"] == []

    hold = by_id["hold_for_class_order_review"]
    assert hold["disposition"] == "held"
    assert hold["held_reasons"] == [
        "held_same_depth_split_required",
        "held_series_mereology_required",
        "held_upstream_ontology_pressure",
    ]


def test_change_review_reports_review_only_pnf_index_surface() -> None:
    packet = load_change_review_packet(FIXTURE)
    report = build_change_review_report(packet)
    expected = packet["expected_report_surface"]["pnf_index"]
    pnf_index = report["pnf_index"]

    assert list(pnf_index) == expected["expected_layer_names"]
    assert {"status": expected["receipt_status"]} in pnf_index["receipt_index"]
    assert {"status": expected["compiler_status"]} in pnf_index["predicate_pnf_index"]
    assert pnf_index["promotion_boundary"]["no_fabricated_pnf_receipts"] is True
    assert report["assumptions"]["no_fabricated_pnf_receipts"] is True
    assert pnf_index["promotion_boundary"]["edit_authority"] is False


def test_change_review_reports_pnf_to_wikidata_grounding_surface_review_only() -> None:
    report = build_change_review_report_from_path(FIXTURE)
    grounding = report["wikidata_grounding"]
    components = grounding["components"]

    assert grounding["direction"] == "PredicatePNF_to_Wikidata"
    assert grounding["authority_policy"] == "review_only"
    assert grounding["edit_authority"] is False
    assert grounding["no_fabricated_qids"] is True
    assert grounding["no_fabricated_pids"] is True
    assert grounding["no_fabricated_pnf_receipts"] is True
    assert grounding["grounding_status"] == "packet_supplied_candidates_only"
    assert grounding["candidate_source_policy"] == "packet_supplied_candidates_only"
    assert grounding["qid_pid_policy"] == "no_fabricated_qids_or_pids"
    assert grounding["receipt_policy"] == "no_fabricated_PNFEmissionReceipt"
    assert grounding["source_pnf"]["structural_signature"] == "event_edition_fibre"

    assert {row["qid"] for row in components["subject_qid_candidates"]} == {"Q27968055"}
    q3331189 = next(row for row in components["object_qid_candidates"] if row["qid"] == "Q3331189")
    assert q3331189["meet_status"] == "no_typed_meet"
    assert q3331189["grounding_residual"] == "no_typed_meet"
    assert q3331189["shape"] == "publication/work-edition"
    assert q3331189["target_fibre"] == "event-edition"
    assert q3331189["reason"] == "publication/work-edition shape does not type-meet the event-edition fibre"
    assert q3331189["fabricated"] is False
    assert all(row.get("fabricated") is False for row in components["pid_candidates"])
    assert components["abstract_q_obligations"][0]["qid"] is None
    assert components["abstract_q_obligations"][0]["qid_pid_assignment"] == "not_implied"
    assert components["abstract_q_obligations"][0]["fabricates_qid"] is False
    assert components["abstract_q_obligations"][0]["creates_wikidata_entity"] is False
    assert components["abstract_p_obligations"][0]["pid"] is None
    assert components["abstract_p_obligations"][0]["qid_pid_assignment"] == "not_implied"
    assert components["abstract_p_obligations"][0]["fabricates_pid"] is False
    assert components["abstract_p_obligations"][0]["creates_wikidata_property"] is False
    assert grounding["promotion_boundary"]["abstract_qp_obligations_only"] is True
    assert grounding["promotion_boundary"]["edit_authority"] is False


def test_change_review_candidates_echo_grounding_delta_and_candidate_grounding() -> None:
    report = build_change_review_report_from_path(FIXTURE)
    by_id = {candidate["candidate_id"]: candidate for candidate in report["candidate_reports"]}

    remove = by_id["remove_p279_q3331189"]
    assert remove["grounding_delta"]["publication_edition_mismatch"] == -1
    assert remove["candidate_grounding"]["direction"] == "PredicatePNF_to_Wikidata"
    assert remove["candidate_grounding"]["edit_authority"] is False

    obligation = by_id["hold_upstream_abstract_obligation"]
    assert obligation["candidate_grounding"]["creates_wikidata_entity"] is False
    assert obligation["candidate_grounding"]["creates_wikidata_property"] is False
    assert obligation["candidate_grounding"]["edit_authority"] is False


def test_change_review_candidates_echo_packet_mutation_pnf_review_only() -> None:
    packet = load_change_review_packet(FIXTURE)
    report = build_change_review_report(packet)
    by_id = {candidate["candidate_id"]: candidate for candidate in report["candidate_reports"]}

    for candidate_packet in packet["candidate_repairs"]:
        candidate_report = by_id[candidate_packet["id"]]

        assert candidate_report["mutation_pnf"] == candidate_packet["mutation_pnf"]
        assert candidate_report["mutation_pnf"]["review_posture"] == "review_only"
        assert candidate_report["mutation_pnf"]["mutation_scope"] == "bounded_slice_in_memory"
        assert (
            candidate_report["mutation_pnf"]["receipt_status"]
            == "diagnostic_only_no_pnf_emission_receipts"
        )
        assert candidate_report["edit_authority"] is False


def test_change_review_holds_family_regressions() -> None:
    packet = load_change_review_packet(FIXTURE)
    packet = json.loads(json.dumps(packet))
    packet["candidate_repairs"] = [
        {
            "id": "add_disjoint_instance_pressure",
            "operation": "add",
            "statement": {
                "subject": "Q27968055",
                "property": "P31",
                "value": "Q1656682",
                "rank": "preferred",
                "references": [],
            },
        }
    ]

    report = build_change_review_report(packet)
    candidate = report["candidate_reports"][0]

    assert candidate["diagnostic_delta"]["disjointness_instance"] > 0
    assert candidate["disposition"] == "held"


def test_change_review_reports_mereology_temporal_check_coverage() -> None:
    report = build_change_review_report_from_path(MEREOLOGY_TEMPORAL_FIXTURE)

    assert report["authority_policy"] == "review_only"
    assert report["edit_authority"] is False
    assert report["check_coverage"]["status"] == "complete"
    assert report["check_coverage"]["run"] == [
        "mereology",
        "temporal_exclusivity",
    ]
    assert report["check_coverage"]["omitted"] == []
    assert report["check_coverage"]["deferred"] == []


def test_change_review_counts_mereology_temporal_evidence_independently() -> None:
    report = build_change_review_report_from_path(MEREOLOGY_TEMPORAL_FIXTURE)
    baseline_counts = report["baseline"]["diagnostic_counts"]
    candidate = report["candidate_reports"][0]
    candidate_counts = candidate["candidate_diagnostic_counts"]
    temporal_report = candidate["temporal_mereology_report"]

    assert baseline_counts["parthood_typing"] == 1
    assert baseline_counts["mereology_overlap"] == 0
    assert baseline_counts["missing_temporal_qualifier"] == 0
    assert candidate_counts["parthood_typing"] == 2
    assert candidate_counts["mereology_overlap"] == 1
    assert candidate_counts["missing_temporal_qualifier"] == 0
    assert candidate["diagnostic_delta"]["parthood_typing"] == 1
    assert candidate["diagnostic_delta"]["mereology_overlap"] == 1
    assert candidate["diagnostic_delta"]["missing_temporal_qualifier"] == 0
    assert candidate["diagnostic_delta"]["unstable_slot"] == 0
    assert candidate["diagnostic_delta"]["qualifier_drift"] == 0
    assert candidate["diagnostic_delta"]["reference_drift"] == 0
    assert temporal_report["mereology_overlap_count"] == 1
    assert temporal_report["missing_temporal_qualifier_count"] == 0


def test_change_review_holds_mereology_temporal_regressions_without_edit_authority() -> None:
    report = build_change_review_report_from_path(MEREOLOGY_TEMPORAL_FIXTURE)
    candidate = report["candidate_reports"][0]

    assert candidate["candidate_id"] == "add_overlapping_part_of_region_b"
    assert candidate["authority_policy"] == "review_only"
    assert candidate["edit_authority"] is False
    assert candidate["mutation_summary"]["applied_in_memory_only"] is True
    assert candidate["diagnostic_delta"]["parthood_typing"] > 0
    assert candidate["diagnostic_delta"]["mereology_overlap"] > 0
    assert candidate["disposition"] == "held"


def test_change_review_reports_omitted_requested_checks() -> None:
    packet = load_change_review_packet(FIXTURE)
    packet = json.loads(json.dumps(packet))
    packet["property_scope"] = ["P31", "P279"]

    report = build_change_review_report(packet)

    assert report["check_coverage"]["status"] == "partial"
    assert report["check_coverage"]["omitted"] == [
        {
            "family": "disjointness",
            "reason": "missing required property scope: P11260, P2738",
        }
    ]


def test_change_review_rejects_unknown_packet_schema(tmp_path) -> None:
    packet = load_change_review_packet(FIXTURE)
    packet = json.loads(json.dumps(packet))
    packet["schema_version"] = "sl.wikidata_change_review_packet.v9"
    path = tmp_path / "bad_packet.json"
    path.write_text(json.dumps(packet), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported ChangeReviewPacket schema_version"):
        load_change_review_packet(path)


def test_change_review_schemas_validate_fixture_and_report() -> None:
    packet = load_change_review_packet(FIXTURE)
    mereology_packet = load_change_review_packet(MEREOLOGY_TEMPORAL_FIXTURE)
    report = build_change_review_report_from_path(FIXTURE)
    mereology_report = build_change_review_report_from_path(MEREOLOGY_TEMPORAL_FIXTURE)

    jsonschema.validate(packet, _schema("sl.wikidata_change_review_packet.v0_1.schema.yaml"))
    jsonschema.validate(mereology_packet, _schema("sl.wikidata_change_review_packet.v0_1.schema.yaml"))
    jsonschema.validate(report, _schema("sl.wikidata_change_review_report.v0_1.schema.yaml"))
    jsonschema.validate(mereology_report, _schema("sl.wikidata_change_review_report.v0_1.schema.yaml"))


def test_change_review_cli_writes_deterministic_json(tmp_path, capsys) -> None:
    out_path = tmp_path / "q27968055_change_review_report.json"

    cli_main.main(
        [
            "wikidata",
            "compare-candidates",
            "--packet",
            str(FIXTURE),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["schema_version"] == CHANGE_REVIEW_REPORT_SCHEMA_VERSION
    assert file_payload["review_summary"]["candidate_count"] == 6
    assert file_payload["review_summary"]["non_authoritative"] is True


def test_change_review_cli_stdout_is_deterministic(capsys) -> None:
    cli_main.main(
        [
            "wikidata",
            "compare-candidates",
            "--packet",
            str(FIXTURE),
        ]
    )

    stdout = capsys.readouterr().out
    assert stdout.startswith('{"assumptions":')
    assert json.loads(stdout)["schema_version"] == CHANGE_REVIEW_REPORT_SCHEMA_VERSION
