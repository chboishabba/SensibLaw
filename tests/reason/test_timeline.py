import json
import json
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.reason.timeline import build_timeline


def _sample_graph():
    nodes = [
        {
            "id": "A",
            "title": "Case A",
            "date": "2020-01-01",
            "citation": "A v B [2020] HCA 1",
        },
        {
            "id": "B",
            "title": "Case B",
            "date": "2021-01-01",
            "citation": "B v C [2021] HCA 2",
        },
    ]
    edges = [
        {
            "from": "A",
            "to": "B",
            "type": "cites",
            "date": "2021-01-02",
            "citation": "A [2]",
        }
    ]
    return nodes, edges


def test_timeline_sorted_with_citations(tmp_path: Path) -> None:
    nodes, edges = _sample_graph()
    events = build_timeline(nodes, edges, "A")
    assert [e.date.isoformat() for e in events] == ["2020-01-01", "2021-01-02"]
    assert all(e.citation for e in events)

    graph = {"nodes": nodes, "edges": edges}
    gfile = tmp_path / "graph.json"
    gfile.write_text(json.dumps(graph))
    cmd = [
        sys.executable,
        "-m",
        "src.cli",
        "query",
        "timeline",
        "--case",
        "A",
        "--graph-file",
        str(gfile),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(completed.stdout)
    assert [e["date"] for e in data] == ["2020-01-01", "2021-01-02"]
    assert data[0]["citation"] == "A v B [2020] HCA 1"
    assert data[1]["citation"] == "A [2]"
