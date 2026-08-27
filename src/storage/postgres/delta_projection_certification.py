"""Reusable exact certification helpers for delta-fed projections.

This module intentionally knows nothing about anaphora or PNF tables. It owns
the evidence algebra used by runtime instances of the contract:

    source delta -> projection atoms -> affected keys -> authoritative observer.

Rows are compared as multisets after portable canonicalisation. This preserves
multiplicity while refusing to treat database-local allocation order as
semantic identity.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence

_SAMPLE_LIMIT = 20


def canonical_cell(value: Any) -> Any:
    if isinstance(value, memoryview):
        value = bytes(value)
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, tuple):
        return [canonical_cell(item) for item in value]
    if isinstance(value, list):
        return [canonical_cell(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): canonical_cell(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    return value


def canonical_row(row: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(canonical_cell(value) for value in row)


def _row_key(row: Sequence[Any]) -> str:
    return json.dumps(
        canonical_row(row),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _digest_counter(counter: Counter[str]) -> str:
    payload = json.dumps(
        sorted(counter.items()),
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def multiset_digest(rows: Iterable[Sequence[Any]]) -> str:
    return _digest_counter(Counter(_row_key(row) for row in rows))


def compare_multiset(
    legacy_rows: Iterable[Sequence[Any]],
    projected_rows: Iterable[Sequence[Any]],
) -> dict[str, Any]:
    legacy = Counter(_row_key(row) for row in legacy_rows)
    projected = Counter(_row_key(row) for row in projected_rows)
    missing = legacy - projected
    extra = projected - legacy
    return {
        "equal": not missing and not extra,
        "legacy_count": sum(legacy.values()),
        "projected_count": sum(projected.values()),
        "legacy_sha256": _digest_counter(legacy),
        "projected_sha256": _digest_counter(projected),
        "missing_count": sum(missing.values()),
        "extra_count": sum(extra.values()),
        "missing": [
            {"row": json.loads(row), "multiplicity": count}
            for row, count in sorted(missing.items())[:_SAMPLE_LIMIT]
        ],
        "extra": [
            {"row": json.loads(row), "multiplicity": count}
            for row, count in sorted(extra.items())[:_SAMPLE_LIMIT]
        ],
    }


@dataclass(frozen=True, slots=True)
class DeltaCertificationLayer:
    name: str
    surfaces: tuple[str, ...]


def certify_layers(
    legacy: Mapping[str, Iterable[Sequence[Any]]],
    projected: Mapping[str, Iterable[Sequence[Any]]],
    *,
    layers: Sequence[DeltaCertificationLayer],
) -> dict[str, Any]:
    surface_results: dict[str, Any] = {}
    layer_results: dict[str, Any] = {}
    for layer in layers:
        missing_surface_names = [
            name
            for name in layer.surfaces
            if name not in legacy or name not in projected
        ]
        if missing_surface_names:
            raise KeyError(
                f"delta certification layer {layer.name!r} is missing surfaces "
                f"{missing_surface_names!r}"
            )
        for surface in layer.surfaces:
            surface_results[surface] = compare_multiset(
                legacy[surface],
                projected[surface],
            )
        failed = [
            surface
            for surface in layer.surfaces
            if not surface_results[surface]["equal"]
        ]
        layer_results[layer.name] = {
            "equal": not failed,
            "surfaces": list(layer.surfaces),
            "mismatch_surfaces": failed,
        }

    failed_layers = [
        name for name, result in layer_results.items() if not result["equal"]
    ]
    return {
        "commuting_square_equal": not failed_layers,
        "layers": layer_results,
        "surfaces": surface_results,
        "mismatch_layers": failed_layers,
    }


__all__ = [
    "DeltaCertificationLayer",
    "canonical_cell",
    "canonical_row",
    "certify_layers",
    "compare_multiset",
    "multiset_digest",
]
