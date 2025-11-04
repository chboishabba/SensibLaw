import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pdf_ingest import build_document  # noqa: E402


def test_infers_jurisdiction_and_title_from_cover_banner():
    pages = [
        {
            "page": 1,
            "heading": "Queensland",
            "text": "Summary Offences Act 2005 An Act to consolidate provisions",
            "lines": [
                "Queensland",
                "Summary Offences Act 2005",
                "An Act to consolidate provisions",
            ],
        }
    ]

    document = build_document(pages, Path("summary-offences.pdf"))

    metadata = document.metadata
    assert metadata.title == "Summary Offences Act 2005"
    assert metadata.jurisdiction == "Queensland"


def test_falls_back_when_cover_banner_missing():
    pages = [
        {
            "page": 1,
            "heading": "Summary Offences Act 2005",
            "text": "An Act to consolidate provisions",
            "lines": [
                "Summary Offences Act 2005",
                "An Act to consolidate provisions",
            ],
        }
    ]

    document = build_document(pages, Path("summary-offences.pdf"))

    metadata = document.metadata
    assert metadata.title == "Summary Offences Act 2005"
    assert metadata.jurisdiction == ""
