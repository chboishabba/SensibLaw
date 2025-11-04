import src.pdf_ingest as pdf_ingest


def test_build_document_skips_table_of_contents_rule_atoms(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_ingest, "section_parser", None, raising=False)

    pages = [
        {
            "heading": "Contents",
            "text": "1 Duties of agents .......... 3\n2 Penalties .......... 4",
            "lines": [
                "Contents",
                "1 Duties of agents .......... 3",
                "2 Penalties .......... 4",
            ],
        },
        {
            "heading": "1 Duties of agents",
            "text": "An agent must register before trading.",
            "lines": [
                "1 Duties of agents",
                "An agent must register before trading.",
            ],
        },
        {
            "heading": "2 Penalties",
            "text": "A person must not trade without registration.",
            "lines": [
                "2 Penalties",
                "A person must not trade without registration.",
            ],
        },
    ]

    document = pdf_ingest.build_document(pages, source=tmp_path / "sample.pdf")

    provision_headings = {prov.heading for prov in document.provisions if prov.heading}
    assert provision_headings == {"Duties of agents", "Penalties"}

    assert "Contents" not in document.body

    rule_texts = [
        atom.text or ""
        for provision in document.provisions
        for atom in provision.rule_atoms
    ]
    assert rule_texts

    toc_snippets = [
        "Contents",
        "1 Duties of agents .......... 3",
        "2 Penalties .......... 4",
    ]
    for snippet in toc_snippets:
        assert all(snippet not in text for text in rule_texts)
