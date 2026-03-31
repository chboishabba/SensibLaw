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

from src.fact_intake.personal_chat_import import build_handoff_input_from_chat_json, build_handoff_report_from_chat_json  # noqa: E402
from src.fact_intake.handoff_artifacts import write_handoff_artifact  # noqa: E402


def build_handoff_from_chat_artifact(input_json_path: Path, output_dir: Path) -> dict[str, object]:
    input_payload = json.loads(input_json_path.read_text(encoding="utf-8"))
    normalized = build_handoff_input_from_chat_json(input_payload)
    report = build_handoff_report_from_chat_json(input_payload)
    mode = str(input_payload.get("mode") or "personal_handoff").strip()
    return write_handoff_artifact(
        output_dir=output_dir,
        normalized=normalized,
        report=report,
        mode=mode,
        extra_metadata={"input_json_path": str(input_json_path)},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a personal handoff or protected disclosure artifact from bounded chat/day JSON.")
    parser.add_argument("--input-json", required=True, help="JSON file describing chat/day messages and handoff mode.")
    parser.add_argument("--output-dir", required=True, help="Directory to write normalized input and report artifacts.")
    args = parser.parse_args(argv)
    payload = build_handoff_from_chat_artifact(Path(args.input_json).resolve(), Path(args.output_dir).resolve())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
