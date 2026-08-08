from __future__ import annotations

from src.storage.postgres.typed_value_store import flatten_typed_value


def test_flatten_typed_value_is_deterministic_and_relational() -> None:
    left = {"z": [1, True, None], "a": {"bytes": b"abc", "text": "x"}}
    right = {"a": {"text": "x", "bytes": b"abc"}, "z": [1, True, None]}

    left_root, left_kind, left_digest, left_rows = flatten_typed_value(left)
    right_root, right_kind, right_digest, right_rows = flatten_typed_value(right)

    assert left_root == right_root
    assert left_kind == right_kind == "mapping"
    assert left_digest == right_digest
    assert left_rows == right_rows
    assert left_rows[0].path_ref == "$"
    assert {row.value_kind for row in left_rows} >= {
        "mapping",
        "sequence",
        "integer",
        "boolean",
        "bytes",
        "text",
        "null",
    }


def test_scalar_roots_preserve_scalar_kind() -> None:
    root_ref, root_kind, digest, rows = flatten_typed_value(42)

    assert root_ref.endswith(digest.hex())
    assert root_kind == "integer"
    assert len(rows) == 1
    assert rows[0].integer_value == 42
