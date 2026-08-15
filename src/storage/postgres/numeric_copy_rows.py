"""Typed COPY staging for the strict numeric PostgreSQL parser path.

The temporary carrier is execution-only.  It copies exactly the requested
column names/types from the authority table with ``WITH NO DATA`` and therefore
does not inherit unrelated NOT NULL/default/constraint metadata.  This avoids
per-batch information_schema inspection and ALTER TABLE repair while preserving
the existing COPY -> INSERT ... ON CONFLICT DO NOTHING authority semantics.
"""

from __future__ import annotations

from typing import Any, Sequence


def _sql_identifier(value: str) -> str:
    """Accept only internal SQL identifiers without invoking regex machinery."""

    text = str(value)
    if not text or not text.replace("_", "").isalnum() or text[0].isdigit():
        raise ValueError(f"invalid internal SQL identifier: {value!r}")
    return text


def copy_numeric_rows(
    cursor: Any,
    *,
    table: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> None:
    """Bulk-admit bounded numeric rows through a constraint-free temp carrier."""

    if not rows:
        return
    target = _sql_identifier(table)
    selected_columns = tuple(_sql_identifier(column) for column in columns)
    if not selected_columns:
        raise ValueError("numeric COPY requires at least one selected column")

    temporary = _sql_identifier("tmp_" + target.removeprefix("semantic_"))
    column_sql = ", ".join(selected_columns)
    cursor.execute(
        f"CREATE TEMP TABLE {temporary} ON COMMIT DROP AS "
        f"SELECT {column_sql} FROM execution.{target} WITH NO DATA"
    )
    with cursor.copy(f"COPY {temporary} ({column_sql}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
    cursor.execute(
        f"INSERT INTO execution.{target} ({column_sql}) "
        f"SELECT {column_sql} FROM {temporary} ON CONFLICT DO NOTHING"
    )


__all__ = ["copy_numeric_rows"]
