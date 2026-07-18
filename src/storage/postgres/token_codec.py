"""Compact, deterministic token and offset codecs for PostgreSQL bytea storage.

Logical lexeme IDs remain stable database identities.  Dense token streams use
frequency-ranked corpus-local symbols encoded as unsigned varints; character
offsets are delta encoded.  The codec is a storage representation only and has
no semantic or entity-resolution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


def encode_uvarint(value: int) -> bytes:
    if value < 0:
        raise ValueError("unsigned varints require non-negative integers")
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def decode_uvarints(payload: bytes) -> tuple[int, ...]:
    values: list[int] = []
    value = 0
    shift = 0
    for byte in payload:
        value |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
            if shift > 63:
                raise ValueError("varint exceeds supported width")
            continue
        values.append(value)
        value = 0
        shift = 0
    if shift:
        raise ValueError("truncated varint payload")
    return tuple(values)


def encode_uint_sequence(values: Iterable[int]) -> bytes:
    return b"".join(encode_uvarint(value) for value in values)


def encode_delta_sequence(values: Sequence[int]) -> bytes:
    previous = 0
    deltas: list[int] = []
    for value in values:
        if value < previous:
            raise ValueError("delta-coded values must be monotone")
        deltas.append(value - previous)
        previous = value
    return encode_uint_sequence(deltas)


def decode_delta_sequence(payload: bytes) -> tuple[int, ...]:
    total = 0
    values: list[int] = []
    for delta in decode_uvarints(payload):
        total += delta
        values.append(total)
    return tuple(values)


@dataclass(frozen=True)
class CorpusCodec:
    """Frequency-ranked logical-ID to physical-symbol mapping."""

    logical_to_symbol: dict[int, int]

    @classmethod
    def from_lexeme_ids(cls, lexeme_ids: Sequence[int]) -> "CorpusCodec":
        frequency: dict[int, int] = {}
        for lexeme_id in lexeme_ids:
            if lexeme_id < 0:
                raise ValueError("lexeme IDs must be non-negative")
            frequency[lexeme_id] = frequency.get(lexeme_id, 0) + 1
        ordered = sorted(frequency, key=lambda item: (-frequency[item], item))
        return cls({lexeme_id: symbol for symbol, lexeme_id in enumerate(ordered)})

    @property
    def symbol_to_logical(self) -> dict[int, int]:
        return {symbol: logical for logical, symbol in self.logical_to_symbol.items()}

    def encode(self, lexeme_ids: Sequence[int]) -> bytes:
        try:
            symbols = (self.logical_to_symbol[value] for value in lexeme_ids)
            return encode_uint_sequence(symbols)
        except KeyError as error:
            raise ValueError(f"lexeme ID absent from codec: {error.args[0]}") from error

    def decode(self, payload: bytes) -> tuple[int, ...]:
        inverse = self.symbol_to_logical
        try:
            return tuple(inverse[symbol] for symbol in decode_uvarints(payload))
        except KeyError as error:
            raise ValueError(f"unknown codec symbol: {error.args[0]}") from error
