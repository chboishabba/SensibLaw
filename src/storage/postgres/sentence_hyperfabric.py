"""DB-free sentence-local numeric PNF composition.

spaCy observations are converted to deterministic fibre-local integer addresses.
No PostgreSQL connection, sequence, or parser-token row participates in the
semantic identity. Database ids are a later publication concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.pnf.numeric_hyperfabric import SymbolKind, numeric_digest
from src.pnf.numeric_operator_composition import (
    NumericSentenceClosure,
    NumericToken,
    OperatorLexicon,
    build_operator_lexicon,
    compose_numeric_sentence,
    operator_symbol_values,
)
from src.storage.postgres.spacy_numeric_projection import _collect_doc
from src.storage.postgres.spacy_parser_model import ParserPartition


@dataclass(frozen=True, slots=True)
class LocalSymbolBinding:
    """Typed lexical boundary retained solely for publication reindexing."""

    local_ref: int
    kind: SymbolKind
    text: str


@dataclass(frozen=True, slots=True)
class LocalSourceEvidence:
    """Stable source observation independent of parser-token database identity."""

    local_token_ref: int
    evidence_digest: bytes
    token_digest: bytes
    start_char: int
    end_char: int


@dataclass(frozen=True, slots=True)
class LocalSentenceComposition:
    """One sentence's stable local carrier and composed semantic closure."""

    sentence_digest: bytes
    ordinal: int
    start_char: int
    end_char: int
    region_ref: int
    tokens: tuple[NumericToken, ...]
    source_evidence: tuple[LocalSourceEvidence, ...]
    symbol_bindings: tuple[LocalSymbolBinding, ...]
    closure: NumericSentenceClosure


def _positive_ref(domain: bytes, *parts: object) -> int:
    digest = numeric_digest(domain, *parts)
    value = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    return value or 1


def stable_sentence_region_ref(sentence_digest: bytes) -> int:
    """Return a deterministic non-database region address."""

    return _positive_ref(b"semantic_pnf_sentence_region_v1", bytes(sentence_digest))


def stable_token_ref(token_digest: bytes) -> int:
    return _positive_ref(b"semantic_parser_token_local_v1", bytes(token_digest))


def stable_symbol_ref(kind: SymbolKind, text: str) -> int:
    return _positive_ref(
        b"semantic_symbol_local_v1",
        int(kind),
        text.encode("utf-8"),
    )


def stable_source_evidence_digest(
    *,
    sentence_digest: bytes,
    token_digest: bytes,
    start_char: int,
    end_char: int,
) -> bytes:
    return numeric_digest(
        b"semantic_pnf_source_evidence_v1",
        bytes(sentence_digest),
        bytes(token_digest),
        int(start_char),
        int(end_char),
        1,
    )


def _local_lexicon() -> OperatorLexicon:
    symbols = {
        (kind, text): stable_symbol_ref(kind, text)
        for kind, text in operator_symbol_values()
    }
    return build_operator_lexicon(symbols)


def _binding(kind: SymbolKind, text: str) -> LocalSymbolBinding:
    return LocalSymbolBinding(
        local_ref=stable_symbol_ref(kind, text),
        kind=kind,
        text=text,
    )


