#!/usr/bin/env python3
"""Inspect constraint fixed-point diagnostics from a compilation JSON artefact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.policy.constraint_fixed_point_diagnostics import (  # noqa: E402
    build_diagnostics_from_artifacts,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Compilation or artefact JSON file")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def main() -> int:
    args = _parse_args()
    payload = _mapping(json.loads(args.input.read_text(encoding="utf-8")), "input")
    artifacts = payload.get("artifacts")
    if artifacts is None and isinstance(payload.get("compilation"), Mapping):
        artifacts = payload["compilation"].get("artifacts")
    if artifacts is None:
        artifacts = payload
    receipt = build_diagnostics_from_artifacts(
        _mapping(artifacts, "compilation artifacts")
    ).to_dict()
    rendered = json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
