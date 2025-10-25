import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.hca import parse_cases_cited


def test_parse_cases_cited_edges():
    section = """
    Cases cited:
    Follows: Mabo v Queensland [1992] HCA 23
    Distinguishes: Foo v Bar [2001] FCA 12
    """
    nodes, edges = parse_cases_cited(section, source="base-case")

    follows = next(e for e in edges if e["type"] == "follows")
    distinguishes = next(e for e in edges if e["type"] == "distinguishes")

    assert follows["weight"] > distinguishes["weight"]
    assert any(n["id"].startswith("Mabo v Queensland") and n["court_rank"] == follows["weight"] for n in nodes)

    follows_node = next(n for n in nodes if n["id"].startswith("Mabo v Queensland"))
    follows_reference = follows_node["reference"]
    assert follows_reference["work"] == "Mabo v Queensland"
    assert follows_reference["section"] == "[1992] HCA 23"
    assert follows_reference["pinpoint"] is None
    assert follows_reference["citation_text"] == "Mabo v Queensland [1992] HCA 23"

    follows_edge_reference = follows["reference"]
    assert follows_edge_reference["section"] == "[1992] HCA 23"
    assert follows_edge_reference["work"] == "Mabo v Queensland"
