"""Batch-oriented PostgreSQL store preserving the generic compiler contract."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.storage.postgres.compiler_store import PostgresCompilerStore, _stable_bytes
from src.storage.postgres.token_codec import CorpusCodec, encode_delta_sequence


class BatchedPostgresCompilerStore(PostgresCompilerStore):
    """Use canonical executemany batches for high-volume immutable child rows."""

    def persist_tokens(
        self,
        cursor: Any,
        *,
        document_ref: str,
        tokenizer_ref: str,
        tokenizer_version: str,
        tokens: Sequence[tuple[str, int, int]],
        language_ref: str = "und",
        lexical_kind_ref: str = "surface",
    ) -> str:
        run_ref = "tokenizer-run:" + canonical_sha256(
            {
                "document_ref": document_ref,
                "tokenizer_ref": tokenizer_ref,
                "tokenizer_version": tokenizer_version,
                "tokens": tokens,
            }
        )
        lexeme_keys = tuple(sorted({surface.casefold() for surface, _, _ in tokens}))
        if lexeme_keys:
            cursor.executemany(
                """
                INSERT INTO language.lexeme
                    (language_ref, normalized_text, lexical_kind_ref)
                VALUES (%s, %s, %s)
                ON CONFLICT (language_ref, normalized_text, lexical_kind_ref)
                DO NOTHING
                """,
                [(language_ref, key, lexical_kind_ref) for key in lexeme_keys],
            )
            cursor.execute(
                """
                SELECT normalized_text, lexeme_id
                FROM language.lexeme
                WHERE language_ref = %s AND lexical_kind_ref = %s
                  AND normalized_text = ANY(%s)
                """,
                (language_ref, lexical_kind_ref, list(lexeme_keys)),
            )
            lexeme_by_key = {str(row[0]): int(row[1]) for row in cursor.fetchall()}
            if len(lexeme_by_key) != len(lexeme_keys):
                raise RuntimeError("lexeme batch did not return every requested key")
        else:
            lexeme_by_key = {}

        lexeme_ids = [lexeme_by_key[surface.casefold()] for surface, _, _ in tokens]
        starts = [start for _, start, _ in tokens]
        ends = [end for _, _, end in tokens]
        cursor.execute(
            """
            INSERT INTO language.tokenizer_run
                (tokenizer_run_ref, document_ref, tokenizer_ref,
                 tokenizer_version, token_count, output_sha256)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tokenizer_run_ref) DO NOTHING
            """,
            (
                run_ref,
                document_ref,
                tokenizer_ref,
                tokenizer_version,
                len(tokens),
                _stable_bytes({"lexeme_ids": lexeme_ids, "starts": starts, "ends": ends}),
            ),
        )
        if not tokens:
            return run_ref

        codec = CorpusCodec.from_lexeme_ids(lexeme_ids)
        codec_ref = "codec:" + canonical_sha256(
            {"run_ref": run_ref, "mapping": codec.logical_to_symbol}
        )
        cursor.execute(
            """
            INSERT INTO language.codec
                (codec_ref, codec_kind_ref, codec_version, dictionary_sha256)
            VALUES (%s, 'frequency-ranked-uvarint', 'v0_1', %s)
            ON CONFLICT (codec_ref) DO NOTHING
            """,
            (codec_ref, _stable_bytes(codec.logical_to_symbol)),
        )
        frequencies: dict[int, int] = {}
        for lexeme_id in lexeme_ids:
            frequencies[lexeme_id] = frequencies.get(lexeme_id, 0) + 1
        ranked = sorted(frequencies, key=lambda value: (-frequencies[value], value))
        cursor.executemany(
            """
            INSERT INTO language.codec_symbol
                (codec_ref, symbol_code, lexeme_id, frequency_rank)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (codec_ref, symbol_code) DO NOTHING
            """,
            [
                (codec_ref, codec.logical_to_symbol[lexeme_id], lexeme_id, rank)
                for rank, lexeme_id in enumerate(ranked)
            ],
        )
        encoded_symbols = codec.encode(lexeme_ids)
        encoded_offsets = encode_delta_sequence(
            [value for pair in zip(starts, ends, strict=True) for value in pair]
        )
        cursor.execute(
            """
            INSERT INTO language.token_stream_chunk
                (tokenizer_run_ref, chunk_index, first_token_index, token_count,
                 codec_ref, encoded_symbols, encoded_offsets, content_sha256)
            VALUES (%s, 0, 0, %s, %s, %s, %s, %s)
            ON CONFLICT (tokenizer_run_ref, chunk_index) DO NOTHING
            """,
            (
                run_ref,
                len(tokens),
                codec_ref,
                encoded_symbols,
                encoded_offsets,
                hashlib.sha256(encoded_symbols + encoded_offsets).digest(),
            ),
        )
        return run_ref

    def persist_annotation_layer(
        self, cursor: Any, *, document_ref: str, layer: Mapping[str, Any]
    ) -> None:
        layer_ref = str(layer["layer_ref"])
        cursor.execute(
            """
            INSERT INTO language.annotation_layer
                (annotation_layer_ref, document_ref, backend_ref,
                 backend_version, input_sha256, output_sha256)
            VALUES (%s, %s, %s, 'v0_1', %s, %s)
            ON CONFLICT (annotation_layer_ref) DO NOTHING
            """,
            (
                layer_ref,
                document_ref,
                str(layer.get("tokenizer_ref") or "unknown"),
                bytes.fromhex(str(layer["text_sha256"])),
                _stable_bytes(layer),
            ),
        )
        node_rows = [
            (
                f"{layer_ref}:token:{token['token_index']}",
                layer_ref,
                str(token["annotation_type"]),
                None,
                str(token["value"]),
            )
            for token in layer.get("token_annotations") or ()
        ]
        node_rows.extend(
            (
                str(span["span_ref"]),
                layer_ref,
                str(span["annotation_type"]),
                str(span["span_ref"]),
                str((span.get("value") or {}).get("surface") or ""),
            )
            for span in layer.get("span_annotations") or ()
        )
        if node_rows:
            cursor.executemany(
                """
                INSERT INTO language.annotation_node
                    (annotation_node_ref, annotation_layer_ref,
                     annotation_type_ref, span_ref, value_ref)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (annotation_node_ref) DO NOTHING
                """,
                node_rows,
            )
        relation_rows = [
            (
                str(row["relation_ref"]),
                layer_ref,
                str(row["relation_type"]),
                str(row["left_ref"]),
                str(row["right_ref"]),
            )
            for row in layer.get("relation_annotations") or ()
        ]
        if relation_rows:
            cursor.executemany(
                """
                INSERT INTO language.annotation_relation
                    (annotation_relation_ref, annotation_layer_ref,
                     relation_type_ref, source_node_ref, target_node_ref)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (annotation_relation_ref) DO NOTHING
                """,
                relation_rows,
            )


__all__ = ["BatchedPostgresCompilerStore"]
