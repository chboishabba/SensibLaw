#!/usr/bin/env python3
"""Run a strict command only until a genuine sentence-close prefix commits.

This wrapper leaves the canonical strict acceptance runner fail-closed.  It sets
opt-in prefix/EXPLAIN controls, launches the supplied command, and recognizes a
run as a successful *diagnostic* only when the child emitted the fsynced
post-commit prefix receipt.  The child is expected to exit non-zero because the
typed diagnostic-complete signal deliberately interrupts normal full-document
completion.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.numeric_prefix_close_diagnostic import (  # noqa: E402
    PREFIX_CLOSE_DIAGNOSTIC_REF,
    STOP_AFTER_ENV,
    STOP_OUTPUT_ENV,
)


def _parse_ordinals(raw: str, *, stop_after: int) -> tuple[int, ...]:
    values = tuple(
        sorted({int(token.strip()) for token in raw.split(",") if token.strip()})
    )
    if not values or any(value < 1 for value in values):
        raise ValueError("--explain-ordinals must contain positive integers")
    if values[-1] > stop_after:
        raise ValueError("EXPLAIN ordinal cannot exceed --stop-after")
    return values


def _parse_explain_request(
    raw_ordinals: str | None,
    output: Path | None,
    *,
    stop_after: int,
) -> tuple[int, ...] | None:
    """Require both live-EXPLAIN controls, or neither for an undistorted profile."""

    if raw_ordinals is None and output is None:
        return None
    if raw_ordinals is None or output is None:
        raise ValueError(
            "--explain-ordinals and --explain-output must be supplied together"
        )
    return _parse_ordinals(raw_ordinals, stop_after=stop_after)


def _load_last_prefix_receipt(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records[-1] if records else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop-after", type=int, required=True)
    parser.add_argument("--explain-ordinals")
    parser.add_argument("--prefix-output", type=Path, required=True)
    parser.add_argument("--explain-output", type=Path)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to launch after --, normally run_strict_tranche_acceptance.py.",
    )
    args = parser.parse_args()

    if args.stop_after < 1:
        parser.error("--stop-after must be positive")
    try:
        ordinals = _parse_explain_request(
            args.explain_ordinals,
            args.explain_output,
            stop_after=args.stop_after,
        )
    except ValueError as error:
        parser.error(str(error))
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a child command is required after --")

    args.prefix_output.parent.mkdir(parents=True, exist_ok=True)
    if args.explain_output is not None:
        args.explain_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    output_paths = (args.prefix_output, args.explain_output)
    for path in output_paths:
        if path is None:
            continue
        if path.exists():
            path.unlink()

    environment = os.environ.copy()
    environment[STOP_AFTER_ENV] = str(args.stop_after)
    environment[STOP_OUTPUT_ENV] = str(args.prefix_output)
    if ordinals is not None:
        environment["SENSIBLAW_REGION_CLOSE_EXPLAIN_ORDINALS"] = ",".join(
            str(value) for value in ordinals
        )
        environment["SENSIBLAW_REGION_CLOSE_EXPLAIN_OUTPUT"] = str(args.explain_output)

    completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    prefix = _load_last_prefix_receipt(args.prefix_output)
    diagnostic_complete = bool(
        prefix
        and prefix.get("contract_ref") == PREFIX_CLOSE_DIAGNOSTIC_REF
        and int(prefix.get("committed_sentence_closes", 0)) >= args.stop_after
    )
    summary = {
        "contract_ref": "sensiblaw.numeric-prefix-close-run.v0_1",
        "state": "diagnostic_complete" if diagnostic_complete else "failed",
        "child_returncode": completed.returncode,
        "stop_after_committed": args.stop_after,
        "explain_ordinals": list(ordinals or ()),
        "prefix_output": str(args.prefix_output),
        "explain_output": str(args.explain_output) if args.explain_output else None,
        "prefix_receipt": prefix,
        "semantics": (
            "success means the requested genuine sentence-close prefix committed; "
            "it is not a full semantic/performance acceptance result"
        ),
    }
    args.summary_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if diagnostic_complete else (completed.returncode or 1)


if __name__ == "__main__":
    raise SystemExit(main())
