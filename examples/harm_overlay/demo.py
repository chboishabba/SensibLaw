"""Example generating a proof tree with harm overlay."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Ensure the src directory is importable when running from repository root
SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from graph.proof_tree import Graph, Node, Edge
from proofs.render import load_harm_index, to_dot_with_harm


def main() -> None:
    here = Path(__file__).resolve().parent
    harm_path = SRC_DIR.parent / "data" / "harm_index.yaml"
    harm_index = load_harm_index(harm_path)

    graph = Graph()
    graph.add_node(Node(id="claim", type="claim", metadata={"label": "Claim", "entity": "person"}))
    graph.add_node(Node(id="evidence", type="evidence", metadata={"label": "Evidence", "entity": "property"}))
    graph.add_edge(Edge(source="claim", target="evidence", type="supports"))

    dot = to_dot_with_harm(graph.nodes, graph.edges, harm_index)
    dot_path = here / "proof_tree.dot"
    dot_path.write_text(dot)

    try:
        subprocess.run(
            ["dot", "-Tpng", str(dot_path), "-o", str(here / "proof_tree.png")],
            check=True,
            cwd=here,
        )
    except FileNotFoundError:
        print("Graphviz 'dot' not found; skipping PNG generation.")
    print("Wrote", dot_path)


if __name__ == "__main__":
    main()
