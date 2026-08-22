"""Diagnostic-only attribution for genuine non-sentence hierarchy closes.

The sentence-prefix experiments established that ordinary sentence-region closes
remain support-local through the corpus tail.  Full strict execution nevertheless
shows a tiny late population of non-sentence closes dominating region-close wall
work.  This probe instruments the shared ``_close_parent_interface`` seam used by
paragraph, adaptive-block, and document hierarchy materialization.

For the first configured closes of each selected ``RegionKind`` it records:

* the exact pre-close hierarchy fibre shape;
* ``EXPLAIN ANALYZE`` for the genuine canonical region-close UPDATE;
* per-query ``pg_stat_statements`` deltas across the complete parent-close call,
  including nested PL/pgSQL/SPI statements when the server tracks them.

No state is reconstructed or replayed.  The probe executes the real close inside
its original transaction.  It is installed only when
``SENSIBLAW_HIERARCHY_CLOSE_EXPLAIN_KINDS`` is explicitly configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import fcntl
import json
import os
from pathlib import Path
from typing import Any, Mapping

from src.pnf.numeric_hyperfabric import RegionKind
from src.storage.postgres.region_close_trigger_probe import plan_metrics


LIVE_HIERARCHY_CLOSE_ATTRIBUTION_REF = (
    "sensiblaw.live-hierarchy-close-attribution.v0_1"
)
_KINDS_ENV = "SENSIBLAW_HIERARCHY_CLOSE_EXPLAIN_KINDS"
_LIMIT_ENV = "SENSIBLAW_HIERARCHY_CLOSE_EXPLAIN_LIMIT_PER_KIND"
_OUTPUT_ENV = "SENSIBLAW_HIERARCHY_CLOSE_EXPLAIN_OUTPUT"
_STATE_ENV = "SENSIBLAW_HIERARCHY_CLOSE_EXPLAIN_STATE"
_INSTALL_MARKER = "_live_hierarchy_close_attribution_installed"
_STATE_REF = "sensiblaw.live-hierarchy-close-attribution-state.v0_1"


def _parse_kinds(raw: str) -> tuple[RegionKind, ...]:
    values: list[RegionKind] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            kind = RegionKind(int(token))
        except ValueError:
            try:
                kind = RegionKind[token.upper()]
            except KeyError as error:
                raise ValueError(f"unknown hierarchy region kind: {token}") from error
        if kind is RegionKind.SENTENCE:
            raise ValueError("hierarchy close attribution must not select SENTENCE")
        values.append(kind)
    if not values:
        raise ValueError(f"{_KINDS_ENV} must contain at least one non-sentence kind")
    if len(set(values)) != len(values):
        raise ValueError(f"{_KINDS_ENV} must not contain duplicate kinds")
    return tuple(sorted(values, key=int))


def _positive_limit() -> int:
    raw = os.environ.get(_LIMIT_ENV, "1").strip()
    value = int(raw)
    if value < 1:
        raise ValueError(f"{_LIMIT_ENV} must be positive")
    return value


def _compact_sql(query: Any) -> str:
    return " ".join(query.lower().split()) if isinstance(query, str) else ""


def _is_region_close_update(query: Any) -> bool:
    compact = _compact_sql(query)
    return (
        compact.startswith(
            "update execution.semantic_pnf_region set closure_state = %s"
        )
        and "graph_revision = %s" in compact
        and "closed_at = current_timestamp" in compact
        and "where region_id = %s" in compact
    )


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reserve_capture(
    *,
    state_path: Path,
    kinds: tuple[RegionKind, ...],
    kind: RegionKind,
    limit: int,
) -> int | None:
    """Reserve one global per-kind close ordinal, returning it when selected."""

    state_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(state_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        os.lseek(descriptor, 0, os.SEEK_SET)
        raw = os.read(descriptor, 65_536)
        configured = [int(item) for item in kinds]
        if raw:
            try:
                state = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise RuntimeError("hierarchy-close attribution state is unreadable") from error
            if state.get("contract_ref") != _STATE_REF:
                raise RuntimeError("hierarchy-close attribution state has wrong contract")
            if state.get("configured_kinds") != configured or state.get("limit") != limit:
                raise RuntimeError("hierarchy-close attribution state belongs to another run")
            counts = {
                str(key): int(value)
                for key, value in dict(state.get("seen_by_kind", {})).items()
            }
        else:
            counts = {}
        key = str(int(kind))
        ordinal = counts.get(key, 0) + 1
        counts[key] = ordinal
        payload = json.dumps(
            {
                "contract_ref": _STATE_REF,
                "configured_kinds": configured,
                "limit": limit,
                "seen_by_kind": counts,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.ftruncate(descriptor, 0)
        os.write(descriptor, payload)
        os.fsync(descriptor)
        return ordinal if ordinal <= limit else None
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _region_metadata(cursor: Any, region_id: int) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT run_ref, document_ref, region_id, parent_region_id, region_kind,
               start_char, end_char, sequence_no, closure_state, graph_revision,
               authored_boundary
          FROM execution.semantic_pnf_region
         WHERE region_id = %s
        """,
        (int(region_id),),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"hierarchy-close region disappeared: {region_id}")
    return {
        "run_ref": str(row[0]),
        "document_ref": str(row[1]),
        "region_id": int(row[2]),
        "parent_region_id": int(row[3]) if row[3] is not None else None,
        "region_kind": int(row[4]),
        "region_kind_name": RegionKind(int(row[4])).name,
        "start_char": int(row[5]),
        "end_char": int(row[6]),
        "sequence_no": int(row[7]),
        "closure_state": int(row[8]),
        "graph_revision": int(row[9]),
        "authored_boundary": bool(row[10]),
    }


