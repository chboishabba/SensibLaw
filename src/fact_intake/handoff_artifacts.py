from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .personal_handoff_bundle import PERSONAL_HANDOFF_REPORT_VERSION, render_personal_handoff_summary
from .protected_disclosure_envelope import (
    PROTECTED_DISCLOSURE_ENVELOPE_VERSION,
    render_protected_disclosure_summary,
)


def resolve_handoff_artifact_metadata(report: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    if mode == "protected_disclosure_envelope":
        return {
            "version": PROTECTED_DISCLOSURE_ENVELOPE_VERSION,
            "summary": render_protected_disclosure_summary(report),
            "primary_count": int(report["integrity"]["sealed_item_count"]),
        }
    return {
        "version": PERSONAL_HANDOFF_REPORT_VERSION,
        "summary": render_personal_handoff_summary(report),
        "primary_count": int(report["recipient_export"]["exported_item_count"]),
    }


def write_handoff_artifact(
    *,
    output_dir: Path,
    normalized: Mapping[str, Any],
    report: Mapping[str, Any],
    mode: str,
    extra_metadata: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = resolve_handoff_artifact_metadata(report, mode=mode)
    version = str(metadata["version"])
    summary = str(metadata["summary"])
    normalized_path = output_dir / "normalized_input.json"
    report_path = output_dir / f"{version}.json"
    summary_path = output_dir / f"{version}.summary.md"
    normalized_path.write_text(json.dumps(dict(normalized), indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(json.dumps(dict(report), indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(summary, encoding="utf-8")

    payload: dict[str, object] = {
        "mode": mode,
        "version": version,
        "normalized_input_path": str(normalized_path),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "recipient_profile": str(report["run"]["recipient_profile"]),
        "primary_count": int(metadata["primary_count"]),
    }
    if extra_metadata:
        payload.update(dict(extra_metadata))
    return payload
