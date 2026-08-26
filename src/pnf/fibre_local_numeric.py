"""Compact fibre-local numeric carrier for the delta-native PNF hot path.

This module deliberately separates:
- durable/global semantic or database identity;
- fibre-local token address;
- transient branch/path address.

The hot representation owns token-local spans and parser annotations, encodes
dependency heads as local displacements, and chooses the narrowest integer
column width that can represent each fibre. It is an execution/storage carrier,
not semantic authority and not a claim about PostgreSQL heap compression.
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import struct
import zlib
from typing import Iterable, Sequence

_MAGIC = b"SLFLN1"
_UNSIGNED_LAYOUTS = (("B", 1), ("H", 2), ("I", 4), ("Q", 8))
_SIGNED_LAYOUTS = (("b", 1), ("h", 2), ("i", 4), ("q", 8))


class FibreLayoutError(ValueError):
    """The proposed fibre-local representation is not lossless/well-formed."""


@dataclass(frozen=True, slots=True)
class FibreTokenAddress:
    """External token address without an independent corpus-global token id."""

    fibre_key: bytes
    token_ordinal: int


@dataclass(frozen=True, slots=True)
class BranchStep:
    option_count: int
    selected_option: int

    def __post_init__(self) -> None:
        if self.option_count <= 0:
            raise FibreLayoutError("branch option_count must be positive")
        if not 0 <= self.selected_option < self.option_count:
            raise FibreLayoutError("selected branch is outside the local radix")


@dataclass(frozen=True, slots=True)
class BranchPathAddress:
    """Transient solver address in the mixed radix induced by local branching."""

    steps: tuple[BranchStep, ...]

    def mixed_radix_code(self) -> int:
        code = 0
        multiplier = 1
        for step in self.steps:
            code += step.selected_option * multiplier
            multiplier *= step.option_count
        return code

    @classmethod
    def from_mixed_radix(
        cls,
        option_counts: Sequence[int],
        code: int,
    ) -> "BranchPathAddress":
        if code < 0:
            raise FibreLayoutError("mixed-radix code must be non-negative")
        remaining = int(code)
        steps: list[BranchStep] = []
        capacity = 1
        for option_count in option_counts:
            if option_count <= 0:
                raise FibreLayoutError("branch option_count must be positive")
            selected = remaining % option_count
            remaining //= option_count
            capacity *= option_count
            steps.append(BranchStep(option_count, selected))
        if remaining:
            raise FibreLayoutError(
                f"mixed-radix code {code} exceeds path capacity {capacity}"
            )
        return cls(tuple(steps))


@dataclass(frozen=True, slots=True)
class TokenObservation:
    """Parser observations owned by one token inside a sentence fibre."""

    start_char: int
    end_char: int
    head_ordinal: int
    orth_id: int
    lemma_id: int
    pos_id: int
    tag_id: int
    dependency_id: int
    morph_id: int
    lemma_origin_id: int = 0
    pos_origin_id: int = 0
    tag_origin_id: int = 0
    dependency_origin_id: int = 0

    def __post_init__(self) -> None:
        if self.start_char < 0 or self.end_char < self.start_char:
            raise FibreLayoutError("token span must be ordered and non-negative")
        for name in (
            "head_ordinal",
            "orth_id",
            "lemma_id",
            "pos_id",
            "tag_id",
            "dependency_id",
            "morph_id",
            "lemma_origin_id",
            "pos_origin_id",
            "tag_origin_id",
            "dependency_origin_id",
        ):
            if int(getattr(self, name)) < 0:
                raise FibreLayoutError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class SentenceFibreObservation:
    fibre_key: bytes
    sentence_ordinal: int
    start_char: int
    end_char: int
    tokens: tuple[TokenObservation, ...]

    def __post_init__(self) -> None:
        if not self.fibre_key:
            raise FibreLayoutError("fibre_key must be non-empty")
        if self.sentence_ordinal < 0:
            raise FibreLayoutError("sentence_ordinal must be non-negative")
        if self.start_char < 0 or self.end_char < self.start_char:
            raise FibreLayoutError("sentence span must be ordered and non-negative")
        count = len(self.tokens)
        previous_start = self.start_char
        for ordinal, token in enumerate(self.tokens):
            if token.start_char < self.start_char or token.end_char > self.end_char:
                raise FibreLayoutError("token span escapes sentence fibre")
            if ordinal and token.start_char < previous_start:
                raise FibreLayoutError("token observations must be in ordinal order")
            if not 0 <= token.head_ordinal < count:
                raise FibreLayoutError("dependency head escapes sentence fibre")
            previous_start = token.start_char


@dataclass(slots=True)
class NarrowIntColumn:
    signed: bool
    typecode: str
    values: array

    @property
    def itemsize(self) -> int:
        return self.values.itemsize

    @property
    def nbytes(self) -> int:
        return len(self.values) * self.values.itemsize

    def as_tuple(self) -> tuple[int, ...]:
        return tuple(int(value) for value in self.values)

    def canonical_bytes(self) -> bytes:
        width = self.itemsize
        payload = bytearray()
        for value in self.values:
            payload.extend(int(value).to_bytes(width, "little", signed=self.signed))
        return bytes(payload)

    @classmethod
    def from_values(
        cls,
        values: Iterable[int],
        *,
        signed: bool,
    ) -> "NarrowIntColumn":
        materialized = tuple(int(value) for value in values)
        layouts = _SIGNED_LAYOUTS if signed else _UNSIGNED_LAYOUTS
        if not signed and any(value < 0 for value in materialized):
            raise FibreLayoutError("unsigned packed column contains a negative value")
        for typecode, width in layouts:
            bits = width * 8
            if signed:
                lower = -(1 << (bits - 1))
                upper = (1 << (bits - 1)) - 1
            else:
                lower = 0
                upper = (1 << bits) - 1
            if all(lower <= value <= upper for value in materialized):
                packed = array(typecode, materialized)
                if packed.itemsize != width:
                    continue
                return cls(signed=signed, typecode=typecode, values=packed)
        raise FibreLayoutError("integer column exceeds 64-bit packed range")

    @classmethod
    def from_canonical_bytes(
        cls,
        payload: bytes,
        *,
        signed: bool,
        width: int,
        count: int,
    ) -> "NarrowIntColumn":
        if width not in (1, 2, 4, 8):
            raise FibreLayoutError(f"unsupported packed integer width: {width}")
        if len(payload) != width * count:
            raise FibreLayoutError("packed column byte length does not match count")
        values = tuple(
            int.from_bytes(
                payload[offset : offset + width],
                "little",
                signed=signed,
            )
            for offset in range(0, len(payload), width)
        )
        column = cls.from_values(values, signed=signed)
        if column.itemsize > width:
            raise FibreLayoutError("packed column cannot be reconstructed at encoded width")
        return column


_COLUMN_NAMES = (
    "start_offset",
    "length",
    "head_delta",
    "orth_id",
    "lemma_id",
    "pos_id",
    "tag_id",
    "dependency_id",
    "morph_id",
    "lemma_origin_id",
    "pos_origin_id",
    "tag_origin_id",
    "dependency_origin_id",
)


@dataclass(slots=True)
class PackedSentenceFibre:
    fibre_key: bytes
    sentence_ordinal: int
    base_char: int
    end_char: int
    columns: dict[str, NarrowIntColumn]

    @property
    def token_count(self) -> int:
        return len(self.columns["start_offset"].values)

    def token_address(self, token_ordinal: int) -> FibreTokenAddress:
        if not 0 <= token_ordinal < self.token_count:
            raise FibreLayoutError("token ordinal is outside the fibre")
        return FibreTokenAddress(self.fibre_key, token_ordinal)

    @property
    def numeric_payload_bytes(self) -> int:
        return sum(column.nbytes for column in self.columns.values())

    def canonical_payload(self) -> bytes:
        payload = bytearray()
        for name in _COLUMN_NAMES:
            column = self.columns[name]
            data = column.canonical_bytes()
            payload.extend(
                struct.pack(
                    "<BBI",
                    int(column.signed),
                    column.itemsize,
                    len(column.values),
                )
            )
            payload.extend(data)
        return bytes(payload)


def pack_sentence_fibre(observation: SentenceFibreObservation) -> PackedSentenceFibre:
    tokens = observation.tokens
    columns: dict[str, NarrowIntColumn] = {
        "start_offset": NarrowIntColumn.from_values(
            (token.start_char - observation.start_char for token in tokens),
            signed=False,
        ),
        "length": NarrowIntColumn.from_values(
            (token.end_char - token.start_char for token in tokens),
            signed=False,
        ),
        "head_delta": NarrowIntColumn.from_values(
            (token.head_ordinal - ordinal for ordinal, token in enumerate(tokens)),
            signed=True,
        ),
        "orth_id": NarrowIntColumn.from_values(
            (token.orth_id for token in tokens), signed=False
        ),
        "lemma_id": NarrowIntColumn.from_values(
            (token.lemma_id for token in tokens), signed=False
        ),
        "pos_id": NarrowIntColumn.from_values(
            (token.pos_id for token in tokens), signed=False
        ),
        "tag_id": NarrowIntColumn.from_values(
            (token.tag_id for token in tokens), signed=False
        ),
        "dependency_id": NarrowIntColumn.from_values(
            (token.dependency_id for token in tokens), signed=False
        ),
        "morph_id": NarrowIntColumn.from_values(
            (token.morph_id for token in tokens), signed=False
        ),
        "lemma_origin_id": NarrowIntColumn.from_values(
            (token.lemma_origin_id for token in tokens), signed=False
        ),
        "pos_origin_id": NarrowIntColumn.from_values(
            (token.pos_origin_id for token in tokens), signed=False
        ),
        "tag_origin_id": NarrowIntColumn.from_values(
            (token.tag_origin_id for token in tokens), signed=False
        ),
        "dependency_origin_id": NarrowIntColumn.from_values(
            (token.dependency_origin_id for token in tokens), signed=False
        ),
    }
    return PackedSentenceFibre(
        fibre_key=bytes(observation.fibre_key),
        sentence_ordinal=observation.sentence_ordinal,
        base_char=observation.start_char,
        end_char=observation.end_char,
        columns=columns,
    )


def unpack_sentence_fibre(packed: PackedSentenceFibre) -> SentenceFibreObservation:
    count = packed.token_count
    values = {name: packed.columns[name].as_tuple() for name in _COLUMN_NAMES}
    if any(len(column) != count for column in values.values()):
        raise FibreLayoutError("packed fibre columns have unequal lengths")
    tokens: list[TokenObservation] = []
    for ordinal in range(count):
        start_char = packed.base_char + values["start_offset"][ordinal]
        end_char = start_char + values["length"][ordinal]
        head_ordinal = ordinal + values["head_delta"][ordinal]
        tokens.append(
            TokenObservation(
                start_char=start_char,
                end_char=end_char,
                head_ordinal=head_ordinal,
                orth_id=values["orth_id"][ordinal],
                lemma_id=values["lemma_id"][ordinal],
                pos_id=values["pos_id"][ordinal],
                tag_id=values["tag_id"][ordinal],
                dependency_id=values["dependency_id"][ordinal],
                morph_id=values["morph_id"][ordinal],
                lemma_origin_id=values["lemma_origin_id"][ordinal],
                pos_origin_id=values["pos_origin_id"][ordinal],
                tag_origin_id=values["tag_origin_id"][ordinal],
                dependency_origin_id=values["dependency_origin_id"][ordinal],
            )
        )
    return SentenceFibreObservation(
        fibre_key=packed.fibre_key,
        sentence_ordinal=packed.sentence_ordinal,
        start_char=packed.base_char,
        end_char=packed.end_char,
        tokens=tuple(tokens),
    )


def encode_packed_fibre(packed: PackedSentenceFibre) -> bytes:
    header = bytearray(_MAGIC)
    header.extend(struct.pack("<H", len(packed.fibre_key)))
    header.extend(packed.fibre_key)
    header.extend(
        struct.pack(
            "<QQQI",
            packed.sentence_ordinal,
            packed.base_char,
            packed.end_char,
            packed.token_count,
        )
    )
    return bytes(header) + packed.canonical_payload()


def decode_packed_fibre(payload: bytes) -> PackedSentenceFibre:
    view = memoryview(payload)
    offset = 0
    if bytes(view[: len(_MAGIC)]) != _MAGIC:
        raise FibreLayoutError("packed fibre magic/version mismatch")
    offset += len(_MAGIC)
    if len(view) < offset + 2:
        raise FibreLayoutError("truncated packed fibre header")
    key_len = struct.unpack_from("<H", view, offset)[0]
    offset += 2
    header_size = struct.calcsize("<QQQI")
    if len(view) < offset + key_len + header_size:
        raise FibreLayoutError("truncated packed fibre header")
    fibre_key = bytes(view[offset : offset + key_len])
    offset += key_len
    sentence_ordinal, base_char, end_char, token_count = struct.unpack_from(
        "<QQQI", view, offset
    )
    offset += header_size
    columns: dict[str, NarrowIntColumn] = {}
    column_header_size = struct.calcsize("<BBI")
    for name in _COLUMN_NAMES:
        if len(view) < offset + column_header_size:
            raise FibreLayoutError("truncated packed column header")
        signed_flag, width, count = struct.unpack_from("<BBI", view, offset)
        offset += column_header_size
        if count != token_count:
            raise FibreLayoutError("packed column count disagrees with fibre token count")
        byte_count = width * count
        if len(view) < offset + byte_count:
            raise FibreLayoutError("truncated packed column payload")
        data = bytes(view[offset : offset + byte_count])
        offset += byte_count
        columns[name] = NarrowIntColumn.from_canonical_bytes(
            data,
            signed=bool(signed_flag),
            width=width,
            count=count,
        )
    if offset != len(view):
        raise FibreLayoutError("trailing bytes after packed fibre")
    return PackedSentenceFibre(
        fibre_key=fibre_key,
        sentence_ordinal=int(sentence_ordinal),
        base_char=int(base_char),
        end_char=int(end_char),
        columns=columns,
    )


@dataclass(frozen=True, slots=True)
class FibreLayoutMeasurement:
    token_count: int
    packed_numeric_payload_bytes: int
    canonical_codec_bytes: int
    zlib_codec_bytes: int
    naive_u64_equivalent_bytes: int
    max_start_offset: int
    max_token_length: int
    max_abs_head_delta: int
    column_widths: tuple[tuple[str, int], ...]


def measure_fibre_layout(packed: PackedSentenceFibre) -> FibreLayoutMeasurement:
    encoded = encode_packed_fibre(packed)
    starts = packed.columns["start_offset"].as_tuple()
    lengths = packed.columns["length"].as_tuple()
    heads = packed.columns["head_delta"].as_tuple()
    # Abstract same-field fixed-u64 payload comparator, not a PostgreSQL row-size
    # estimate. Tuple/index/page/TOAST overhead is deliberately excluded.
    naive_u64_equivalent_bytes = packed.token_count * len(_COLUMN_NAMES) * 8
    return FibreLayoutMeasurement(
        token_count=packed.token_count,
        packed_numeric_payload_bytes=packed.numeric_payload_bytes,
        canonical_codec_bytes=len(encoded),
        zlib_codec_bytes=len(zlib.compress(encoded, level=9)),
        naive_u64_equivalent_bytes=naive_u64_equivalent_bytes,
        max_start_offset=max(starts, default=0),
        max_token_length=max(lengths, default=0),
        max_abs_head_delta=max((abs(value) for value in heads), default=0),
        column_widths=tuple(
            (name, packed.columns[name].itemsize) for name in _COLUMN_NAMES
        ),
    )


__all__ = [
    "BranchPathAddress",
    "BranchStep",
    "FibreLayoutError",
    "FibreLayoutMeasurement",
    "FibreTokenAddress",
    "NarrowIntColumn",
    "PackedSentenceFibre",
    "SentenceFibreObservation",
    "TokenObservation",
    "decode_packed_fibre",
    "encode_packed_fibre",
    "measure_fibre_layout",
    "pack_sentence_fibre",
    "unpack_sentence_fibre",
]
