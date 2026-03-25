import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cli import __main__ as cli_main


FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "wikidata"
    / "disjointness_p2738_pilot_pack_v1"
    / "slice.json"
)


def test_wikidata_disjointness_report_cli_writes_report(tmp_path, capsys) -> None:
    out_path = tmp_path / "disjointness_report.json"

    cli_main.main(
        [
            "wikidata",
            "disjointness-report",
            "--input",
            str(FIXTURE_PATH),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert payload["schema_version"] == "wikidata_disjointness_report/v1"
    assert payload["subclass_violation_count"] == 2
    assert payload["instance_violation_count"] == 2
