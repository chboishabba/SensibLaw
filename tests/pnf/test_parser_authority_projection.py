from __future__ import annotations

from dataclasses import dataclass

from src.pnf.packed_sentence_fibre import pack_spacy_partition
from src.pnf.parser_authority_projection import (
    ObservationRole,
    project_sentence_authority,
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


@dataclass(frozen=True)
class _Partition:
    run_ref: str = "run"
    document_ref: str = "doc"
    partition_kind: str = "structural"
    context_start_char: int = 0
    context_start_byte: int = 0
    owner_start_char: int = 0
    owner_end_char: int = 1


def _owned_signature(partitions: tuple[_Partition, ...]) -> tuple[tuple[object, ...], ...]:
    doc = _Doc()
    fibres = tuple(
        fibre
        for partition in partitions
        for fibre in pack_spacy_partition(partition, doc).sentences
    )
    return tuple(
        (
            fibre.start_char,
            fibre.end_char,
            fibre.sentence_digest,
            tuple(token.evidence_digest for token in fibre.tokens),
        )
        for fibre in sorted(fibres, key=lambda item: item.start_char)
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
