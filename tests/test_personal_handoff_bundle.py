from __future__ import annotations

import json
from pathlib import Path

from scripts.build_personal_handoff_bundle import build_handoff_artifact, main
from src.fact_intake.personal_handoff_bundle import build_personal_handoff_report

_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "fact_intake" / "personal_handoff_input_v1.json"
)
_PROTECTED_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "fact_intake" / "personal_handoff_protected_input_v1.json"
)


def test_personal_handoff_report_applies_scope_and_redaction() -> None:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))

    report = build_personal_handoff_report(payload)

    assert report["version"] == "personal.handoff.report.v1"
    assert report["run"]["recipient_profile"] == "lawyer"
    assert report["run"]["local_only"] is True
    assert report["recipient_export"]["preferred_operator_view"]["key"] == "professional_handoff"
    assert report["recipient_export"]["exported_item_count"] == 3
    assert report["recipient_export"]["excluded_item_count"] == 1
    exported_by_unit = {
        tuple(item["unit_ids"]): item for item in report["recipient_export"]["items"]
    }
    assert ("p3",) in exported_by_unit
    assert exported_by_unit[("p3",)]["text_redacted"] is True
    assert exported_by_unit[("p3",)]["export_text"] == "[REDACTED]"
    excluded = report["recipient_export"]["excluded_items"]
    assert excluded[0]["unit_ids"] == ["p4"]
    assert excluded[0]["exclusion_reason"] == "recipient_not_permitted"
    assert report["review_summary"]["summary"]["review_queue_count"] >= 1


def test_personal_handoff_script_writes_report_and_summary(tmp_path, capsys) -> None:
    output_dir = tmp_path / "handoff"

    exit_code = main(["--input-json", str(_FIXTURE_PATH), "--output-dir", str(output_dir)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["version"] == "personal.handoff.report.v1"
    report_path = Path(payload["report_path"])
    summary_path = Path(payload["summary_path"])
    assert report_path.exists()
    assert summary_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    summary = summary_path.read_text(encoding="utf-8")
    assert report["recipient_export"]["exported_item_count"] == 3
    assert "Private journal entry not yet ready for legal export." not in summary
    assert "recipient_not_permitted" in summary


def test_build_handoff_artifact_returns_paths(tmp_path) -> None:
    payload = build_handoff_artifact(_FIXTURE_PATH, tmp_path / "artifact")
    assert payload["recipient_profile"] == "lawyer"
    assert payload["exported_item_count"] == 3


def test_protected_disclosure_envelope_forces_local_flags_and_scopes_export() -> None:
    payload = json.loads(_PROTECTED_FIXTURE_PATH.read_text(encoding="utf-8"))

    lawyer_report = build_personal_handoff_report(payload)

    assert lawyer_report["protected_disclosure"]["enabled"] is True
    assert lawyer_report["run"]["local_only"] is True
    assert lawyer_report["run"]["do_not_sync"] is True
    assert lawyer_report["protected_disclosure"]["allowed_recipient_profiles"] == ["lawyer", "regulator"]
    exported_by_unit = {
        tuple(item["unit_ids"]): item for item in lawyer_report["recipient_export"]["items"]
    }
    assert ("w2",) in exported_by_unit
    assert exported_by_unit[("w2",)]["protected_disclosure_only"] is True
    assert exported_by_unit[("w2",)]["protected_disclosure_reason"] == "potential workplace retaliation risk"
    assert exported_by_unit[("w2",)]["text_redacted"] is True

    payload["recipient_profile"] = "advocate"
    advocate_report = build_personal_handoff_report(payload)
    excluded_by_unit = {
        tuple(item["unit_ids"]): item for item in advocate_report["recipient_export"]["excluded_items"]
    }
    assert ("w2",) in excluded_by_unit
    assert excluded_by_unit[("w2",)]["exclusion_reason"] == "protected_disclosure_scope_mismatch"


def test_protected_disclosure_summary_emits_envelope_without_leaking_excluded_text(tmp_path, capsys) -> None:
    output_dir = tmp_path / "protected"

    exit_code = main(["--input-json", str(_PROTECTED_FIXTURE_PATH), "--output-dir", str(output_dir)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    summary = Path(payload["summary_path"]).read_text(encoding="utf-8")
    assert "## Protected disclosure" in summary
    assert "workplace_integrity_v1" in summary
    assert "Protected workplace-integrity material must remain local-only" in summary
    assert "potential workplace retaliation risk" not in summary
