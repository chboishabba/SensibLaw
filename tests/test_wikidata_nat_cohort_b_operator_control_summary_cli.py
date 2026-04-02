import json
from pathlib import Path

from cli.cohort_b_operator_control_summary import main


def test_cohort_b_operator_control_summary_cli_materializes_pinned_fixture(tmp_path) -> None:
    root = Path(__file__).resolve().parent
    fixture_dir = root / "fixtures" / "wikidata"
    index1 = fixture_dir / "wikidata_nat_cohort_b_operator_evidence_index_20260402.json"
    index2 = fixture_dir / "wikidata_nat_cohort_b_operator_evidence_index_case2_20260402.json"
    expected = json.loads(
        (fixture_dir / "wikidata_nat_cohort_b_operator_control_summary_20260402.json").read_text(
            encoding="utf-8"
        )
    )
    out_path = tmp_path / "cohort_b_operator_control_summary.json"

    exit_code = main(
        [
            "--inputs",
            str(index1),
            str(index2),
            "--min-ready-indexes",
            "2",
            "--output",
            str(out_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload == expected
