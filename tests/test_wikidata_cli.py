import json
import sys
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cli import __main__ as cli_main


def test_wikidata_project_cli_writes_report(tmp_path, capsys) -> None:
    in_path = tmp_path / "wikidata_slice.json"
    out_path = tmp_path / "wikidata_report.json"
    in_path.write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "id": "t1",
                        "statement_bundles": [
                            {
                                "subject": "Q1",
                                "property": "P31",
                                "value": "Q2",
                                "rank": "preferred",
                                "references": [{"P248": "Qsrc"}],
                            }
                        ],
                    },
                    {
                        "id": "t2",
                        "statement_bundles": [
                            {
                                "subject": "Q1",
                                "property": "P31",
                                "value": "Q2",
                                "rank": "deprecated",
                                "references": [{"P248": "Qsrc"}],
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["unstable_slots"][0]["slot_id"] == "Q1|P31"


def test_wikidata_build_slice_cli_groups_window_files(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    source_a = root / "fixtures" / "wikidata" / "entitydata_window_a.json"
    source_b = root / "fixtures" / "wikidata" / "entitydata_window_b.json"
    out_path = tmp_path / "built_slice.json"

    cli_main.main(
        [
            "wikidata",
            "build-slice",
            "--window-file",
            f"t1:{source_a}",
            "--window-file",
            f"t2:{source_b}",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert [window["id"] for window in file_payload["windows"]] == ["t1", "t2"]
    assert file_payload["windows"][0]["statement_bundles"][0]["subject"] == "Q9779"


def test_wikidata_project_cli_emits_qualifier_drift(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = root / "fixtures" / "wikidata" / "qualifier_drift_slice_20260307.json"
    out_path = tmp_path / "qualifier_report.json"

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--property",
            "P166",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["qualifier_drift"][0]["slot_id"] == "Qposthumous_case|P166"


def test_wikidata_build_slice_and_project_real_qualifier_baseline(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    out_slice = tmp_path / "real_qualifier_slice.json"
    out_report = tmp_path / "real_qualifier_report.json"

    cli_main.main(
        [
            "wikidata",
            "build-slice",
            "--window-file",
            f"t1:{root / 'fixtures' / 'wikidata' / 'entitydata_qualifier_q28792860_prev.json'}",
            "--window-file",
            f"t1:{root / 'fixtures' / 'wikidata' / 'entitydata_qualifier_q1336181_prev.json'}",
            "--window-file",
            f"t2:{root / 'fixtures' / 'wikidata' / 'entitydata_qualifier_q28792860_current.json'}",
            "--window-file",
            f"t2:{root / 'fixtures' / 'wikidata' / 'entitydata_qualifier_q1336181_current.json'}",
            "--property",
            "P166",
            "--output",
            str(out_slice),
        ]
    )
    capsys.readouterr()

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(out_slice),
            "--property",
            "P166",
            "--output",
            str(out_report),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_report.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_report)
    assert file_payload["qualifier_drift"] == []
    assert {
        slot["slot_id"] for slot in file_payload["windows"][0]["slots"]
    } == {"Q1336181|P166", "Q28792860|P166"}


def test_wikidata_project_cli_matches_repo_pinned_live_drift_case(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "q100104196_p166_2277985537_2277985693"
        / "slice.json"
    )
    out_path = tmp_path / "repo_pinned_live_drift_report.json"

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--property",
            "P166",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["qualifier_drift"][0]["slot_id"] == "Q100104196|P166"
    assert file_payload["qualifier_drift"][0]["severity"] == "medium"


def test_wikidata_project_cli_matches_repo_pinned_second_live_drift_case(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "q100152461_p54_2456615151_2456615274"
        / "slice.json"
    )
    out_path = tmp_path / "repo_pinned_second_live_drift_report.json"

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--property",
            "P54",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["qualifier_drift"][0]["slot_id"] == "Q100152461|P54"
    assert file_payload["qualifier_drift"][0]["severity"] == "medium"


def test_wikidata_build_migration_pack_cli_writes_pack(tmp_path, capsys) -> None:
    in_path = tmp_path / "migration_slice.json"
    out_path = tmp_path / "migration_pack.json"
    in_path.write_text(
        json.dumps(
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
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "build-migration-pack",
            "--input",
            str(in_path),
            "--source-property",
            "P5991",
            "--target-property",
            "P14143",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["candidate_count"] == 1
    assert file_payload["source_property"] == "P5991"
    assert file_payload["target_property"] == "P14143"
    assert file_payload["candidates"][0]["claim_bundle_after"]["property"] == "P14143"
    assert file_payload["summary"]["checked_safe_subset"] == [
        file_payload["candidates"][0]["candidate_id"]
    ]


def test_wikidata_project_cli_accepts_prepopulation_core_profile(tmp_path, capsys) -> None:
    in_path = tmp_path / "prepopulation_core_slice.json"
    out_path = tmp_path / "prepopulation_core_report.json"
    in_path.write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "id": "t1",
                        "statement_bundles": [
                            {"subject": "Q1", "property": "P31", "value": "QClass", "rank": "preferred"},
                            {"subject": "Q1", "property": "P361", "value": "QWhole", "rank": "preferred"},
                            {"subject": "QWhole", "property": "P527", "value": "Q1", "rank": "preferred"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--profile",
            "prepopulation_core",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert file_payload["bounded_slice"]["profile"] == "prepopulation_core"
    assert file_payload["bounded_slice"]["properties"] == ["P279", "P31", "P361", "P527"]
    assert file_payload["windows"][0]["diagnostics"]["parthood_typing"]["classifications"]


def test_wikidata_export_migration_pack_openrefine_cli_writes_csv(tmp_path, capsys) -> None:
    in_path = tmp_path / "migration_pack.json"
    out_path = tmp_path / "migration_pack_openrefine.csv"
    in_path.write_text(
        json.dumps(
            {
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
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "export-migration-pack-openrefine",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    rows = list(csv.DictReader(out_path.open(encoding="utf-8")))
    assert stdout["output"] == str(out_path)
    assert stdout["row_count"] == 1
    assert rows[0]["entity_qid"] == "Q1"
    assert rows[0]["action"] == "migrate_with_refs"
    assert rows[0]["suggested_action"] == "migrate_with_refs"
    assert rows[0]["split_axis_count"] == "0"


def test_wikidata_export_migration_pack_checked_safe_cli_writes_csv(tmp_path, capsys) -> None:
    in_path = tmp_path / "migration_pack.json"
    out_path = tmp_path / "migration_pack_checked_safe.csv"
    in_path.write_text(
        json.dumps(
            {
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
                            "qualifiers": {},
                            "references": [],
                        },
                        "claim_bundle_after": {
                            "property": "P14143",
                            "value": "200",
                            "rank": "normal",
                            "qualifiers": {},
                            "references": [],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "export-migration-pack-checked-safe",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    rows = list(csv.DictReader(out_path.open(encoding="utf-8")))
    assert stdout["output"] == str(out_path)
    assert stdout["row_count"] == 1
    assert stdout["export_scope"] == "checked_safe_subset_only"
    assert rows[0]["candidate_id"] == "Q1|P5991|1"
    assert rows[0]["action"] == "migrate_with_refs"


def test_wikidata_verify_migration_pack_cli_writes_json(tmp_path, capsys) -> None:
    migration_pack_path = tmp_path / "migration_pack.json"
    after_path = tmp_path / "after.json"
    out_path = tmp_path / "verification.json"
    migration_pack_path.write_text(
        json.dumps(
            {
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
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    after_path.write_text(
        json.dumps(
            {
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
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "verify-migration-pack",
            "--input",
            str(migration_pack_path),
            "--after",
            str(after_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["verified_candidate_count"] == 1
    assert stdout["counts_by_status"] == {"verified": 1}
    assert payload["rows"][0]["status"] == "verified"


def test_wikidata_build_split_plan_cli_writes_json(tmp_path, capsys) -> None:
    in_path = tmp_path / "migration_pack.json"
    out_path = tmp_path / "split_plan.json"
    in_path.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "build-split-plan",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["plan_count"] == 1
    assert stdout["counts_by_status"] == {"structurally_decomposable": 1}
    assert payload["plans"][0]["status"] == "structurally_decomposable"


def test_wikidata_cohort_c_operator_packet_cli_wraps_scan_payload(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = root / "fixtures" / "wikidata" / "wikidata_nat_cohort_c_population_scan_20260402.json"
    out_path = tmp_path / "cohort_c_operator_packet.json"

    cli_main.main(
        [
            "wikidata",
            "cohort-c-operator-packet",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["decision"] == "review"
    assert stdout["candidate_count"] == 3
    assert payload["decision"] == "review"
    assert payload["triage_prompts"][0].startswith("Review the candidate P459 status split")
