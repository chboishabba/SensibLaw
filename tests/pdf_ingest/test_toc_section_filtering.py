from pathlib import Path

from src.pdf_ingest import build_document


def test_build_document_filters_toc_pages_from_provisions():
    toc_lines = [
        "1 The director must publish reports.............. 3",
        "2 Commencement obligations.............. 4",
    ]
    pages = [
        {
            "page": 1,
            "heading": "Contents",
            "text": "\n".join(toc_lines),
            "lines": ["Contents", *toc_lines],
        },
        {
            "page": 2,
            "heading": "1 Publication duties",
            "text": "The director must publish reports within 30 days.",
        },
        {
            "page": 3,
            "heading": "2 Commencement obligations",
            "text": "Each entity must commence operations by 1 July.",
        },
    ]

    document = build_document(pages, Path("toc-filter.pdf"))

    assert [prov.identifier for prov in document.provisions] == ["1", "2"]
    assert [prov.heading for prov in document.provisions] == [
        "Publication duties",
        "Commencement obligations",
    ]
    assert all("........" not in (prov.heading or "") for prov in document.provisions)

    rule_texts = [
        atom.text or ""
        for provision in document.provisions
        for atom in provision.rule_atoms
    ]

    assert rule_texts, "expected rule atoms extracted from real sections"

    for toc_line in toc_lines:
        assert all(toc_line not in text for text in rule_texts)

    assert any("publish reports" in text.lower() for text in rule_texts)
