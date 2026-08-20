"""Rollback-contained diagnosis of the physical sentence-region close path.

This is deliberately a diagnostic probe, not a close implementation.  A
completed retained run no longer contains a genuine pre-close sentence row, so
the probe states its limitation explicitly: it reopens one final local region
inside a clone transaction, explains the real close UPDATE, and rolls back.
It therefore identifies work attached to the transition without claiming to
reconstruct the historical pre-close relation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from src.pnf.numeric_hyperfabric import ClosureState, RegionKind
from src.storage.postgres.spacy_parser_model import connect


REGION_CLOSE_TRIGGER_PROBE_REF = "sensiblaw.region-close-trigger-probe.v0_1"
_CLOSE_SQL = """
UPDATE execution.semantic_pnf_region
   SET closure_state = %s,
       graph_revision = %s,
       closed_at = CURRENT_TIMESTAMP
 WHERE region_id = %s
""".strip()


@dataclass(frozen=True, slots=True)
class RegionCloseCandidate:
    region_id: int
    interface_id: int
    graph_revision: int
    ancestor_rows: int


def build_template_clone(
    source_database_url: str, *, clone_prefix: str = "sensiblaw_probe_regionclose"
) -> tuple[str, dict[str, str]]:
    """Create an exact PostgreSQL template clone or fail without fallback.

    PostgreSQL refuses a template clone while the source has sessions.  We
    check that condition first and never terminate sessions or substitute a
    dump/copy path.
    """

    source = conninfo_to_dict(source_database_url)
    source_database = str(source.get("dbname") or "")
    if not source_database:
        raise ValueError("region-close probe requires source database name")
    clone_database = f"{clone_prefix}_{uuid4().hex[:12]}"[:63]
    maintenance = dict(source)
    maintenance["dbname"] = "postgres"
    with psycopg.connect(make_conninfo(**maintenance), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                  FROM pg_stat_activity
                 WHERE datname = %s
                   AND pid <> pg_backend_pid()
                """,
                (source_database,),
            )
            source_sessions = int(cursor.fetchone()[0])
            if source_sessions:
                raise RuntimeError(
                    "template clone refused: source database has active sessions"
                )
            cursor.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                    sql.Identifier(clone_database), sql.Identifier(source_database)
                )
            )
    clone = dict(source)
    clone["dbname"] = clone_database
    return make_conninfo(**clone), {
        "source_database": source_database,
        "clone_database": clone_database,
        "clone_method": "postgresql-template-exact",
    }


def region_close_candidates(
    cursor: Any, *, limit: int
) -> tuple[RegionCloseCandidate, ...]:
    """Return deterministic, evenly spaced final sentence regions for scouting."""

    if limit < 3:
        raise ValueError("region-close probe needs at least three scout candidates")
    cursor.execute(
        """
        WITH candidates AS (
            SELECT region.region_id,
                   interface.interface_id,
                   region.graph_revision,
                   count(ancestor.ancestor_interface_id)::BIGINT AS ancestor_rows,
                   ntile(%s) OVER (ORDER BY region.region_id) AS bucket
              FROM execution.semantic_pnf_region AS region
              JOIN execution.semantic_pnf_interface AS interface
                ON interface.region_id = region.region_id
              LEFT JOIN execution.semantic_pnf_interface_ancestor AS ancestor
                ON ancestor.interface_id = interface.interface_id
             WHERE region.region_kind = %s
               AND region.closure_state = %s
             GROUP BY region.region_id, interface.interface_id, region.graph_revision
        )
        SELECT DISTINCT ON (bucket)
               region_id, interface_id, graph_revision, ancestor_rows
          FROM candidates
         ORDER BY bucket, region_id
        """,
        (int(limit), int(RegionKind.SENTENCE), int(ClosureState.LOCALLY_CLOSED)),
    )
    return tuple(
        RegionCloseCandidate(
            region_id=int(row[0]),
            interface_id=int(row[1]),
            graph_revision=int(row[2]),
            ancestor_rows=int(row[3]),
        )
        for row in cursor.fetchall()
    )


def _plan_root(value: Any) -> Mapping[str, Any]:
    if isinstance(value, list) and value and isinstance(value[0], Mapping):
        return value[0]
    if isinstance(value, Mapping):
        return value
    raise ValueError("EXPLAIN FORMAT JSON returned no mapping")


