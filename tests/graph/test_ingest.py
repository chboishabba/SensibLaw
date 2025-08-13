import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.models.document import Document, DocumentMetadata
from src.models.provision import Provision
from src.graph.ingest import Graph, ingest_document


def test_ingest_document_builds_nodes_and_edges():
    meta = DocumentMetadata(
        jurisdiction="Australia", citation="CaseA", date=date(2020, 1, 1)
    )
    provision = Provision(text="s 1", identifier="p1")
    doc = Document(metadata=meta, body="body text", provisions=[provision])
    doc.cited_authorities = ["CaseB"]

    g = Graph()
    ingest_document(doc, g)

    assert "CaseA" in g.nodes
    assert "p1" in g.nodes
    assert any(
        e.source == "CaseA" and e.target == "p1" and e.type == "INTERPRETS"
        for e in g.edges
    )
    assert any(
        e.source == "CaseA" and e.target == "CaseB" and e.type == "CITES"
        for e in g.edges
    )