def _hierarchy_support(cursor: Any, *, region_id: int) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT child.region_kind, child.closure_state, count(*)
          FROM execution.semantic_pnf_region AS child
         WHERE child.parent_region_id = %s
         GROUP BY child.region_kind, child.closure_state
         ORDER BY child.region_kind, child.closure_state
        """,
        (int(region_id),),
    )
    children = [
        {
            "region_kind": int(row[0]),
            "region_kind_name": RegionKind(int(row[0])).name,
            "closure_state": int(row[1]),
            "count": int(row[2]),
        }
        for row in cursor.fetchall()
    ]
    cursor.execute(
        """
        SELECT count(*),
               COALESCE(sum(interface.interface_cardinality), 0),
               COALESCE(sum(interface.unresolved_count), 0),
               COALESCE(sum(interface.node_count), 0),
               COALESCE(sum(interface.edge_count), 0)
          FROM execution.semantic_pnf_region AS child
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = child.region_id
         WHERE child.parent_region_id = %s
        """,
        (int(region_id),),
    )
    interface_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT export.target_kind, count(*)
          FROM execution.semantic_pnf_region AS child
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = child.region_id
          JOIN execution.semantic_pnf_interface_export AS export
            ON export.interface_id = interface.interface_id
         WHERE child.parent_region_id = %s
         GROUP BY export.target_kind
         ORDER BY export.target_kind
        """,
        (int(region_id),),
    )
    exports = {str(int(row[0])): int(row[1]) for row in cursor.fetchall()}
    return {
        "child_populations": children,
        "child_count": sum(item["count"] for item in children),
        "child_interface_count": int(interface_row[0]),
        "child_interface_cardinality": int(interface_row[1]),
        "child_unresolved_count": int(interface_row[2]),
        "child_node_count": int(interface_row[3]),
        "child_edge_count": int(interface_row[4]),
        "child_export_count_by_target_kind": exports,
    }


_STAT_SQL = """
SELECT queryid, calls, total_exec_time, rows,
       shared_blks_hit, shared_blks_read, shared_blks_dirtied, shared_blks_written,
       temp_blks_read, temp_blks_written, wal_records, wal_bytes, query
  FROM pg_stat_statements
 WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
   AND query NOT ILIKE '%%pg_stat_statements%%'
"""


def _statement_snapshot(cursor: Any) -> dict[int, dict[str, Any]]:
    cursor.execute(_STAT_SQL)
    result: dict[int, dict[str, Any]] = {}
    for row in cursor.fetchall():
        if row[0] is None:
            continue
        query_id = int(row[0])
        result[query_id] = {
            "query_id": query_id,
            "calls": int(row[1]),
            "total_exec_ms": float(row[2]),
            "rows": int(row[3]),
            "shared_blks_hit": int(row[4]),
            "shared_blks_read": int(row[5]),
            "shared_blks_dirtied": int(row[6]),
            "shared_blks_written": int(row[7]),
            "temp_blks_read": int(row[8]),
            "temp_blks_written": int(row[9]),
            "wal_records": int(row[10]),
            "wal_bytes": int(row[11]),
            "query": str(row[12]),
        }
    return result


