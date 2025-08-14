import sys
from pathlib import Path
import json
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion import hansard
from src.ingestion.dispatcher import SourceDispatcher


def test_normalization_and_citation_extraction():
    text = "\n  This references the Crimes Act 1914  and   Another Act 2000.\n"
    norm = hansard.normalize_text(text)
    assert norm == "This references the Crimes Act 1914 and Another Act 2000."
    citations = hansard.extract_citations(norm)
    assert citations == ["Crimes Act 1914", "Another Act 2000"]


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
    # Ensure citation and edge captured
    assert nodes1[1]["id"] == "Crimes Act 1914"
    assert edges1[0]["to"] == "Crimes Act 1914"


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
