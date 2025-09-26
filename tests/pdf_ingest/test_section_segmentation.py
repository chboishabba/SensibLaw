import importlib
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture(name="pdf_ingest")
def _pdf_ingest_module(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    sys.modules.pop("src.pdf_ingest", None)
    module = importlib.import_module("src.pdf_ingest")

    def fake_parse_sections(text):
        def _node(identifier: str, heading: str, body: str):
            return types.SimpleNamespace(
                text=body,
                identifier=identifier,
                heading=heading,
                node_type="section",
                rule_tokens={"modality": None, "conditions": [], "references": []},
                children=[],
            )

        return [
            _node("1", "Section 1", "The agent must file reports."),
            _node("2", "Section 2", "The director may refuse permits."),
        ]

    monkeypatch.setattr(
        module,
        "section_parser",
        types.SimpleNamespace(parse_sections=fake_parse_sections),
        raising=False,
    )

    from src.rules import Rule

    def fake_extract_rules(text: str):
        if "must file reports" in text:
            return [Rule(actor="Agent", modality="must", action="file reports")]
        if "may refuse permits" in text:
            return [Rule(actor="Director", modality="may", action="refuse permits")]
        return []

    monkeypatch.setattr(module, "extract_rules", fake_extract_rules)
    return module


def test_build_document_splits_sections(pdf_ingest):
    pages = [
        {"page": 1, "heading": "Section 1", "text": "The agent must file reports."},
        {"page": 2, "heading": "Section 2", "text": "The director may refuse permits."},
    ]

    document = pdf_ingest.build_document(pages, source=Path("dummy.pdf"))

    assert [prov.identifier for prov in document.provisions] == ["1", "2"]
    assert [prov.heading for prov in document.provisions] == [
        "Section 1",
        "Section 2",
    ]
    assert document.provisions[0].principles == ["Agent must file reports"]
    assert document.provisions[1].principles == ["Director may refuse permits"]
