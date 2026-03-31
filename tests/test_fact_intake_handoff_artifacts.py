from __future__ import annotations

import json

from src.fact_intake.handoff_artifacts import resolve_handoff_artifact_metadata, write_handoff_artifact


def test_resolve_handoff_artifact_metadata_handles_personal_and_protected_modes() -> None:
    personal = resolve_handoff_artifact_metadata(
        {"recipient_export": {"exported_item_count": 2}},
        mode="personal_handoff",
    )
    protected = resolve_handoff_artifact_metadata(
        {"integrity": {"sealed_item_count": 3}},
        mode="protected_disclosure_envelope",
    )

    assert personal["version"] == "personal.handoff.report.v1"
    assert personal["primary_count"] == 2
    assert protected["version"] == "protected.disclosure.envelope.v1"
    assert protected["primary_count"] == 3


def test_write_handoff_artifact_emits_normalized_report_and_summary(tmp_path) -> None:
    payload = write_handoff_artifact(
        output_dir=tmp_path,
        normalized={"source_label": "fixture"},
        report={
            "run": {"recipient_profile": "lawyer"},
            "recipient_export": {"exported_item_count": 1},
        },
        mode="personal_handoff",
        extra_metadata={"source_kind": "chat"},
    )

    assert payload["version"] == "personal.handoff.report.v1"
    assert payload["source_kind"] == "chat"
    normalized = json.loads((tmp_path / "normalized_input.json").read_text(encoding="utf-8"))
    report = json.loads((tmp_path / "personal.handoff.report.v1.json").read_text(encoding="utf-8"))
    assert normalized["source_label"] == "fixture"
    assert report["run"]["recipient_profile"] == "lawyer"
