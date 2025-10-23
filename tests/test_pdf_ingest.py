import importlib
import json
import sys
import types
from pathlib import Path


def _load_pdf_ingest(fake_text: str):
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    sys.modules["pdfminer.high_level"] = types.SimpleNamespace(
        extract_text=lambda path: fake_text
    )
    sys.modules.pop("src.pdf_ingest", None)
    return importlib.import_module("src.pdf_ingest")


def test_extract_pdf(tmp_path):
    pdf_ingest = _load_pdf_ingest("Heading 1\nHello  \nWorld\fHeading2\nSecond\tPage")

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


def test_extract_pdf_removes_dot_leaders_from_body(tmp_path):
    pdf_ingest = _load_pdf_ingest(
        "Heading 1\nAlpha . . . . Beta\nGamma ......... Delta\fHeading 2\nClean line"
    )

    pdf_path = tmp_path / "dots.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    pages = pdf_ingest.extract_pdf_text(pdf_path)
    assert pages[0]["lines"][1] == "Alpha Beta"
    assert pages[0]["lines"][2] == "Gamma Delta"
    assert pages[0]["text"] == "Alpha Beta Gamma Delta"

    document = pdf_ingest.build_document(pages, pdf_path)
    assert ". ." not in document.body
    assert "...." not in document.body
