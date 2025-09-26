from pathlib import Path


def test_build_document_creates_multiple_sections(monkeypatch):
    from src import pdf_ingest

    monkeypatch.setattr(pdf_ingest, "section_parser", None, raising=False)
    monkeypatch.setattr(pdf_ingest, "extract_rules", lambda text: [])

    pages = [
        {"page": 1, "heading": "Part 1 Preliminary Matters", "text": ""},
        {"page": 2, "heading": "Division 1 Introductory", "text": ""},
        {
            "page": 3,
            "heading": "1 Short title",
            "text": "(1) This Act may be cited as the Sample Act.\n(2) Regulations must set required forms.",
        },
        {
            "page": 4,
            "heading": "2 Application of Act",
            "text": "The Minister must not delay action if urgent circumstances exist.",
        },
    ]

    document = pdf_ingest.build_document(pages, source=Path("sample.pdf"))

    assert len(document.provisions) == 2
    identifiers = [prov.identifier for prov in document.provisions]
    assert identifiers == ["1", "2"]

    first, second = document.provisions
    assert first.heading == "Short title"
    assert "may be cited as the Sample Act" in first.text
    assert second.heading == "Application of Act"
    assert "must not delay action" in second.text
