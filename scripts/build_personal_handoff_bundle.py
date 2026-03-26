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

from src.fact_intake.personal_handoff_bundle import (  # noqa: E402
    PERSONAL_HANDOFF_REPORT_VERSION,
    build_personal_handoff_report,
    render_personal_handoff_summary,
)


def build_handoff_artifact(input_json_path: Path, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    input_payload = json.loads(input_json_path.read_text(encoding="utf-8"))
    report = build_personal_handoff_report(input_payload)
    summary = render_personal_handoff_summary(report)
    json_path = output_dir / f"{PERSONAL_HANDOFF_REPORT_VERSION}.json"
    summary_path = output_dir / f"{PERSONAL_HANDOFF_REPORT_VERSION}.summary.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(summary, encoding="utf-8")
    return {
        "version": PERSONAL_HANDOFF_REPORT_VERSION,
        "input_json_path": str(input_json_path),
        "report_path": str(json_path),
        "summary_path": str(summary_path),
        "fact_run_id": str(report["run"]["fact_run_id"]),
        "recipient_profile": str(report["run"]["recipient_profile"]),
        "exported_item_count": int(report["recipient_export"]["exported_item_count"]),
        "excluded_item_count": int(report["recipient_export"]["excluded_item_count"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a bounded personal day-to-escalation handoff report.")
    parser.add_argument("--input-json", required=True, help="JSON file describing personal entries, scopes, observations, and reviews.")
    parser.add_argument("--output-dir", required=True, help="Directory to write the handoff report into.")
    args = parser.parse_args(argv)
    payload = build_handoff_artifact(Path(args.input_json).resolve(), Path(args.output_dir).resolve())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
