import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.dispatcher import SourceDispatcher


def test_dispatch_populates_graph_with_records():
    config = ROOT / "data" / "foundation_sources.json"
    dispatcher = SourceDispatcher(config)
    record = {
        "metadata": {
            "jurisdiction": "Australia",
            "citation": "CaseX",
            "date": "2023-01-01",
        },
        "body": "body text",
        "cited_authorities": ["CaseY"],
    }

    dispatcher.dispatch(names=["AustLII (reference only)"], records=[record])

    prov_id = "CaseX:p0"
    g = dispatcher.graph
    assert "CaseX" in g.nodes
    assert prov_id in g.nodes
    assert any(
        e.source == "CaseX" and e.target == prov_id and e.type == "INTERPRETS"
        for e in g.edges
    )
    assert any(
        e.source == "CaseX" and e.target == "CaseY" and e.type == "CITES"
        for e in g.edges
    )
