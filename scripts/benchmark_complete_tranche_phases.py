#!/usr/bin/env python3
"""Run one complete tranche while durably timing every phase receipt.

The timing harness is a production-performance entrypoint.  It therefore runs
the strict numeric PostgreSQL path by default even though the historical tranche
runner retains an explicit compatibility mode for parity/migration work.
Compatibility replay must be requested here with ``--compatibility-replay``.

In addition to outer phase receipts, the runner's detailed ``PhaseRecorder`` is
replaced with a failure-surviving recorder.  Every stage transition, observation
and heartbeat is atomically fsynced while the compile is still running.  A later
compiler/receipt failure therefore cannot erase the substage history that led to
it.
"""

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
from src.runtime.durable_progress import DurablePhaseRecorder


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
    parser.add_argument(
        "--compatibility-replay",
        action="store_true",
        help=(
            "Explicitly benchmark the historical local-compatibility replay path. "
            "The default is strict numeric PostgreSQL production."
        ),
    )
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


def _runner_strategy_args(
    *, compatibility_replay: bool, passthrough: list[str]
) -> list[str]:
    """Return an explicit execution-mode argument for the underlying runner.

    ``run_complete_tranche.py`` predates the repository-wide PostgreSQL numeric
    production default and still interprets omission of ``--strict-exact`` as a
    compatibility request.  Never let that historical CLI default silently
    contaminate a production-performance measurement.
    """

    if compatibility_replay:
        if "--strict-exact" in passthrough:
            raise ValueError(
                "--compatibility-replay and --strict-exact are mutually exclusive"
            )
        return list(passthrough)
    if "--strict-exact" in passthrough:
        return list(passthrough)
    return ["--strict-exact", *passthrough]


def main() -> int:
    args, passthrough = _parse_args()
    runner_args = _runner_strategy_args(
        compatibility_replay=args.compatibility_replay,
        passthrough=passthrough,
    )
    output_root = args.output_root.resolve()
    tranche_root = output_root / args.tranche.lower()
    timing_path = tranche_root / "complete_tranche_phase_timings.json"
    detailed_progress_path = tranche_root / "local_pnf_compile_progress.json"
    timer = CompleteTranchePhaseTimer()
    timer.prime(None, epoch_ns=time_ns(), monotonic_ns=monotonic_ns())
    runner = _load_runner()
    original_phase_receipt = runner.PhaseReceipt
    original_phase_recorder = runner.PhaseRecorder
    original_load_checkpoint = runner._load_phase_checkpoint
    suppress_observation = False

    def persist(returncode: int | None) -> None:
        report = timer.report(tranche=args.tranche, process_returncode=returncode)
        report["execution_mode"] = (
            "local-compatibility-replay"
            if args.compatibility_replay
            else "strict-numeric-postgresql"
        )
        report["detailed_progress_path"] = str(detailed_progress_path)
        _write(timing_path, report)

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

    class TimedDurablePhaseRecorder(DurablePhaseRecorder):
        """Use the runner's normal recorder API with per-event durable writes."""

        def __init__(self, stream=None, json_lines: bool = False, **_kwargs: Any):
            super().__init__(
                durable_path=detailed_progress_path,
                stream=stream,
                json_lines=json_lines,
            )

    def load_checkpoint_without_charging_reuse(*load_args, **load_kwargs):
        nonlocal suppress_observation
        previous = suppress_observation
        suppress_observation = True
        try:
            return original_load_checkpoint(*load_args, **load_kwargs)
        finally:
            suppress_observation = previous

    runner.PhaseReceipt = TimedPhaseReceipt
    runner.PhaseRecorder = TimedDurablePhaseRecorder
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
            *runner_args,
        ]
        returncode = int(runner.main())
        return returncode
    finally:
        sys.argv = saved_argv
        runner.PhaseReceipt = original_phase_receipt
        runner.PhaseRecorder = original_phase_recorder
        runner._load_phase_checkpoint = original_load_checkpoint
        persist(returncode)
        report = timer.report(tranche=args.tranche, process_returncode=returncode)
        report["execution_mode"] = (
            "local-compatibility-replay"
            if args.compatibility_replay
            else "strict-numeric-postgresql"
        )
        report["detailed_progress_path"] = str(detailed_progress_path)
        print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
