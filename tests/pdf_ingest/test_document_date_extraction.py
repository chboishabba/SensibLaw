"""Regression tests for document date extraction during PDF ingestion."""

from datetime import date
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pdf_ingest import build_document


@pytest.fixture
def pages():
    return [
        {
            "page": 1,
            "heading": "Queensland",
            "text": (
                "Queensland\n"
                "Summary Offences Act 2005\n"
                "Current as at 2 September 2024\n"
                "Some additional context"
            ),
            "lines": [
                "Queensland",
                "Summary Offences Act 2005",
                "Current as at 2 September 2024",
                "Some additional context",
            ],
        }
    ]


def test_build_document_uses_detected_document_date(pages):
    document = build_document(pages, Path("summary-offences.pdf"))

    assert document.metadata.date == date(2024, 9, 2)
