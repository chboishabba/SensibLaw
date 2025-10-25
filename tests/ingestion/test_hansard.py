import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion import hansard
from src.ingestion.dispatcher import SourceDispatcher


@pytest.fixture
def act_reference_text() -> str:
    return "\n  This references the Crimes Act 1914  and   Another Act 2000.\n"


@pytest.fixture
def section_reference_text() -> str:
    return "We looked at s 223 of the Crimes Act 1914 and Part 3 of the Another Act 2000."


def test_normalization_and_citation_extraction(act_reference_text):
    norm = hansard.normalize_text(act_reference_text)
    assert norm == "This references the Crimes Act 1914 and Another Act 2000."
    citations = hansard.extract_citations(norm)
    assert citations == [
        {
            "work": "Crimes Act 1914",
            "section": None,
            "pinpoint": None,
            "text": "Crimes Act 1914",
        },
        {
            "work": "Another Act 2000",
            "section": None,
            "pinpoint": None,
            "text": "Another Act 2000",
        },
    ]


def test_extracts_section_and_part_markers(section_reference_text):
    norm = hansard.normalize_text(section_reference_text)
    citations = hansard.extract_citations(norm)
    assert citations == [
        {
            "work": "Crimes Act 1914",
            "section": "s 223",
            "pinpoint": None,
            "text": "s 223 of the Crimes Act 1914",
        },
        {
            "work": "Another Act 2000",
            "section": None,
            "pinpoint": "Part 3",
            "text": "Part 3 of the Another Act 2000",
        },
    ]


def test_hash_stability_and_graph_generation():
    debates = [
        {
            "id": "deb1",
            "text": "Debate on the Crimes Act 1914",
            "date": "2023-01-01",
        }
    ]
    nodes1, edges1 = hansard.fetch_debates(debates)
    nodes2, edges2 = hansard.fetch_debates(debates)
    hash1 = nodes1[0]["metadata"]["hash"]
    hash2 = nodes2[0]["metadata"]["hash"]
    assert hash1 == hash2
    citations = nodes1[0]["metadata"]["citations"]
    assert citations == [
        {
            "work": "Crimes Act 1914",
            "section": None,
            "pinpoint": None,
            "citation_text": "Crimes Act 1914",
            "glossary_id": None,
        }
    ]
    # Ensure citation node and edge captured
    assert nodes1[1]["id"] == "Crimes Act 1914"
    assert edges1[0]["to"] == "Crimes Act 1914"


def test_fetch_debates_with_sections(section_reference_text):
    debates = [
        {
            "id": "deb2",
            "text": section_reference_text,
        }
    ]
    nodes, edges = hansard.fetch_debates(debates)
    metadata = nodes[0]["metadata"]
    citations = metadata["citations"]
    assert citations == [
        {
            "work": "Crimes Act 1914",
            "section": "s 223",
            "pinpoint": None,
            "citation_text": "s 223 of the Crimes Act 1914",
            "glossary_id": None,
        },
        {
            "work": "Another Act 2000",
            "section": None,
            "pinpoint": "Part 3",
            "citation_text": "Part 3 of the Another Act 2000",
            "glossary_id": None,
        },
    ]
    # Only two additional act nodes should be present alongside the debate node
    act_nodes = [node for node in nodes if node["type"] == "act"]
    assert {node["id"] for node in act_nodes} == {"Crimes Act 1914", "Another Act 2000"}
    assert {(edge["from"], edge["to"]) for edge in edges} == {
        ("deb2", "Crimes Act 1914"),
        ("deb2", "Another Act 2000"),
    }


def test_dispatch_persists_hansard(tmp_path):
    db_path = tmp_path / "hansard.db"
    config = {
        "sources": [
            {
                "name": "Hansard",
                "adapter": "hansard",
                "debates": [
                    {"id": "d1", "text": "Discussion of the Crimes Act 1914"}
                ],
                "db_path": str(db_path),
            }
        ]
    }
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps(config))
    dispatcher = SourceDispatcher(cfg)
    dispatcher.dispatch()
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, type FROM nodes").fetchall()
    conn.close()
    assert ("d1", "debate") in [(r[0], r[1]) for r in rows]
