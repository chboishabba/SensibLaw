import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def pdf_ingest(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    module = importlib.import_module("src.pdf_ingest")
    importlib.reload(module)

    monkeypatch.setattr(module, "section_parser", None, raising=False)
    return module


def test_parse_sections_regex_fallback_preserves_prefix(pdf_ingest):
    text = (
        "Preface text providing context.\n\n"
        "1 Heading One\nBody of the first section.\n\n"
        "2 Heading Two\nBody of the second section."
    )

    sections = pdf_ingest.parse_sections(text)

    assert len(sections) == 2

    first, second = sections

    assert first.identifier == "1"
    assert first.heading == "Heading One"
    assert first.text.startswith("Preface text providing context.")
    assert "Heading One" in first.text
    assert "Body of the first section." in first.text

    assert second.identifier == "2"
    assert second.heading == "Heading Two"
    assert second.text.startswith("Heading Two")
    assert "Body of the second section." in second.text

    # Ensure the fallback segmentation is being used by confirming the text is not
    # returned as a single monolithic provision.
    assert first.text != text
    assert first.text + "\n\n" + second.text != text
