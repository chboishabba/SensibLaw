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