def compile_doc_sentences(
    *,
    partition: ParserPartition,
    doc: Any,
) -> tuple[LocalSentenceComposition, ...]:
    """Compose all owned sentences in ``doc`` without touching PostgreSQL."""

    sentences, raw_tokens, _entities, _crossings, _symbols = _collect_doc(partition, doc)
    lexicon = _local_lexicon()
    raw_by_sentence: dict[str, list[Any]] = {}
    for raw in raw_tokens:
        raw_by_sentence.setdefault(raw.sentence_ref, []).append(raw)

    operator_bindings = {
        (int(kind), text): _binding(kind, text)
        for kind, text in operator_symbol_values()
    }
    composed: list[LocalSentenceComposition] = []
    for sentence in sentences:
        raws = tuple(raw_by_sentence.get(sentence.sentence_ref, ()))
        token_id_by_span = {
            (raw.start_char, raw.end_char): stable_token_ref(raw.token_digest)
            for raw in raws
        }
        tokens: list[NumericToken] = []
        evidence: list[LocalSourceEvidence] = []
        bindings = dict(operator_bindings)
        for raw in raws:
            token_id = token_id_by_span[(raw.start_char, raw.end_char)]
            declared_head = (raw.head_start_char, raw.head_end_char)
            head_token_id = (
                token_id
                if raw.head_is_self
                else token_id_by_span.get(declared_head, token_id)
            )
            for kind, text in (
                (SymbolKind.ORTH, raw.orth),
                (SymbolKind.LEMMA, raw.lemma),
                (SymbolKind.POS, raw.pos),
                (SymbolKind.TAG, raw.tag),
                (SymbolKind.DEPENDENCY, raw.dependency),
            ):
                bindings[(int(kind), text)] = _binding(kind, text)
            tokens.append(
                NumericToken(
                    token_id=token_id,
                    orth_id=stable_symbol_ref(SymbolKind.ORTH, raw.orth),
                    lemma_id=stable_symbol_ref(SymbolKind.LEMMA, raw.lemma),
                    pos_id=stable_symbol_ref(SymbolKind.POS, raw.pos),
                    tag_id=stable_symbol_ref(SymbolKind.TAG, raw.tag),
                    dependency_id=stable_symbol_ref(
                        SymbolKind.DEPENDENCY, raw.dependency
                    ),
                    head_token_id=head_token_id,
                    morph_set_id=(
                        _positive_ref(b"semantic_morph_set_local_v1", raw.morphology)
                        if raw.morphology
                        else None
                    ),
                    start_char=raw.start_char,
                    end_char=raw.end_char,
                )
            )
            evidence.append(
                LocalSourceEvidence(
                    local_token_ref=token_id,
                    evidence_digest=stable_source_evidence_digest(
                        sentence_digest=sentence.sentence_digest,
                        token_digest=raw.token_digest,
                        start_char=raw.start_char,
                        end_char=raw.end_char,
                    ),
                    token_digest=raw.token_digest,
                    start_char=raw.start_char,
                    end_char=raw.end_char,
                )
            )
        token_tuple = tuple(
            sorted(tokens, key=lambda token: (token.start_char, token.end_char))
        )
        region_ref = stable_sentence_region_ref(sentence.sentence_digest)
        closure = compose_numeric_sentence(
            region_id=region_ref,
            tokens=token_tuple,
            lexicon=lexicon,
        )
        composed.append(
            LocalSentenceComposition(
                sentence_digest=sentence.sentence_digest,
                ordinal=sentence.ordinal,
                start_char=sentence.start_char,
                end_char=sentence.end_char,
                region_ref=region_ref,
                tokens=token_tuple,
                source_evidence=tuple(
                    sorted(evidence, key=lambda row: (row.start_char, row.end_char))
                ),
                symbol_bindings=tuple(
                    sorted(
                        bindings.values(),
                        key=lambda row: (int(row.kind), row.text, row.local_ref),
                    )
                ),
                closure=closure,
            )
        )
    return tuple(composed)


def closure_digest_observation(
    composition: LocalSentenceComposition,
) -> tuple[tuple[bytes, ...], tuple[bytes, ...], tuple[bytes, ...]]:
    """Return the stable direct digest surface for publication checks."""

    return (
        tuple(row.object_digest for row in composition.closure.objects),
        tuple(row.factor_digest for row in composition.closure.factors),
        tuple(row.demand_digest for row in composition.closure.demands),
    )


__all__ = [
    "LocalSentenceComposition",
    "LocalSourceEvidence",
    "LocalSymbolBinding",
    "closure_digest_observation",
    "compile_doc_sentences",
    "stable_sentence_region_ref",
    "stable_source_evidence_digest",
    "stable_symbol_ref",
    "stable_token_ref",
]
