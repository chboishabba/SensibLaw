from __future__ import annotations

from pathlib import Path

import spacy
from spacy.language import Language
from spacy.tokens import Span

from src.pipeline.ner import (
    REFERENCE_SPAN_KEY,
    analyze_references,
    configure_ner_pipeline,
)


def test_configure_pipeline_combines_patterns_and_ner_entities():
    nlp = spacy.blank("en")
    configure_ner_pipeline(
        nlp,
        patterns_path=Path("patterns/legal_patterns.jsonl"),
        overwrite_ruler=True,
    )

    @Language.component("mock_ner")
    def mock_ner(doc):
        ents = list(doc.ents)
        ents.append(Span(doc, 0, 1, label="ORG"))
        doc.set_ents(ents)
        return doc

    nlp.add_pipe("mock_ner", before="reference_resolver")

    doc = nlp("OpenAI referenced section 12 of the Privacy Act 1988.")
    references = {span.text: span for span in doc.spans[REFERENCE_SPAN_KEY]}

    assert "OpenAI" in references
    assert references["OpenAI"]._.reference_source == "ORG"
    assert "section 12" in references
    assert "Privacy Act 1988" in references


def test_analyze_references_uses_cached_pipeline(monkeypatch):
    calls = []

    def fake_loader(model_name=None):
        calls.append(model_name)
        return spacy.blank("en")

    monkeypatch.setattr("src.pipeline.ner._load_language", fake_loader)

    spans_first = analyze_references("See section 10 of the Privacy Act 1988.")
    spans_second = analyze_references("See section 11 of the Privacy Act 1988.")

    assert calls == [None]
    assert any(span.text == "section 10" for span in spans_first)
    assert any(span.text == "section 11" for span in spans_second)
    assert all(span.label_ == "REFERENCE" for span in spans_first + spans_second)
