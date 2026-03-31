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

from src.fact_intake.google_public_import import load_google_public_units, parse_google_public_url  # noqa: E402
from src.fact_intake.handoff_artifacts import write_handoff_artifact  # noqa: E402
from src.fact_intake.personal_chat_import import build_handoff_input_from_units, build_handoff_report_from_chat_json  # noqa: E402


def build_handoff_from_google_public_artifact(
    *,
    url: str,
    output_dir: Path,
    recipient_profile: str,
    source_label: str,
    mode: str,
    limit: int | None = None,
    notes: str | None = None,
) -> dict[str, object]:
    units = load_google_public_units(url)
    if limit is not None:
        units = units[: int(limit)]
    normalized = build_handoff_input_from_units(
        units=units,
        source_label=source_label,
        recipient_profile=recipient_profile,
        mode=mode,
        notes=notes,
    )
    report = build_handoff_report_from_chat_json(normalized)
    parsed = parse_google_public_url(url)
    return write_handoff_artifact(
        output_dir=output_dir,
        normalized=normalized,
        report=report,
        mode=mode,
        extra_metadata={"google_kind": parsed["kind"], "url": url},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a personal handoff or protected disclosure artifact from a public Google Doc/Sheet URL.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--recipient-profile", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--mode", choices=("personal_handoff", "protected_disclosure_envelope"), default="personal_handoff")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    payload = build_handoff_from_google_public_artifact(
        url=str(args.url),
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
