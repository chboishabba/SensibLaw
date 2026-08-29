from __future__ import annotations

from types import SimpleNamespace

from src.pnf.numeric_hyperfabric import SymbolKind
from src.storage.postgres import sentence_hyperfabric as subject


def test_local_addresses_are_positive_stable_and_domain_separated() -> None:
    digest = bytes(range(32))
    assert subject.stable_sentence_region_ref(digest) == subject.stable_sentence_region_ref(digest)
    assert subject.stable_token_ref(digest) == subject.stable_token_ref(digest)
    assert subject.stable_sentence_region_ref(digest) > 0
    assert subject.stable_token_ref(digest) > 0
    assert subject.stable_sentence_region_ref(digest) != subject.stable_token_ref(digest)
    assert subject.stable_symbol_ref(SymbolKind.LEMMA, "shall") == subject.stable_symbol_ref(
        SymbolKind.LEMMA, "shall"
    )
    assert subject.stable_symbol_ref(SymbolKind.LEMMA, "shall") != subject.stable_symbol_ref(
        SymbolKind.LEMMA, "may"
    )


def test_compile_doc_sentences_needs_no_database_identity(monkeypatch) -> None:
    sentence_digest = b"s" * 32
    token_digest = b"t" * 32
    sentence = SimpleNamespace(
        sentence_ref="parser-sentence:local",
        sentence_digest=sentence_digest,
    )
    token = SimpleNamespace(
        sentence_ref=sentence.sentence_ref,
        token_digest=token_digest,
        start_char=10,
        end_char=15,
        head_start_char=10,
        head_end_char=15,
        head_is_self=True,
        orth="shall",
        lemma="shall",
        pos="AUX",
        tag="MD",
        dependency="aux",
        morphology=(),
    )
    monkeypatch.setattr(
        subject,
        "_collect_doc",
        lambda partition, doc: ((sentence,), (token,), (), (), ()),
    )
    captured = {}

    def fake_compose(*, region_id, tokens, lexicon):
        captured["region_id"] = region_id
        captured["tokens"] = tokens
        return SimpleNamespace(objects=(), factors=(), demands=())

    monkeypatch.setattr(subject, "compose_numeric_sentence", fake_compose)
    result = subject.compile_doc_sentences(partition=object(), doc=object())

    assert len(result) == 1
    assert result[0].region_ref == subject.stable_sentence_region_ref(sentence_digest)
    assert result[0].tokens[0].token_id == subject.stable_token_ref(token_digest)
    assert result[0].tokens[0].head_token_id == result[0].tokens[0].token_id
    assert captured["region_id"] == result[0].region_ref
    assert result[0].token_digests == ((result[0].tokens[0].token_id, token_digest),)
