"""Read-only PostgreSQL mutation/churn and query-template attribution.

This is a diagnostic consumer, not compiler work. It is intended for fresh or
explicitly diagnostic databases where PostgreSQL cumulative counters can be
interpreted against one known run. It never resets statistics and never writes
semantic state.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


CHURN_AUDIT_REF = "sensiblaw.postgres-runtime-churn-audit.v0_1"


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return 0.0 if numerator == 0 else None
    return numerator / denominator


@dataclass(frozen=True, slots=True)
class TableChurnReceipt:
    schema_name: str
    table_name: str
    inserts: int
    updates: int
    deletes: int
    live_rows: int
    dead_rows: int
    sequential_scans: int
    index_scans: int

    @property
    def total_mutations(self) -> int:
        return self.inserts + self.updates + self.deletes

    @property
    def churn_amplification(self) -> float | None:
        return _ratio(self.total_mutations, self.live_rows)

    @property
    def delete_to_live_ratio(self) -> float | None:
        return _ratio(self.deletes, self.live_rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_name": self.schema_name,
            "table_name": self.table_name,
            "inserts": self.inserts,
            "updates": self.updates,
            "deletes": self.deletes,
            "live_rows": self.live_rows,
            "dead_rows": self.dead_rows,
            "total_mutations": self.total_mutations,
            "churn_amplification": self.churn_amplification,
            "delete_to_live_ratio": self.delete_to_live_ratio,
            "sequential_scans": self.sequential_scans,
            "index_scans": self.index_scans,
        }


@dataclass(frozen=True, slots=True)
class QueryTemplateReceipt:
    query_id: int | None
    query: str
    calls: int
    rows: int
    total_exec_ms: float
    mean_exec_ms: float
    shared_blks_hit: int
    shared_blks_read: int
    shared_blks_dirtied: int
    shared_blks_written: int
    temp_blks_read: int
    temp_blks_written: int
    wal_records: int | None
    wal_bytes: int | None

    def to_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


def _table_churn(
    cursor: Any, *, schemas: tuple[str, ...]
) -> tuple[TableChurnReceipt, ...]:
    cursor.execute(
        """
        SELECT schemaname,
               relname,
               n_tup_ins,
               n_tup_upd,
               n_tup_del,
               n_live_tup,
               n_dead_tup,
               seq_scan,
               idx_scan
          FROM pg_stat_user_tables
         WHERE schemaname = ANY(%s)
         ORDER BY (n_tup_ins + n_tup_upd + n_tup_del) DESC,
                  schemaname,
                  relname
        """,
        (list(schemas),),
    )
    return tuple(
        TableChurnReceipt(
            schema_name=str(row[0]),
            table_name=str(row[1]),
            inserts=int(row[2]),
            updates=int(row[3]),
            deletes=int(row[4]),
            live_rows=int(row[5]),
            dead_rows=int(row[6]),
            sequential_scans=int(row[7]),
            index_scans=int(row[8] or 0),
        )
        for row in cursor.fetchall()
    )


def _pg_stat_statements_available(cursor: Any) -> bool:
    """Require both extension registration and postmaster preload."""

    cursor.execute(
        """
        SELECT EXISTS (
                   SELECT 1
                     FROM pg_extension
                    WHERE extname = 'pg_stat_statements'
               ),
               current_setting('shared_preload_libraries', true)
        """
    )
    extension_exists, preloaded = cursor.fetchone()
    libraries = {
        item.strip()
        for item in str(preloaded or "").split(",")
        if item.strip()
    }
    return bool(extension_exists) and "pg_stat_statements" in libraries


def _statement_columns(cursor: Any) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'pg_stat_statements'
        """
    )
    return {str(row[0]) for row in cursor.fetchall()}


