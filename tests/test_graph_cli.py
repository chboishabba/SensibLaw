import json
import json
import subprocess
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))


def run_cli(*args: str) -> str:
    cmd = ["python", "-m", "src.cli", *args]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def test_graph_query_type():
    graph_path = Path(__file__).resolve().parent / "graph" / "sample_graph.json"
    out = run_cli("graph", "query", "--graph", str(graph_path), "--type", "case")
    data = json.loads(out)
    assert {n["id"] for n in data["nodes"]} == {"1", "3"}


def test_graph_query_traverse():
    graph_path = Path(__file__).resolve().parent / "graph" / "sample_graph.json"
    out = run_cli(
        "graph",
        "query",
        "--graph",
        str(graph_path),
        "--start",
        "1",
        "--depth",
        "2",
    )
    data = json.loads(out)
    assert len(data["edges"]) == 2
    assert {n["id"] for n in data["nodes"]} == {"1", "2", "3"}
