"""Bounded super-batches for streamed resolution persistence.

Resolution manifest chunks expose immutable demand/meet/refinement/evidence rows.
Their callers only need deterministic refs immediately; no downstream SQL reads
those rows until binding/link publication. Buffering execution payloads therefore
preserves semantic order while avoiding one 14-statement authority cycle per
small artifact chunk.
"""

from __future__ import annotations

import os
from typing import Any

from src.storage.postgres.work_conserving_copy_observability import (
    observable_complete_stage,
    observable_stage_payloads,
)
from src.storage.postgres.work_conserving_graph_batching import flush_graph_batch
from src.storage.postgres.work_conserving_resolution_persistence import (
    _resolution_payloads,
)
from src.storage.postgres.work_conserving_stage import StagePayload, _runtime


def _payload_limit() -> int:
    raw = os.environ.get("SENSIBLAW_PERSISTENCE_RESOLUTION_BATCH_PAYLOADS", "16384")
    value = int(raw)
    if value < 1:
        raise ValueError(
            "SENSIBLAW_PERSISTENCE_RESOLUTION_BATCH_PAYLOADS must be positive"
        )
    return value


def _buffer(runtime: Any) -> tuple[list[StagePayload], set[StagePayload]]:
    payloads = getattr(runtime, "_resolution_batch_payloads", None)
    payload_set = getattr(runtime, "_resolution_batch_payload_set", None)
    if payloads is None:
        payloads = []
        setattr(runtime, "_resolution_batch_payloads", payloads)
    if payload_set is None:
        payload_set = set()
        setattr(runtime, "_resolution_batch_payload_set", payload_set)
    return payloads, payload_set


def _append_unique(runtime: Any, rows: list[StagePayload]) -> None:
    payloads, payload_set = _buffer(runtime)
    for row in rows:
        if row in payload_set:
            continue
        payload_set.add(row)
        payloads.append(row)


def persist_resolution_batched(cursor: Any, **kwargs: Any) -> tuple[str, ...]:
    runtime = _runtime()
    previous_cursor = getattr(runtime, "_resolution_batch_cursor", None)
    if previous_cursor is not None and previous_cursor is not cursor:
        raise RuntimeError("resolution super-batch crossed publication cursors")
    setattr(runtime, "_resolution_batch_cursor", cursor)

    payloads = _resolution_payloads(**kwargs)
    _append_unique(runtime, payloads)
    buffered, _ = _buffer(runtime)
    if len(buffered) >= _payload_limit():
        flush_resolution_batch(cursor)
    return tuple(sorted(str(row["demand_ref"]) for row in kwargs["demands"]))


def flush_resolution_batch(cursor: Any | None = None) -> None:
    runtime = _runtime()
    payloads, payload_set = _buffer(runtime)
    if not payloads:
        return
    active_cursor = cursor or getattr(runtime, "_resolution_batch_cursor", None)
    if active_cursor is None:
        raise RuntimeError("pending resolution super-batch has no publication cursor")
    if cursor is not None:
        previous_cursor = getattr(runtime, "_resolution_batch_cursor", None)
        if previous_cursor is not None and previous_cursor is not cursor:
            raise RuntimeError("resolution super-batch flush used a different cursor")

    # Resolution rows may introduce resulting factor revisions and demand FKs,
    # but their base graph factors must already be authority rows.
    flush_graph_batch(active_cursor)
    staged = tuple(payloads)
    stage_ref = observable_stage_payloads(
        active_cursor,
        family_ref="resolution_artifacts_superbatch",
        lane_ref="resolution",
        payloads=staged,
    )
    statements_sql = (
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
        """
        INSERT INTO evidence.local_evidence
            (evidence_ref, document_ref, evidence_type_ref, relation_ref,
             evidence_sha256)
        SELECT text_01, text_02, text_03, text_04, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'evidence'
        ON CONFLICT (evidence_ref) DO NOTHING
        """,
        """
        INSERT INTO evidence.local_evidence_subject (evidence_ref, subject_ref)
        SELECT text_01, text_02
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'evidence_subject'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.demand
            (demand_ref, factor_ref, factor_revision_ref, subject_kind_ref,
             formal_role_ref, scope_ref, semantic_key_sha256,
             budget_class_ref, demand_state_ref)
        SELECT text_01, text_02, text_03, text_04, text_05, text_06,
               bytea_01, text_07, text_08
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'demand'
        ON CONFLICT (demand_ref) DO NOTHING
        """,
        """
        INSERT INTO resolution.demand_facet (demand_ref, facet_ref)
        SELECT text_01, text_02
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'demand_facet'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.typed_meet
            (meet_ref, left_ref, right_ref, meet_type_ref, meet_state_ref,
             meet_sha256)
        SELECT text_01, text_02, text_03, text_04, text_05, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'meet'
        ON CONFLICT (meet_ref) DO NOTHING
        """,
        """
        INSERT INTO resolution.meet_evidence (meet_ref, evidence_ref)
        SELECT text_01, text_02
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'meet_evidence'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.refinement
            (refinement_ref, factor_ref, prior_factor_revision_ref,
             resulting_factor_revision_ref, refinement_sha256)
        SELECT text_01, text_02, text_03, text_04, bytea_01
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s AND row_kind_ref = 'refinement'
        ON CONFLICT (refinement_ref) DO NOTHING
        """,
        """
        INSERT INTO resolution.refinement_alternative_transition
            (refinement_ref, alternative_ref, transition_type_ref)
        SELECT text_01, text_02, text_03
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s
          AND row_kind_ref = 'refinement_alternative_transition'
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO resolution.refinement_residual_transition
            (refinement_ref, residual_ref, prior_state_ref, resulting_state_ref)
        SELECT text_01, text_02, text_03, text_04
        FROM execution.document_persistence_stage
        WHERE stage_ref = %s
          AND row_kind_ref = 'refinement_residual_transition'
        ON CONFLICT DO NOTHING
        """,
    )
    for statement in statements_sql:
        active_cursor.execute(statement, (stage_ref,))
    observable_complete_stage(
        active_cursor,
        stage_ref=stage_ref,
        statement_count=len(statements_sql),
    )
    setattr(
        runtime,
        "resolution_superbatches_flushed",
        int(getattr(runtime, "resolution_superbatches_flushed", 0)) + 1,
    )
    setattr(
        runtime,
        "resolution_superbatch_payloads",
        int(getattr(runtime, "resolution_superbatch_payloads", 0)) + len(staged),
    )
    payloads.clear()
    payload_set.clear()


__all__ = ["flush_resolution_batch", "persist_resolution_batched"]
