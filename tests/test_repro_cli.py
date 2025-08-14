import json
import os
import subprocess
from pathlib import Path


def run_repro(tmp_path: Path, *args: str) -> str:
    env = os.environ.copy()
    ledger = tmp_path / "ledger.csv"
    env["SENSIBLAW_CORRECTIONS_FILE"] = str(ledger)
    env["USER"] = "tester"
    cmd = ["python", "-m", "src.cli", "repro", *args]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
    return completed.stdout.strip()


def test_log_and_list(tmp_path: Path):
    issue = tmp_path / "issue.txt"
    issue.write_text("Something is wrong")
    out = run_repro(tmp_path, "log-correction", "--file", str(issue))
    data = json.loads(out)
    assert data["description"] == "Something is wrong"
    assert data["author"] == "tester"
    out2 = run_repro(tmp_path, "list-corrections")
    entries = json.loads(out2)
    assert len(entries) == 1
    assert entries[0]["description"] == "Something is wrong"
