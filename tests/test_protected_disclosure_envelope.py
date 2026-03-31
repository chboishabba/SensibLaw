from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

from scripts.build_protected_disclosure_envelope import build_protected_disclosure_artifact, main
from src.fact_intake import protected_disclosure_envelope
from src.fact_intake.protected_disclosure_envelope import build_protected_disclosure_envelope

_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "fact_intake" / "protected_disclosure_input_v1.json"
)


def test_protected_disclosure_envelope_is_metadata_only_and_deny_by_default(monkeypatch) -> None:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("sqlite forbidden")))

    report = build_protected_disclosure_envelope(payload)
    serialized = json.dumps(report, sort_keys=True)

    assert report["version"] == "protected.disclosure.envelope.v1"
    assert report["run"]["local_only"] is True
    assert report["run"]["do_not_sync"] is True
    assert report["protected_disclosure"]["disclosure_route"] == "counsel_or_regulator_first"
    assert report["protected_disclosure"]["minimization_mode"] == "standard_metadata_only"
    assert report["integrity"]["sealed_item_count"] == 3
    assert report["integrity"]["exclusion_count"] == 1
    assert "I wrote the full account immediately after the meeting." not in serialized
    assert "The email thread confirms the meeting date and attendees." not in serialized
    assert "2026-02-14" not in serialized
    assert "Keep provisional until documentary corroboration is assembled." not in serialized
    excluded = {item["unit_id"]: item for item in report["exclusions"]}
    assert excluded["pd4"]["exclusion_reason"] == "recipient_not_permitted"
    exported = {item["unit_id"]: item for item in report["sealed_items"]}
    assert exported["pd2"]["retaliation_risk_tags"] == ["manager_visibility", "workplace_retaliation"]


def test_protected_disclosure_scope_blocks_protected_only_item_for_advocate() -> None:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["recipient_profile"] = "advocate"

    report = build_protected_disclosure_envelope(payload)

    excluded = {item["unit_id"]: item for item in report["exclusions"]}
    assert report["integrity"]["sealed_item_count"] == 0
    assert excluded["pd1"]["exclusion_reason"] == "disclosure_route_mismatch"
    assert excluded["pd2"]["exclusion_reason"] == "disclosure_route_mismatch"
    assert excluded["pd2"]["protected_disclosure_reason"] == "potential workplace retaliation risk"


def test_protected_disclosure_minimization_can_exclude_named_identity_items() -> None:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["handoff"]["retaliation_risk_level"] = "extreme"
    payload["handoff"]["protected_disclosure"]["minimization_mode"] = "withheld_identity_only"

    report = build_protected_disclosure_envelope(payload)

    exported = {item["unit_id"]: item for item in report["sealed_items"]}
    excluded = {item["unit_id"]: item for item in report["exclusions"]}
    assert "pd1" in exported
    assert "pd2" not in exported
    assert "pd3" not in exported
    assert excluded["pd2"]["exclusion_reason"] == "identity_policy_too_exposed"
    assert excluded["pd3"]["exclusion_reason"] == "identity_policy_too_exposed"


def test_protected_disclosure_script_writes_artifact_and_summary(tmp_path, capsys) -> None:
    output_dir = tmp_path / "protected"

    exit_code = main(["--input-json", str(_FIXTURE_PATH), "--output-dir", str(output_dir)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    summary = Path(payload["summary_path"]).read_text(encoding="utf-8")
    assert report["integrity"]["sealed_item_count"] == 3
    assert "## Envelope" in summary
    assert "Protected workplace-integrity material must remain local-only" in summary
    assert "- Disclosure route: counsel_or_regulator_first" in summary
    assert "- Minimization mode: standard_metadata_only" in summary
    assert "Keep provisional until documentary corroboration is assembled." not in summary
    assert "I wrote the full account immediately after the meeting." not in summary


def test_build_protected_disclosure_artifact_returns_paths(tmp_path) -> None:
    payload = build_protected_disclosure_artifact(_FIXTURE_PATH, tmp_path / "artifact")
    assert payload["recipient_profile"] == "lawyer"
    assert payload["sealed_item_count"] == 3


def test_protected_disclosure_envelope_uses_shared_disclosure_policy() -> None:
    source = inspect.getsource(protected_disclosure_envelope)

    assert "build_protected_disclosure_settings" in source
    assert "normalize_profile(" in source
    assert "normalize_share_with(" in source
    assert "sha256_payload(" in source
