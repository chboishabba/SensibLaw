"""Diagnostic-only EXPLAIN of genuine sentence-region close transitions.

A completed database cannot be reopened into its historical pre-close state:
region close consumes/advances demand and projection state.  This module therefore
instruments selected *real* closes while they are happening.  PostgreSQL
``EXPLAIN ANALYZE`` executes the original UPDATE and all attached triggers inside
the existing sentence transaction, so no transaction split, fake reopen, trigger
bypass, or alternate semantic authority is introduced.

The selector has one fsynced, run-scoped ordinal ledger shared by every Python
process in the diagnostic.  A strict serial *worker* configuration can still
create more than one process over the life of a run, so a process-local counter
would silently duplicate ordinal strata.  Selected closes also record a compact
pre-close semantic support vector so cost can be compared with local fibre/
boundary population instead of treating ordinal as the semantic state variable.
No instrumentation is installed unless
``SENSIBLAW_REGION_CLOSE_EXPLAIN_ORDINALS`` is explicitly set.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import fcntl
import json
import os
from pathlib import Path
from typing import Any, Mapping

from src.policy.region_close_support_vector import capture_region_close_support_vector
from src.storage.postgres.region_close_trigger_probe import plan_metrics


LIVE_REGION_CLOSE_EXPLAIN_REF = "sensiblaw.live-region-close-explain.v0_2"
_ORDINAL_ENV = "SENSIBLAW_REGION_CLOSE_EXPLAIN_ORDINALS"
_OUTPUT_ENV = "SENSIBLAW_REGION_CLOSE_EXPLAIN_OUTPUT"
_STATE_ENV = "SENSIBLAW_REGION_CLOSE_EXPLAIN_STATE"
_INSTALL_MARKER = "_live_region_close_explain_installed"
_ORDINAL_STATE_REF = "sensiblaw.live-region-close-explain-ordinal-state.v0_1"


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
               region.region_kind,
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
        "region_kind": int(row[4]),
        "start_char": int(row[5]),
        "end_char": int(row[6]),
        "sequence_no": int(row[7]),
        "closure_state": int(row[8]),
        "graph_revision": int(row[9]),
        "work_id": int(row[10]),
        "work_state": int(row[11]),
        "lease_epoch": int(row[12]),
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


def _global_close_ordinal(*, state_path: Path, ordinals: tuple[int, ...]) -> int:
    """Reserve one diagnostic ordinal across all run processes.

    The reservation deliberately happens before the selected close executes.
    If that transaction subsequently fails, the requested ordinal will be
    absent from the receipt and the prefix runner rejects the diagnostic rather
    than mislabelling a later close as the selected transition.
    """

    state_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(state_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        os.lseek(descriptor, 0, os.SEEK_SET)
        raw = os.read(descriptor, 65_536)
        if raw:
            try:
                state = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise RuntimeError(
                    "live region-close ordinal state is unreadable"
                ) from error
            if state.get("contract_ref") != _ORDINAL_STATE_REF or state.get(
                "configured_ordinals"
            ) != list(ordinals):
                raise RuntimeError(
                    "live region-close ordinal state belongs to another diagnostic"
                )
            previous = state.get("last_reserved_ordinal")
            if not isinstance(previous, int) or previous < 0:
                raise RuntimeError("live region-close ordinal state is invalid")
        else:
            previous = 0
        ordinal = previous + 1
        payload = json.dumps(
            {
                "contract_ref": _ORDINAL_STATE_REF,
                "configured_ordinals": list(ordinals),
                "last_reserved_ordinal": ordinal,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.ftruncate(descriptor, 0)
        os.write(descriptor, payload)
        os.fsync(descriptor)
        return ordinal
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
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
    state_raw = os.environ.get(_STATE_ENV, "").strip()
    state = (
        Path(state_raw)
        if state_raw
        else output.with_name(f"{output.name}.ordinal-state.json")
    )

    from src.storage.postgres import numeric_sentence_admission as admission

    if getattr(admission, _INSTALL_MARKER, False):
        return False
    original = admission.persist_sentence_closure_setwise
    ordinal_set = frozenset(ordinals)

    def persist_sentence_closure_setwise(
        cursor: Any,
        *,
        lease: Any,
        closure: Any,
        profile: Any,
    ) -> int:
        ordinal = _global_close_ordinal(state_path=state, ordinals=ordinals)
        if ordinal not in ordinal_set:
            return original(cursor, lease=lease, closure=closure, profile=profile)

        preclose = _preclose_metadata(
            cursor,
            work_id=int(lease.work_id),
            region_id=int(lease.region_id),
        )
        support_vector = capture_region_close_support_vector(
            cursor,
            preclose=preclose,
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
                        "run-scoped close ordinal shared by all diagnostic "
                        "processes; intended for strict serial closure-workers=1 "
                        "runs"
                    ),
                },
                "preclose": preclose,
                "semantic_support_vector": support_vector,
                "interface_id": int(interface_id),
                "expected_graph_revision": capture.graph_revision,
                "triggers": capture.triggers,
                "metrics": plan_metrics(capture.raw_plan),
                "plan": capture.raw_plan,
                "transaction_semantics": (
                    "support counts were observed before the close; EXPLAIN ANALYZE "
                    "then executed the genuine canonical close UPDATE and attached "
                    "triggers inside the original sentence transaction; the JSONL "
                    "record is fsynced before outer transaction commit"
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
