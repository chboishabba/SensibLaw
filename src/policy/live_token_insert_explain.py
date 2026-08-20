"""Diagnostic-only EXPLAIN of genuine numeric parser-token authority INSERTs.

This probe observes the real first-write token admission inside the existing
parser partition transaction.  It never disables constraints, triggers or
indexes.  Selected token COPY batches execute their canonical
``INSERT .. SELECT .. ON CONFLICT DO NOTHING`` under ``EXPLAIN ANALYZE`` and
record the exact token-table constraint/index/trigger inventory that was active.

Installation must precede ``numeric_parser_projection_hot_path`` so the latter's
producer-complete enrichment still flows through this wrapper with final
``sentence_id``, ``token_id`` and ``head_token_id`` coordinates present.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.storage.postgres.region_close_trigger_probe import plan_metrics


LIVE_TOKEN_INSERT_EXPLAIN_REF = "sensiblaw.live-token-insert-explain.v0_1"
_ORDINAL_ENV = "SENSIBLAW_TOKEN_INSERT_EXPLAIN_ORDINALS"
_OUTPUT_ENV = "SENSIBLAW_TOKEN_INSERT_EXPLAIN_OUTPUT"
_INSTALL_MARKER = "_live_token_insert_explain_installed"


def _parse_ordinals(raw: str) -> tuple[int, ...]:
    values = tuple(sorted(int(part.strip()) for part in raw.split(",") if part.strip()))
    if not values or any(value < 1 for value in values):
        raise ValueError(f"{_ORDINAL_ENV} requires positive ordinals")
    if len(set(values)) != len(values):
        raise ValueError(f"{_ORDINAL_ENV} must not contain duplicates")
    return values


def _compact_sql(query: Any) -> str:
    return " ".join(query.lower().split()) if isinstance(query, str) else ""


def _is_token_insert(query: Any) -> bool:
    compact = _compact_sql(query)
    return (
        compact.startswith("insert into execution.semantic_parser_token (")
        and " from tmp_parser_token on conflict do nothing" in compact
    )


def _constraint_inventory(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT constraint.oid,
               constraint.conname,
               constraint.contype,
               constraint.condeferrable,
               constraint.condeferred,
               pg_get_constraintdef(constraint.oid, TRUE),
               CASE WHEN constraint.confrelid = 0
                    THEN NULL
                    ELSE constraint.confrelid::regclass::text
                END
          FROM pg_constraint AS constraint
         WHERE constraint.conrelid = 'execution.semantic_parser_token'::regclass
         ORDER BY constraint.contype, constraint.conname
        """
    )
    return [
        {
            "oid": int(row[0]),
            "name": str(row[1]),
            "type": str(row[2]),
            "deferrable": bool(row[3]),
            "deferred": bool(row[4]),
            "definition": str(row[5]),
            "referenced_relation": str(row[6]) if row[6] is not None else None,
        }
        for row in cursor.fetchall()
    ]


