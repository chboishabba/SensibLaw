from __future__ import annotations

import json
from pathlib import Path

from scripts.build_personal_handoff_from_chat_json import build_handoff_from_chat_artifact, main
from src.fact_intake.personal_chat_import import build_handoff_input_from_chat_json, build_handoff_report_from_chat_json

_PERSONAL_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "fact_intake" / "personal_chat_input_v1.json"
)
_PROTECTED_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "fact_intake" / "protected_chat_input_v1.json"
)


def test_chat_import_builds_personal_handoff_input_and_report() -> None:
    payload = json.loads(_PERSONAL_FIXTURE_PATH.read_text(encoding="utf-8"))

    normalized = build_handoff_input_from_chat_json(payload)
    report = build_handoff_report_from_chat_json(payload)

    assert normalized["entries"][0]["text"].startswith("[2026-03-20T09:15:00Z] Me:")
    assert normalized["entries"][2]["text_export_policy"] == "redact"
    assert report["version"] == "personal.handoff.report.v1"
    assert report["recipient_export"]["exported_item_count"] == 3


def test_chat_import_builds_protected_envelope_without_raw_text_in_report() -> None:
    payload = json.loads(_PROTECTED_FIXTURE_PATH.read_text(encoding="utf-8"))

    normalized = build_handoff_input_from_chat_json(payload)
    report = build_handoff_report_from_chat_json(payload)
    serialized = json.dumps(report, sort_keys=True)

    assert normalized["entries"][0]["local_handle"] == "chat://pc1"
    assert normalized["entries"][0]["envelope_summary"] == "Chat message from Me at 2026-03-18T08:45:00Z"
    assert report["version"] == "protected.disclosure.envelope.v1"
    assert "I believe the procurement direction may have been improper." not in serialized
    assert "Keep provisional until documentary support is assembled." not in serialized


def test_chat_import_script_writes_normalized_input_and_report(tmp_path, capsys) -> None:
    output_dir = tmp_path / "chat-import"

    exit_code = main(["--input-json", str(_PROTECTED_FIXTURE_PATH), "--output-dir", str(output_dir)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    normalized = json.loads(Path(payload["normalized_input_path"]).read_text(encoding="utf-8"))
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    assert normalized["entries"][1]["protected_disclosure_only"] is True
    assert report["integrity"]["sealed_item_count"] == 2


def test_build_handoff_from_chat_artifact_returns_paths(tmp_path) -> None:
    payload = build_handoff_from_chat_artifact(_PERSONAL_FIXTURE_PATH, tmp_path / "artifact")
    assert payload["mode"] == "personal_handoff"
    assert payload["primary_count"] == 3
