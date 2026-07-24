"""Direct persistence for execution-only stage timing rows."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def persist_stage_timings(
    cursor: Any,
    *,
    document_ref: str,
    timings: Iterable[Mapping[str, Any]],
) -> None:
    rows = []
    for timing in timings:
        rows.append(
            (
                str(timing["timing_ref"]),
                document_ref,
                str(timing["stage"]),
                int(timing["ordinal"]),
                int(timing["elapsed_ms"]),
                timing.get("backend_ref"),
                timing.get("input_nodes"),
                timing.get("output_nodes"),
                timing.get("input_edges"),
                timing.get("output_edges"),
                timing.get("proposals_generated"),
                timing.get("duplicates_collapsed"),
                timing.get("invalid_rejected"),
                timing.get("alternatives_retained"),
                timing.get("residuals_emitted"),
                timing.get("tokens_processed"),
                timing.get("tokens_per_second"),
                timing.get("reduction_ratio"),
                timing.get("reduction_efficiency_edges_per_second"),
                _json(timing.get("details") or {}),
            )
        )
    if rows:
        cursor.executemany(
            """
            INSERT INTO semantic_stage_timing
                (timing_ref, document_ref, stage, ordinal, elapsed_ms,
                 backend_ref, input_nodes, output_nodes, input_edges,
                 output_edges, proposals_generated, duplicates_collapsed,
                 invalid_rejected, alternatives_retained, residuals_emitted,
                 tokens_processed, tokens_per_second, reduction_ratio,
                 reduction_efficiency_edges_per_second, details)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (timing_ref) DO NOTHING
            """,
            rows,
        )


__all__ = ["persist_stage_timings"]
