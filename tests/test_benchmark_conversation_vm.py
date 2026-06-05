from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_conversation_vm_fixture_modes_emit_stage_metrics() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/benchmark_conversation_vm.py",
            "--fixture-mode",
            "conflict_density",
            "--iterations",
            "1",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["schema"] == "sensiblaw.conversation_vm.benchmark.v0_1"
    assert payload["fixture_mode"] == "conflict_density"
    stages = {row["stage"] for row in payload["stage_metrics"]}
    assert {"segmentation", "projection", "join", "cross_residual_derivation"} <= stages
    assert payload["state_metadata"]["contested_count"] > 0
