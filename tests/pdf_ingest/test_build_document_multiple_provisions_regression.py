from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from types import SimpleNamespace
from unittest.mock import patch

from src.pdf_ingest import build_document


def test_build_document_preserves_multiple_provisions():
    pages = [
        {
            "page": 1,
            "heading": "1 Preliminary",
            "text": "This is section 1.\n\n2 Application\nThis applies to everyone.",
        }
    ]

    document = build_document(pages, Path("multi-section.pdf"))

    assert len(document.provisions) == 2
    assert [prov.identifier for prov in document.provisions] == ["1", "2"]
    assert [prov.heading for prov in document.provisions] == [
        "Preliminary",
        "Application",
    ]


def test_build_document_section_parser_fallback_returns_provisions_with_atoms():
    pages = [
        {
            "page": 1,
            "heading": "Preface",
            "text": "Section 1 text\n\nMore text in section 2",
        }
    ]

    nodes = [
        SimpleNamespace(
            text="Section 1 text",
            identifier="1",
            heading="Intro",
            node_type="section",
            children=[],
            rule_tokens={},
            references=[],
        ),
        SimpleNamespace(
            text="More text in section 2",
            identifier="2",
            heading="Scope",
            node_type="section",
            children=[],
            rule_tokens={},
            references=[],
        ),
    ]

    class DummyParser:
        def parse_sections(self, _text):
            return nodes

    with patch("src.pdf_ingest.parse_sections", return_value=[]), patch(
        "src.pdf_ingest.section_parser",
        DummyParser(),
    ):
        document = build_document(pages, Path("dummy.pdf"))

    assert [prov.identifier for prov in document.provisions] == ["1", "2"]
    assert all(isinstance(prov.atoms, list) for prov in document.provisions)
    assert all(isinstance(prov.principles, list) for prov in document.provisions)