def _query_templates(cursor: Any, *, limit: int) -> tuple[QueryTemplateReceipt, ...]:
    if not _pg_stat_statements_available(cursor):
        return ()
    columns = _statement_columns(cursor)
    required = {
        "query",
        "calls",
        "rows",
        "total_exec_time",
        "mean_exec_time",
        "shared_blks_hit",
        "shared_blks_read",
        "shared_blks_dirtied",
        "shared_blks_written",
        "temp_blks_read",
        "temp_blks_written",
    }
    if not required <= columns:
        return ()
    queryid_expr = "queryid" if "queryid" in columns else "NULL::bigint"
    wal_records_expr = "wal_records" if "wal_records" in columns else "NULL::bigint"
    wal_bytes_expr = "wal_bytes" if "wal_bytes" in columns else "NULL::numeric"
    cursor.execute(
        f"""
        SELECT {queryid_expr},
               query,
               calls,
               rows,
               total_exec_time,
               mean_exec_time,
               shared_blks_hit,
               shared_blks_read,
               shared_blks_dirtied,
               shared_blks_written,
               temp_blks_read,
               temp_blks_written,
               {wal_records_expr},
               {wal_bytes_expr}
          FROM public.pg_stat_statements
         WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
           AND (query ILIKE '%execution.%' OR query ILIKE '%resolution.%')
         ORDER BY total_exec_time DESC
         LIMIT %s
        """,
        (int(limit),),
    )
    receipts: list[QueryTemplateReceipt] = []
    for row in cursor.fetchall():
        wal_bytes = row[13]
        if isinstance(wal_bytes, Decimal):
            wal_bytes = int(wal_bytes)
        receipts.append(
            QueryTemplateReceipt(
                query_id=None if row[0] is None else int(row[0]),
                query=str(row[1]),
                calls=int(row[2]),
                rows=int(row[3]),
                total_exec_ms=float(row[4]),
                mean_exec_ms=float(row[5]),
                shared_blks_hit=int(row[6]),
                shared_blks_read=int(row[7]),
                shared_blks_dirtied=int(row[8]),
                shared_blks_written=int(row[9]),
                temp_blks_read=int(row[10]),
                temp_blks_written=int(row[11]),
                wal_records=None if row[12] is None else int(row[12]),
                wal_bytes=None if wal_bytes is None else int(wal_bytes),
            )
        )
    return tuple(receipts)


def build_runtime_churn_audit(
    database_url: str,
    *,
    schemas: tuple[str, ...] = ("execution", "resolution"),
    query_limit: int = 30,
) -> dict[str, Any]:
    """Return cumulative per-table churn and optional query-template evidence."""

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    SELECT current_database(),
                           pg_postmaster_start_time(),
                           stats_reset
                      FROM pg_stat_database
                     WHERE datname = current_database()
                    """
                )
                database_name, postmaster_started, stats_reset = cursor.fetchone()
                tables = _table_churn(cursor, schemas=schemas)
                statements_available = _pg_stat_statements_available(cursor)
                queries = (
                    _query_templates(cursor, limit=query_limit)
                    if statements_available
                    else ()
                )
                totals = {
                    "inserts": sum(row.inserts for row in tables),
                    "updates": sum(row.updates for row in tables),
                    "deletes": sum(row.deletes for row in tables),
                    "live_rows": sum(row.live_rows for row in tables),
                    "dead_rows": sum(row.dead_rows for row in tables),
                }
                total_mutations = (
                    totals["inserts"] + totals["updates"] + totals["deletes"]
                )
                totals["total_mutations"] = total_mutations
                totals["churn_amplification"] = _ratio(
                    total_mutations, totals["live_rows"]
                )
                return {
                    "contract_ref": CHURN_AUDIT_REF,
                    "database": str(database_name),
                    "postmaster_started_at": postmaster_started.isoformat(),
                    "stats_reset_at": (
                        None if stats_reset is None else stats_reset.isoformat()
                    ),
                    "counter_semantics": (
                        "cumulative PostgreSQL statistics since their reset; interpret as "
                        "one-run attribution only on a fresh/dedicated database"
                    ),
                    "schemas": list(schemas),
                    "totals": totals,
                    "tables": [row.to_dict() for row in tables],
                    "pg_stat_statements_available": statements_available,
                    "query_templates": [row.to_dict() for row in queries],
                }
    finally:
        connection.close()


__all__ = [
    "CHURN_AUDIT_REF",
    "QueryTemplateReceipt",
    "TableChurnReceipt",
    "build_runtime_churn_audit",
]
