from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pdf_ingest import build_document


def test_build_document_preserves_multiple_provisions():
    pages = [
        {
            "page": 1,
            "heading": "1 Preliminary",
            "text": "This is section 1.\n\n2 Application\nThis applies to everyone.",
        }
    ]

    document = build_document(pages, Path("multi-section.pdf"))

    assert len(document.provisions) == 2
    assert [prov.identifier for prov in document.provisions] == ["1", "2"]
    assert [prov.heading for prov in document.provisions] == [
        "Preliminary",
        "Application",
    ]
