from pathlib import Path
import sys

# ruff: noqa: E402

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

    with (
        patch("src.pdf_ingest.parse_sections", return_value=[]),
        patch(
            "src.pdf_ingest.section_parser",
            DummyParser(),
        ),
    ):
        document = build_document(pages, Path("dummy.pdf"))

    assert [prov.identifier for prov in document.provisions] == ["1", "2"]
    assert all(isinstance(prov.atoms, list) for prov in document.provisions)
    assert all(isinstance(prov.principles, list) for prov in document.provisions)


def test_build_document_parses_table_of_contents():
    pages = [
        {
            "page": 1,
            "heading": "Contents",
            "text": (
                "Part 1 Preliminary............................ 3\n"
                "Section 1 Short title............... 4\n"
                "Section 2 Definitions............... 5"
            ),
            "lines": [
                "Contents",
                "Part 1 Preliminary............................ 3",
                "Section 1 Short title............... 4",
                "Section 2 Definitions............... 5",
            ],
        },
        {
            "page": 2,
            "heading": "Part 1 Preliminary",
            "text": "Section 1 Short title\nShort title text",
        },
    ]

    document = build_document(pages, Path("toc.pdf"))

    assert document.toc_entries, "expected parsed TOC entries"
    part_entry = document.toc_entries[0]
    assert part_entry.node_type == "part"
    assert part_entry.identifier == "1"
    assert part_entry.title == "Preliminary"
    assert part_entry.page_number == 3
    assert len(part_entry.children) == 2
    first_section = part_entry.children[0]
    assert first_section.node_type == "section"
    assert first_section.identifier == "1"
    assert first_section.title == "Short title"
    assert first_section.page_number == 4


def test_build_document_strips_toc_from_body():
    pages = [
        {
            "page": 1,
            "heading": "Queensland Summary Offences Act 2005",
            "text": (
                "Queensland Summary Offences Act 2005 Contents\n"
                "Part 1 Preliminary............................ 3\n"
                "Section 1 Short title............... 4\n"
                "Section 2 Definitions............... 5"
            ),
            "lines": [
                "Queensland Summary Offences Act 2005",
                "Contents",
                "Part 1 Preliminary............................ 3",
                "Section 1 Short title............... 4",
                "Section 2 Definitions............... 5",
            ],
        },
        {
            "page": 2,
            "heading": "Part 1 Preliminary",
            "text": (
                "1 Short title\n"
                "Short title text\n\n"
                "2 Definitions\n"
                "Definitions text"
            ),
            "lines": [
                "Part 1 Preliminary",
                "1 Short title",
                "Short title text",
                "2 Definitions",
                "Definitions text",
            ],
        },
    ]

    document = build_document(pages, Path("toc-cleanup.pdf"))

    assert document.toc_entries, "expected parsed TOC entries"
    assert "Contents" not in document.body
    assert document.body.startswith("Part 1 Preliminary")
    assert "Short title text" in document.body
