import json
import subprocess
import json
import subprocess


def run_cli(*args: str) -> str:
    cmd = ["python", "-m", "src.cli", *args]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def test_cli_subgraph_json():
    out = run_cli("graph", "subgraph", "--node", "doc1", "--node", "doc2")
    data = json.loads(out)
    assert len(data["nodes"]) == 2
    assert any(e["target"] == "doc2" for e in data["edges"])


def test_cli_subgraph_dot():
    out = run_cli("graph", "subgraph", "--node", "doc1", "--node", "doc2", "--dot")
    assert "digraph" in out and "doc1" in out


def test_cli_treatment():
    out = run_cli("treatment", "--doc", "doc1")
    data = json.loads(out)
    assert any(e["target"] == "doc2" for e in data)


def test_cli_provision():
    out = run_cli("provision", "--doc", "doc1", "--id", "prov1")
    data = json.loads(out)
    assert data["identifier"] == "prov1"
