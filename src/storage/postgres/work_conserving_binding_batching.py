"""Bounded super-batches for streamed binding persistence.

Binding anchors, candidate sets, candidate builds and candidate-set links are
already published by one set-wise SQL surface. Streaming them through separate
physical stages multiplies stage and validation overhead without changing
semantic authority. Buffer typed execution payloads and publish them together;
resolution authority is flushed first so all FK parents remain available.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

from src.storage.postgres.work_conserving_binding_persistence import (
    _binding_payloads,
    _publish_binding_stage,
    _validate_binding_stage,
)
from src.storage.postgres.work_conserving_copy_observability import (
    observable_complete_stage,
    observable_stage_payloads,
)
from src.storage.postgres.work_conserving_resolution_batching import (
    flush_resolution_batch,
)
from src.storage.postgres.work_conserving_stage import StagePayload, _runtime, _text_sha


def _payload_limit() -> int:
    raw = os.environ.get("SENSIBLAW_PERSISTENCE_BINDING_BATCH_PAYLOADS", "16384")
    value = int(raw)
    if value < 1:
        raise ValueError("SENSIBLAW_PERSISTENCE_BINDING_BATCH_PAYLOADS must be positive")
    return value


def _buffer(runtime: Any) -> tuple[list[StagePayload], set[StagePayload]]:
    payloads = getattr(runtime, "_binding_batch_payloads", None)
    payload_set = getattr(runtime, "_binding_batch_payload_set", None)
    if payloads is None:
        payloads = []
        setattr(runtime, "_binding_batch_payloads", payloads)
    if payload_set is None:
        payload_set = set()
        setattr(runtime, "_binding_batch_payload_set", payload_set)
    return payloads, payload_set


def _append_unique(runtime: Any, rows: Sequence[StagePayload]) -> None:
    payloads, payload_set = _buffer(runtime)
    for row in rows:
        if row in payload_set:
            continue
        payload_set.add(row)
        payloads.append(row)


def _bind_cursor(runtime: Any, cursor: Any) -> None:
    previous_cursor = getattr(runtime, "_binding_batch_cursor", None)
    if previous_cursor is not None and previous_cursor is not cursor:
        raise RuntimeError("binding super-batch crossed publication cursors")
    setattr(runtime, "_binding_batch_cursor", cursor)


def _maybe_flush(runtime: Any, cursor: Any) -> None:
    payloads, _ = _buffer(runtime)
    if len(payloads) >= _payload_limit():
        flush_binding_batch(cursor)


def persist_binding_batched(cursor: Any, **kwargs: Any) -> None:
    runtime = _runtime()
    _bind_cursor(runtime, cursor)
    payloads = _binding_payloads(
        candidate_sets=kwargs.get("candidate_sets") or (),
        refinements=kwargs.get("refinements") or (),
        factor_revisions=kwargs["factor_revisions"],
        factor_anchors=kwargs.get("factor_anchors") or (),
        builds=kwargs.get("builds") or (),
        meets=kwargs.get("meets") or (),
        demands=kwargs.get("demands") or (),
    )
    _append_unique(runtime, payloads)
    if kwargs.get("validate_indexed_query") and kwargs.get("candidate_sets"):
        setattr(runtime, "_binding_batch_needs_validation", True)
    _maybe_flush(runtime, cursor)


def persist_streamed_candidate_builds_batched(
    cursor: Any, rows: Sequence[Mapping[str, Any]]
) -> None:
    runtime = _runtime()
    _bind_cursor(runtime, cursor)
    payloads: list[StagePayload] = []
    for row in rows:
        identity = {
            "generator_build_ref": row["generator_build_ref"],
            "reference_factor_revision_ref": row["reference_factor_revision_ref"],
            "document_pnf_index_ref": row.get("document_pnf_index_ref"),
            "accessibility_declaration_ref": row["accessibility_declaration_ref"],
            "compatibility_declaration_ref": row["compatibility_declaration_ref"],
            "referential_type_ref": row["referential_type_ref"],
        }
        payloads.append(
            StagePayload(
                "candidate_build",
                texts=(
                    str(row["generator_build_ref"]),
                    str(row["candidate_set_ref"]),
                    str(row["reference_factor_revision_ref"]),
                    str(row.get("document_pnf_index_ref") or ""),
                    str(row["accessibility_declaration_ref"]),
                    str(row["compatibility_declaration_ref"]),
                    str(row["referential_type_ref"]),
                    _text_sha(identity),
                    "completed",
                ),
            )
        )
    _append_unique(runtime, payloads)
    _maybe_flush(runtime, cursor)


def persist_streamed_candidate_links_batched(
    cursor: Any, *, kind: str, rows: Sequence[Mapping[str, Any]]
) -> None:
    runtime = _runtime()
    _bind_cursor(runtime, cursor)
    specifications = {
        "refinement": ("refinement_ref", "refinement_candidate_set"),
        "meet": ("meet_ref", "meet_candidate_set"),
        "demand": ("demand_ref", "demand_candidate_set"),
    }
    source_column, row_kind = specifications[kind]
    payloads = [
        StagePayload(
            row_kind,
            texts=(str(row[source_column]), str(candidate_set_ref)),
        )
        for row in rows
        for candidate_set_ref in row.get("candidate_set_refs") or ()
    ]
    _append_unique(runtime, payloads)
    _maybe_flush(runtime, cursor)


def flush_binding_batch(cursor: Any | None = None) -> None:
    runtime = _runtime()
    payloads, payload_set = _buffer(runtime)
    if not payloads:
        return
    active_cursor = cursor or getattr(runtime, "_binding_batch_cursor", None)
    if active_cursor is None:
        raise RuntimeError("pending binding super-batch has no publication cursor")
    if cursor is not None:
        previous_cursor = getattr(runtime, "_binding_batch_cursor", None)
        if previous_cursor is not None and previous_cursor is not cursor:
            raise RuntimeError("binding super-batch flush used a different cursor")

    flush_resolution_batch(active_cursor)
    staged = tuple(payloads)
    stage_ref = observable_stage_payloads(
        active_cursor,
        family_ref="binding_candidates_superbatch",
        lane_ref="binding",
        payloads=staged,
    )
    statements = _publish_binding_stage(active_cursor, stage_ref=stage_ref)
    if bool(getattr(runtime, "_binding_batch_needs_validation", False)):
        _validate_binding_stage(active_cursor, stage_ref=stage_ref)
        statements += 1
    observable_complete_stage(
        active_cursor,
        stage_ref=stage_ref,
        statement_count=statements,
    )
    setattr(
        runtime,
        "binding_superbatches_flushed",
        int(getattr(runtime, "binding_superbatches_flushed", 0)) + 1,
    )
    setattr(
        runtime,
        "binding_superbatch_payloads",
        int(getattr(runtime, "binding_superbatch_payloads", 0)) + len(staged),
    )
    payloads.clear()
    payload_set.clear()
    setattr(runtime, "_binding_batch_needs_validation", False)


__all__ = [
    "flush_binding_batch",
    "persist_binding_batched",
    "persist_streamed_candidate_builds_batched",
    "persist_streamed_candidate_links_batched",
]
