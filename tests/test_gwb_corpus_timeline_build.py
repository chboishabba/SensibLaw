from __future__ import annotations

from scripts.gwb_corpus_timeline_build import _chunk_snippets, _is_tocish, _split_sentences


def test_split_sentences_and_toc_filter() -> None:
    text = (
        "George, Chapter 12.1, 12.2, 12.3, 12.4, 12.5. "
        "The reason was a law called the Foreign Intelligence Surveillance Act. "
        "I signed the bill into law."
    )
    sents = _split_sentences(text)
    assert any("Foreign Intelligence Surveillance Act" in sent for sent in sents)
    assert all("Chapter 12.1" not in sent for sent in sents)
    assert _is_tocish("George, Chapter 12.1, 12.2, 12.3, 12.4, 12.5")


def test_chunk_snippets_prioritizes_salient_legal_sentences() -> None:
    sents = [
        "This is a generic memoir sentence about growing up in Texas.",
        "The reason was a law called the Foreign Intelligence Surveillance Act.",
        "I narrowed the list down to five judges: Samuel Alito, John Roberts, and others.",
        "Another ordinary sentence about baseball and family life.",
    ]
    chunks = _chunk_snippets(sents, max_snippets=4, snippet_chars=240)
    assert chunks
    assert "Foreign Intelligence Surveillance Act" in chunks[0] or "Samuel Alito" in chunks[0]
    assert any("John Roberts" in chunk or "Foreign Intelligence Surveillance Act" in chunk for chunk in chunks[:2])
