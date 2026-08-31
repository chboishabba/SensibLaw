from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.pnf.packed_sentence_fibre import pack_spacy_partition
from src.pnf.parser_authority_projection import (
    ObservationRole,
    project_sentence_authority,
)
from src.pnf.parser_schedule_parity import (
    assert_schedule_authority_parity,
    observe_owned_schedule,
)


class _Morph:
    def to_dict(self) -> dict[str, str]:
        return {}


class _Token:
    def __init__(self, idx: int, text: str, dep: str = "ROOT") -> None:
        self.idx = idx
        self.text = text
        self.lemma_ = text.lower().strip(".")
        self.pos_ = "VERB"
        self.tag_ = "VB"
        self.dep_ = dep
        self.morph = _Morph()
        self.head = self


class _Span:
    def __init__(self, start_char: int, end_char: int, tokens: tuple[_Token, ...]) -> None:
        self.start_char = start_char
        self.end_char = end_char
        self._tokens = tokens

    def __iter__(self):
        return iter(self._tokens)


class _Doc:
    def __init__(self) -> None:
        self.text = "Alpha beta. Gamma delta."
        a = _Token(0, "Alpha")
        b = _Token(6, "beta.")
        b.head = a
        c = _Token(12, "Gamma")
        d = _Token(18, "delta.")
        d.head = c
        self.sents = (
            _Span(0, 11, (a, b)),
            _Span(12, len(self.text), (c, d)),
        )
        self.ents = ()

    def has_annotation(self, name: str) -> bool:
        return name == "SENT_START"


class _TruncatedDoc:
    def __init__(self) -> None:
        self.text = "Alpha beta"
        a = _Token(0, "Alpha")
        b = _Token(6, "beta")
        b.head = a
        self.sents = (_Span(0, len(self.text), (a, b)),)
        self.ents = ()

    def has_annotation(self, name: str) -> bool:
        return name == "SENT_START"


class _CompletedDoc:
    def __init__(self) -> None:
        self.text = "Alpha beta. tail"
        a = _Token(0, "Alpha")
        b = _Token(6, "beta.")
        b.head = a
        tail = _Token(12, "tail")
        self.sents = (
            _Span(0, 11, (a, b)),
            _Span(12, len(self.text), (tail,)),
        )
        self.ents = ()

    def has_annotation(self, name: str) -> bool:
        return name == "SENT_START"


@dataclass(frozen=True)
class _Partition:
    run_ref: str = "run"
    document_ref: str = "doc"
    partition_kind: str = "structural"
    context_start_char: int = 0
    context_end_char: int = len(_Doc().text)
    context_start_byte: int = 0
    owner_start_char: int = 0
    owner_end_char: int = 1


def _owned_fibres(partitions: tuple[_Partition, ...]):
    doc = _Doc()
    return tuple(
        fibre
        for partition in partitions
        for fibre in pack_spacy_partition(
            partition,
            doc,
            context_reaches_source_end=(partition.context_end_char == len(doc.text)),
        ).sentences
    )


def _owned_signature(partitions: tuple[_Partition, ...]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            fibre.start_char,
            fibre.end_char,
            fibre.sentence_digest,
            tuple(token.evidence_digest for token in fibre.tokens),
        )
        for fibre in sorted(_owned_fibres(partitions), key=lambda item: item.start_char)
    )


def test_crossing_sentence_has_one_structural_start_anchor_owner() -> None:
    left = _Partition(owner_start_char=0, owner_end_char=7)
    right = _Partition(owner_start_char=7, owner_end_char=len(_Doc().text))

    left_projection = project_sentence_authority(left, start_char=0)
    right_projection = project_sentence_authority(right, start_char=0)

    assert left_projection.role is ObservationRole.STRUCTURAL_OWNER
    assert left_projection.authority_bearing is True
    assert right_projection.role is ObservationRole.STRUCTURAL_CONTEXT
    assert right_projection.authority_bearing is False

    left_packed = pack_spacy_partition(left, _Doc())
    right_packed = pack_spacy_partition(right, _Doc())
    assert [f.start_char for f in left_packed.sentences] == [0]
    assert [f.start_char for f in right_packed.sentences] == [12]
    assert left_packed.boundary_obligations


def test_context_edge_owned_sentence_defers_until_completion() -> None:
    truncated = _Partition(
        owner_start_char=0,
        owner_end_char=7,
        context_end_char=len(_TruncatedDoc().text),
    )
    packed = pack_spacy_partition(truncated, _TruncatedDoc())

    assert packed.sentences == ()
    assert packed.boundary_obligations
    assert packed.observed_sentences[0].touches_context_end is True


def test_completed_evidence_can_publish_under_same_start_anchor_owner() -> None:
    completed = _Partition(
        owner_start_char=0,
        owner_end_char=7,
        context_end_char=len(_CompletedDoc().text),
    )
    packed = pack_spacy_partition(completed, _CompletedDoc())

    assert [f.start_char for f in packed.sentences] == [0]
    assert packed.sentences[0].end_char == 11
    assert packed.observed_sentences[0].touches_context_end is False


def test_boundary_repair_is_observation_only() -> None:
    repair = _Partition(
        partition_kind="boundary_repair",
        owner_start_char=0,
        owner_end_char=11,
    )
    packed = pack_spacy_partition(repair, _Doc())

    assert packed.sentences == ()
    assert packed.boundary_obligations == ()
    assert [(row.start_char, row.end_char) for row in packed.observed_sentences] == [
        (0, 11)
    ]


def test_owned_semantic_stream_is_invariant_under_physical_partition_refinement() -> None:
    source_end = len(_Doc().text)
    coarse = (
        _Partition(owner_start_char=0, owner_end_char=12),
        _Partition(owner_start_char=12, owner_end_char=source_end),
    )
    refined = (
        _Partition(owner_start_char=0, owner_end_char=7),
        _Partition(owner_start_char=7, owner_end_char=17),
        _Partition(owner_start_char=17, owner_end_char=source_end),
    )

    assert _owned_signature(coarse) == _owned_signature(refined)
    coarse_observation = observe_owned_schedule(_owned_fibres(coarse))
    refined_observation = observe_owned_schedule(_owned_fibres(refined))
    assert_schedule_authority_parity(coarse_observation, refined_observation)


def test_schedule_parity_fails_closed_on_changed_owned_sentence_authority() -> None:
    source_end = len(_Doc().text)
    coarse = (
        _Partition(owner_start_char=0, owner_end_char=12),
        _Partition(owner_start_char=12, owner_end_char=source_end),
    )
    coarse_observation = observe_owned_schedule(_owned_fibres(coarse))

    with pytest.raises(RuntimeError, match="performance comparison is forbidden"):
        assert_schedule_authority_parity(coarse_observation, coarse_observation[:-1])


def test_physical_partition_identity_does_not_enter_evidence_digest() -> None:
    doc = _Doc()
    a = _Partition(owner_start_char=0, owner_end_char=12)
    b = _Partition(owner_start_char=0, owner_end_char=7)

    evidence_a = tuple(
        token.evidence_digest
        for token in pack_spacy_partition(a, doc).sentences[0].tokens
    )
    evidence_b = tuple(
        token.evidence_digest
        for token in pack_spacy_partition(b, doc).sentences[0].tokens
    )
    assert evidence_a == evidence_b
