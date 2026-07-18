from pathlib import Path

from src import pdf_ingest
from src.ingestion.section_parser import fetch_section as fetch_canonical_section
from src.section_parser import fetch_section as fetch_legacy_section


def test_legacy_section_json_is_a_projection_of_the_canonical_parser():
    html = "<p>1 A person must not drive if intoxicated under s 5B.</p>"

    canonical = fetch_canonical_section(html)
    legacy = fetch_legacy_section(html)

    assert legacy == {
        "number": canonical["number"],
        "heading": canonical["heading"],
        "text": canonical["text"],
        "rules": {
            "modality": canonical["rules"]["modality"],
            "conditions": canonical["rules"]["conditions"],
            "references": [
                reference["citation_text"]
                for reference in canonical["rules"]["references"]
            ],
        },
    }


def test_canonical_parser_no_longer_imports_the_legacy_projection():
    source = (
        Path(__file__).resolve().parents[1] / "src" / "ingestion" / "section_parser.py"
    ).read_text(encoding="utf-8")

    assert "import section_parser as _legacy_section_parser" not in source


def test_pdf_ingestion_prefers_canonical_parser_nodes():
    assert pdf_ingest.section_parser is not None
    assert pdf_ingest.section_parser.__name__ == "src.ingestion.section_parser"
