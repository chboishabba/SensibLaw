"""Diagnostic-only EXPLAIN of genuine sentence-region close transitions.

A completed database cannot be reopened into its historical pre-close state:
region close consumes/advances demand and projection state.  This module therefore
instruments selected *real* closes while they are happening.  PostgreSQL
``EXPLAIN ANALYZE`` executes the original UPDATE and all attached triggers inside
the existing sentence transaction, so no transaction split, fake reopen, trigger
bypass, or alternate semantic authority is introduced.

The selector is intentionally process-local.  It is designed for the strict
serial diagnostic run (one closure worker) used by the acceptance harness.  No
instrumentation is installed unless ``SENSIBLAW_REGION_CLOSE_EXPLAIN_ORDINALS``
is explicitly set.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any, Mapping

from src.storage.postgres.region_close_trigger_probe import plan_metrics


LIVE_REGION_CLOSE_EXPLAIN_REF = "sensiblaw.live-region-close-explain.v0_1"
_ORDINAL_ENV = "SENSIBLAW_REGION_CLOSE_EXPLAIN_ORDINALS"
_OUTPUT_ENV = "SENSIBLAW_REGION_CLOSE_EXPLAIN_OUTPUT"
_INSTALL_MARKER = "_live_region_close_explain_installed"


def _parse_ordinals(raw: str) -> tuple[int, ...]:
    values: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        value = int(token)
        if value < 1:
            raise ValueError(f"{_ORDINAL_ENV} values must be positive")
        values.append(value)
    if not values:
        raise ValueError(f"{_ORDINAL_ENV} must contain at least one ordinal")
    if len(set(values)) != len(values):
        raise ValueError(f"{_ORDINAL_ENV} must not contain duplicate ordinals")
    return tuple(sorted(values))


def _compact_sql(query: Any) -> str:
    if not isinstance(query, str):
        return ""
    return " ".join(query.lower().split())


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


def _trigger_inventory(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT trigger.tgname,
               trigger.tgenabled,
               pg_get_triggerdef(trigger.oid, TRUE),
               namespace.nspname,
               procedure.proname,
               pg_get_functiondef(procedure.oid)
          FROM pg_trigger AS trigger
          JOIN pg_proc AS procedure
            ON procedure.oid = trigger.tgfoid
          JOIN pg_namespace AS namespace
            ON namespace.oid = procedure.pronamespace
         WHERE trigger.tgrelid = 'execution.semantic_pnf_region'::regclass
           AND NOT trigger.tgisinternal
         ORDER BY trigger.tgname
        """
    )
    return [
        {
            "trigger_name": str(row[0]),
            "enabled": str(row[1]),
            "trigger_definition": str(row[2]),
            "function_schema": str(row[3]),
            "function_name": str(row[4]),
            "function_definition": str(row[5]),
        }
        for row in cursor.fetchall()
    ]


