"""Exact COPY encoding policy for the typed persistence staging table."""

from __future__ import annotations

import os
from typing import Any, Iterable


# Must match work_conserving_stage._STAGE_COLUMNS and migration 061 exactly:
# five execution text coordinates, partition int4, ordinal int8, twelve text
# payload slots, six int8 payload slots, two bytea payload slots.
STAGE_BINARY_TYPES: tuple[str, ...] = (
    *("text" for _ in range(5)),
    "int4",
    "int8",
    *("text" for _ in range(12)),
    *("int8" for _ in range(6)),
    "bytea",
    "bytea",
)


def binary_copy_enabled() -> bool:
    raw = os.environ.get("SENSIBLAW_PERSISTENCE_BINARY_COPY", "1")
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def write_stage_rows(cursor: Any, copy_sql: str, rows: Iterable[tuple[Any, ...]]) -> None:
    """COPY typed stage rows using exact binary types when enabled."""

    sql = copy_sql + " (FORMAT BINARY)" if binary_copy_enabled() else copy_sql
    with cursor.copy(sql) as copy:
        if binary_copy_enabled():
            copy.set_types(STAGE_BINARY_TYPES)
        for row in rows:
            if len(row) != len(STAGE_BINARY_TYPES):
                raise ValueError(
                    "staged COPY row width disagrees with typed persistence schema: "
                    f"row={len(row)} schema={len(STAGE_BINARY_TYPES)}"
                )
            copy.write_row(row)


__all__ = ["STAGE_BINARY_TYPES", "binary_copy_enabled", "write_stage_rows"]
