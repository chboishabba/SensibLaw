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

from src.fact_intake.handoff_artifacts import write_handoff_artifact  # noqa: E402
from src.fact_intake.personal_chat_import import build_handoff_input_from_units, build_handoff_report_from_chat_json  # noqa: E402
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
    units = load_openrecall_units(itir_db_path, import_run_id=import_run_id, date=date, limit=limit)
    normalized = build_handoff_input_from_units(
        units=units,
        source_label=source_label,
        recipient_profile=recipient_profile,
        mode=mode,
        notes=notes,
    )
    report = build_handoff_report_from_chat_json(normalized)
    return write_handoff_artifact(
        output_dir=output_dir,
        normalized=normalized,
        report=report,
        mode=mode,
        extra_metadata={"itir_db_path": str(itir_db_path)},
    )


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