def _preclose_metadata(cursor: Any, *, work_id: int, region_id: int) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT region.run_ref,
               region.document_ref,
               region.region_id,
               region.parent_region_id,
               region.start_char,
               region.end_char,
               region.sequence_no,
               region.closure_state,
               region.graph_revision,
               work.work_id,
               work.state_id,
               work.lease_epoch
          FROM execution.semantic_pnf_region AS region
          JOIN execution.semantic_pnf_work_item AS work
            ON work.region_id = region.region_id
         WHERE region.region_id = %s
           AND work.work_id = %s
        """,
        (int(region_id), int(work_id)),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("live region-close probe lost its exact region/work fibre")
    return {
        "run_ref": str(row[0]),
        "document_ref": str(row[1]),
        "region_id": int(row[2]),
        "parent_region_id": int(row[3]) if row[3] is not None else None,
        "start_char": int(row[4]),
        "end_char": int(row[5]),
        "sequence_no": int(row[6]),
        "closure_state": int(row[7]),
        "graph_revision": int(row[8]),
        "work_id": int(row[9]),
        "work_state": int(row[10]),
        "lease_epoch": int(row[11]),
    }


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


@dataclass(slots=True)
class _ExplainCapture:
    ordinal: int
    work_id: int
    region_id: int
    graph_revision: int
    preclose: dict[str, Any]
    triggers: list[dict[str, Any]]
    raw_plan: Any | None = None


class _RegionCloseExplainCursor:
    """Transparent cursor proxy replacing exactly one real close with EXPLAIN."""

    def __init__(self, cursor: Any, capture: _ExplainCapture) -> None:
        self._cursor = cursor
        self._capture = capture

    def execute(self, query: Any, params: Any = None, *args: Any, **kwargs: Any) -> Any:
        if _is_region_close_update(query):
            if self._capture.raw_plan is not None:
                raise RuntimeError(
                    "selected sentence attempted more than one region close"
                )
            if params is None or len(params) < 3:
                raise RuntimeError("region-close UPDATE lost its typed parameter fibre")
            if int(params[1]) != self._capture.graph_revision:
                raise RuntimeError("region-close graph revision changed before EXPLAIN")
            if int(params[2]) != self._capture.region_id:
                raise RuntimeError("region-close region id changed before EXPLAIN")
            self._cursor.execute(
                "EXPLAIN (ANALYZE, BUFFERS, WAL, VERBOSE, SETTINGS, FORMAT JSON) "
                + query,
                params,
                *args,
                **kwargs,
            )
            row = self._cursor.fetchone()
            if row is None:
                raise RuntimeError("live region-close EXPLAIN returned no plan")
            self._capture.raw_plan = row[0]
            return self
        self._cursor.execute(query, params, *args, **kwargs)
        return self

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


def install_live_region_close_explain() -> bool:
    """Install exact in-transaction close probes when explicitly configured."""

    raw_ordinals = os.environ.get(_ORDINAL_ENV, "").strip()
    if not raw_ordinals:
        return False
    ordinals = _parse_ordinals(raw_ordinals)
    output_raw = os.environ.get(_OUTPUT_ENV, "").strip()
    if not output_raw:
        raise ValueError(f"{_OUTPUT_ENV} is required when {_ORDINAL_ENV} is enabled")
    output = Path(output_raw)

    from src.storage.postgres import numeric_sentence_admission as admission

    if getattr(admission, _INSTALL_MARKER, False):
        return False
    original = admission.persist_sentence_closure_setwise
    ordinal_set = frozenset(ordinals)
    close_ordinal = 0

    def persist_sentence_closure_setwise(
        cursor: Any,
        *,
        lease: Any,
        closure: Any,
        profile: Any,
    ) -> int:
        nonlocal close_ordinal
        close_ordinal += 1
        ordinal = close_ordinal
        if ordinal not in ordinal_set:
            return original(cursor, lease=lease, closure=closure, profile=profile)

        preclose = _preclose_metadata(
            cursor,
            work_id=int(lease.work_id),
            region_id=int(lease.region_id),
        )
        capture = _ExplainCapture(
            ordinal=ordinal,
            work_id=int(lease.work_id),
            region_id=int(lease.region_id),
            graph_revision=int(preclose["graph_revision"]) + 1,
            preclose=preclose,
            triggers=_trigger_inventory(cursor),
        )
        proxy = _RegionCloseExplainCursor(cursor, capture)
        interface_id = original(proxy, lease=lease, closure=closure, profile=profile)
        if capture.raw_plan is None:
            raise RuntimeError(
                "selected sentence completed without executing the canonical region close"
            )
        _append_jsonl(
            output,
            {
                "contract_ref": LIVE_REGION_CLOSE_EXPLAIN_REF,
                "recorded_at": datetime.now(UTC).isoformat(),
                "pid": os.getpid(),
                "selection": {
                    "close_ordinal": ordinal,
                    "configured_ordinals": list(ordinals),
                    "semantics": (
                        "process-local close ordinal; intended for strict serial "
                        "closure-workers=1 diagnostic runs"
                    ),
                },
                "preclose": preclose,
                "interface_id": int(interface_id),
                "expected_graph_revision": capture.graph_revision,
                "triggers": capture.triggers,
                "metrics": plan_metrics(capture.raw_plan),
                "plan": capture.raw_plan,
                "transaction_semantics": (
                    "EXPLAIN ANALYZE executed the genuine canonical close UPDATE and "
                    "attached triggers inside the original sentence transaction; "
                    "the JSONL record is fsynced before outer transaction commit"
                ),
                "commit_confirmation": "not_observed_by_in_transaction_probe",
            },
        )
        return interface_id

    admission.persist_sentence_closure_setwise = persist_sentence_closure_setwise
    setattr(admission, _INSTALL_MARKER, True)
    return True


__all__ = [
    "LIVE_REGION_CLOSE_EXPLAIN_REF",
    "install_live_region_close_explain",
]
