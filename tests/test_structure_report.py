from __future__ import annotations

from pathlib import Path

from src.reporting.structure_report import TextUnit, build_structure_report, load_file_units


def test_structure_report_surfaces_useful_and_interlinked_atoms():
    units = [
        TextUnit(
            unit_id="u1",
            source_id="chat",
            source_type="chat_test_db",
            text="User: cite Civil Liability Act 2002 (NSW) s 5B applies here and run `pytest -q` in ./SensibLaw/tests/test_lexeme_layer.py",
        ),
        TextUnit(
            unit_id="u2",
            source_id="chat",
            source_type="chat_test_db",
            text="Assistant: the Civil Liability Act 2002 (NSW) s 5B still matters; $ pytest SensibLaw/tests/test_lexeme_layer.py -q",
        ),
        TextUnit(
            unit_id="u3",
            source_id="ctx",
            source_type="context_file",
            text="# Current Direction\n- Run pytest again\n- Inspect ./SensibLaw/tests/test_lexeme_layer.py",
        ),
    ]
    report = build_structure_report(units, top_n=10)
    assert report["unit_count"] == 3
    assert report["structural_token_count"] > 0
    top_atoms = {(row["norm_text"], row["kind"]) for row in report["top_structural_atoms"]}
    assert ("act:civil_liability_act_2002_nsw", "act_ref") in top_atoms
    assert ("cmd:pytest", "command_ref") in top_atoms
    section_atoms = {(row["norm_text"], row["kind"]) for row in report["top_structural_atoms_by_kind"]["section_ref"]}
    assert ("sec:5b", "section_ref") in section_atoms
    assert any(row["neighbor_count"] > 0 for row in report["top_interlinked_atoms"])
    assert any(row["utility_score"] > 0 for row in report["top_useful_atoms"])


def test_load_file_units_splits_bracketed_transcript_fixture_into_message_units():
    fixture = (
        Path(__file__).resolve().parents[2]
        / "tircorder-JOBBIE"
        / "tests"
        / "data"
        / "telegram_bracketed.txt"
    )
    units = load_file_units(fixture, "transcript_file")
    assert len(units) == 6
    assert units[0].text.startswith("[5/3/26 8:50")
    assert units[-1].text.startswith("[7/3/26 2:00")