def _index_inventory(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT index_meta.indexrelid::regclass::text,
               index_meta.indisprimary,
               index_meta.indisunique,
               index_meta.indisvalid,
               index_meta.indisready,
               pg_get_indexdef(index_meta.indexrelid)
          FROM pg_index AS index_meta
         WHERE index_meta.indrelid = 'execution.semantic_parser_token'::regclass
         ORDER BY index_meta.indexrelid::regclass::text
        """
    )
    return [
        {
            "name": str(row[0]),
            "primary": bool(row[1]),
            "unique": bool(row[2]),
            "valid": bool(row[3]),
            "ready": bool(row[4]),
            "definition": str(row[5]),
        }
        for row in cursor.fetchall()
    ]


def _trigger_inventory(cursor: Any) -> list[dict[str, Any]]:
    # Internal triggers are intentionally included: PostgreSQL implements FK
    # enforcement through internal RI triggers, which is precisely part of the
    # physical fan-out this diagnostic is intended to attribute.
    cursor.execute(
        """
        SELECT trigger.tgname,
               trigger.tgisinternal,
               trigger.tgenabled,
               pg_get_triggerdef(trigger.oid, TRUE),
               namespace.nspname,
               procedure.proname
          FROM pg_trigger AS trigger
          JOIN pg_proc AS procedure ON procedure.oid = trigger.tgfoid
          JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
         WHERE trigger.tgrelid = 'execution.semantic_parser_token'::regclass
         ORDER BY trigger.tgisinternal DESC, trigger.tgname
        """
    )
    return [
        {
            "name": str(row[0]),
            "internal": bool(row[1]),
            "enabled": str(row[2]),
            "definition": str(row[3]),
            "function_schema": str(row[4]),
            "function_name": str(row[5]),
        }
        for row in cursor.fetchall()
    ]


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(slots=True)
class _TokenInsertCapture:
    ordinal: int
    row_count: int
    columns: tuple[str, ...]
    constraints: list[dict[str, Any]]
    indexes: list[dict[str, Any]]
    triggers: list[dict[str, Any]]
    raw_plan: Any | None = None


class _TokenInsertExplainCursor:
    def __init__(self, cursor: Any, capture: _TokenInsertCapture) -> None:
        self._cursor = cursor
        self._capture = capture

    def execute(self, query: Any, params: Any = None, *args: Any, **kwargs: Any) -> Any:
        if _is_token_insert(query):
            if self._capture.raw_plan is not None:
                raise RuntimeError("selected token batch attempted duplicate authority INSERT")
            self._cursor.execute(
                "EXPLAIN (ANALYZE, BUFFERS, WAL, VERBOSE, SETTINGS, FORMAT JSON) "
                + query,
                params,
                *args,
                **kwargs,
            )
            row = self._cursor.fetchone()
            if row is None:
                raise RuntimeError("token INSERT EXPLAIN returned no plan")
            self._capture.raw_plan = row[0]
            return self
        self._cursor.execute(query, params, *args, **kwargs)
        return self

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


def install_live_token_insert_explain() -> bool:
    raw_ordinals = os.environ.get(_ORDINAL_ENV, "").strip()
    if not raw_ordinals:
        return False
    ordinals = _parse_ordinals(raw_ordinals)
    output_raw = os.environ.get(_OUTPUT_ENV, "").strip()
    if not output_raw:
        raise ValueError(f"{_OUTPUT_ENV} is required when {_ORDINAL_ENV} is enabled")
    output = Path(output_raw)

    from src.storage.postgres import spacy_numeric_projection as projection

    if getattr(projection, _INSTALL_MARKER, False):
        return False
    original = projection._copy_rows
    ordinal_set = frozenset(ordinals)
    token_batch_ordinal = 0

    def copy_rows(
        cursor: Any,
        *,
        table: str,
        columns: Sequence[str],
        rows: Iterable[Sequence[Any]],
        **kwargs: Any,
    ) -> Any:
        nonlocal token_batch_ordinal
        materialized = tuple(tuple(row) for row in rows)
        if table != "semantic_parser_token":
            return original(cursor, table=table, columns=columns, rows=materialized, **kwargs)

        token_batch_ordinal += 1
        ordinal = token_batch_ordinal
        if ordinal not in ordinal_set:
            return original(cursor, table=table, columns=columns, rows=materialized, **kwargs)

        capture = _TokenInsertCapture(
            ordinal=ordinal,
            row_count=len(materialized),
            columns=tuple(str(column) for column in columns),
            constraints=_constraint_inventory(cursor),
            indexes=_index_inventory(cursor),
            triggers=_trigger_inventory(cursor),
        )
        proxy = _TokenInsertExplainCursor(cursor, capture)
        result = original(proxy, table=table, columns=columns, rows=materialized, **kwargs)
        if capture.raw_plan is None:
            raise RuntimeError("selected token batch did not execute canonical authority INSERT")
        _append_jsonl(
            output,
            {
                "contract_ref": LIVE_TOKEN_INSERT_EXPLAIN_REF,
                "recorded_at": datetime.now(UTC).isoformat(),
                "pid": os.getpid(),
                "selection": {
                    "token_batch_ordinal": ordinal,
                    "configured_ordinals": list(ordinals),
                    "semantics": "process-local parser-token COPY batch ordinal",
                },
                "row_count": capture.row_count,
                "columns": list(capture.columns),
                "producer_complete_first_write": all(
                    name in capture.columns
                    for name in ("sentence_id", "token_id", "head_token_id")
                ),
                "constraints": capture.constraints,
                "indexes": capture.indexes,
                "triggers": capture.triggers,
                "metrics": plan_metrics(capture.raw_plan),
                "plan": capture.raw_plan,
                "transaction_semantics": (
                    "EXPLAIN ANALYZE executed the genuine first-write token INSERT "
                    "with all active constraints/indexes/triggers inside the original "
                    "parser partition transaction"
                ),
            },
        )
        return result

    projection._copy_rows = copy_rows
    setattr(projection, _INSTALL_MARKER, True)
    return True


__all__ = ["LIVE_TOKEN_INSERT_EXPLAIN_REF", "install_live_token_insert_explain"]
