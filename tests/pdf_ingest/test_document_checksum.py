import hashlib
from pathlib import Path

from src.pdf_ingest import build_document


def test_build_document_sets_metadata_checksum():
    pages = [
        {
            "heading": "Introductory Matter",
            "text": "This is a short document body for checksum testing.",
        }
    ]

    document = build_document(pages, Path("dummy.pdf"))

    expected_checksum = hashlib.sha256(document.body.encode("utf-8")).hexdigest()

    assert document.metadata.checksum == expected_checksum
