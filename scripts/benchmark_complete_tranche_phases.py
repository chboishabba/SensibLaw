#!/usr/bin/env python3
"""Run one complete tranche while durably timing every phase receipt."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from time import monotonic_ns, time_ns
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.complete_tranche_phase_timing import CompleteTranchePhaseTimer


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
    args, passthrough = parser.parse_known_args()
    return args, passthrough


def _load_runner():
    path = ROOT / "scripts/run_complete_tranche.py"
    spec = importlib.util.spec_from_file_location("_sensiblaw_timed_complete_tranche", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load complete tranche runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    args, passthrough = _parse_args()
    output_root = args.output_root.resolve()
    timing_path = (
        output_root
        / args.tranche.lower()
        / "complete_tranche_phase_timings.json"
    )
    timer = CompleteTranchePhaseTimer()
    timer.prime(None, epoch_ns=time_ns(), monotonic_ns=monotonic_ns())
    runner = _load_runner()
    original_phase_receipt = runner.PhaseReceipt
    original_load_checkpoint = runner._load_phase_checkpoint
    suppress_observation = False

    def persist(returncode: int | None) -> None:
        _write(
            timing_path,
            timer.report(tranche=args.tranche, process_returncode=returncode),
        )

    class TimedPhaseReceipt(original_phase_receipt):
        """Drop-in PhaseReceipt that observes completion but not receipt identity."""

        def __init__(self, phase, state, input_refs, output_refs, detail):
            super().__init__(phase, state, input_refs, output_refs, detail)
            if suppress_observation:
                return
            synthetic_state = {
                "last_phase": phase.name,
                "last_receipt_ref": self.receipt_ref,
                "phases": {
                    phase.name: {
                        "phase_ref": phase.phase_ref,
                        "state": state,
                        "detail": dict(detail),
                    }
                },
            }
            timer.observe(
                synthetic_state,
                epoch_ns=time_ns(),
                monotonic_ns=monotonic_ns(),
            )
            persist(None)

    def load_checkpoint_without_charging_reuse(*load_args, **load_kwargs):
        nonlocal suppress_observation
        previous = suppress_observation
        suppress_observation = True
        try:
            return original_load_checkpoint(*load_args, **load_kwargs)
        finally:
            suppress_observation = previous

    runner.PhaseReceipt = TimedPhaseReceipt
    runner._load_phase_checkpoint = load_checkpoint_without_charging_reuse

    saved_argv = sys.argv
    returncode = 1
    try:
        sys.argv = [
            str(ROOT / "scripts/run_complete_tranche.py"),
            "--tranche",
            args.tranche,
            "--output-root",
            str(output_root),
            *passthrough,
        ]
        returncode = int(runner.main())
        return returncode
    finally:
        sys.argv = saved_argv
        persist(returncode)
        print(
            json.dumps(
                timer.report(tranche=args.tranche, process_returncode=returncode),
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
