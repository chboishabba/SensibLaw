from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts import build_personal_handoff_from_google_public
from scripts.build_personal_handoff_from_google_public import build_handoff_from_google_public_artifact
from src.fact_intake import google_public_import
from src.fact_intake.google_public_import import (
    build_google_public_export_url,
    extract_affidavit_text_from_doc_text,
    load_google_doc_units_from_text,
    load_google_sheet_units_from_csv_text,
    parse_google_public_url,
)


def test_parse_google_public_url_and_export_url() -> None:
    sheet_url = "https://docs.google.com/spreadsheets/d/abc123/edit?usp=sharing"
    doc_url = "https://docs.google.com/document/d/xyz789/edit?usp=sharing"
    assert parse_google_public_url(sheet_url) == {"kind": "sheet", "doc_id": "abc123"}
    assert parse_google_public_url(doc_url) == {"kind": "doc", "doc_id": "xyz789"}
    assert build_google_public_export_url(sheet_url).endswith("/spreadsheets/d/abc123/export?format=csv")
    assert build_google_public_export_url(doc_url).endswith("/document/d/xyz789/export?format=txt")


def test_google_sheet_csv_units_are_rendered_compactly() -> None:
    csv_text = (
        "ID#1,ID#2,ID as is,Event,Evidenced,Type,Filename,Description\n"
        "1,1,257,John begins seeking justice,,, ,Divorce from Monica and workplace trouble.\n"
    )
    units = load_google_sheet_units_from_csv_text(csv_text, source_id="google_sheet:test")
    assert len(units) == 1
    assert "Event: John begins seeking justice" in units[0].text
    assert "Description: Divorce from Monica and workplace trouble." in units[0].text


def test_google_doc_units_and_affidavit_extraction() -> None:
    text = (
        "Intro line\n\n"
        "Affidavit Text:\n"
        "I, Example Person, affirm this statement.\n"
        "The respondent cut off my internet.\n\n"
        "Which Allegations Can You Plausibly Deny or Explain?\n"
        "Analysis starts here.\n"
    )
    units = load_google_doc_units_from_text(text, source_id="google_doc:test")
    assert units[0].text == "Intro line"
    affidavit_text = extract_affidavit_text_from_doc_text(text)
    assert "The respondent cut off my internet." in affidavit_text
    assert "Analysis starts here." not in affidavit_text


def test_build_handoff_from_google_public_artifact_uses_public_units(monkeypatch, tmp_path: Path) -> None:
    from scripts import build_personal_handoff_from_google_public as module

    fake_units = load_google_doc_units_from_text(
        "First note.\n\nSecond note.",
        source_id="google_doc:test",
    )
    monkeypatch.setattr(module, "load_google_public_units", lambda url: fake_units)
    payload = build_handoff_from_google_public_artifact(
        url="https://docs.google.com/document/d/testdoc/edit?usp=sharing",
        output_dir=tmp_path / "artifact",
        recipient_profile="lawyer",
        source_label="fixture:google_public_doc",
        mode="personal_handoff",
    )
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    assert payload["google_kind"] == "doc"
    assert report["recipient_export"]["exported_item_count"] == 2


def test_google_public_script_uses_shared_handoff_artifact_writer() -> None:
    source = inspect.getsource(build_personal_handoff_from_google_public)

    assert "write_handoff_artifact(" in source


def test_google_public_loader_uses_shared_text_unit_builder() -> None:
    source = inspect.getsource(google_public_import)

    assert "build_indexed_text_unit(" in source


def test_google_public_loader_uses_shared_source_identity_policy() -> None:
    source = inspect.getsource(google_public_import)

    assert "build_google_public_source_id(" in source


def test_google_public_loader_uses_shared_source_loader_policy() -> None:
    source = inspect.getsource(google_public_import)

    assert "fetch_text_url(" in source
