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

from src.fact_intake.personal_chat_import import build_handoff_input_from_units, build_handoff_report_from_chat_json  # noqa: E402
from src.fact_intake.personal_handoff_bundle import PERSONAL_HANDOFF_REPORT_VERSION, render_personal_handoff_summary  # noqa: E402
from src.fact_intake.protected_disclosure_envelope import (  # noqa: E402
    PROTECTED_DISCLOSURE_ENVELOPE_VERSION,
    render_protected_disclosure_summary,
)
from src.reporting.structure_report import load_chat_units, load_messenger_units  # noqa: E402


def build_handoff_from_message_db_artifact(
    *,
    db_path: Path,
    source_kind: str,
    output_dir: Path,
    recipient_profile: str,
    source_label: str,
    mode: str,
    run_id: str | None = None,
    notes: str | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if source_kind == "chat":
        units = load_chat_units(db_path, run_id)
    elif source_kind == "messenger":
        units = load_messenger_units(db_path, run_id)
    else:
        raise ValueError(f"unsupported source_kind: {source_kind}")
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
        "source_kind": source_kind,
        "version": version,
        "db_path": str(db_path),
        "normalized_input_path": str(normalized_path),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "recipient_profile": str(report["run"]["recipient_profile"]),
        "primary_count": primary_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a personal handoff or protected disclosure artifact from chat_test_db or messenger_test_db.")
    parser.add_argument("--db-path", required=True, help="Path to chat_test_db or messenger_test_db sqlite file.")
    parser.add_argument("--source-kind", choices=("chat", "messenger"), required=True)
    parser.add_argument("--recipient-profile", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--mode", choices=("personal_handoff", "protected_disclosure_envelope"), default="personal_handoff")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    payload = build_handoff_from_message_db_artifact(
        db_path=Path(args.db_path).resolve(),
        source_kind=str(args.source_kind),
        output_dir=Path(args.output_dir).resolve(),
        recipient_profile=str(args.recipient_profile),
        source_label=str(args.source_label),
        mode=str(args.mode),
        run_id=str(args.run_id) if args.run_id else None,
        notes=str(args.notes) if args.notes else None,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
