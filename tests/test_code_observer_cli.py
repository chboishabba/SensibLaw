from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter")
pytest.importorskip("tree_sitter_python")

ROOT = Path(__file__).resolve().parents[1]


def test_code_observer_cli_observe_outputs_jsonl(tmp_path: Path) -> None:
    (tmp_path / "example.py").write_text("def main():\n    print('ok')\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "cli", "code-observer", "observe", "--root", str(tmp_path), "--include-glob", "**/*.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    rows = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert rows
    assert rows[0]["schema"] == "code_observation_v1"
    assert rows[0]["commit"]


def test_code_observer_cli_observe_writes_output_file(tmp_path: Path) -> None:
    root = tmp_path / "scan"
    root.mkdir()
    output = tmp_path / "out" / "observations.jsonl"
    (root / "example.py").write_text("def main():\n    print('ok')\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "code-observer",
            "observe",
            "--root",
            str(root),
            "--include-glob",
            "**/*.py",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert proc.stdout == ""
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    assert rows[0]["schema"] == "code_observation_v1"
