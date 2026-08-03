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
    """Hash canonical JSON incrementally without retaining detached copies.

    ``canonical_json`` remains the API for callers that need an owned carrier.
    Hashing only needs its deterministic wire representation, so streaming the
    same encoder avoids a detached object graph and a whole-payload byte string.
    """

    options = {
        "ensure_ascii": False,
        "sort_keys": True,
        "separators": (",", ":"),
    }
    direct_values = value.values() if isinstance(value, Mapping) else (value,)
    # Closure replay persists proposal batches of at most 65,536 rows.  Let the
    # C encoder handle those bounded artifacts: it is substantially faster and
    # its temporary wire buffer remains small relative to the resident carrier
    # graph.  Larger materialized projections still use the incremental path so
    # hashing cannot add another whole, potentially multi-gigabyte byte string.
    requires_streaming = any(
        isinstance(item, (list, tuple)) and len(item) > 131_072
        for item in direct_values
    )
    try:
        if not requires_streaming:
            return hashlib.sha256(
                json.dumps(value, **options).encode("utf-8")
            ).hexdigest()
        digest = hashlib.sha256()
        for chunk in json.JSONEncoder(**options).iterencode(value):
            digest.update(chunk.encode("utf-8"))
    except (TypeError, ValueError) as error:
        raise ValueError("carrier value must be JSON-serializable") from error
    return digest.hexdigest()
