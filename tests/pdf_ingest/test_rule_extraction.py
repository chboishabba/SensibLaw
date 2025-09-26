import json
import sys
import types
from pathlib import Path


def test_rule_extraction(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))

    def fake_extract_text(path):
        return "Heading\nThe agent must file reports."

    sys.modules["pdfminer.high_level"] = types.SimpleNamespace(
        extract_text=fake_extract_text
    )

    sys.modules.pop("src.pdf_ingest", None)
    from src.models.provision import Provision
    import src.pdf_ingest as pdf_ingest

    def fake_parse_sections(text):
        body = text.split("\n", 1)[1] if "\n" in text else text
        return [
            Provision(
                text=body,
                identifier="1",
                heading="Heading",
                node_type="section",
                rule_tokens={
                    "modality": "must",
                    "conditions": [],
                    "references": [],
                },
            )
        ]

    monkeypatch.setattr(
        pdf_ingest,
        "section_parser",
        types.SimpleNamespace(parse_sections=fake_parse_sections),
        raising=False,
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    out = tmp_path / "out.json"
    doc = pdf_ingest.process_pdf(
        pdf_path,
        output=out,
        jurisdiction="US",
        citation="CIT",
    )

    assert doc.provisions
    assert doc.provisions[0].principles
    assert "must file reports" in doc.provisions[0].principles[0]
    atoms = [a for a in doc.provisions[0].atoms if a.role == "principle"]
    assert any("must file reports" in (a.text or "") for a in atoms)

    with out.open() as f:
        saved = json.load(f)
    assert saved["metadata"]["provenance"] == str(pdf_path)
    assert saved["provisions"][0]["principles"]
    assert saved["provisions"][0]["atoms"]
