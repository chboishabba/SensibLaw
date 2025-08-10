import json
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.rules.extractor import extract_rules
from src.rules.reasoner import check_rules


def run_cli(*args: str) -> str:
    cmd = ["python", "-m", "src.cli", *args]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def test_extractor_and_reasoner():
    text = (
        "The operator must file reports when requested. "
        "The operator must not file reports. "
        "The manager may delegate inspections to the agent. "
        "The agent must not conduct inspections."
    )
    rules = extract_rules(text)
    assert len(rules) == 4
    issues = check_rules(rules)
    assert any("Contradiction" in i for i in issues)
    assert any("Delegation breach" in i for i in issues)


def test_cli_extract_and_check():
    text = "The operator must file reports. The operator must not file reports."
    out = run_cli("extract", "--text", text)
    rules = json.loads(out)
    assert len(rules) == 2
    out2 = run_cli("check", "--rules", json.dumps(rules))
    issues = json.loads(out2)
    assert any("Contradiction" in i for i in issues)


def test_shall_not_detection():
    text = "The driver shall not park here. The driver shall park here."
    rules = extract_rules(text)
    assert len(rules) == 2
    issues = check_rules(rules)
    assert any("Contradiction" in i for i in issues)
