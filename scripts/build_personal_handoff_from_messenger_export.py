#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.fact_intake.messenger_export_import import load_messenger_export_units  # noqa: E402
from src.fact_intake.personal_chat_import import build_handoff_input_from_units, build_handoff_report_from_chat_json  # noqa: E402
from src.fact_intake.personal_handoff_bundle import PERSONAL_HANDOFF_REPORT_VERSION, render_personal_handoff_summary  # noqa: E402
from src.fact_intake.protected_disclosure_envelope import (  # noqa: E402
    PROTECTED_DISCLOSURE_ENVELOPE_VERSION,
    render_protected_disclosure_summary,
)


def build_handoff_from_messenger_export_artifact(
    *,
    export_path: Path,
    output_dir: Path,
    recipient_profile: str,
    source_label: str,
    mode: str,
    limit: int | None = None,
    notes: str | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    units = load_messenger_export_units(export_path, limit=limit)
    normalized = build_handoff_input_from_units(
        units=units,
        source_label=source_label,
        recipient_profile=recipient_profile,
        mode=mode,
        notes=notes,
    )
    report = build_handoff_report_from_chat_json(normalized)
    if mode == "protected_disclosure_envelope":
        version = PROTECTED_DISCLOSURE_ENVELOPE_VERSION
        summary = render_protected_disclosure_summary(report)
        primary_count = int(report["integrity"]["sealed_item_count"])
    else:
        version = PERSONAL_HANDOFF_REPORT_VERSION
        summary = render_personal_handoff_summary(report)
        primary_count = int(report["recipient_export"]["exported_item_count"])
    normalized_path = output_dir / "normalized_input.json"
    report_path = output_dir / f"{version}.json"
    summary_path = output_dir / f"{version}.summary.md"
    normalized_path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(summary, encoding="utf-8")
    return {
        "mode": mode,
        "version": version,
        "export_path": str(export_path),
        "normalized_input_path": str(normalized_path),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "recipient_profile": str(report["run"]["recipient_profile"]),
        "primary_count": primary_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a personal handoff or protected disclosure artifact from Messenger/Facebook export JSON.")
    parser.add_argument("--export-path", required=True, help="Path to a message_1.json file or a directory containing Messenger export JSON files.")
    parser.add_argument("--recipient-profile", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--mode", choices=("personal_handoff", "protected_disclosure_envelope"), default="personal_handoff")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    payload = build_handoff_from_messenger_export_artifact(
        export_path=Path(args.export_path).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        recipient_profile=str(args.recipient_profile),
        source_label=str(args.source_label),
        mode=str(args.mode),
        limit=int(args.limit) if args.limit is not None else None,
        notes=str(args.notes) if args.notes else None,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
