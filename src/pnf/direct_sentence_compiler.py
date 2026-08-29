"""Pure packed-fibre adapter for the existing numeric sentence composer.

No PostgreSQL import is permitted here.  The adapter gives lexical and source
evidence values deterministic local numeric identities, then reuses
``compose_numeric_sentence`` unchanged as the semantic owner.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.pnf.numeric_hyperfabric import SymbolKind, numeric_digest
from src.pnf.numeric_operator_composition import (
    NumericSentenceClosure,
    NumericToken,
    build_operator_lexicon,
    compose_numeric_sentence,
    operator_symbol_values,
)
from src.pnf.packed_sentence_fibre import PackedSentenceFibre


@dataclass(frozen=True, slots=True)
class DirectSentenceCompileReceipt:
    closure: NumericSentenceClosure
    source_evidence_ids: tuple[tuple[int, bytes], ...]
    symbol_ids: tuple[tuple[SymbolKind, str, int], ...]
    database_crossings: int = 0


def _stable_positive_id(kind: bytes, *parts: bytes) -> int:
    raw = numeric_digest(kind, *parts)
    value = int.from_bytes(raw[:8], "big") & ((1 << 63) - 1)
    return value or 1


def source_evidence_id(digest: bytes) -> int:
    return _stable_positive_id(b"source-token-evidence-id:v1", digest)


def _symbol_id(kind: SymbolKind, text: str) -> int:
    return _stable_positive_id(
        b"fibre-symbol-id:v1",
        int(kind).to_bytes(2, "big", signed=False),
        text.encode("utf-8"),
    )


def compile_packed_sentence(
    *,
    region_id: int,
    fibre: PackedSentenceFibre,
) -> DirectSentenceCompileReceipt:
    """Execute the existing sentence semantics entirely in memory."""

    values = set(operator_symbol_values())
    for token in fibre.tokens:
        values.update(
            {
                (SymbolKind.ORTH, token.orth),
                (SymbolKind.LEMMA, token.lemma),
                (SymbolKind.POS, token.pos),
                (SymbolKind.TAG, token.tag),
                (SymbolKind.DEPENDENCY, token.dependency),
            }
        )
    symbols = {(kind, text): _symbol_id(kind, text) for kind, text in values}
    inverse: dict[int, tuple[SymbolKind, str]] = {}
    for key, value in symbols.items():
        prior = inverse.setdefault(value, key)
        if prior != key:
            raise RuntimeError(
                f"stable fibre symbol collision: {prior!r} and {key!r} -> {value}"
            )
    lexicon = build_operator_lexicon(symbols)

    evidence_by_local = {
        token.local_id: source_evidence_id(token.evidence_digest) for token in fibre.tokens
    }
    inverse_evidence: dict[int, bytes] = {}
    for token in fibre.tokens:
        evidence_id = evidence_by_local[token.local_id]
        prior = inverse_evidence.setdefault(evidence_id, token.evidence_digest)
        if prior != token.evidence_digest:
            raise RuntimeError("stable source-evidence id collision")

    numeric_tokens = tuple(
        NumericToken(
            token_id=evidence_by_local[token.local_id],
            orth_id=symbols[(SymbolKind.ORTH, token.orth)],
            lemma_id=symbols[(SymbolKind.LEMMA, token.lemma)],
            pos_id=symbols[(SymbolKind.POS, token.pos)],
            tag_id=symbols[(SymbolKind.TAG, token.tag)],
            dependency_id=symbols[(SymbolKind.DEPENDENCY, token.dependency)],
            head_token_id=evidence_by_local[token.head_local_id],
            morph_set_id=(
                _stable_positive_id(
                    b"fibre-morph-set-id:v1",
                    repr(token.morphology).encode("utf-8"),
                )
                if token.morphology
                else None
            ),
            start_char=token.start_char,
            end_char=token.end_char,
        )
        for token in fibre.tokens
    )
    closure = compose_numeric_sentence(
        region_id=region_id,
        tokens=numeric_tokens,
        lexicon=lexicon,
    )
    return DirectSentenceCompileReceipt(
        closure=closure,
        source_evidence_ids=tuple(
            sorted((evidence_by_local[token.local_id], token.evidence_digest) for token in fibre.tokens)
        ),
        symbol_ids=tuple(
            sorted(
                ((kind, text, value) for (kind, text), value in symbols.items()),
                key=lambda row: (int(row[0]), row[1]),
            )
        ),
    )


__all__ = [
    "DirectSentenceCompileReceipt",
    "compile_packed_sentence",
    "source_evidence_id",
]
