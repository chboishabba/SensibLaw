"""Set-based token and annotation persistence on typed COPY lanes."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
from types import MethodType
from typing import Any, Callable, Iterator, Mapping, Sequence

from src.policy.artifact_projection import iter_verified_records
from src.policy.carriers.canonical import canonical_sha256
from src.storage.postgres.token_codec import CorpusCodec, encode_delta_sequence
from src.storage.postgres.work_conserving_stage import (
    StagePayload,
    _complete_stage,
    _sha,
    _stage_payloads,
)


def _token_stream_header(
    *,
    document_ref: str,
    tokenizer_ref: str,
    tokenizer_version: str,
    batches: Callable[[], Iterator[Sequence[tuple[str, int, int]]]],
    token_count: int,
) -> tuple[str, dict[str, int], str]:
    vocabulary: set[str] = set()
    frequency_by_key: dict[str, int] = {}
    digest = hashlib.sha256()
    digest.update(b"[")
    seen = 0
    for batch in batches():
        if len(batch) > 256:
            raise ValueError("token batches must contain at most 256 rows")
        for token in batch:
            if seen:
                digest.update(b",")
            surface, start, end = token
            encoded_surface = surface.encode("utf-8")
            digest.update(len(encoded_surface).to_bytes(8, "big"))
            digest.update(encoded_surface)
            digest.update(int(start).to_bytes(8, "big", signed=True))
            digest.update(int(end).to_bytes(8, "big", signed=True))
            seen += 1
            key = token[0].casefold()
            vocabulary.add(key)
            frequency_by_key[key] = frequency_by_key.get(key, 0) + 1
    digest.update(b"]")
    if seen != token_count:
        raise ValueError(
            "token source count changed between descriptor and first pass"
        )
    stream_digest = digest.hexdigest()
    run_ref = "tokenizer-run:" + canonical_sha256(
        {
            "document_ref": document_ref,
            "tokenizer_ref": tokenizer_ref,
            "tokenizer_version": tokenizer_version,
            "token_stream_digest": stream_digest,
            "token_count": token_count,
        }
    )
    return run_ref, frequency_by_key, stream_digest


def persist_token_batches_work_conserving(
    self: Any,
    cursor: Any,
    *,
    document_ref: str,
    tokenizer_ref: str,
    tokenizer_version: str,
    batches: Callable[[], Iterator[Sequence[tuple[str, int, int]]]],
    token_count: int,
    language_ref: str = "und",
    lexical_kind_ref: str = "surface",
) -> str:
    del self
    run_ref, frequency_by_key, stream_digest = _token_stream_header(
        document_ref=document_ref,
        tokenizer_ref=tokenizer_ref,
        tokenizer_version=tokenizer_version,
        batches=batches,
        token_count=token_count,
    )
    lexeme_payloads = [
        StagePayload(
            "lexeme",
            texts=(language_ref, key, lexical_kind_ref),
            ints=(frequency,),
        )
        for key, frequency in sorted(frequency_by_key.items())
    ]
    lexeme_stage_ref = _stage_payloads(
        cursor,
        family_ref="token_lexemes",
        lane_ref="token",
        payloads=lexeme_payloads,
    )
    cursor.execute(
        """
        INSERT INTO language.lexeme
            (language_ref, normalized_text, lexical_kind_ref)
        SELECT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'lexeme'
        ON CONFLICT (language_ref, normalized_text, lexical_kind_ref) DO NOTHING
        """,
        (lexeme_stage_ref,),
    )
    cursor.execute(
        """
        SELECT staged.text_02, lexeme.lexeme_id, staged.int_01
        FROM execution.document_persistence_stage AS staged
        JOIN language.lexeme AS lexeme
          ON lexeme.language_ref = staged.text_01
         AND lexeme.normalized_text = staged.text_02
         AND lexeme.lexical_kind_ref = staged.text_03
        WHERE staged.stage_ref = %s AND staged.row_kind_ref = 'lexeme'
        """,
        (lexeme_stage_ref,),
    )
    lexeme_rows = cursor.fetchall()
    lexeme_by_key = {str(row[0]): int(row[1]) for row in lexeme_rows}
    frequency_by_id = {int(row[1]): int(row[2]) for row in lexeme_rows}
    if len(lexeme_by_key) != len(frequency_by_key):
        raise RuntimeError("lexeme set merge did not return every requested key")
    _complete_stage(cursor, stage_ref=lexeme_stage_ref, statement_count=2)

    ranked_ids = sorted(
        frequency_by_id, key=lambda item: (-frequency_by_id[item], item)
    )
    codec = CorpusCodec(
        {lexeme_id: symbol for symbol, lexeme_id in enumerate(ranked_ids)}
    )
    codec_ref = "codec:" + canonical_sha256(
        {"run_ref": run_ref, "mapping": codec.logical_to_symbol}
    )
    token_payloads = [
        StagePayload(
            "codec_symbol",
            texts=(codec_ref,),
            ints=(codec.logical_to_symbol[lexeme_id], lexeme_id, rank),
        )
        for rank, lexeme_id in enumerate(ranked_ids)
    ]
    offset = 0
    emitted = 0
    for chunk_index, batch in enumerate(batches()):
        if len(batch) > 256:
            raise ValueError("token batches must contain at most 256 rows")
        lexeme_ids = [
            lexeme_by_key[surface.casefold()]
            for surface, _start, _end in batch
        ]
        offsets = [
            value for _surface, start, end in batch for value in (start, end)
        ]
        encoded_symbols = codec.encode(lexeme_ids)
        encoded_offsets = encode_delta_sequence(offsets)
        token_payloads.append(
            StagePayload(
                "token_chunk",
                texts=(
                    run_ref,
                    codec_ref,
                    hashlib.sha256(
                        encoded_symbols + encoded_offsets
                    ).hexdigest(),
                ),
                ints=(chunk_index, offset, len(batch)),
                byteas=(encoded_symbols, encoded_offsets),
            )
        )
        offset += len(batch)
        emitted += len(batch)
    if emitted != token_count:
        raise ValueError("token source changed between streaming passes")
    token_stage_ref = _stage_payloads(
        cursor,
        family_ref="token_stream",
        lane_ref="token",
        payloads=token_payloads,
    )
    cursor.execute(
        """
        INSERT INTO language.tokenizer_run
            (tokenizer_run_ref, document_ref, tokenizer_ref, tokenizer_version,
             token_count, output_sha256)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (tokenizer_run_ref) DO NOTHING
        """,
        (
            run_ref,
            document_ref,
            tokenizer_ref,
            tokenizer_version,
            token_count,
            _sha({"token_stream_digest": stream_digest}),
        ),
    )
    cursor.execute(
        """
        INSERT INTO language.codec
            (codec_ref, codec_kind_ref, codec_version, dictionary_sha256)
        VALUES (%s, 'frequency-ranked-uvarint', 'v0_1', %s)
        ON CONFLICT (codec_ref) DO NOTHING
        """,
        (codec_ref, _sha(codec.logical_to_symbol)),
    )
    cursor.execute(
        """
        INSERT INTO language.codec_symbol
            (codec_ref, symbol_code, lexeme_id, frequency_rank)
        SELECT text_01, int_01, int_02, int_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'codec_symbol'
        ON CONFLICT (codec_ref, symbol_code) DO NOTHING
        """,
        (token_stage_ref,),
    )
    cursor.execute(
        """
        INSERT INTO language.token_stream_chunk
            (tokenizer_run_ref, chunk_index, first_token_index, token_count,
             codec_ref, encoded_symbols, encoded_offsets, content_sha256)
        SELECT text_01, int_01, int_02, int_03, text_02, bytea_01, bytea_02,
               decode(text_03, 'hex')
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'token_chunk'
        ON CONFLICT (tokenizer_run_ref, chunk_index) DO NOTHING
        """,
        (token_stage_ref,),
    )
    _complete_stage(cursor, stage_ref=token_stage_ref, statement_count=4)
    return run_ref


def _persist_annotation_payloads(
    cursor: Any,
    *,
    document_ref: str,
    layer_ref: str,
    backend_ref: str,
    input_sha256: bytes,
    output_sha256: bytes,
    payloads: Sequence[StagePayload],
    family_ref: str,
) -> None:
    stage_ref = _stage_payloads(
        cursor,
        family_ref=family_ref,
        lane_ref="annotation",
        payloads=payloads,
    )
    cursor.execute(
        """
        INSERT INTO language.annotation_layer
            (annotation_layer_ref, document_ref, backend_ref,
             backend_version, input_sha256, output_sha256)
        VALUES (%s, %s, %s, 'v0_1', %s, %s)
        ON CONFLICT (annotation_layer_ref) DO NOTHING
        """,
        (layer_ref, document_ref, backend_ref, input_sha256, output_sha256),
    )
    cursor.execute(
        """
        INSERT INTO language.annotation_node
            (annotation_node_ref, annotation_layer_ref, annotation_type_ref,
             span_ref, value_ref)
        SELECT text_01, text_02, text_03, text_04, text_05
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'annotation_node'
        ON CONFLICT (annotation_node_ref) DO NOTHING
        """,
        (stage_ref,),
    )
    cursor.execute(
        """
        INSERT INTO language.annotation_relation
            (annotation_relation_ref, annotation_layer_ref, relation_type_ref,
             source_node_ref, target_node_ref)
        SELECT text_01, text_02, text_03, text_04, text_05
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'annotation_relation'
        ON CONFLICT (annotation_relation_ref) DO NOTHING
        """,
        (stage_ref,),
    )
    _complete_stage(cursor, stage_ref=stage_ref, statement_count=3)


def persist_annotation_layer_work_conserving(
    self: Any, cursor: Any, *, document_ref: str, layer: Mapping[str, Any]
) -> None:
    del self
    layer_ref = str(layer["layer_ref"])
    payloads = [
        StagePayload(
            "annotation_node",
            texts=(
                f"{layer_ref}:token:{row['token_index']}",
                layer_ref,
                str(row["annotation_type"]),
                None,
                str(row["value"]),
            ),
        )
        for row in layer.get("token_annotations") or ()
    ]
    payloads.extend(
        StagePayload(
            "annotation_node",
            texts=(
                str(row["span_ref"]),
                layer_ref,
                str(row["annotation_type"]),
                str(row["span_ref"]),
                str((row.get("value") or {}).get("surface") or ""),
            ),
        )
        for row in layer.get("span_annotations") or ()
    )
    payloads.extend(
        StagePayload(
            "annotation_relation",
            texts=(
                str(row["relation_ref"]),
                layer_ref,
                str(row["relation_type"]),
                str(row["left_ref"]),
                str(row["right_ref"]),
            ),
        )
        for row in layer.get("relation_annotations") or ()
    )
    _persist_annotation_payloads(
        cursor,
        document_ref=document_ref,
        layer_ref=layer_ref,
        backend_ref=str(layer.get("tokenizer_ref") or "unknown"),
        input_sha256=bytes.fromhex(str(layer["text_sha256"])),
        output_sha256=_sha(layer),
        payloads=payloads,
        family_ref="annotation_layer",
    )


def persist_annotation_layer_batches_work_conserving(
    self: Any,
    cursor: Any,
    *,
    document_ref: str,
    descriptor: Mapping[str, Any],
    reader: Any,
) -> None:
    del self
    metadata: dict[str, Any] = {}
    for batch in reader.iter_records(str(descriptor["artifact_key"])):
        for record in batch:
            if record.get("reconstruction") == "mapping_scalar":
                metadata[str(record["field"])] = record.get("value")
    layer_ref = str(metadata["layer_ref"])
    payloads: list[StagePayload] = []
    for batch in iter_verified_records(reader, descriptor):
        for record in batch:
            family = str(record.get("family") or "")
            row = record.get("value")
            if not isinstance(row, Mapping):
                continue
            if family == "token_annotations":
                payloads.append(
                    StagePayload(
                        "annotation_node",
                        texts=(
                            f"{layer_ref}:token:{row['token_index']}",
                            layer_ref,
                            str(row["annotation_type"]),
                            None,
                            str(row["value"]),
                        ),
                    )
                )
            elif family == "span_annotations":
                payloads.append(
                    StagePayload(
                        "annotation_node",
                        texts=(
                            str(row["span_ref"]),
                            layer_ref,
                            str(row["annotation_type"]),
                            str(row["span_ref"]),
                            str((row.get("value") or {}).get("surface") or ""),
                        ),
                    )
                )
            elif family == "relation_annotations":
                payloads.append(
                    StagePayload(
                        "annotation_relation",
                        texts=(
                            str(row["relation_ref"]),
                            layer_ref,
                            str(row["relation_type"]),
                            str(row["left_ref"]),
                            str(row["right_ref"]),
                        ),
                    )
                )
    _persist_annotation_payloads(
        cursor,
        document_ref=document_ref,
        layer_ref=layer_ref,
        backend_ref=str(metadata.get("tokenizer_ref") or "unknown"),
        input_sha256=bytes.fromhex(str(metadata["text_sha256"])),
        output_sha256=_sha(metadata),
        payloads=payloads,
        family_ref="annotation_layer_manifest",
    )


@contextmanager
def activate_work_conserving_store_bindings(store: Any) -> Iterator[None]:
    replacements = {
        "persist_token_batches": persist_token_batches_work_conserving,
        "persist_annotation_layer": persist_annotation_layer_work_conserving,
        "persist_annotation_layer_batches": (
            persist_annotation_layer_batches_work_conserving
        ),
    }
    missing = object()
    originals = {name: store.__dict__.get(name, missing) for name in replacements}
    for name, replacement in replacements.items():
        setattr(store, name, MethodType(replacement, store))
    try:
        yield
    finally:
        for name, original in originals.items():
            if original is missing:
                delattr(store, name)
            else:
                setattr(store, name, original)


__all__ = ["activate_work_conserving_store_bindings"]
