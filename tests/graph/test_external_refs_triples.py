import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph.inference import legal_graph_to_triples
from src.graph.models import EdgeType, LegalGraph, Node, NodeType


def test_graph_triples_preserve_dbpedia_uris():
    graph = LegalGraph(
        nodes={
            "concept:demo": Node(
                identifier="concept:demo",
                type=NodeType.CONCEPT,
                metadata={
                    "external_refs": [
                        {
                            "provider": "dbpedia",
                            "external_id": "http://dbpedia.org/resource/Westmead_Hospital",
                        }
                    ]
                },
            )
        },
        edges=[],
    )

    pack = legal_graph_to_triples(graph, include_external_refs=True)
    assert ("concept:demo", "owl:sameAs", "http://dbpedia.org/resource/Westmead_Hospital") in pack.triples
    assert ("concept:demo", "skos:exactMatch", "http://dbpedia.org/resource/Westmead_Hospital") in pack.triples


def test_graph_triples_canonicalize_wikidata_qids():
    graph = LegalGraph(
        nodes={
            "concept:demo": Node(
                identifier="concept:demo",
                type=NodeType.CONCEPT,
                metadata={"external_refs": [{"provider": "wikidata", "external_id": "Q42"}]},
            )
        },
        edges=[],
    )

    pack = legal_graph_to_triples(graph, include_external_refs=True)
    assert ("concept:demo", "owl:sameAs", "wikidata:Q42") in pack.triples
    assert ("concept:demo", "skos:exactMatch", "wikidata:Q42") in pack.triples

