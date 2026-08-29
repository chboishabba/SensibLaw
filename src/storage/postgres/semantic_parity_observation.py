"""Canonical parity surface for local and legacy SQL sentence composition.

Raw numeric digests are intentionally not compared: legacy composition hashes
allocated database ids, while direct composition hashes stable local ids.  The
parity surface instead resolves both carriers to typed symbol text and source
spans, then compares the complete object/factor/demand structure before PNF
publication.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.pnf.numeric_operator_composition import (
    NumericSentenceClosure,
    NumericToken,
    compose_numeric_sentence,
)
from src.storage.postgres.numeric_hyperfabric_store import (
    _load_sentence_tokens,
    _operator_lexicon,
)
from src.storage.postgres.numeric_symbol_store import load_symbol_texts
from src.storage.postgres.sentence_hyperfabric import (
    LocalSentenceComposition,
    compile_doc_sentences,
)
from src.storage.postgres.spacy_parser_model import ParserPartition, connect


def _symbol_ids(closure: NumericSentenceClosure) -> set[int]:
    values: set[int] = set()
    for row in closure.objects:
        values.update((row.object_kind_symbol_id, row.head_symbol_id))
    for row in closure.factors:
        values.update((row.factor_type_symbol_id, row.predicate_symbol_id))
        values.update(slot.role_symbol_id for slot in row.slots)
        values.update(row.residual_symbol_ids)
    for row in closure.demands:
        values.add(row.residual_type_symbol_id)
        for value in (
            row.expected_factor_type_symbol_id,
            row.expected_object_kind_symbol_id,
            row.lexical_symbol_id,
            row.role_symbol_id,
        ):
            if value is not None:
                values.add(value)
    return values


def canonical_closure_observation(
    closure: NumericSentenceClosure,
    *,
    tokens: Sequence[NumericToken],
    symbol_text_by_id: Mapping[int, str],
) -> tuple[object, ...]:
    spans = {
        token.token_id: (token.start_char, token.end_char)
        for token in tokens
    }

    def text(symbol_id: int | None) -> str | None:
        if symbol_id is None:
            return None
        try:
            return str(symbol_text_by_id[int(symbol_id)])
        except KeyError as error:
            raise RuntimeError(f"parity observation lost symbol {int(symbol_id)}") from error

    def span(token_id: int) -> tuple[int, int]:
        try:
            return spans[int(token_id)]
        except KeyError as error:
            raise RuntimeError(f"parity observation lost token {int(token_id)}") from error

    objects = tuple(
        (
            span(row.source_token_id),
            text(row.object_kind_symbol_id),
            text(row.head_symbol_id),
            row.information_gain,
            row.representation_cost,
            row.ambiguity_cost,
            row.promotion_evidence,
        )
        for row in closure.objects
    )
    factors = tuple(
        (
            text(row.factor_type_symbol_id),
            text(row.predicate_symbol_id),
            row.modal_state,
            row.temporal_state,
            tuple(
                (
                    text(slot.role_symbol_id),
                    span(slot.source_token_id),
                    int(slot.resolution_state),
                    slot.required,
                )
                for slot in row.slots
            ),
            tuple(span(token_id) for token_id in row.support_token_ids),
            tuple(text(symbol_id) for symbol_id in row.residual_symbol_ids),
            row.support_score,
        )
        for row in closure.factors
    )
    demands = tuple(
        (
            int(row.expected_target_kind),
            text(row.expected_factor_type_symbol_id),
            text(row.expected_object_kind_symbol_id),
            text(row.lexical_symbol_id),
            text(row.role_symbol_id),
            text(row.residual_type_symbol_id),
            int(row.recency_class),
            row.max_candidates,
        )
        for row in closure.demands
    )
    return (objects, factors, demands, closure.measure)


def local_parity_observations(
    *,
    partition: ParserPartition,
    doc: Any,
) -> dict[bytes, tuple[object, ...]]:
    result: dict[bytes, tuple[object, ...]] = {}
    for composition in compile_doc_sentences(partition=partition, doc=doc):
        symbols = {
            binding.local_ref: binding.text
            for binding in composition.symbol_bindings
        }
        result[composition.sentence_digest] = canonical_closure_observation(
            composition.closure,
            tokens=composition.tokens,
            symbol_text_by_id=symbols,
        )
    return result


def reference_parity_observations(
    database_url: str,
    *,
    partition: ParserPartition,
) -> dict[bytes, tuple[object, ...]]:
    """Read the actual committed legacy carrier and compose it without persisting PNF."""

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                lexicon = _operator_lexicon(cursor, database_url)
                cursor.execute(
                    """
                    SELECT sentence.sentence_digest, link.region_id
                      FROM execution.semantic_parser_sentence AS sentence
                      JOIN execution.semantic_pnf_sentence_region AS link
                        ON link.sentence_id = sentence.sentence_id
                     WHERE sentence.partition_ref = %s
                       AND sentence.representation_version = 2
                     ORDER BY sentence.local_sentence_ordinal, sentence.sentence_id
                    """,
                    (partition.partition_ref,),
                )
                rows = tuple(cursor.fetchall())
                result: dict[bytes, tuple[object, ...]] = {}
                for sentence_digest, region_id in rows:
                    tokens = _load_sentence_tokens(cursor, int(region_id))
                    closure = compose_numeric_sentence(
                        region_id=int(region_id),
                        tokens=tokens,
                        lexicon=lexicon,
                    )
                    symbol_texts = load_symbol_texts(cursor, _symbol_ids(closure))
                    result[bytes(sentence_digest)] = canonical_closure_observation(
                        closure,
                        tokens=tokens,
                        symbol_text_by_id=symbol_texts,
                    )
                return result
    finally:
        connection.close()


__all__ = [
    "canonical_closure_observation",
    "local_parity_observations",
    "reference_parity_observations",
]
