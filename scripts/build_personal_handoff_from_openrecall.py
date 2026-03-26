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
from src.reporting.openrecall_import import load_openrecall_units  # noqa: E402


def build_handoff_from_openrecall_artifact(
    *,
    itir_db_path: Path,
    output_dir: Path,
    recipient_profile: str,
    source_label: str,
    mode: str,
    import_run_id: str | None = None,
    date: str | None = None,
    limit: int | None = None,
    notes: str | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    units = load_openrecall_units(itir_db_path, import_run_id=import_run_id, date=date, limit=limit)
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
        "itir_db_path": str(itir_db_path),
        "normalized_input_path": str(normalized_path),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "recipient_profile": str(report["run"]["recipient_profile"]),
        "primary_count": primary_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a personal handoff or protected disclosure artifact from imported OpenRecall captures.")
    parser.add_argument("--itir-db-path", required=True)
    parser.add_argument("--recipient-profile", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--mode", choices=("personal_handoff", "protected_disclosure_envelope"), default="personal_handoff")
    parser.add_argument("--import-run-id", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    payload = build_handoff_from_openrecall_artifact(
        itir_db_path=Path(args.itir_db_path).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        recipient_profile=str(args.recipient_profile),
        source_label=str(args.source_label),
        mode=str(args.mode),
        import_run_id=str(args.import_run_id) if args.import_run_id else None,
        date=str(args.date) if args.date else None,
        limit=int(args.limit) if args.limit is not None else None,
        notes=str(args.notes) if args.notes else None,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
