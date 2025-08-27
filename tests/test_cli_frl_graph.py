import json
import subprocess
import sys
from pathlib import Path


def test_extract_frl_to_graph(tmp_path: Path) -> None:
    payload = {
        "results": [
            {
                "id": "NTA1993",
                "title": "Native Title Act 1993",
                "sections": [
                    {"number": "223", "title": "Definition of native title"}
                ],
            }
        ]
    }
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps(payload))

    extract_cmd = [
        sys.executable,
        "-m",
        "cli",
        "extract",
        "frl",
        "--data",
        str(payload_file),
    ]
    extract = subprocess.run(extract_cmd, capture_output=True, text=True, check=True)

    graph_cmd = [
        sys.executable,
        "-m",
        "cli",
        "graph",
        "subgraph",
        "--node",
        "NTA1993",
        "--graph-file",
        "-",
    ]
    graph = subprocess.run(
        graph_cmd, input=extract.stdout, capture_output=True, text=True, check=True
    )
    assert "digraph G" in graph.stdout

