import importlib
import json
import sys
import types
from pathlib import Path


def test_extract_pdf(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    class DummyPage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class DummyPDF:
        def __init__(self, pages):
            self.pages = pages

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_open(path):
        return DummyPDF([
            DummyPage("Hello  \nWorld"),
            DummyPage("Second\tPage")
        ])

    sys.modules["pdfplumber"] = types.SimpleNamespace(open=fake_open)
    pdf_ingest = importlib.import_module("src.pdf_ingest")

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    pages = pdf_ingest.extract_pdf_text(pdf_path)
    assert pages == [
        {"page": 1, "text": "Hello World"},
        {"page": 2, "text": "Second Page"},
    ]

    out = tmp_path / "out.json"
    pdf_ingest.save_json(pages, out)
    with out.open() as f:
        data = json.load(f)
    assert data == pages
