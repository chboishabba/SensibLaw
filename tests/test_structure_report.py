from __future__ import annotations

import inspect
from pathlib import Path

from src.reporting import structure_report
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


def test_load_file_units_groups_timestamp_bullet_transcript_into_sentenceish_units(tmp_path: Path) -> None:
    fixture = tmp_path / "hearing_transcript.md"
    fixture.write_text(
        "\n".join(
            [
                "# Transcript (demo, en-x-autogen)",
                "",
                "- [00:00:01.000 --> 00:00:03.000] The High Court of Australia is now in session.",
                "- [00:00:03.100 --> 00:00:05.000] Please be seated.",
                "- [00:00:05.100 --> 00:00:07.000] Mr Herzfeld appears for the appellant.",
                "- [00:00:07.100 --> 00:00:09.000] Mr Gleeson appears for the respondent.",
                "- [00:00:09.100 --> 00:00:11.000] The matter concerns the duty of care issue.",
                "- [00:00:11.100 --> 00:00:13.000] Counsel refers to the Civil Liability Act.",
            ]
        ),
        encoding="utf-8",
    )
    units = load_file_units(fixture, "transcript_file")
    assert len(units) >= 2
    assert not any(unit.text.startswith("# Transcript") for unit in units)
    assert units[0].text.startswith("[00:00:01.000 -> 00:00:11.000]")
    assert "Civil Liability Act" in units[-1].text


def test_load_file_units_splits_court_transcript_on_speaker_turns(tmp_path: Path) -> None:
    fixture = tmp_path / "01_Hearing.txt"
    fixture.write_text(
        "\n".join(
            [
                "AustLII Search",
                "High Court of Australia Transcripts",
                "TRANSCRIPT OF PROCEEDINGS",
                "AT CANBERRA",
                "MR P.D. HERZFELD,",
                "SC : Your Honours, I appear for the appellant.",
                "I will address the duty of care issue first.",
                "",
                "GAGELER CJ: Yes. Thank you, Mr Herzfeld.",
                "MR J.T. GLEESON,",
                "SC : I appear for the respondent.",
            ]
        ),
        encoding="utf-8",
    )
    units = load_file_units(fixture, "transcript_file")
    assert len(units) == 3
    assert units[0].text.startswith("MR P.D. HERZFELD, SC :")
    assert "AustLII Search" not in units[0].text
    assert units[1].text.startswith("GAGELER CJ:")


def test_structure_report_db_loaders_use_shared_text_unit_builders() -> None:
    source = inspect.getsource(structure_report)

    assert "build_indexed_text_unit(" in source
    assert "build_timestamped_speaker_text(" in source
