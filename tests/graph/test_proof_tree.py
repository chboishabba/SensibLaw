import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.graph.proof_tree import (
    ProofTree,
    Provenance,
    ResultNode,
    ResultTable,
)


def _build_sample_table() -> ResultTable:
    """Construct a sample ResultTable for testing."""

    f0 = ResultNode(id="F0", label="Root", satisfied=True, children=["F1", "F2"])
    f1 = ResultNode(
        id="F1",
        label="Child 1",
        satisfied=True,
        children=["F3"],
        provenance=Provenance(case="Case A", paragraph="1"),
    )
    f2 = ResultNode(id="F2", label="Child 2", satisfied=False)
    f3 = ResultNode(
        id="F3",
        label="Grandchild",
        satisfied=True,
        provenance=Provenance(statute="Statute B", section="10"),
    )
    results = {n.id: n for n in [f0, f1, f2, f3]}
    return ResultTable(results=results, root_id="F0")


def test_builds_only_satisfied_factors():
    table = _build_sample_table()
    tree = ProofTree.from_result_table(table)

    assert set(tree.nodes) == {"F0", "F1", "F3"}
    edges = sorted((e.source, e.target) for e in tree.edges)
    assert edges == [("F0", "F1"), ("F1", "F3")]

    edge_map = {(e.source, e.target): e for e in tree.edges}
    edge1 = edge_map[("F0", "F1")]
    edge2 = edge_map[("F1", "F3")]
    assert edge1.provenance.case == "Case A"
    assert edge1.provenance.paragraph == "1"
    assert edge2.provenance.statute == "Statute B"
    assert edge2.provenance.section == "10"


def test_export_formats():
    table = _build_sample_table()
    tree = ProofTree.from_result_table(table)

    dot = tree.to_dot()
    assert "Case A" in dot
    assert "Statute B" in dot

    data = tree.to_json()
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2
    # ensure JSON serialisable
    json.dumps(data)
