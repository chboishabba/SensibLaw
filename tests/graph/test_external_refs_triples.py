import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph.inference import legal_graph_to_triples
from src.graph.models import LegalGraph, Node, NodeType


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


def test_graph_triples_roundtrip_au_branch_external_refs():
    graph = LegalGraph(
        nodes={
            "concept:au_case_mabo": Node(
                identifier="concept:au_case_mabo",
                type=NodeType.CONCEPT,
                metadata={"external_refs": [{"provider": "wikidata", "external_id": "Q6729646"}]},
            ),
            "concept:au_juris_commonwealth": Node(
                identifier="concept:au_juris_commonwealth",
                type=NodeType.CONCEPT,
                metadata={
                    "external_refs": [
                        {"provider": "wikidata", "external_id": "Q408"},
                        {"provider": "dbpedia", "external_id": "http://dbpedia.org/resource/Australia"},
                    ]
                },
            ),
            "actor:hca": Node(
                identifier="actor:hca",
                type=NodeType.PERSON,
                metadata={
                    "external_refs": [
                        {"provider": "wikidata", "external_id": "Q16903290"},
                        {"provider": "dbpedia", "external_id": "http://dbpedia.org/resource/High_Court_of_Australia"},
                    ]
                },
            ),
        },
        edges=[],
    )

    pack = legal_graph_to_triples(graph, include_external_refs=True)
    assert ("concept:au_case_mabo", "owl:sameAs", "wikidata:Q6729646") in pack.triples
    assert ("concept:au_case_mabo", "skos:exactMatch", "wikidata:Q6729646") in pack.triples
    assert ("concept:au_juris_commonwealth", "owl:sameAs", "http://dbpedia.org/resource/Australia") in pack.triples
    assert ("concept:au_juris_commonwealth", "skos:exactMatch", "wikidata:Q408") in pack.triples
    assert ("actor:hca", "owl:sameAs", "http://dbpedia.org/resource/High_Court_of_Australia") in pack.triples


def test_graph_triples_roundtrip_nsw_branch_external_refs():
    graph = LegalGraph(
        nodes={
            "concept:au_case_house": Node(
                identifier="concept:au_case_house",
                type=NodeType.CONCEPT,
                metadata={
                    "external_refs": [
                        {
                            "provider": "austlii",
                            "external_id": "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/cth/HCA/1936/40.html",
                        }
                    ]
                },
            ),
            "concept:au_case_lepore": Node(
                identifier="concept:au_case_lepore",
                type=NodeType.CONCEPT,
                metadata={
                    "external_refs": [
                        {
                            "provider": "hcourt_au",
                            "external_id": "https://www.hcourt.gov.au/cases-and-judgments/judgments/judgments-2000-current/new-south-wales-v-lepore",
                        }
                    ]
                },
            ),
            "concept:au_act_cla": Node(
                identifier="concept:au_act_cla",
                type=NodeType.CONCEPT,
                metadata={
                    "external_refs": [
                        {
                            "provider": "nsw_legislation",
                            "external_id": "https://legislation.nsw.gov.au/view/html/inforce/current/act-2002-022",
                        }
                    ]
                },
            ),
        },
        edges=[],
    )

    pack = legal_graph_to_triples(graph, include_external_refs=True)
    assert (
        "concept:au_case_house",
        "owl:sameAs",
        "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/cth/HCA/1936/40.html",
    ) in pack.triples
    assert (
        "concept:au_case_lepore",
        "skos:exactMatch",
        "https://www.hcourt.gov.au/cases-and-judgments/judgments/judgments-2000-current/new-south-wales-v-lepore",
    ) in pack.triples
    assert (
        "concept:au_act_cla",
        "owl:sameAs",
        "https://legislation.nsw.gov.au/view/html/inforce/current/act-2002-022",
    ) in pack.triples
