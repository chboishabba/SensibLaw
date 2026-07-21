"""PostgreSQL persistence for streaming coordination and constraint worklists."""

from __future__ import annotations

import json
from typing import Any, Mapping


def _json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def persist_streaming_coordination_artifacts(
    cursor: Any,
    *,
    document_ref: str,
    coordination: Mapping[str, Any],
    constraint_worklist: Mapping[str, Any],
    region_coordinator: Mapping[str, Any],
) -> None:
    for row in coordination.get("supersession_notices") or ():
        cursor.execute(
            """
            INSERT INTO semantic_supersession_notice
                (notice_ref, document_ref, replacement_pairs, reason_ref,
                 evidence_refs)
            VALUES (%s, %s, %s::jsonb, %s, %s::jsonb)
            ON CONFLICT (notice_ref) DO NOTHING
            """,
            (
                str(row["notice_ref"]),
                document_ref,
                _json(row.get("replacement_pairs") or ()),
                str(row["reason_ref"]),
                _json(row.get("evidence_refs") or ()),
            ),
        )

    for row in coordination.get("retraction_notices") or ():
        cursor.execute(
            """
            INSERT INTO semantic_retraction_notice
                (notice_ref, document_ref, proposal_refs, receipt_refs,
                 supersession_notice_ref, reason, semantic_state_promoted)
            VALUES
                (%s, %s, %s::jsonb, %s::jsonb, %s, %s, FALSE)
            ON CONFLICT (notice_ref) DO NOTHING
            """,
            (
                str(row["notice_ref"]),
                document_ref,
                _json(row.get("proposal_refs") or ()),
                _json(row.get("receipt_refs") or ()),
                str(row["supersession_notice_ref"]),
                str(row.get("reason") or "superseded_input"),
            ),
        )

    for row in coordination.get("stale_receipts") or ():
        cursor.execute(
            """
            INSERT INTO semantic_stale_solver_receipt
                (record_ref, receipt_ref, job_ref, stale_input_refs,
                 replacement_job_ref, supersession_notice_refs,
                 proposal_outputs_admitted)
            VALUES
                (%s, %s, %s, %s::jsonb, %s, %s::jsonb, FALSE)
            ON CONFLICT (record_ref) DO NOTHING
            """,
            (
                str(row["record_ref"]),
                str(row["receipt_ref"]),
                str(row["job_ref"]),
                _json(row.get("stale_input_refs") or ()),
                row.get("replacement_job_ref"),
                _json(row.get("supersession_notice_refs") or ()),
            ),
        )

    for ordinal, row in enumerate(coordination.get("admission_events") or ()):
        snapshot = row.get("snapshot") or {}
        cursor.execute(
            """
            INSERT INTO semantic_backpressure_event
                (document_ref, event_ordinal, delta_ref, admission_state,
                 pending_jobs, in_flight_jobs, dirty_groups, branching_mass,
                 deferred_deltas, paused, reasons)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (document_ref, event_ordinal) DO NOTHING
            """,
            (
                document_ref,
                ordinal,
                str(row["delta_ref"]),
                str(row["state"]),
                int(snapshot.get("pending_jobs", 0)),
                int(snapshot.get("in_flight_jobs", 0)),
                int(snapshot.get("dirty_groups", 0)),
                int(snapshot.get("branching_mass", 0)),
                int(snapshot.get("deferred_deltas", 0)),
                bool(snapshot.get("paused", False)),
                _json(snapshot.get("reasons") or ()),
            ),
        )

    for row in constraint_worklist.get("work_items") or ():
        cursor.execute(
            """
            INSERT INTO semantic_constraint_work_item
                (work_ref, document_ref, constraint_ref,
                 incident_factor_refs, triggering_factor_refs)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
            ON CONFLICT (work_ref) DO NOTHING
            """,
            (
                str(row["work_ref"]),
                document_ref,
                str(row["constraint_ref"]),
                _json(row.get("incident_factor_refs") or ()),
                _json(row.get("triggering_factor_refs") or ()),
            ),
        )

    if constraint_worklist:
        cursor.execute(
            """
            INSERT INTO semantic_constraint_worklist_result
                (result_ref, document_ref, assessment_refs, work_refs,
                 changed_factor_refs, fixed_point_rounds, pending_work_items,
                 semantic_state_promoted, legal_truth_closed)
            VALUES
                (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, 0,
                 FALSE, FALSE)
            ON CONFLICT (result_ref) DO NOTHING
            """,
            (
                str(constraint_worklist["result_ref"]),
                document_ref,
                _json(
                    [
                        row.get("assessment_ref")
                        for row in constraint_worklist.get("assessments") or ()
                    ]
                ),
                _json(
                    [
                        row.get("work_ref")
                        for row in constraint_worklist.get("work_items") or ()
                    ]
                ),
                _json(constraint_worklist.get("changed_factor_refs") or ()),
                int(constraint_worklist.get("fixed_point_rounds", 0)),
            ),
        )

    if region_coordinator:
        cursor.execute(
            """
            INSERT INTO semantic_document_region_coordinator
                (coordinator_ref, document_ref, region_summary_refs,
                 region_certificate_refs, boundary_routes,
                 discharged_boundary_refs, unresolved_boundary_refs,
                 local_fixed_point, identity_promoted, legal_truth_closed)
            VALUES
                (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                 %s::jsonb, %s, FALSE, FALSE)
            ON CONFLICT (coordinator_ref) DO NOTHING
            """,
            (
                str(region_coordinator["coordinator_ref"]),
                document_ref,
                _json(
                    [
                        row.get("summary_ref")
                        for row in region_coordinator.get("region_summaries") or ()
                    ]
                ),
                _json(region_coordinator.get("region_certificate_refs") or {}),
                _json(region_coordinator.get("boundary_routes") or {}),
                _json(
                    region_coordinator.get("discharged_boundary_refs") or ()
                ),
                _json(region_coordinator.get("unresolved_boundary_refs") or ()),
                str(region_coordinator["local_fixed_point"]),
            ),
        )


__all__ = ["persist_streaming_coordination_artifacts"]
