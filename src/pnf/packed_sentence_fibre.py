"""Database-neutral packed sentence fibres produced directly from spaCy output.

This is the G1 carrier boundary. It intentionally imports no PostgreSQL code:
parser observations receive stable typed evidence identities and fibre-local
head addresses before any durable projection exists.

Physical parser observation is not semantic authority. Structural partitions own
sentence authority by canonical sentence-start coordinate; bilateral context and
boundary-repair partitions are evidence-only. See
``ExactlyOnceParserAuthorityProjectionExact.agda`` and
``ParserBoundaryCompletionExact.agda``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.pnf.numeric_hyperfabric import numeric_digest
from src.pnf.parser_authority_projection import project_sentence_authority


class PartitionView(Protocol):
    run_ref: str
    document_ref: str
    partition_kind: str
    context_start_char: int
    context_end_char: int
    context_start_byte: int
    owner_start_char: int
    owner_end_char: int


@dataclass(frozen=True, slots=True)
class PackedSourceToken:
    local_id: int
    evidence_digest: bytes
    ordinal: int
    start_char: int
    end_char: int
    start_byte: int
    end_byte: int
    orth: str
    lemma: str
    pos: str
    tag: str
    dependency: str
    head_local_id: int
    morphology: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class PackedSentenceFibre:
    sentence_digest: bytes
    ordinal: int
    start_char: int
    end_char: int
    start_byte: int
    end_byte: int
    tokens: tuple[PackedSourceToken, ...]


@dataclass(frozen=True, slots=True)
class PackedObservedSentence:
    """Non-authoritative parser observation used only for boundary resolution."""

    start_char: int
    end_char: int
    start_byte: int
    end_byte: int
    touches_context_end: bool = False


@dataclass(frozen=True, slots=True)
class PackedPartitionFibres:
    sentences: tuple[PackedSentenceFibre, ...]
    boundary_obligations: tuple[tuple[int, int, int, int], ...]
    observed_sentences: tuple[PackedObservedSentence, ...] = ()


def _byte_offsets(text: str, offsets: set[int]) -> dict[int, int]:
    ordered = sorted(offsets)
    result: dict[int, int] = {}
    byte_count = 0
    previous = 0
    for offset in ordered:
        if offset < previous or offset > len(text):
            raise ValueError(f"invalid character offset {offset}")
        byte_count += len(text[previous:offset].encode("utf-8"))
        result[offset] = byte_count
        previous = offset
    return result


def pack_spacy_partition(partition: PartitionView, doc: Any) -> PackedPartitionFibres:
    """Project spaCy observations to exactly-once owned sentence fibres.

    A structural partition owns a sentence iff the sentence's canonical start
    coordinate lies in that partition's disjoint owner interval. A sentence may
    extend beyond the physical owner boundary only when the parser context
    contains a complete observation. If an owned sentence terminates exactly at
    a non-owner context edge, publication is deferred until boundary-completion
    evidence supplies a complete view. Context-only and repair observations
    never independently enter the semantic compiler.
    """

    spans = tuple(doc.sents) if doc.has_annotation("SENT_START") else (doc[:],)
    wanted: set[int] = {0, len(doc.text)}
    for span in spans:
        wanted.update((int(span.start_char), int(span.end_char)))
        for token in span:
            wanted.update((int(token.idx), int(token.idx + len(token.text))))
    local_bytes = _byte_offsets(doc.text, wanted)

    fibres: list[PackedSentenceFibre] = []
    boundary: list[tuple[int, int, int, int]] = []
    observed: list[PackedObservedSentence] = []
    owned_ordinal = 0
    for span in spans:
        local_start = int(span.start_char)
        local_end = int(span.end_char)
        start_char = partition.context_start_char + local_start
        end_char = partition.context_start_char + local_end
        start_byte = partition.context_start_byte + local_bytes[local_start]
        end_byte = partition.context_start_byte + local_bytes[local_end]
        overlaps_owner = (
            start_char < partition.owner_end_char
            and end_char > partition.owner_start_char
        )
        if not overlaps_owner:
            continue

        touches_context_end = (
            local_end == len(doc.text)
            and end_char == int(partition.context_end_char)
        )
        observed.append(
            PackedObservedSentence(
                start_char=start_char,
                end_char=end_char,
                start_byte=start_byte,
                end_byte=end_byte,
                touches_context_end=touches_context_end,
            )
        )
        projection = project_sentence_authority(partition, start_char=start_char)

        crossing_owner = (
            start_char < partition.owner_start_char
            or end_char > partition.owner_end_char
        )
        if str(partition.partition_kind) == "structural" and crossing_owner:
            boundary.append((start_char, end_char, start_byte, end_byte))

        if not projection.authority_bearing:
            continue

        # A start-owned sentence reaching the right parser-context edge while
        # extending beyond its owner interval may be a truncated spaCy sentence.
        # Keep the owner, but defer publication until a wider evidence-only
        # observation completes it. The document-final owner does not trigger
        # this condition because its owner/context ends coincide.
        if touches_context_end and end_char > partition.owner_end_char:
            if (start_char, end_char, start_byte, end_byte) not in boundary:
                boundary.append((start_char, end_char, start_byte, end_byte))
            continue

        sentence_digest = numeric_digest(
            partition.run_ref.encode("utf-8"),
            partition.document_ref.encode("utf-8"),
            start_char,
            end_char,
            2,
        )
        span_tokens = tuple(span)
        local_by_start = {int(token.idx): index for index, token in enumerate(span_tokens)}
        packed: list[PackedSourceToken] = []
        for ordinal, token in enumerate(span_tokens):
            local_token_start = int(token.idx)
            local_token_end = int(token.idx + len(token.text))
            token_start = partition.context_start_char + local_token_start
            token_end = partition.context_start_char + local_token_end
            pos = str(token.pos_)
            dependency = str(token.dep_)
            if not pos or not dependency:
                raise RuntimeError(
                    f"strict numeric PNF token lacks typed parser annotation at {token_start}"
                )
            head_local_id = local_by_start.get(int(token.head.idx))
            if head_local_id is None:
                raise RuntimeError(
                    "declared dependency head is outside its packed sentence fibre"
                )
            morphology = tuple(
                sorted(
                    (str(feature), str(value))
                    for feature, raw_values in token.morph.to_dict().items()
                    for value in (
                        raw_values if isinstance(raw_values, (list, tuple)) else (raw_values,)
                    )
                )
            )
            evidence_digest = numeric_digest(
                b"source-token-evidence:v2",
                sentence_digest,
                token_start,
                token_end,
            )
            packed.append(
                PackedSourceToken(
                    local_id=ordinal,
                    evidence_digest=evidence_digest,
                    ordinal=ordinal,
                    start_char=token_start,
                    end_char=token_end,
                    start_byte=partition.context_start_byte + local_bytes[local_token_start],
                    end_byte=partition.context_start_byte + local_bytes[local_token_end],
                    orth=str(token.text),
                    lemma=str(token.lemma_) if token.lemma_ else str(token.text),
                    pos=pos,
                    tag=str(token.tag_) if token.tag_ else pos,
                    dependency=dependency,
                    head_local_id=head_local_id,
                    morphology=morphology,
                )
            )
        fibres.append(
            PackedSentenceFibre(
                sentence_digest=sentence_digest,
                ordinal=owned_ordinal,
                start_char=start_char,
                end_char=end_char,
                start_byte=start_byte,
                end_byte=end_byte,
                tokens=tuple(packed),
            )
        )
        owned_ordinal += 1
    return PackedPartitionFibres(
        tuple(fibres),
        tuple(boundary),
        tuple(observed),
    )


__all__ = [
    "PackedObservedSentence",
    "PackedPartitionFibres",
    "PackedSentenceFibre",
    "PackedSourceToken",
    "PartitionView",
    "pack_spacy_partition",
]
