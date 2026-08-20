#!/usr/bin/env python3
"""Run a strict command only until a genuine sentence-close prefix commits.

This wrapper leaves the canonical strict acceptance runner fail-closed. It sets
opt-in prefix and live-EXPLAIN controls, launches the supplied command, and
recognizes success only when the child emitted the fsynced post-commit prefix
receipt. Diagnostic completion is not full semantic/performance acceptance.
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


def _parse_ordinals(raw: str, *, label: str) -> tuple[int, ...]:
    values = tuple(sorted({int(token.strip()) for token in raw.split(",") if token.strip()}))
    if not values or any(value < 1 for value in values):
        raise ValueError(f"{label} must contain positive integers")
    return values


def _paired_request(
    raw_ordinals: str | None,
    output: Path | None,
    *,
    label: str,
) -> tuple[int, ...] | None:
    if raw_ordinals is None and output is None:
        return None
    if raw_ordinals is None or output is None:
        raise ValueError(f"{label} ordinals and output must be supplied together")
    return _parse_ordinals(raw_ordinals, label=label)


def _load_last_prefix_receipt(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
    return records[-1] if records else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop-after", type=int, required=True)
    parser.add_argument("--explain-ordinals", help="selected sentence-close ordinals")
    parser.add_argument("--explain-output", type=Path)
    parser.add_argument("--token-explain-ordinals", help="selected parser-token batch ordinals")
    parser.add_argument("--token-explain-output", type=Path)
    parser.add_argument("--prefix-output", type=Path, required=True)
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
        close_ordinals = _paired_request(
            args.explain_ordinals,
            args.explain_output,
            label="--explain",
        )
        token_ordinals = _paired_request(
            args.token_explain_ordinals,
            args.token_explain_output,
            label="--token-explain",
        )
    except ValueError as error:
        parser.error(str(error))
    if close_ordinals is not None and close_ordinals[-1] > args.stop_after:
        parser.error("sentence-close EXPLAIN ordinal cannot exceed --stop-after")

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a child command is required after --")

    output_paths = (
        args.prefix_output,
        args.explain_output,
        args.token_explain_output,
        args.summary_output,
    )
    for path in output_paths:
        if path is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path != args.summary_output:
            path.unlink()

    environment = os.environ.copy()
    environment[STOP_AFTER_ENV] = str(args.stop_after)
    environment[STOP_OUTPUT_ENV] = str(args.prefix_output)
    if close_ordinals is not None:
        environment["SENSIBLAW_REGION_CLOSE_EXPLAIN_ORDINALS"] = ",".join(
            str(value) for value in close_ordinals
        )
        environment["SENSIBLAW_REGION_CLOSE_EXPLAIN_OUTPUT"] = str(args.explain_output)
    if token_ordinals is not None:
        environment["SENSIBLAW_TOKEN_INSERT_EXPLAIN_ORDINALS"] = ",".join(
            str(value) for value in token_ordinals
        )
        environment["SENSIBLAW_TOKEN_INSERT_EXPLAIN_OUTPUT"] = str(
            args.token_explain_output
        )

    completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    prefix = _load_last_prefix_receipt(args.prefix_output)
    diagnostic_complete = bool(
        prefix
        and prefix.get("contract_ref") == PREFIX_CLOSE_DIAGNOSTIC_REF
        and int(prefix.get("committed_sentence_closes", 0)) >= args.stop_after
    )
    summary = {
        "contract_ref": "sensiblaw.numeric-prefix-close-run.v0_2",
        "state": "diagnostic_complete" if diagnostic_complete else "failed",
        "child_returncode": completed.returncode,
        "stop_after_committed": args.stop_after,
        "close_explain_ordinals": list(close_ordinals or ()),
        "close_explain_output": str(args.explain_output) if args.explain_output else None,
        "token_explain_ordinals": list(token_ordinals or ()),
        "token_explain_output": (
            str(args.token_explain_output) if args.token_explain_output else None
        ),
        "prefix_output": str(args.prefix_output),
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
