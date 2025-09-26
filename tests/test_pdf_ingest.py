import importlib
import json
import sys
import types
from pathlib import Path


def test_extract_pdf(tmp_path):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    def fake_extract_text(path):
        return "Heading 1\nHello  \nWorld\fHeading2\nSecond\tPage"

    sys.modules["pdfminer.high_level"] = types.SimpleNamespace(
        extract_text=fake_extract_text
    )
    sys.modules.pop("src.pdf_ingest", None)
    pdf_ingest = importlib.import_module("src.pdf_ingest")

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    pages = pdf_ingest.extract_pdf_text(pdf_path)
    assert pages == [
        {
            "page": 1,
            "heading": "Heading 1",
            "text": "Hello World",
            "lines": ["Heading 1", "Hello", "World"],
        },
        {
            "page": 2,
            "heading": "Heading2",
            "text": "Second Page",
            "lines": ["Heading2", "Second Page"],
        },
    ]

    meta = pdf_ingest.build_metadata(pdf_path, pages)
    assert meta["source"] == "sample.pdf"
    assert meta["page_count"] == 2

    out = tmp_path / "out.json"
    pdf_ingest.save_json(pages, out, pdf_path)
    with out.open() as f:
        data = json.load(f)
    assert data["source"] == str(pdf_path)
    assert data["page_count"] == 2
    assert data["pages"] == pages
