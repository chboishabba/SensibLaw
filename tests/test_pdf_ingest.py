import importlib
import json
import sys
import types
from pathlib import Path


def test_extract_pdf(tmp_path):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    class DummyLTTextContainer:
        def __init__(self, text):
            self._text = text

        def get_text(self):
            return self._text

    def fake_extract_pages(path):
        return [
            [DummyLTTextContainer("Hello  \nWorld")],
            [DummyLTTextContainer("Second\tPage")],
        ]

    sys.modules["pdfminer.high_level"] = types.SimpleNamespace(
        extract_pages=fake_extract_pages
    )
    sys.modules["pdfminer.layout"] = types.SimpleNamespace(
        LTTextContainer=DummyLTTextContainer
    )

    pdf_ingest = importlib.import_module("src.pdf_ingest")

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    pages = pdf_ingest.extract_pdf_text(pdf_path)
    assert pages == [
        {"page": 1, "text": "Hello\nWorld"},
        {"page": 2, "text": "Second Page"},
    ]

    meta = pdf_ingest.build_metadata(pdf_path, pages)
    out = tmp_path / "out.json"
    pdf_ingest.save_json(meta, out)
    with out.open() as f:
        data = json.load(f)

    assert data["source"] == "sample.pdf"
    assert data["page_count"] == 2
    assert data["pages"] == pages
