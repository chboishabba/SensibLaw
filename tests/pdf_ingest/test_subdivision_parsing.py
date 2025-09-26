import importlib.util
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

fixtures_path = Path(__file__).with_name("fixtures.py")
spec = importlib.util.spec_from_file_location("pdf_ingest_fixtures", fixtures_path)
fixtures = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(fixtures)
STATUTE_WITH_SUBDIVISIONS = fixtures.STATUTE_WITH_SUBDIVISIONS

from src.section_parser import parse_sections as parse_sections_core
from src.ingestion.section_parser import parse_sections as parse_sections_ingest


def _assert_subdivision_structure(nodes):
    assert len(nodes) == 1
    part = nodes[0]
    assert part.node_type == "part"

    assert len(part.children) == 1
    division = part.children[0]
    assert division.node_type == "division"

    assert len(division.children) == 2
    subdivision_a, subdivision_b = division.children

    assert subdivision_a.node_type == "subdivision"
    assert subdivision_a.identifier == "A"
    assert subdivision_a.heading == "Preliminary matters"

    assert len(subdivision_a.children) == 1
    section_three = subdivision_a.children[0]
    assert section_three.node_type == "section"
    assert section_three.identifier == "3"
    assert "Board is established" in section_three.text
    assert not section_three.children

    assert subdivision_b.node_type == "subdivision"
    assert subdivision_b.identifier == "B"
    assert subdivision_b.heading is None

    assert len(subdivision_b.children) == 1
    section_four = subdivision_b.children[0]
    assert section_four.node_type == "section"
    assert section_four.identifier == "4"
    assert len(section_four.children) == 2
    first_subsection = section_four.children[0]
    assert first_subsection.node_type == "subsection"
    assert first_subsection.identifier == "(1)"
    assert "Members must be appointed" in first_subsection.text


def test_core_parser_emits_subdivisions():
    provisions = parse_sections_core(STATUTE_WITH_SUBDIVISIONS)
    _assert_subdivision_structure(provisions)


def test_ingestion_parser_emits_subdivisions():
    nodes = parse_sections_ingest(STATUTE_WITH_SUBDIVISIONS)
    _assert_subdivision_structure(nodes)
