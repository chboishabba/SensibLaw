import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.frl import fetch_acts


def test_fetch_acts_creates_graph():
    payload = {
        "results": [
            {
                "id": "NTA1993",
                "title": "Native Title Act 1993",
                "sections": [
                    {"number": "223", "title": "Definition of native title"}
                ],
            }
        ]
    }
    nodes, edges = fetch_acts("http://example.com", data=payload)
    assert nodes == [
        {
            "id": "NTA1993",
            "type": "act",
            "title": "Native Title Act 1993",
            "point_in_time": None,
        },
        {
            "id": "NTA1993:223",
            "type": "section",
            "number": "223",
            "title": "Definition of native title",
        },
    ]
    assert edges == [
        {"from": "NTA1993", "to": "NTA1993:223", "type": "has_section"}
    ]

