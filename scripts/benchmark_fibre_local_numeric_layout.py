#!/usr/bin/env python3
"""Measure the dream fibre-local carrier against current normalized PG authority.

Read-only diagnostic. It reconstructs each strict-v2 sentence from PostgreSQL,
re-addresses dependency heads from global token ids to local ordinals, packs the
sentence into the fibre-local carrier, verifies exact round trips, and reports
physical payload/width/compression statistics. It never mutates authority.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from time import monotonic_ns
from typing import Any

from src.pnf.fibre_local_numeric import (
    decode_packed_fibre,
    encode_packed_fibre,
    measure_fibre_layout,
    pack_sentence_fibre,
    unpack_sentence_fibre,
)
from src.pnf.fibre_local_relational_bridge import (
    RelationalSentenceRows,
    RelationalTokenRow,
    localize_relational_sentence,
    relational_head_deltas,
)
from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.fibre-local-numeric-layout.v0_1"


def _load_sentences(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str | None,
    limit_sentences: int,
) -> tuple[RelationalSentenceRows, ...]:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    WITH selected AS (
                        SELECT sentence_ref
                          FROM execution.semantic_parser_sentence
                         WHERE run_ref = %s
                           AND representation_version = 2
                           AND (%s IS NULL OR document_ref = %s)
                         ORDER BY document_ref, start_char, end_char, sentence_ref
                         LIMIT %s
                    )
                    SELECT
                        sentence.sentence_ref,
                        sentence.document_ref,
                        sentence.sentence_digest,
                        sentence.local_sentence_ordinal,
                        sentence.start_char,
                        sentence.end_char,
                        token.token_id,
                        token.local_token_ordinal,
                        token.start_char,
                        token.end_char,
                        token.head_token_id,
                        token.orth_symbol_id,
                        token.lemma_symbol_id,
                        token.pos_symbol_id,
                        token.tag_symbol_id,
                        token.dependency_symbol_id,
                        COALESCE(token.morph_set_id, 0),
                        token.lemma_origin_id,
                        token.pos_origin_id,
                        token.tag_origin_id,
                        token.dependency_origin_id
                      FROM selected
                      JOIN execution.semantic_parser_sentence AS sentence
                        ON sentence.sentence_ref = selected.sentence_ref
                      JOIN execution.semantic_parser_token AS token
                        ON token.sentence_ref = sentence.sentence_ref
                       AND token.representation_version = 2
                     ORDER BY
                        sentence.document_ref,
                        sentence.start_char,
                        sentence.end_char,
                        sentence.sentence_ref,
                        token.local_token_ordinal
                    """,
                    (run_ref, document_ref, document_ref, limit_sentences),
                )
                rows = cursor.fetchall()
    finally:
        connection.close()

    grouped: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
    order: list[str] = []
    for row in rows:
        sentence_ref = str(row[0])
        if sentence_ref not in grouped:
            order.append(sentence_ref)
        grouped[sentence_ref].append(row)

    result: list[RelationalSentenceRows] = []
    for sentence_ref in order:
        sentence_rows = grouped[sentence_ref]
        first = sentence_rows[0]
        digest = first[2]
        if digest is None:
            raise RuntimeError(f"strict-v2 sentence {sentence_ref} has no digest")
        fibre_key = bytes(digest)
        tokens: list[RelationalTokenRow] = []
        for row in sentence_rows:
            if row[6] is None or row[10] is None:
                raise RuntimeError(
                    f"strict-v2 sentence {sentence_ref} has incomplete token/head identity"
                )
            required = row[11:16]
            if any(value is None for value in required):
                raise RuntimeError(
                    f"strict-v2 sentence {sentence_ref} has missing numeric annotation"
                )
            tokens.append(
                RelationalTokenRow(
                    token_id=int(row[6]),
                    local_token_ordinal=int(row[7]),
                    start_char=int(row[8]),
                    end_char=int(row[9]),
                    head_token_id=int(row[10]),
                    orth_symbol_id=int(row[11]),
                    lemma_symbol_id=int(row[12]),
                    pos_symbol_id=int(row[13]),
                    tag_symbol_id=int(row[14]),
                    dependency_symbol_id=int(row[15]),
                    morph_set_id=int(row[16]),
                    lemma_origin_id=int(row[17]),
                    pos_origin_id=int(row[18]),
                    tag_origin_id=int(row[19]),
                    dependency_origin_id=int(row[20]),
                )
            )
        result.append(
            RelationalSentenceRows(
                fibre_key=fibre_key,
                sentence_ordinal=int(first[3]),
                start_char=int(first[4]),
                end_char=int(first[5]),
                tokens=tuple(tokens),
            )
        )
    return tuple(result)


