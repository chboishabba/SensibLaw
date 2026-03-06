import json
import sys
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
