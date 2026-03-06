import json
from pathlib import Path

from src.ontology.wikidata import SCHEMA_VERSION, project_wikidata_payload


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
