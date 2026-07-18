"""Canonical JSON, hashing, and reference normalization for policy carriers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any


def require_text(value: Any, field: str) -> str:
    """Return a non-empty normalized string or fail with a field-specific error."""

    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def canonical_refs(values: Iterable[Any] | None) -> tuple[str, ...]:
    """Return unique, non-empty references in deterministic serialization order."""

    return tuple(sorted({require_text(value, "reference") for value in values or ()}))


def canonical_json(value: Any) -> Any:
    """Return a detached, JSON-safe value with deterministic mapping key order.

    The returned value contains no aliases to caller-owned mutable containers.
    Ordering of alternatives remains representational only; this function does
    not rank or select semantic alternatives.
    """

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ValueError("carrier value must be JSON-serializable") from error
    return json.loads(encoded)


def canonical_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = canonical_json(dict(value or {}))
    if not isinstance(normalized, dict):
        raise ValueError("carrier payload must be a mapping")
    return normalized


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        canonical_json(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