def _statement_delta(
    before: Mapping[int, Mapping[str, Any]],
    after: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    metrics = (
        "calls",
        "total_exec_ms",
        "rows",
        "shared_blks_hit",
        "shared_blks_read",
        "shared_blks_dirtied",
        "shared_blks_written",
        "temp_blks_read",
        "temp_blks_written",
        "wal_records",
        "wal_bytes",
    )
    deltas: list[dict[str, Any]] = []
    for query_id, current in after.items():
        prior = before.get(query_id, {})
        item: dict[str, Any] = {
            "query_id": query_id,
            "query": current["query"],
        }
        for metric in metrics:
            item[metric] = current[metric] - prior.get(metric, 0)
        if item["calls"] > 0 or item["total_exec_ms"] > 0:
            deltas.append(item)
    deltas.sort(
        key=lambda item: (float(item["total_exec_ms"]), int(item["calls"])),
        reverse=True,
    )
    return deltas


@dataclass(slots=True)
class _CloseCapture:
    region_id: int
    expected_graph_revision: int
    raw_plan: Any | None = None


class _HierarchyCloseCursor:
    def __init__(self, cursor: Any, capture: _CloseCapture) -> None:
        self._cursor = cursor
        self._capture = capture

    def execute(self, query: Any, params: Any = None, *args: Any, **kwargs: Any) -> Any:
        if _is_region_close_update(query):
            if params is None or len(params) < 3:
                raise RuntimeError("hierarchy close UPDATE lost typed parameters")
            if int(params[2]) != self._capture.region_id:
                return self._cursor.execute(query, params, *args, **kwargs)
            if self._capture.raw_plan is not None:
                raise RuntimeError("hierarchy parent close executed more than once")
            if int(params[1]) != self._capture.expected_graph_revision:
                raise RuntimeError("hierarchy close graph revision changed before EXPLAIN")
            self._cursor.execute(
                "EXPLAIN (ANALYZE, BUFFERS, WAL, VERBOSE, SETTINGS, FORMAT JSON) "
                + query,
                params,
                *args,
                **kwargs,
            )
            row = self._cursor.fetchone()
            if row is None:
                raise RuntimeError("hierarchy close EXPLAIN returned no plan")
            self._capture.raw_plan = row[0]
            return self
        return self._cursor.execute(query, params, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


def install_live_hierarchy_close_attribution() -> bool:
    raw_kinds = os.environ.get(_KINDS_ENV, "").strip()
    if not raw_kinds:
        return False
    kinds = _parse_kinds(raw_kinds)
    selected = frozenset(kinds)
    limit = _positive_limit()
    output_raw = os.environ.get(_OUTPUT_ENV, "").strip()
    if not output_raw:
        raise ValueError(f"{_OUTPUT_ENV} is required when {_KINDS_ENV} is enabled")
    output = Path(output_raw)
    state_raw = os.environ.get(_STATE_ENV, "").strip()
    state = Path(state_raw) if state_raw else output.with_name(f"{output.name}.state.json")

    from src.storage.postgres import numeric_hyperfabric_store as store

    if getattr(store, _INSTALL_MARKER, False):
        return False
    original = store._close_parent_interface

    def close_parent_interface(cursor: Any, *, region_id: int, profile: Any) -> int:
        metadata = _region_metadata(cursor, int(region_id))
        kind = RegionKind(int(metadata["region_kind"]))
        if kind not in selected:
            return original(cursor, region_id=region_id, profile=profile)
        per_kind_ordinal = _reserve_capture(
            state_path=state,
            kinds=kinds,
            kind=kind,
            limit=limit,
        )
        if per_kind_ordinal is None:
            return original(cursor, region_id=region_id, profile=profile)

        support = _hierarchy_support(cursor, region_id=int(region_id))
        before = _statement_snapshot(cursor)
        capture = _CloseCapture(
            region_id=int(region_id),
            expected_graph_revision=int(metadata["graph_revision"]) + 1,
        )
        proxy = _HierarchyCloseCursor(cursor, capture)
        interface_id = original(proxy, region_id=region_id, profile=profile)
        after = _statement_snapshot(cursor)
        if capture.raw_plan is None:
            raise RuntimeError("selected hierarchy fibre did not execute canonical close UPDATE")
        _append_jsonl(
            output,
            {
                "contract_ref": LIVE_HIERARCHY_CLOSE_ATTRIBUTION_REF,
                "recorded_at": datetime.now(UTC).isoformat(),
                "pid": os.getpid(),
                "selection": {
                    "region_kind": int(kind),
                    "region_kind_name": kind.name,
                    "per_kind_ordinal": per_kind_ordinal,
                    "limit_per_kind": limit,
                },
                "preclose": metadata,
                "hierarchy_support": support,
                "interface_id": int(interface_id),
                "close_metrics": plan_metrics(capture.raw_plan),
                "close_plan": capture.raw_plan,
                "nested_statement_deltas": _statement_delta(before, after),
                "semantics": (
                    "diagnostic-only genuine hierarchy close; support and statement "
                    "baseline were observed before the parent close, EXPLAIN ANALYZE "
                    "executed its canonical close UPDATE in the original transaction, "
                    "and pg_stat_statements deltas were observed immediately afterward"
                ),
            },
        )
        return interface_id

    store._close_parent_interface = close_parent_interface
    setattr(store, _INSTALL_MARKER, True)
    return True


__all__ = [
    "LIVE_HIERARCHY_CLOSE_ATTRIBUTION_REF",
    "install_live_hierarchy_close_attribution",
]
