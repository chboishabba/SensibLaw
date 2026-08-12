"""Lossless packed codec for the committed numeric spaCy observation tape.

The codec is deliberately a physical projection only. PostgreSQL parser rows remain
authority. Annotation-origin ids are part of the tape because parser observations and
fallback observations are intentionally distinct authority states.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

_CODEC_MAGIC = b"PNFTAPE2"


@dataclass(frozen=True, slots=True)
class NumericObservationRow:
    token_id: int
    sentence_id: int
    local_ordinal: int
    start_char: int
    end_char: int
    orth_symbol_id: int
    lemma_symbol_id: int
    pos_symbol_id: int | None
    tag_symbol_id: int | None
    dependency_symbol_id: int | None
    morph_set_id: int | None
    head_token_id: int
    lemma_origin_id: int
    pos_origin_id: int
    tag_origin_id: int
    dependency_origin_id: int

    def __post_init__(self) -> None:
        required = (
            self.token_id,
            self.sentence_id,
            self.local_ordinal,
            self.start_char,
            self.end_char,
            self.orth_symbol_id,
            self.lemma_symbol_id,
            self.head_token_id,
            self.lemma_origin_id,
            self.pos_origin_id,
            self.tag_origin_id,
            self.dependency_origin_id,
        )
        if any(value < 0 for value in required):
            raise ValueError("numeric observation ids/offsets must be non-negative")
        if self.end_char < self.start_char:
            raise ValueError("end_char must be >= start_char")
        for value in (
            self.pos_symbol_id,
            self.tag_symbol_id,
            self.dependency_symbol_id,
            self.morph_set_id,
        ):
            if value is not None and value < 0:
                raise ValueError("optional numeric observation ids must be non-negative")


@dataclass(frozen=True, slots=True)
class NumericObservationTapeReceipt:
    token_count: int
    encoded_bytes: int
    authority_digest: bytes
    packed_digest: bytes
    codec_version: int = 2


def canonical_tape_bytes(rows: Iterable[NumericObservationRow]) -> bytes:
    result = bytearray()
    row_tuple = tuple(rows)
    result.extend(_encode_uvarint(len(row_tuple)))
    for row in row_tuple:
        for value in _row_values(row):
            result.extend(_encode_optional_uvarint(value))
    return bytes(result)


def pack_numeric_observation_tape(
    rows: Iterable[NumericObservationRow],
) -> tuple[bytes, NumericObservationTapeReceipt]:
    row_tuple = tuple(rows)
    payload = bytearray(_CODEC_MAGIC)
    payload.extend(_encode_uvarint(len(row_tuple)))

    previous_token = 0
    previous_sentence = 0
    previous_start = 0
    for row in row_tuple:
        payload.extend(_encode_svarint(row.token_id - previous_token))
        payload.extend(_encode_svarint(row.sentence_id - previous_sentence))
        payload.extend(_encode_uvarint(row.local_ordinal))
        payload.extend(_encode_svarint(row.start_char - previous_start))
        payload.extend(_encode_uvarint(row.end_char - row.start_char))
        payload.extend(_encode_uvarint(row.orth_symbol_id))
        payload.extend(_encode_uvarint(row.lemma_symbol_id))
        payload.extend(_encode_optional_uvarint(row.pos_symbol_id))
        payload.extend(_encode_optional_uvarint(row.tag_symbol_id))
        payload.extend(_encode_optional_uvarint(row.dependency_symbol_id))
        payload.extend(_encode_optional_uvarint(row.morph_set_id))
        payload.extend(_encode_svarint(row.head_token_id - row.token_id))
        payload.extend(_encode_uvarint(row.lemma_origin_id))
        payload.extend(_encode_uvarint(row.pos_origin_id))
        payload.extend(_encode_uvarint(row.tag_origin_id))
        payload.extend(_encode_uvarint(row.dependency_origin_id))
        previous_token = row.token_id
        previous_sentence = row.sentence_id
        previous_start = row.start_char

    packed = bytes(payload)
    decoded = unpack_numeric_observation_tape(packed)
    if decoded != row_tuple:
        raise AssertionError("numeric observation tape codec failed exact roundtrip")
    authority = sha256(canonical_tape_bytes(row_tuple)).digest()
    return packed, NumericObservationTapeReceipt(
        token_count=len(row_tuple),
        encoded_bytes=len(packed),
        authority_digest=authority,
        packed_digest=sha256(packed).digest(),
    )


def unpack_numeric_observation_tape(payload: bytes) -> tuple[NumericObservationRow, ...]:
    if not payload.startswith(_CODEC_MAGIC):
        raise ValueError("invalid numeric observation tape magic/version")
    offset = len(_CODEC_MAGIC)
    count, offset = _decode_uvarint(payload, offset)
    rows: list[NumericObservationRow] = []
    previous_token = previous_sentence = previous_start = 0
    for _ in range(count):
        token_delta, offset = _decode_svarint(payload, offset)
        sentence_delta, offset = _decode_svarint(payload, offset)
        local_ordinal, offset = _decode_uvarint(payload, offset)
        start_delta, offset = _decode_svarint(payload, offset)
        span, offset = _decode_uvarint(payload, offset)
        orth, offset = _decode_uvarint(payload, offset)
        lemma, offset = _decode_uvarint(payload, offset)
        pos, offset = _decode_optional_uvarint(payload, offset)
        tag, offset = _decode_optional_uvarint(payload, offset)
        dependency, offset = _decode_optional_uvarint(payload, offset)
        morph, offset = _decode_optional_uvarint(payload, offset)
        head_delta, offset = _decode_svarint(payload, offset)
        lemma_origin, offset = _decode_uvarint(payload, offset)
        pos_origin, offset = _decode_uvarint(payload, offset)
        tag_origin, offset = _decode_uvarint(payload, offset)
        dependency_origin, offset = _decode_uvarint(payload, offset)

        token = previous_token + token_delta
        sentence = previous_sentence + sentence_delta
        start = previous_start + start_delta
        row = NumericObservationRow(
            token_id=token,
            sentence_id=sentence,
            local_ordinal=local_ordinal,
            start_char=start,
            end_char=start + span,
            orth_symbol_id=orth,
            lemma_symbol_id=lemma,
            pos_symbol_id=pos,
            tag_symbol_id=tag,
            dependency_symbol_id=dependency,
            morph_set_id=morph,
            head_token_id=token + head_delta,
            lemma_origin_id=lemma_origin,
            pos_origin_id=pos_origin,
            tag_origin_id=tag_origin,
            dependency_origin_id=dependency_origin,
        )
        rows.append(row)
        previous_token = token
        previous_sentence = sentence
        previous_start = start
    if offset != len(payload):
        raise ValueError("trailing bytes in numeric observation tape")
    return tuple(rows)


def verify_numeric_observation_tape(
    rows: Iterable[NumericObservationRow], payload: bytes
) -> NumericObservationTapeReceipt:
    row_tuple = tuple(rows)
    decoded = unpack_numeric_observation_tape(payload)
    if decoded != row_tuple:
        raise ValueError("packed tape does not reconstruct canonical numeric observations")
    return NumericObservationTapeReceipt(
        token_count=len(row_tuple),
        encoded_bytes=len(payload),
        authority_digest=sha256(canonical_tape_bytes(row_tuple)).digest(),
        packed_digest=sha256(payload).digest(),
    )


def _row_values(row: NumericObservationRow) -> tuple[int | None, ...]:
    return (
        row.token_id,
        row.sentence_id,
        row.local_ordinal,
        row.start_char,
        row.end_char,
        row.orth_symbol_id,
        row.lemma_symbol_id,
        row.pos_symbol_id,
        row.tag_symbol_id,
        row.dependency_symbol_id,
        row.morph_set_id,
        row.head_token_id,
        row.lemma_origin_id,
        row.pos_origin_id,
        row.tag_origin_id,
        row.dependency_origin_id,
    )


def _encode_optional_uvarint(value: int | None) -> bytes:
    return _encode_uvarint(0 if value is None else value + 1)


def _decode_optional_uvarint(payload: bytes, offset: int) -> tuple[int | None, int]:
    encoded, offset = _decode_uvarint(payload, offset)
    return (None if encoded == 0 else encoded - 1), offset


def _encode_svarint(value: int) -> bytes:
    zigzag = value * 2 if value >= 0 else (-value * 2) - 1
    return _encode_uvarint(zigzag)


def _decode_svarint(payload: bytes, offset: int) -> tuple[int, int]:
    zigzag, offset = _decode_uvarint(payload, offset)
    value = zigzag // 2 if zigzag % 2 == 0 else -(zigzag // 2) - 1
    return value, offset


def _encode_uvarint(value: int) -> bytes:
    if value < 0:
        raise ValueError("uvarint cannot encode a negative value")
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _decode_uvarint(payload: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if offset >= len(payload):
            raise ValueError("truncated uvarint")
        byte = payload[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift > 70:
            raise ValueError("uvarint is too large")
