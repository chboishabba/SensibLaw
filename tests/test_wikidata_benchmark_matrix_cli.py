from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wikidata_benchmark_matrix_cli_defaults_cache_only() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "cli", "wikidata", "benchmark-matrix", "--lane", "projection"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["network_mode"] == "cache-only"
    assert payload["lanes"][0]["lane"] == "projection"
