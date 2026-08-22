"""Bounded super-batches for streamed graph persistence.

Manifest artifacts arrive in small verified factor chunks. Persisting each chunk
as its own PostgreSQL stage preserves semantics but multiplies physical stage
setup, completeness proof, telemetry and authority-merge overhead. This module
buffers only execution payloads. Immutable factor/revision identities are
returned to the compiler immediately, while authority publication is flushed
before any downstream resolution/binding consumer or before the document
persistence scope exits.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from src.storage.postgres.work_conserving_copy_observability import (
    observable_complete_stage,
    observable_stage_payloads,
)
from src.storage.postgres.work_conserving_graph_persistence import _factor_payloads
from src.storage.postgres.work_conserving_stage import StagePayload, _runtime, _sha


def _payload_limit() -> int:
    raw = os.environ.get("SENSIBLAW_PERSISTENCE_GRAPH_BATCH_PAYLOADS", "8192")
    value = int(raw)
    if value < 1:
        raise ValueError("SENSIBLAW_PERSISTENCE_GRAPH_BATCH_PAYLOADS must be positive")
    return value


def _graph_state(factors: tuple[Mapping[str, Any], ...]) -> str:
    return (
        "locally_closed"
        if all(
            row.get("closure_state") in {"locally_closed", "closed", "not_required"}
            for row in factors
        )
        else "open"
    )


def _buffer(runtime: Any) -> tuple[list[StagePayload], set[StagePayload]]:
    payloads = getattr(runtime, "_graph_batch_payloads", None)
    payload_set = getattr(runtime, "_graph_batch_payload_set", None)
    if payloads is None:
        payloads = []
        setattr(runtime, "_graph_batch_payloads", payloads)
    if payload_set is None:
        payload_set = set()
        setattr(runtime, "_graph_batch_payload_set", payload_set)
    return payloads, payload_set


def _append_unique(runtime: Any, rows: list[StagePayload]) -> None:
    payloads, payload_set = _buffer(runtime)
    for row in rows:
        if row in payload_set:
            continue
        payload_set.add(row)
        payloads.append(row)


def persist_pnf_graph_batched(
    cursor: Any,
    *,
    document_ref: str,
    graph: Mapping[str, Any],
) -> dict[str, str]:
    """Buffer graph rows while returning exact factor revision identities."""

    runtime = _runtime()
    previous_cursor = getattr(runtime, "_graph_batch_cursor", None)
    if previous_cursor is not None and previous_cursor is not cursor:
        raise RuntimeError("graph super-batch crossed publication cursors")
    setattr(runtime, "_graph_batch_cursor", cursor)

    graph_ref = str(graph["graph_ref"])
    factors = tuple(graph.get("factors") or ())
    factor_payloads, revisions = _factor_payloads(
        document_ref=document_ref,
        factors=factors,
        graph_ref=graph_ref,
    )

    # The legacy streamed path inserted the graph row once per chunk with
    # ON CONFLICT DO NOTHING, so the first chunk for a graph_ref determined the
    # stored graph hash/state. Preserve that exact first-writer behavior within
    # each buffered super-stage.
    header_refs = getattr(runtime, "_graph_batch_header_refs", None)
    if header_refs is None:
        header_refs = set()
        setattr(runtime, "_graph_batch_header_refs", header_refs)
    header_rows: list[StagePayload] = []
    if graph_ref not in header_refs:
        header_refs.add(graph_ref)
        header_rows.append(
            StagePayload(
                "graph_header",
                texts=(graph_ref, document_ref, _graph_state(factors)),
                byteas=(_sha(graph),),
            )
        )
    _append_unique(runtime, [*header_rows, *factor_payloads])

    payloads, _ = _buffer(runtime)
    if len(payloads) >= _payload_limit():
        flush_graph_batch(cursor)
    return revisions


def flush_graph_batch(cursor: Any | None = None) -> None:
    """Publish the pending graph super-stage, if any."""

    runtime = _runtime()
    payloads, payload_set = _buffer(runtime)
    if not payloads:
        return
    active_cursor = cursor or getattr(runtime, "_graph_batch_cursor", None)
    if active_cursor is None:
        raise RuntimeError("pending graph super-batch has no publication cursor")
    if cursor is not None:
        previous_cursor = getattr(runtime, "_graph_batch_cursor", None)
        if previous_cursor is not None and previous_cursor is not cursor:
            raise RuntimeError("graph super-batch flush used a different cursor")

    staged = tuple(payloads)
    stage_ref = observable_stage_payloads(
        active_cursor,
        family_ref="pnf_graph_superbatch",
        lane_ref="graph",
        payloads=staged,
    )
    statements = 0
    active_cursor.execute(
        """
        INSERT INTO pnf.graph
            (graph_ref, document_ref, graph_type_ref, schema_version_ref,
             closure_state_ref, graph_sha256)
        SELECT text_01, text_02, 'generic.factor_graph', 'v0_1', text_03,
               bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'graph_header'
        ON CONFLICT (graph_ref) DO NOTHING
        """,
        (stage_ref,),
    )
    statements += 1
    for statement in (
        """
        INSERT INTO algebra.factor (factor_ref, document_ref, factor_type_ref)
        SELECT DISTINCT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'factor'
        ON CONFLICT (factor_ref) DO NOTHING
        """,
        """
        INSERT INTO algebra.factor_revision
            (factor_revision_ref, factor_ref, closure_state_ref, factor_sha256)
        SELECT DISTINCT text_01, text_02, text_03, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'factor_revision'
        ON CONFLICT (factor_revision_ref) DO NOTHING
        """,
        """
        INSERT INTO pnf.graph_factor_revision
            (graph_ref, factor_revision_ref, graph_role_ref)
        SELECT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'graph_factor'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO algebra.alternative
            (alternative_ref, type_ref, value_ref, value_literal,
             authority_state_ref, alternative_sha256)
        SELECT DISTINCT text_01, text_02, text_03, text_04, text_05, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'alternative'
        ON CONFLICT (alternative_ref) DO NOTHING
        """,
        """
        INSERT INTO algebra.factor_revision_alternative
            (factor_revision_ref, alternative_ref, alternative_state_ref)
        SELECT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'factor_alternative'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO algebra.residual
            (residual_ref, target_ref, residual_type_ref,
             residual_state_ref, residual_sha256)
        SELECT text_01, text_02, text_03, text_04, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'residual'
        ON CONFLICT (residual_ref) DO NOTHING
        """,
    ):
        active_cursor.execute(statement, (stage_ref,))
        statements += 1
    observable_complete_stage(
        active_cursor,
        stage_ref=stage_ref,
        statement_count=statements,
    )

    setattr(
        runtime,
        "graph_superbatches_flushed",
        int(getattr(runtime, "graph_superbatches_flushed", 0)) + 1,
    )
    setattr(
        runtime,
        "graph_superbatch_payloads",
        int(getattr(runtime, "graph_superbatch_payloads", 0)) + len(staged),
    )
    payloads.clear()
    payload_set.clear()
    getattr(runtime, "_graph_batch_header_refs", set()).clear()


def persist_resolution_after_graph_flush(cursor: Any, **kwargs: Any) -> tuple[str, ...]:
    from src.storage.postgres.work_conserving_resolution_persistence import (
        persist_resolution_artifacts_work_conserving,
    )

    flush_graph_batch(cursor)
    return persist_resolution_artifacts_work_conserving(cursor, **kwargs)


def persist_binding_after_graph_flush(cursor: Any, **kwargs: Any) -> None:
    from src.storage.postgres.work_conserving_binding_persistence import (
        persist_binding_candidate_sets_work_conserving,
    )

    flush_graph_batch(cursor)
    persist_binding_candidate_sets_work_conserving(cursor, **kwargs)


def persist_streamed_builds_after_graph_flush(cursor: Any, rows: Any) -> None:
    from src.storage.postgres.work_conserving_binding_persistence import (
        persist_streamed_candidate_builds_work_conserving,
    )

    flush_graph_batch(cursor)
    persist_streamed_candidate_builds_work_conserving(cursor, rows)


def persist_streamed_links_after_graph_flush(
    cursor: Any, *, kind: str, rows: Any
) -> None:
    from src.storage.postgres.work_conserving_binding_persistence import (
        persist_streamed_candidate_links_work_conserving,
    )

    flush_graph_batch(cursor)
    persist_streamed_candidate_links_work_conserving(cursor, kind=kind, rows=rows)


__all__ = [
    "flush_graph_batch",
    "persist_binding_after_graph_flush",
    "persist_pnf_graph_batched",
    "persist_resolution_after_graph_flush",
    "persist_streamed_builds_after_graph_flush",
    "persist_streamed_links_after_graph_flush",
]
