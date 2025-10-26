from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from src.pdf_ingest import build_document


def _queensland_pages() -> list[dict[str, object]]:
    return [
        {
            "page": 1,
            "heading": "Queensland",
            "text": "Summary Offences Act 2005 Current as at 2 September 2024 2005",
            "lines": [
                "Queensland",
                "Summary Offences Act 2005",
                "Current as at 2 September 2024",
                "2005",
            ],
        }
    ]


def test_build_document_infers_cover_metadata() -> None:
    pages = _queensland_pages()
    document = build_document(pages, Path("act-2005-004.pdf"))

    assert document.metadata.jurisdiction == "Queensland"
    assert document.metadata.title == "Summary Offences Act 2005"
    assert document.metadata.date == date(2024, 9, 2)


def test_build_document_computes_checksum() -> None:
    pages = _queensland_pages()
    document = build_document(pages, Path("act-2005-004.pdf"))

    expected_body = (
        "Queensland\n"
        "Summary Offences Act 2005 Current as at 2 September 2024 2005"
    )
    expected_checksum = hashlib.sha256(expected_body.encode("utf-8")).hexdigest()

    assert document.metadata.checksum == expected_checksum


def test_build_document_without_cover_banner_defaults() -> None:
    pages = [
        {
            "page": 1,
            "heading": "Corporations Act 2001",
            "text": "Corporations Act 2001",
            "lines": ["Corporations Act 2001"],
        }
    ]
    today = date.today()
    document = build_document(pages, Path("corporations.pdf"))

    assert document.metadata.jurisdiction == ""
    assert document.metadata.title == "Corporations Act 2001"
    assert document.metadata.date == today

