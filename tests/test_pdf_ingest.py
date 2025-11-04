import importlib
import json
import sys
import types
from pathlib import Path
from typing import Iterable, Sequence


def _make_text_container(text: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(get_text=lambda text=text: text)


def _load_pdf_ingest(page_layouts: Sequence[Iterable[types.SimpleNamespace]]):
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    pages = [list(layout) for layout in page_layouts]

    def fake_extract_pages(*_args, **_kwargs):
        def _iter():
            for layout in pages:
                yield list(layout)

        return _iter()

    sys.modules["pdfminer.high_level"] = types.SimpleNamespace(
        extract_pages=fake_extract_pages
    )
    sys.modules.pop("src.pdf_ingest", None)
    return importlib.import_module("src.pdf_ingest")


def test_extract_pdf(tmp_path):
    pdf_ingest = _load_pdf_ingest(
        [
            [_make_text_container("Heading 1\nHello  \nWorld")],
            [_make_text_container("Heading2\nSecond\tPage")],
        ]
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    pages = list(pdf_ingest.extract_pdf_text(pdf_path))
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
        [
            [
                _make_text_container(
                    "Heading 1\nAlpha . . . . Beta\nGamma ......... Delta"
                )
            ],
            [_make_text_container("Heading 2\nClean line")],
        ]
    )

    pdf_path = tmp_path / "dots.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    pages = list(pdf_ingest.extract_pdf_text(pdf_path))
    assert pages[0]["lines"][1] == "Alpha Beta"
    assert pages[0]["lines"][2] == "Gamma Delta"
    assert pages[0]["text"] == "Alpha Beta Gamma Delta"

    document = pdf_ingest.build_document(pages, pdf_path)
    assert ". ." not in document.body
    assert "...." not in document.body


def test_extract_pdf_streams_pages_incrementally(tmp_path):
    class RecordingContainer:
        def __init__(self, text: str):
            self.text = text
            self.calls = 0

        def get_text(self) -> str:
            self.calls += 1
            return self.text

    first = RecordingContainer("Heading 1\nBody line")
    second = RecordingContainer("Heading 2\nAnother body line")

    pdf_ingest = _load_pdf_ingest([[first], [second]])

    pdf_path = tmp_path / "stream.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    iterator = pdf_ingest.extract_pdf_text(pdf_path)
    first_page = next(iterator)

    assert first_page["page"] == 1
    assert first.calls == 1
    assert second.calls == 0, "Second page should not be extracted until iterated"

    remaining = list(iterator)
    assert len(remaining) == 1
    assert remaining[0]["page"] == 2
    assert second.calls == 1