def plan_metrics(value: Any) -> dict[str, Any]:
    """Extract present EXPLAIN metrics; unsupported fields remain ``unknown``."""

    root = _plan_root(value)
    plan = root.get("Plan") if isinstance(root.get("Plan"), Mapping) else {}
    return {
        "planning_time_ms": root.get("Planning Time", "unknown"),
        "execution_time_ms": root.get("Execution Time", "unknown"),
        "trigger_metrics": root.get("Triggers", "unknown"),
        "shared_hit_blocks": plan.get("Shared Hit Blocks", "unknown"),
        "shared_read_blocks": plan.get("Shared Read Blocks", "unknown"),
        "shared_dirtied_blocks": plan.get("Shared Dirtied Blocks", "unknown"),
        "shared_written_blocks": plan.get("Shared Written Blocks", "unknown"),
        "temp_read_blocks": plan.get("Temp Read Blocks", "unknown"),
        "temp_written_blocks": plan.get("Temp Written Blocks", "unknown"),
        "wal_records": plan.get("WAL Records", "unknown"),
        "wal_bytes": plan.get("WAL Bytes", "unknown"),
    }


def _region_snapshot(cursor: Any, region_id: int) -> tuple[int, int, datetime | None]:
    cursor.execute(
        """
        SELECT closure_state, graph_revision, closed_at
          FROM execution.semantic_pnf_region
         WHERE region_id = %s
        """,
        (int(region_id),),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("region-close probe region disappeared")
    return int(row[0]), int(row[1]), row[2]


def probe_reclose(cursor: Any, candidate: RegionCloseCandidate) -> dict[str, Any]:
    """Explain a close transition after transaction-local reopen; caller rolls back."""

    before = _region_snapshot(cursor, candidate.region_id)
    if before[0] != int(ClosureState.LOCALLY_CLOSED):
        raise ValueError("region-close probe requires a locally closed sentence")
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_region
           SET closure_state = %s,
               closed_at = NULL
         WHERE region_id = %s
        """,
        (int(ClosureState.OPEN), candidate.region_id),
    )
    cursor.execute(
        "EXPLAIN (ANALYZE, BUFFERS, WAL, VERBOSE, SETTINGS, FORMAT JSON) " + _CLOSE_SQL,
        (
            int(ClosureState.LOCALLY_CLOSED),
            candidate.graph_revision,
            candidate.region_id,
        ),
    )
    raw_plan = cursor.fetchone()[0]
    return {
        "region_id": candidate.region_id,
        "interface_id": candidate.interface_id,
        "ancestor_rows": candidate.ancestor_rows,
        "counterfactual": "transaction-local reopen then close; not historical pre-close replay",
        "before": {"closure_state": before[0], "graph_revision": before[1]},
        "metrics": plan_metrics(raw_plan),
        "plan": raw_plan,
    }


def _pick_strata(probes: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if len(probes) < 3:
        raise ValueError("region-close probe produced fewer than three scouts")

    ordered = sorted(
        probes,
        key=lambda item: float(item["metrics"]["execution_time_ms"]),
    )
    return {
        "cheap": ordered[0],
        "median": ordered[len(ordered) // 2],
        "expensive": ordered[-1],
    }


def run_region_close_probe(
    clone_database_url: str, *, scout_count: int = 9
) -> dict[str, Any]:
    """Run rollback-contained trigger-aware probes and verify clone containment."""

    connection = connect(clone_database_url)
    probes: list[dict[str, Any]] = []
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                candidates = region_close_candidates(cursor, limit=scout_count)
        for candidate in candidates:
            try:
                with connection.cursor() as cursor:
                    before = _region_snapshot(cursor, candidate.region_id)
                    probe = probe_reclose(cursor, candidate)
                connection.rollback()
            except BaseException:
                connection.rollback()
                raise
            with connection.transaction():
                with connection.cursor() as cursor:
                    after = _region_snapshot(cursor, candidate.region_id)
            probe["rollback_parity"] = before == after
            if not probe["rollback_parity"]:
                raise RuntimeError("region-close probe rollback containment failed")
            probes.append(probe)
        strata = _pick_strata(probes)
        return {
            "contract_ref": REGION_CLOSE_TRIGGER_PROBE_REF,
            "probe_semantics": "counterfactual close transition in exact template clone",
            "scout_count": len(probes),
            "all_rollback_parity": all(item["rollback_parity"] for item in probes),
            "strata": strata,
        }
    finally:
        connection.close()


__all__ = [
    "REGION_CLOSE_TRIGGER_PROBE_REF",
    "RegionCloseCandidate",
    "build_template_clone",
    "plan_metrics",
    "region_close_candidates",
    "run_region_close_probe",
]
