#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = Path(__file__).resolve().parents[1]
if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.jmd_bridge import build_jmd_sl_bridge_artifacts  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a JMD runtime object into SensibLaw bridge payloads.")
    parser.add_argument("--runtime-object", type=Path, required=True)
    parser.add_argument("--ingest-output", type=Path)
    parser.add_argument("--overlay-output", type=Path)
    args = parser.parse_args(argv)

    runtime_object = json.loads(args.runtime_object.read_text(encoding="utf-8"))
    payloads = build_jmd_sl_bridge_artifacts(runtime_object)
    rendered_ingest = json.dumps(payloads["ingest"], indent=2, sort_keys=True) + "\n"
    rendered_overlay = json.dumps(payloads["overlay"], indent=2, sort_keys=True) + "\n"
    if args.ingest_output:
        args.ingest_output.write_text(rendered_ingest, encoding="utf-8")
    else:
        print(rendered_ingest, end="")
    if args.overlay_output:
        args.overlay_output.write_text(rendered_overlay, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
