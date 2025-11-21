import json
import subprocess

from src.nlp.taxonomy import Modality
from src.rules.extractor import extract_rules
from src.rules.reasoner import check_rules


def run_cli(*args: str) -> str:
    cmd = ["python", "-m", "cli", *args]
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
    assert rules[0].modality == Modality.MUST.value
    assert rules[1].modality == Modality.MUST_NOT.value
    issues = check_rules(rules)
    assert any("Contradiction" in i for i in issues)
    assert any("Delegation breach" in i for i in issues)


def test_cli_extract_and_check():
    text = "The operator must file reports. The operator must not file reports."
    out = run_cli("extract", "--text", text)
    rules = json.loads(out)
    assert len(rules) == 2
    assert rules[0]["modality"] == Modality.MUST.value
    out2 = run_cli("check", "--rules", json.dumps(rules))
    issues = json.loads(out2)
    assert any("Contradiction" in i for i in issues)


def test_shall_not_detection():
    text = "The driver shall not park here. The driver shall park here."
    rules = extract_rules(text)
    assert len(rules) == 2
    assert rules[0].modality == Modality.SHALL_NOT.value
    issues = check_rules(rules)
    assert any("Contradiction" in i for i in issues)


def test_extract_rules_preserves_parenthetical_citations():
    text = "The judge must refer to some of the facts (R. v. Sidlow (1))."
    rules = extract_rules(text)
    assert len(rules) == 1
    assert rules[0].action == "refer to some of the facts (R. v. Sidlow (1))"
