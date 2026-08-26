#!/usr/bin/env python3
"""Read-only corpus parity/timing check for packed normative composition.

The benchmark reconstructs the same strict-v2 sentence fibres used by the
layout benchmark, solves normative/modal factors directly from packed local
memory, applies authoritative database token ids only at materialization, and
compares the result with the normative projection of ``compose_numeric_sentence``.

No symbol interning, authority publication, or database mutation is performed.
Synthetic region ids are used only so both sides receive identical digest
inputs; this benchmark does not claim those ids as database authority.
"""

from __future__ import annotations

import argparse
import json
from time import monotonic_ns
from typing import Any

from scripts.benchmark_fibre_local_numeric_layout import _load_sentences
from src.pnf.fibre_local_numeric import pack_sentence_fibre
from src.pnf.fibre_local_relational_bridge import localize_relational_sentence
from src.pnf.numeric_hyperfabric import SymbolKind
from src.pnf.numeric_operator_composition import (
    NumericToken,
    build_operator_lexicon,
    compose_numeric_sentence,
    operator_symbol_values,
)
from src.pnf.packed_numeric_composition import (
    MaterializedNormativeDelta,
    compose_packed_normative_delta,
    materialize_normative_delta,
)
from src.storage.postgres.numeric_symbol_store import normalize_symbol
from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.packed-normative-parity.v0_1"


def _load_operator_lexicon(database_url: str):
    requested = {
        (SymbolKind(kind), normalize_symbol(SymbolKind(kind), text))
        for kind, text in operator_symbol_values()
    }
    kinds = sorted({int(kind) for kind, _text in requested})
    texts = sorted({text for _kind, text in requested})

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    SELECT kind_id, symbol_text, symbol_id
                      FROM execution.semantic_symbol
                     WHERE kind_id = ANY(%s)
                       AND symbol_text = ANY(%s)
                    """,
                    (kinds, texts),
                )
                rows = cursor.fetchall()
    finally:
        connection.close()

    symbols = {
        (SymbolKind(int(kind_id)), str(text)): int(symbol_id)
        for kind_id, text, symbol_id in rows
        if (SymbolKind(int(kind_id)), str(text)) in requested
    }
    missing = sorted(
        requested - set(symbols),
        key=lambda item: (int(item[0]), item[1]),
    )
    if missing:
        raise RuntimeError(f"operator lexicon symbols missing from authority: {missing!r}")
    return build_operator_lexicon(symbols)


def _reference_tokens(sentence) -> tuple[NumericToken, ...]:
    return tuple(
        NumericToken(
            token_id=row.token_id,
            orth_id=row.orth_symbol_id,
            lemma_id=row.lemma_symbol_id,
            pos_id=row.pos_symbol_id,
            tag_id=row.tag_symbol_id,
            dependency_id=row.dependency_symbol_id,
            head_token_id=row.head_token_id,
            morph_set_id=row.morph_set_id or None,
            start_char=row.start_char,
            end_char=row.end_char,
        )
        for row in sorted(sentence.tokens, key=lambda item: item.local_token_ordinal)
    )


def _reference_normative_projection(reference, normative_factor_type_id: int):
    factors = tuple(
        factor
        for factor in reference.factors
        if factor.factor_type_symbol_id == normative_factor_type_id
    )
    participating_token_ids = {
        slot.source_token_id for factor in factors for slot in factor.slots
    }
    objects = tuple(
        obj for obj in reference.objects if obj.source_token_id in participating_token_ids
    )
    demands = tuple(
        demand
        for demand in reference.demands
        if demand.expected_factor_type_symbol_id == normative_factor_type_id
    )
    return MaterializedNormativeDelta(
        objects=objects,
        factors=factors,
        demands=demands,
    )


def benchmark_packed_normative_parity(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str | None = None,
    limit_sentences: int = 10_000,
) -> dict[str, Any]:
    if limit_sentences <= 0:
        raise ValueError("limit_sentences must be positive")

    load_started = monotonic_ns()
    sentences = _load_sentences(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        limit_sentences=limit_sentences,
    )
    lexicon = _load_operator_lexicon(database_url)
    load_ns = monotonic_ns() - load_started

    local_solve_ns = 0
    materialize_ns = 0
    reference_ns = 0
    mismatch_count = 0
    normative_factor_count = 0
    normative_sentence_count = 0
    first_mismatches: list[int] = []
    normative_factor_type_id = int(
        lexicon.factor_type_ids["semantic.normative_relation"]
    )

    for sentence_index, sentence in enumerate(sentences):
        local_observation = localize_relational_sentence(sentence)
        packed = pack_sentence_fibre(local_observation)
        ordered_rows = tuple(
            sorted(sentence.tokens, key=lambda item: item.local_token_ordinal)
        )
        token_ids = tuple(row.token_id for row in ordered_rows)
        reference_tokens = _reference_tokens(sentence)
        synthetic_region_id = sentence_index + 1

        started = monotonic_ns()
        local_delta = compose_packed_normative_delta(packed, lexicon)
        local_solve_ns += monotonic_ns() - started

        started = monotonic_ns()
        materialized = materialize_normative_delta(
            local_delta,
            region_id=synthetic_region_id,
            token_ids_by_ordinal=token_ids,
        )
        materialize_ns += monotonic_ns() - started

        started = monotonic_ns()
        reference = compose_numeric_sentence(
            region_id=synthetic_region_id,
            tokens=reference_tokens,
            lexicon=lexicon,
        )
        reference_ns += monotonic_ns() - started
        projected = _reference_normative_projection(
            reference,
            normative_factor_type_id,
        )

        normative_factor_count += len(materialized.factors)
        if materialized.factors:
            normative_sentence_count += 1
        if materialized != projected:
            mismatch_count += 1
            if len(first_mismatches) < 20:
                first_mismatches.append(sentence_index)

    token_count = sum(len(sentence.tokens) for sentence in sentences)
    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "sentence_limit": limit_sentences,
        "sentence_count": len(sentences),
        "token_count": token_count,
        "normative_sentence_count": normative_sentence_count,
        "normative_factor_count": normative_factor_count,
        "authority_equal": mismatch_count == 0,
        "mismatch_count": mismatch_count,
        "first_mismatch_sentence_indices": first_mismatches,
        "timing_ns": {
            "postgres_and_lexicon_read": load_ns,
            "packed_local_normative_solve": local_solve_ns,
            "authority_id_materialization": materialize_ns,
            "reference_full_sentence_composition": reference_ns,
        },
        "authority": {
            "database_mutations_performed": False,
            "provider_io_performed": False,
            "synthetic_region_ids_are_benchmark_only": True,
            "token_ids_applied_only_at_materialization": True,
            "comparison_scope": "normative/modal projection",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref")
    parser.add_argument("--limit-sentences", type=int, default=10_000)
    parser.add_argument("--output")
    args = parser.parse_args()

    receipt = benchmark_packed_normative_parity(
        args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
        limit_sentences=args.limit_sentences,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.write("\n")
    print(rendered)
    return 0 if receipt["authority_equal"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
