import json
import subprocess
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.tests.evaluator import evaluate


def test_evaluate_basic():
    template = {"factors": [{"id": "F1"}, {"id": "F2"}]}
    facts = {"F1": ["ref1"]}
    table = evaluate(template, facts)
    assert table.to_json() == [
        {"factor": "F1", "status": True, "evidence": ["ref1"]},
        {"factor": "F2", "status": False, "evidence": []},
    ]


def test_cli_tests_run(tmp_path: Path):
    template = {"factors": [{"id": "A"}, {"id": "B"}]}
    facts = {"A": ["para1", "para2"]}
    template_path = tmp_path / "template.json"
    facts_path = tmp_path / "facts.json"
    template_path.write_text(json.dumps(template))
    facts_path.write_text(json.dumps(facts))

    cmd = [
        "python",
        "-m",
        "src.cli",
        "tests",
        "run",
        "--template",
        str(template_path),
        "--facts",
        str(facts_path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    assert data[0]["factor"] == "A"
    assert data[0]["status"] is True
    assert data[0]["evidence"] == ["para1", "para2"]
    assert data[1]["factor"] == "B"
    assert data[1]["status"] is False
    assert data[1]["evidence"] == []
