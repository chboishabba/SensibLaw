from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from src.pdf_ingest import build_document


def test_build_document_splits_sections():
    pages = [
        {"page": 1, "heading": "1 Duty to act", "text": "A person must act."},
        {
            "page": 2,
            "heading": "2 Duty to inform",
            "text": "The person must inform the regulator.",
        },
    ]

    doc = build_document(pages, Path("sample.pdf"))

    assert [prov.identifier for prov in doc.provisions] == ["1", "2"]
    assert [prov.heading for prov in doc.provisions] == [
        "Duty to act",
        "Duty to inform",
    ]
    assert all(prov.children == [] for prov in doc.provisions)
