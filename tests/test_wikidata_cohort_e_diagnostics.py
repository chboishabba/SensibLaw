import json
import sys
from pathlib import Path

from cli import cohort_e_diagnostics
from src.ontology.wikidata_cohort_e_diagnostics import (
    build_cohort_e_diagnostic_report,
)
from src.ontology.wikidata_cohort_e_summary_index import build_summary_index


def _load_sample_axis_fixture() -> dict[str, object]:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_split_axis_sample_20260403.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_cohort_e_diagnostic_report_holds_on_mismatch() -> None:
    fixture = _load_sample_axis_fixture()
    sample = fixture["samples"]
    report = build_cohort_e_diagnostic_report(
        primary_candidate=sample[0],
        reference_candidates=[sample[1]],
        max_comparisons=1,
    )

    assert report["lane_id"] == "wikidata_nat_cohort_e_unreconciled_instanceof"
    assert report["hold_reason"] == "unreconciled instance of"
    assert report["comparisons"][0]["status"] == "disagreement"
    assert "__value__" in report["comparisons"][0]["disagreements"]
    assert report["non_authoritative"] is True
    assert "axis_specific_unreconciled_instance_of" in report["diagnostic_flags"]


def test_diagnostic_fixture_matches_helper() -> None:
    fixture = _load_sample_axis_fixture()
    sample = fixture["samples"]
    computed = build_cohort_e_diagnostic_report(
        primary_candidate=sample[0],
        reference_candidates=[sample[1]],
        max_comparisons=1,
    )
    fixture_report = _load_diagnostic_report_fixture()

    assert computed == fixture_report


def _load_diagnostic_report_fixture() -> dict[str, object]:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_diagnostic_report_20260403.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _load_batch_sample_fixture() -> dict[str, object]:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_split_axis_batch_sample_20260403.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _load_batch_report_fixture() -> list[dict[str, object]]:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_diagnostic_batch_report_20260403.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _load_batch_summary_fixture() -> dict[str, object]:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_diagnostic_summary_20260403.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_cli_regenerates_diagnostic_report(tmp_path, monkeypatch) -> None:
    samples_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_split_axis_sample_20260403.json"
    )
    output_path = tmp_path / "generated_report.json"
    summary_path = tmp_path / "generated_summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cohort-e-diagnostics",
            "--samples",
            str(samples_path),
            "--output",
            str(output_path),
            "--summary-output",
            str(summary_path),
        ],
    )
    cohort_e_diagnostics.main()
    assert output_path.exists()
    generated = json.loads(output_path.read_text(encoding="utf-8"))
    fixture = _load_diagnostic_report_fixture()
    assert generated == fixture


def test_cli_batch_outputs_repeat(tmp_path, monkeypatch) -> None:
    samples_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_split_axis_batch_sample_20260403.json"
    )
    output_path = tmp_path / "batch_report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cohort-e-diagnostics",
            "--batch",
            "--samples",
            str(samples_path),
            "--output",
            str(output_path),
            "--summary-output",
            str(tmp_path / "batch_summary_repeat.json"),
        ],
    )
    cohort_e_diagnostics.main()
    assert output_path.exists()
    generated = json.loads(output_path.read_text(encoding="utf-8"))
    fixture = _load_batch_report_fixture()
    assert generated == fixture


def test_cli_batch_outputs_summary(tmp_path, monkeypatch) -> None:
    samples_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_split_axis_batch_sample_20260403.json"
    )
    output_path = tmp_path / "batch_report.json"
    summary_path = tmp_path / "batch_summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cohort-e-diagnostics",
            "--batch",
            "--samples",
            str(samples_path),
            "--output",
            str(output_path),
            "--summary-output",
            str(summary_path),
        ],
    )
    cohort_e_diagnostics.main()
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary == _load_batch_summary_fixture()
    index = build_summary_index([summary, summary])
    expected_index = _load_summary_index_fixture()
    assert index == expected_index


def test_cli_index_output(tmp_path, monkeypatch) -> None:
    summary_fixture = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_diagnostic_summary_20260403.json"
    )
    output_path = tmp_path / "batch_report.json"
    summary_path = tmp_path / "batch_summary.json"
    index_path = tmp_path / "summary_index.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cohort-e-diagnostics",
            "--batch",
            "--samples",
            str(summary_fixture),
            "--output",
            str(output_path),
            "--summary-output",
            str(summary_path),
            "--summaries",
            str(summary_fixture),
            str(summary_fixture),
            "--index-output",
            str(index_path),
        ],
    )
    cohort_e_diagnostics.main()
    assert index_path.exists()
    generated_index = json.loads(index_path.read_text(encoding="utf-8"))
    fixture = _load_summary_index_fixture()
    assert generated_index == fixture

def _load_summary_index_fixture() -> dict[str, object]:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_e_summary_index_20260403.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))
