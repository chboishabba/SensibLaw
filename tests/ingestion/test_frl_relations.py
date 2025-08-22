from src.ingestion.frl import fetch_acts


def test_fetch_acts_extracts_definitions_and_citations():
    data = {
        "results": [
            {
                "id": "Act1",
                "title": "Sample Act",
                "sections": [
                    {
                        "number": "1",
                        "title": "Definitions",
                        "body": '"Dog" means a domesticated animal.',
                    },
                    {
                        "number": "2",
                        "title": "Care",
                        "body": "A person must care for their dog. See section 1.",
                    },
                ],
            }
        ]
    }

    nodes, edges = fetch_acts("http://example", data=data)

    defines_edges = [e for e in edges if e["type"] == "defines"]
    cites_edges = [e for e in edges if e["type"] == "cites"]

    assert {"from": "Act1:1", "to": "Act1:2", "type": "defines", "text": "dog"} in defines_edges
    assert {"from": "Act1:2", "to": "Act1:1", "type": "cites", "text": "section 1"} in cites_edges
