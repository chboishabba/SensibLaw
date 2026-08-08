"""Typed canonical hashing and reference normalization for policy carriers.

JSON is deliberately forbidden as an identity, persistence, checkpoint, or
transport substrate.  Canonical identities are length-prefixed typed byte
streams under an explicit contract version.  ``canonical_json`` remains only
as a compatibility spelling for callers that need a detached primitive value;
it performs no JSON serialization or parsing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import math
import struct
from typing import Any


TYPED_CANONICAL_CONTRACT = "itir.typed-canonical.v1"


def require_text(value: Any, field: str) -> str:
    """Return a non-empty normalized string or fail with a field-specific error."""

    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def canonical_refs(values: Iterable[Any] | None) -> tuple[str, ...]:
    """Return unique, non-empty references in deterministic order."""

    return tuple(sorted({require_text(value, "reference") for value in values or ()}))


def _primitive_copy(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str, bytes)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return float("nan")
        return float(value)
    if isinstance(value, Enum):
        return _primitive_copy(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return _primitive_copy(asdict(value))
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _primitive_copy(to_dict())
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item)):
            text_key = str(key) if not isinstance(key, str) else key
            normalized[text_key] = _primitive_copy(value[key])
        return normalized
    if isinstance(value, (set, frozenset)):
        rows = [_primitive_copy(item) for item in value]
        return sorted(rows, key=canonical_bytes)
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, memoryview)
    ):
        return [_primitive_copy(item) for item in value]
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    raise ValueError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json(value: Any) -> Any:
    """Compatibility spelling for a detached typed primitive value.

    This function performs no JSON encoding or decoding.  New code should use
    ``canonical_value``; the old name is retained only to avoid hidden serde in
    compatibility callers while they are migrated.
    """

    return _primitive_copy(value)


def canonical_value(value: Any) -> Any:
    return _primitive_copy(value)


def canonical_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = canonical_value(dict(value or {}))
    if not isinstance(normalized, dict):
        raise ValueError("carrier payload must be a mapping")
    return normalized


def _length_prefix(length: int) -> bytes:
    if length < 0:
        raise ValueError("canonical length cannot be negative")
    return length.to_bytes(8, "big", signed=False)


def _encode_integer(value: int) -> bytes:
    sign = b"-" if value < 0 else b"+"
    magnitude = abs(value)
    width = max(1, (magnitude.bit_length() + 7) // 8)
    raw = magnitude.to_bytes(width, "big", signed=False)
    return b"I" + sign + _length_prefix(len(raw)) + raw


def _encode_into(chunks: list[bytes], value: Any) -> None:
    value = _primitive_copy(value)
    if value is None:
        chunks.append(b"N")
        return
    if value is False:
        chunks.append(b"B0")
        return
    if value is True:
        chunks.append(b"B1")
        return
    if isinstance(value, int) and not isinstance(value, bool):
        chunks.append(_encode_integer(value))
        return
    if isinstance(value, float):
        chunks.append(b"F" + struct.pack(">d", value))
        return
    if isinstance(value, str):
        raw = value.encode("utf-8")
        chunks.append(b"S" + _length_prefix(len(raw)) + raw)
        return
    if isinstance(value, bytes):
        chunks.append(b"Y" + _length_prefix(len(value)) + value)
        return
    if isinstance(value, Mapping):
        chunks.append(b"M" + _length_prefix(len(value)))
        for key in sorted(value):
            _encode_into(chunks, key)
            _encode_into(chunks, value[key])
        return
    if isinstance(value, list):
        chunks.append(b"Q" + _length_prefix(len(value)))
        for item in value:
            _encode_into(chunks, item)
        return
    raise ValueError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Return the deterministic typed byte representation for ``value``."""

    chunks = [b"ITIR", _length_prefix(len(TYPED_CANONICAL_CONTRACT))]
    chunks.append(TYPED_CANONICAL_CONTRACT.encode("ascii"))
    _encode_into(chunks, value)
    return b"".join(chunks)


def canonical_sha256(value: Any) -> str:
    """Hash typed canonical bytes without JSON serialization."""

    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def canonical_fields_sha256(*fields: Any) -> str:
    """Hash an ordered tuple of typed fields under the canonical contract."""

    return canonical_sha256(list(fields))


__all__ = [
    "TYPED_CANONICAL_CONTRACT",
    "canonical_bytes",
    "canonical_fields_sha256",
    "canonical_json",
    "canonical_mapping",
    "canonical_refs",
    "canonical_sha256",
    "canonical_value",
    "require_text",
]
