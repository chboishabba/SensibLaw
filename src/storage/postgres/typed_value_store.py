"""Relational storage for open typed values without JSON or JSONB.

The execution schema uses this only where a semantic mapping is genuinely open
(e.g. qualifier state, candidate payload, metrics).  Control-plane state stays
in ordinary typed columns and never traverses this tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256, canonical_value


TYPED_VALUE_CONTRACT = "itir.relational-typed-value.v1"


@dataclass(frozen=True)
class TypedValueRow:
    path_ref: str
    parent_path_ref: str | None
    ordinal: int
    key_ref: str | None
    value_kind: str
    text_value: str | None = None
    integer_value: int | None = None
    float_value: float | None = None
    boolean_value: bool | None = None
    bytes_value: bytes | None = None


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "text"
    if isinstance(value, bytes):
        return "bytes"
    if isinstance(value, Mapping):
        return "mapping"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return "sequence"
    raise ValueError(f"unsupported relational typed value: {type(value).__name__}")


def _path(parent: str | None, ordinal: int, key: str | None) -> str:
    segment = f"{ordinal}:{key}" if key is not None else str(ordinal)
    return f"{parent}/{segment}" if parent else f"$/{segment}"


def flatten_typed_value(value: Any) -> tuple[str, str, bytes, tuple[TypedValueRow, ...]]:
    normalized = canonical_value(value)
    root_kind = _kind(normalized)
    digest = bytes.fromhex(canonical_sha256(normalized))
    root_ref = "typed-value:" + digest.hex()
    rows: list[TypedValueRow] = []

    def visit(current: Any, *, path_ref: str, parent: str | None, ordinal: int, key: str | None) -> None:
        current_kind = _kind(current)
        kwargs: dict[str, Any] = {}
        if current_kind == "text":
            kwargs["text_value"] = current
        elif current_kind == "integer":
            kwargs["integer_value"] = current
        elif current_kind == "float":
            kwargs["float_value"] = current
        elif current_kind == "boolean":
            kwargs["boolean_value"] = current
        elif current_kind == "bytes":
            kwargs["bytes_value"] = current
        rows.append(
            TypedValueRow(
                path_ref=path_ref,
                parent_path_ref=parent,
                ordinal=ordinal,
                key_ref=key,
                value_kind=current_kind,
                **kwargs,
            )
        )
        if current_kind == "mapping":
            for child_ordinal, child_key in enumerate(sorted(current)):
                child_path = _path(path_ref, child_ordinal, child_key)
                visit(
                    current[child_key],
                    path_ref=child_path,
                    parent=path_ref,
                    ordinal=child_ordinal,
                    key=child_key,
                )
        elif current_kind == "sequence":
            for child_ordinal, child in enumerate(current):
                child_path = _path(path_ref, child_ordinal, None)
                visit(
                    child,
                    path_ref=child_path,
                    parent=path_ref,
                    ordinal=child_ordinal,
                    key=None,
                )

    visit(normalized, path_ref="$", parent=None, ordinal=0, key=None)
    return root_ref, root_kind, digest, tuple(rows)


def persist_typed_value(cursor: Any, value: Any) -> str:
    root_ref, root_kind, digest, rows = flatten_typed_value(value)
    cursor.execute(
        """
        INSERT INTO execution.semantic_typed_value_root
            (root_ref, contract_ref, root_kind, root_sha256)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (root_ref) DO NOTHING
        """,
        (root_ref, TYPED_VALUE_CONTRACT, root_kind, digest),
    )
    cursor.executemany(
        """
        INSERT INTO execution.semantic_typed_value_node
            (root_ref, path_ref, parent_path_ref, ordinal, key_ref, value_kind,
             text_value, integer_value, float_value, boolean_value, bytes_value)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (root_ref, path_ref) DO NOTHING
        """,
        [
            (
                root_ref,
                row.path_ref,
                row.parent_path_ref,
                row.ordinal,
                row.key_ref,
                row.value_kind,
                row.text_value,
                row.integer_value,
                row.float_value,
                row.boolean_value,
                row.bytes_value,
            )
            for row in rows
        ],
    )
    return root_ref


def load_typed_value(cursor: Any, root_ref: str | None) -> Any:
    if root_ref is None:
        return {}
    cursor.execute(
        """
        SELECT path_ref, parent_path_ref, ordinal, key_ref, value_kind,
               text_value, integer_value, float_value, boolean_value, bytes_value
        FROM execution.semantic_typed_value_node
        WHERE root_ref = %s
        ORDER BY length(path_ref) DESC, path_ref DESC
        """,
        (root_ref,),
    )
    rows = cursor.fetchall()
    if not rows:
        raise ValueError(f"typed value root has no nodes: {root_ref}")
    built: dict[str, Any] = {}
    metadata: dict[str, tuple[str | None, int, str | None, str]] = {}
    for row in rows:
        (
            path_ref,
            parent_path_ref,
            ordinal,
            key_ref,
            value_kind,
            text_value,
            integer_value,
            float_value,
            boolean_value,
            bytes_value,
        ) = row
        path_ref = str(path_ref)
        kind = str(value_kind)
        if kind == "mapping":
            value: Any = {}
        elif kind == "sequence":
            value = []
        elif kind == "text":
            value = str(text_value)
        elif kind == "integer":
            value = int(integer_value)
        elif kind == "float":
            value = float(float_value)
        elif kind == "boolean":
            value = bool(boolean_value)
        elif kind == "bytes":
            value = bytes(bytes_value)
        elif kind == "null":
            value = None
        else:  # pragma: no cover - database constraint protects this
            raise ValueError(f"unsupported stored typed value kind: {kind}")
        built[path_ref] = value
        metadata[path_ref] = (
            str(parent_path_ref) if parent_path_ref is not None else None,
            int(ordinal),
            str(key_ref) if key_ref is not None else None,
            kind,
        )

    for path_ref in sorted(built, key=len, reverse=True):
        parent, ordinal, key, _kind_ref = metadata[path_ref]
        if parent is None:
            continue
        parent_value = built[parent]
        if isinstance(parent_value, dict):
            if key is None:
                raise ValueError("mapping child is missing key")
            parent_value[key] = built[path_ref]
        elif isinstance(parent_value, list):
            while len(parent_value) <= ordinal:
                parent_value.append(None)
            parent_value[ordinal] = built[path_ref]
        else:
            raise ValueError("typed value child has scalar parent")

    result = built["$"]
    cursor.execute(
        "SELECT encode(root_sha256, 'hex') FROM execution.semantic_typed_value_root WHERE root_ref = %s",
        (root_ref,),
    )
    row = cursor.fetchone()
    if row is None or str(row[0]) != canonical_sha256(result):
        raise ValueError("relational typed value digest mismatch")
    return result


__all__ = [
    "TYPED_VALUE_CONTRACT",
    "TypedValueRow",
    "flatten_typed_value",
    "load_typed_value",
    "persist_typed_value",
]
