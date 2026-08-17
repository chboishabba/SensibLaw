#!/usr/bin/env python3
"""Run one complete tranche while durably timing its phase checkpoints."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from time import monotonic_ns, sleep, time_ns
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.complete_tranche_phase_timing import CompleteTranchePhaseTimer


def _read_state(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    temp.replace(path)
    parent_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tranche", required=True, choices=("GWB", "AU", "BREXIT"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--poll-ms", type=int, default=100)
    args, passthrough = parser.parse_known_args()
    if args.poll_ms < 10:
        parser.error("--poll-ms must be >= 10")
    return args, passthrough


def main() -> int:
    args, passthrough = _parse_args()
    output_root = args.output_root.resolve()
    tranche_root = output_root / args.tranche.lower()
    state_path = tranche_root / "tranche_run_state.json"
    timing_path = tranche_root / "complete_tranche_phase_timings.json"

    timer = CompleteTranchePhaseTimer()
    timer.prime(
        _read_state(state_path), epoch_ns=time_ns(), monotonic_ns=monotonic_ns()
    )
    command = [
        sys.executable,
        str(ROOT / "scripts/run_complete_tranche.py"),
        "--tranche",
        args.tranche,
        "--output-root",
        str(output_root),
        *passthrough,
    ]
    process = subprocess.Popen(command, cwd=ROOT)
    returncode: int | None = None
    try:
        while returncode is None:
            state = _read_state(state_path)
            if state is not None:
                changed = timer.observe(
                    state, epoch_ns=time_ns(), monotonic_ns=monotonic_ns()
                )
                if changed is not None:
                    _write(
                        timing_path,
                        timer.report(tranche=args.tranche, process_returncode=None),
                    )
            returncode = process.poll()
            if returncode is None:
                sleep(args.poll_ms / 1000)
    finally:
        if returncode is None:
            returncode = process.wait()
        state = _read_state(state_path)
        if state is not None:
            timer.observe(state, epoch_ns=time_ns(), monotonic_ns=monotonic_ns())
        _write(
            timing_path,
            timer.report(tranche=args.tranche, process_returncode=returncode),
        )

    report = timer.report(tranche=args.tranche, process_returncode=returncode)
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(returncode)


if __name__ == "__main__":
    raise SystemExit(main())
