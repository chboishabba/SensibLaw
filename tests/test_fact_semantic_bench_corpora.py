from __future__ import annotations

import json
from pathlib import Path

import pytest

_ALLOWED_LENGTH_BUCKETS = {"short", "medium", "long"}

_CORPORA = [
    {
        "path": Path("tests/fixtures/fact_semantic_bench/wiki_revision_seed.json"),
        "corpus_id": "wiki_revision",
        "adversarial_ids": {
            "wiki-adversarial-noise",
            "wiki-adversarial-repetitive",
            "wiki-adversarial-linkspam",
            "wiki-adversarial-prompt-injection",
        },
    },
    {
        "path": Path("tests/fixtures/fact_semantic_bench/chat_archive_seed.json"),
        "corpus_id": "chat_archive",
        "adversarial_ids": {
            "chat-adversarial-ocr",
            "chat-adversarial-fragment",
            "chat-adversarial-prompt-injection",
            "chat-adversarial-code-switch",
        },
    },
    {
        "path": Path("tests/fixtures/fact_semantic_bench/transcript_handoff_seed.json"),
        "corpus_id": "transcript_handoff",
        "adversarial_ids": {
            "transcript-adversarial-noise",
            "transcript-adversarial-redaction",
            "transcript-adversarial-runon",
        },
    },
    {
        "path": Path("tests/fixtures/fact_semantic_bench/au_legal_seed.json"),
        "corpus_id": "au_legal",
        "adversarial_ids": {
            "au-adversarial-noise",
            "au-adversarial-press-release",
            "au-adversarial-docket-noise",
        },
    },
]


def _load_corpus(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload.get("entries"), list), f"{path} missing entries array"
    return payload


@pytest.mark.parametrize("corpus", _CORPORA)
def test_corpus_contains_adversarial_entries(corpus: dict[str, object]) -> None:
    payload = _load_corpus(corpus["path"])
    entry_ids = {str(entry.get("id")) for entry in payload["entries"]}
    assert payload["corpus_id"] == corpus["corpus_id"]
    assert corpus["adversarial_ids"].issubset(entry_ids)
    assert any("adversarial" in entry_id for entry_id in entry_ids)


@pytest.mark.parametrize("corpus", _CORPORA)
def test_corpus_entries_are_well_formed(corpus: dict[str, object]) -> None:
    payload = _load_corpus(corpus["path"])
    entries = payload["entries"]
    length_buckets = set()
    for entry in entries:
        assert entry.get("id"), "id required"
        assert entry.get("source_type"), "source_type required"
        assert str(entry.get("text") or "").strip(), "text required"
        length = str(entry.get("length_bucket") or "")
        assert length in _ALLOWED_LENGTH_BUCKETS, f"invalid length_bucket: {length}"
        length_buckets.add(length)
        assert isinstance(entry.get("expected_classes"), list)
        assert isinstance(entry.get("expected_policies"), list)
        assert "provenance" in entry
    assert length_buckets.issuperset({"short", "medium", "long"})
