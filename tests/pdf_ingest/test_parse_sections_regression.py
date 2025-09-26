import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.pdf_ingest as pdf_ingest
from src.pdf_ingest import build_document, parse_sections


def test_parse_sections_structured_and_regex_fallback(monkeypatch):
    text = "1 Heading\nBody of the section."

    section_node = SimpleNamespace(
        text="Heading\nBody of the section.",
        identifier="1",
        heading="Heading",
        node_type="section",
        children=[],
        rule_tokens={},
        references=[],
    )

    fake_parser = SimpleNamespace(parse_sections=lambda _: [section_node])
    monkeypatch.setattr(pdf_ingest, "section_parser", fake_parser, raising=False)

    structured_sections = parse_sections(text)
    assert [section.identifier for section in structured_sections] == ["1"]

    monkeypatch.setattr(pdf_ingest, "section_parser", None, raising=False)

    fallback_sections = parse_sections(text)
    assert fallback_sections
    assert fallback_sections[0].identifier == "1"

    pages = [{"heading": "1 Heading", "text": "Body of the section."}]
    document = build_document(pages, Path("dummy.pdf"))
    assert document.provisions
