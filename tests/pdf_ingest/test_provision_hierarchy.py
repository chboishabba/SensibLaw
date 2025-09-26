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
MULTI_LEVEL_STATUTE = fixtures.MULTI_LEVEL_STATUTE

from src.section_parser import parse_sections


def test_multi_level_provision_hierarchy():
    provisions = parse_sections(MULTI_LEVEL_STATUTE)

    assert len(provisions) == 1

    part = provisions[0]
    assert part.node_type == "part"
    assert part.identifier == "1"
    assert part.heading == "Preliminary Matters"

    assert len(part.children) == 1
    division = part.children[0]
    assert division.node_type == "division"
    assert division.identifier == "1"
    assert division.heading == "Introductory"

    assert len(division.children) == 2
    section_one, section_two = division.children

    assert section_one.node_type == "section"
    assert section_one.identifier == "1"
    assert section_one.heading == "Short title"
    assert len(section_one.children) == 2
    sub_one, sub_two = section_one.children
    assert sub_one.identifier == "(1)"
    assert "may be cited" in sub_one.text
    assert sub_one.rule_tokens["modality"] == "may"
    assert sub_two.rule_tokens["modality"] == "must"

    assert section_two.node_type == "section"
    assert section_two.identifier == "2"
    assert section_two.rule_tokens["modality"] == "must not"
    assert not section_two.children
