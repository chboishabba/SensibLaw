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


def test_parse_sections_logs_fallback(monkeypatch, caplog):
    from src import pdf_ingest

    monkeypatch.setattr(pdf_ingest, "section_parser", None, raising=False)

    sample_text = "1 Short title\nThis Act may be cited as the Sample Act."

    with caplog.at_level("DEBUG", logger="src.pdf_ingest"):
        sections = pdf_ingest.parse_sections(sample_text)

    assert sections
    matching_records = [
        record
        for record in caplog.records
        if record.name == "src.pdf_ingest"
        and "Falling back to regex-based section parsing" in record.message
    ]
    assert matching_records, "Expected fallback log message was not emitted"
    record = matching_records[-1]
    assert record.section_parser_available is False
    assert "section_parser_available=False" in record.message
