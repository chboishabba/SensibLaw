from src.graph.principle_graph import build_principle_graph


def test_build_principle_graph_structure() -> None:
    provision = {
        "provision_id": "Provision#TEST",
        "title": "Test Provision",
        "atoms": [
            {
                "id": "atom-1",
                "role": "principle",
                "label": "Principle label",
                "proof": {"status": "proven", "confidence": 0.8, "evidenceCount": 3},
                "principle": {
                    "id": "principle-1",
                    "title": "Principle Title",
                    "summary": "Summary",
                    "tags": ["continuity"],
                    "authorities": [
                        {
                            "id": "Case#Example",
                            "title": "Example v Sample",
                            "relationship": "applies",
                            "pinpoint": "123",
                        }
                    ],
                },
                "children": [
                    {
                        "id": "fact-1",
                        "label": "Key fact",
                        "role": "fact",
                        "proof": {"status": "contested", "evidenceCount": 1},
                    }
                ],
            }
        ],
    }

    graph = build_principle_graph(provision)

    node_by_id = {node["id"]: node for node in graph["nodes"]}
    assert set(node_by_id) == {
        "Provision#TEST",
        "principle-1",
        "fact-1",
        "Case#Example",
    }

    principle_meta = node_by_id["principle-1"]["metadata"]
    assert principle_meta["summary"] == "Summary"
    assert principle_meta["status"] == "proven"
    assert principle_meta["confidence"] == 0.8
    assert principle_meta["evidence_count"] == 3

    fact_meta = node_by_id["fact-1"]["metadata"]
    assert fact_meta["role"].lower() == "fact"
    assert fact_meta["status"] == "contested"
    assert fact_meta["evidence_count"] == 1

    authority_meta = node_by_id["Case#Example"]["metadata"]
    assert authority_meta["relationship"] == "applies"
    assert authority_meta["pinpoint"] == "123"

    edges = {(edge["source"], edge["target"], edge["label"]) for edge in graph["edges"]}
    assert (
        "Provision#TEST",
        "principle-1",
        "principle",
    ) in edges
    assert ("principle-1", "fact-1", "fact") in edges
    assert ("principle-1", "Case#Example", "applies") in edges


def test_preserves_multiple_citations_to_same_authority() -> None:
    provision = {
        "provision_id": "Provision#TEST",
        "title": "Test Provision",
        "atoms": [
            {
                "id": "atom-1",
                "role": "principle",
                "principle": {
                    "id": "principle-1",
                    "authorities": [
                        {
                            "id": "Case#Example",
                            "relationship": "applies",
                            "pinpoint": "123",
                        },
                        {
                            "id": "Case#Example",
                            "relationship": "applies",
                            "pinpoint": "456",
                        },
                    ],
                },
            }
        ],
    }

    graph = build_principle_graph(provision)

    edges = [
        edge
        for edge in graph["edges"]
        if edge["source"] == "principle-1"
        and edge["target"] == "Case#Example"
        and edge["label"] == "applies"
    ]

    assert len(edges) == 2
    pinpoints = {edge["metadata"].get("pinpoint") for edge in edges}
    assert pinpoints == {"123", "456"}
