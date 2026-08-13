from __future__ import annotations

import ast
from pathlib import Path

from src.policy.carriers.canonical import (
    TYPED_CANONICAL_CONTRACT,
    canonical_bytes,
    canonical_json,
    canonical_sha256,
)


def test_mapping_order_does_not_change_typed_identity() -> None:
    left = {"b": [2, 3], "a": {"x": True, "y": None}}
    right = {"a": {"y": None, "x": True}, "b": [2, 3]}

    assert canonical_sha256(left) == canonical_sha256(right)
    assert canonical_bytes(left).startswith(b"ITIR")
    assert TYPED_CANONICAL_CONTRACT.encode("ascii") in canonical_bytes(left)


def test_sequence_order_and_scalar_types_remain_distinct() -> None:
    assert canonical_sha256([1, 2]) != canonical_sha256([2, 1])
    assert canonical_sha256(1) != canonical_sha256("1")
    assert canonical_sha256(False) != canonical_sha256(0)


def test_compatibility_normalizer_performs_no_json_roundtrip() -> None:
    source = Path("src/policy/carriers/canonical.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert "json" not in imported
    value = {"tuple": (1, 2), "bytes": b"abc"}
    detached = canonical_json(value)
    assert detached == {"bytes": b"abc", "tuple": [1, 2]}
    assert detached is not value
