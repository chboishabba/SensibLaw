import json
import subprocess
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_proof_tree_cli(tmp_path):
    graph = {
        "nodes": [
            {"id": "A", "type": "document", "date": "2020-01-01"},
            {"id": "B", "type": "document", "date": "2019-01-01"},
            {"id": "C", "type": "document", "date": "2018-01-01"},
        ],
        "edges": [
            {
                "source": "A",
                "target": "B",
                "type": "proposed_by",
                "date": "2019-01-01",
            },
            {
                "source": "B",
                "target": "C",
                "type": "explains",
                "date": "2018-01-01",
            },
        ],
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph))
    cmd = [
        "python",
        "-m",
        "src.cli",
        "proof-tree",
        "--graph",
        str(path),
        "--seed",
        "A",
        "--hops",
        "2",
        "--as-at",
        "2021-01-01",
        "--dot",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = completed.stdout.strip()
    assert "digraph proof_tree" in out
    assert "A" in out and "B" in out and "C" in out
