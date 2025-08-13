import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph import GraphNode, LegalGraph, NodeType, ingest_extrinsic


def test_extrinsic_weighting():
    graph = LegalGraph()
    bill = GraphNode(type=NodeType.DOCUMENT, identifier="bill-1")
    graph.add_node(bill)

    ingest_extrinsic(
        graph,
        identifier="speech-minister",
        role="Minister",
        stage="2nd reading",
        target=bill.identifier,
    )
    ingest_extrinsic(
        graph,
        identifier="speech-backbencher",
        role="Backbencher",
        stage="2nd reading",
        target=bill.identifier,
    )

    minister_edge = graph.find_edges(source="speech-minister")[0]
    backbencher_edge = graph.find_edges(source="speech-backbencher")[0]
    assert minister_edge.weight > backbencher_edge.weight

    heavy_edges = graph.find_edges(min_weight=2.0)
    assert all(e.weight >= 2.0 for e in heavy_edges)
