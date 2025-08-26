"""Tests for text similarity helpers exposed via the receipts CLI."""

import subprocess
from pathlib import Path


def run_diff(old: Path, new: Path) -> subprocess.CompletedProcess:
    cmd = ["python", "-m", "src.cli", "receipts", "diff", "--old", str(old), "--new", str(new)]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_cosmetic_change(tmp_path: Path):
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    old.write_text("Hello world\n")
    new.write_text("Hello   world\n")
    completed = run_diff(old, new)
    assert completed.stdout.strip() == "cosmetic"


def test_substantive_change(tmp_path: Path):
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    old.write_text("Hello world\n")
    new.write_text("Goodbye world\n")
    completed = run_diff(old, new)
    assert completed.stdout.strip() == "substantive"