def benchmark_layout(
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
    load_ns = monotonic_ns() - load_started

    token_count = 0
    packed_numeric_bytes = 0
    canonical_codec_bytes = 0
    compressed_codec_bytes = 0
    naive_u64_bytes = 0
    max_start_offset = 0
    max_token_length = 0
    max_abs_head_delta = 0
    token_count_distribution: Counter[int] = Counter()
    head_delta_distribution: Counter[int] = Counter()
    column_width_fibres: dict[str, Counter[int]] = defaultdict(Counter)
    column_width_tokens: dict[str, Counter[int]] = defaultdict(Counter)

    packing_started = monotonic_ns()
    roundtrip_failures = 0
    for sentence in sentences:
        local = localize_relational_sentence(sentence)
        packed = pack_sentence_fibre(local)
        if unpack_sentence_fibre(packed) != local:
            roundtrip_failures += 1
            continue
        encoded = encode_packed_fibre(packed)
        decoded = decode_packed_fibre(encoded)
        if unpack_sentence_fibre(decoded) != local:
            roundtrip_failures += 1
            continue

        measurement = measure_fibre_layout(packed)
        token_count += measurement.token_count
        packed_numeric_bytes += measurement.packed_numeric_payload_bytes
        canonical_codec_bytes += measurement.canonical_codec_bytes
        compressed_codec_bytes += measurement.zlib_codec_bytes
        naive_u64_bytes += measurement.naive_u64_equivalent_bytes
        max_start_offset = max(max_start_offset, measurement.max_start_offset)
        max_token_length = max(max_token_length, measurement.max_token_length)
        max_abs_head_delta = max(max_abs_head_delta, measurement.max_abs_head_delta)
        token_count_distribution[measurement.token_count] += 1
        head_delta_distribution.update(relational_head_deltas(sentence))
        for name, width in measurement.column_widths:
            column_width_fibres[name][width] += 1
            column_width_tokens[name][width] += measurement.token_count
    packing_ns = monotonic_ns() - packing_started

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "contract": CONTRACT,
        "run_ref": run_ref,
        "document_ref": document_ref,
        "sentence_limit": limit_sentences,
        "sentence_count": len(sentences),
        "token_count": token_count,
        "roundtrip_failures": roundtrip_failures,
        "exact_roundtrip": roundtrip_failures == 0,
        "bytes": {
            "packed_numeric_payload": packed_numeric_bytes,
            "canonical_fibre_codec": canonical_codec_bytes,
            "zlib_fibre_codec": compressed_codec_bytes,
            "abstract_same_fields_u64_payload": naive_u64_bytes,
        },
        "ratios": {
            "packed_vs_abstract_u64": ratio(packed_numeric_bytes, naive_u64_bytes),
            "canonical_vs_abstract_u64": ratio(canonical_codec_bytes, naive_u64_bytes),
            "zlib_vs_abstract_u64": ratio(compressed_codec_bytes, naive_u64_bytes),
            "zlib_vs_canonical": ratio(compressed_codec_bytes, canonical_codec_bytes),
        },
        "coordinate_extrema": {
            "max_sentence_relative_start": max_start_offset,
            "max_token_length": max_token_length,
            "max_abs_head_delta": max_abs_head_delta,
        },
        "token_count_distribution": {
            str(value): count for value, count in sorted(token_count_distribution.items())
        },
        "head_delta_distribution": {
            str(value): count
            for value, count in sorted(head_delta_distribution.items())
        },
        "column_width_fibres": {
            name: {str(width): count for width, count in sorted(widths.items())}
            for name, widths in sorted(column_width_fibres.items())
        },
        "column_width_tokens": {
            name: {str(width): count for width, count in sorted(widths.items())}
            for name, widths in sorted(column_width_tokens.items())
        },
        "timing_ns": {
            "postgres_read": load_ns,
            "localize_pack_roundtrip_measure": packing_ns,
        },
        "authority": {
            "source": "existing strict-v2 PostgreSQL numeric parser rows",
            "database_mutations_performed": False,
            "provider_io_performed": False,
            "postgres_heap_bytes_claimed": False,
            "u64_comparator_is_abstract_payload_only": True,
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

    receipt = benchmark_layout(
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
    return 0 if receipt["exact_roundtrip"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
