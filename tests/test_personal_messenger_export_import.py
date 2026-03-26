from __future__ import annotations

import json
from pathlib import Path

from scripts.build_personal_handoff_from_messenger_export import build_handoff_from_messenger_export_artifact, main
from src.fact_intake.messenger_export_import import load_messenger_export_units


_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "fact_intake" / "facebook_message_1_v1.json"


def test_messenger_export_loader_filters_noise_and_orders_messages() -> None:
    units = load_messenger_export_units(_FIXTURE_PATH)

    assert len(units) == 2
    assert units[0].source_type == "facebook_messages_archive_sample"
    assert units[0].text.startswith("[2026-03-21T03:00:00Z] Jordan Example:")
    assert "Call started" not in units[0].text
    assert units[1].text.startswith("[2026-03-21T03:01:00Z] Alex Example:")


def test_messenger_export_builds_personal_handoff(tmp_path: Path) -> None:
    payload = build_handoff_from_messenger_export_artifact(
        export_path=_FIXTURE_PATH,
        output_dir=tmp_path / "artifact",
        recipient_profile="lawyer",
        source_label="fixture:messenger_export_handoff",
        mode="personal_handoff",
    )

    normalized = json.loads(Path(payload["normalized_input_path"]).read_text(encoding="utf-8"))
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    assert normalized["entries"][0]["source_type"] == "facebook_messages_archive_sample"
    assert report["recipient_export"]["exported_item_count"] == 2


def test_messenger_export_builds_protected_envelope_without_raw_text(tmp_path: Path) -> None:
    payload = build_handoff_from_messenger_export_artifact(
        export_path=_FIXTURE_PATH,
        output_dir=tmp_path / "artifact",
        recipient_profile="lawyer",
        source_label="fixture:messenger_export_protected",
        mode="protected_disclosure_envelope",
    )

    normalized = json.loads(Path(payload["normalized_input_path"]).read_text(encoding="utf-8"))
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    serialized = json.dumps(report, sort_keys=True)
    assert normalized["entries"][0]["local_handle"].startswith("facebook_messages_archive_sample://")
    assert report["integrity"]["sealed_item_count"] == 2
    assert "Please keep the appointment notes" not in serialized
    assert "I wrote down the sequence" not in serialized


def test_messenger_export_script_writes_artifact(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "--export-path",
            str(_FIXTURE_PATH),
            "--recipient-profile",
            "lawyer",
            "--source-label",
            "fixture:messenger_export_handoff",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert Path(payload["report_path"]).exists()
