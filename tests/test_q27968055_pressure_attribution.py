import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_change_review import build_change_review_report_from_path


FIXTURE = ROOT / "tests" / "fixtures" / "wikidata" / "q27968055_change_review_packet.json"


def _packet() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _report() -> dict:
    return build_change_review_report_from_path(FIXTURE)


def test_q27968055_packet_carries_deterministic_pressure_attribution() -> None:
    packet = _packet()
    expected = packet["expected_report_surface"]["pressure_attribution"]

    assert packet["authority_policy"] == "review_only"
    assert packet["expected_report_surface"]["edit_authority"] is False
    assert packet["pressure_attribution"] == expected
    assert sorted(packet["pressure_attribution"]) == [
        "downstream_dependency_pressure",
        "local_statement_pressure",
        "sibling_shape_pressure",
        "upstream_inheritance_pressure",
    ]


def test_q27968055_report_echoes_pressure_attribution_without_edit_authority() -> None:
    packet = _packet()
    report = _report()

    assert report["authority_policy"] == "review_only"
    assert report["edit_authority"] is False
    assert report["pressure_attribution"] == packet["expected_report_surface"]["pressure_attribution"]


def test_q27968055_held_candidate_echoes_pressure_reasons() -> None:
    packet = _packet()
    report = _report()
    expected = packet["expected_report_surface"]["candidate_reports"]["hold_for_class_order_review"]
    by_id = {candidate["candidate_id"]: candidate for candidate in report["candidate_reports"]}
    candidate = by_id["hold_for_class_order_review"]

    assert candidate["disposition"] == "held"
    assert candidate["authority_policy"] == "review_only"
    assert candidate["edit_authority"] is False
    assert candidate["review_reasons"] == expected["review_reasons"]
    assert candidate["pressure_attribution"] == expected["pressure_attribution"]
