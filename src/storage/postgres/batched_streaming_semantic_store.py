"""Batched persistence for append-only streaming semantic receipts."""

from __future__ import annotations

import json
from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256
from src.storage.postgres.stage_timing_store import persist_stage_timings


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def persist_streaming_semantic_artifacts_batched(
    cursor: Any,
    *,
    document_ref: str,
    streaming_build: Mapping[str, Any],
    stage_timing_ledger: Mapping[str, Any],
) -> None:
    ledger = streaming_build.get("ledger") or {}
    deltas = [
        row
        for row in streaming_build.get("observation_deltas") or ()
        if isinstance(row, Mapping)
    ]
    if deltas:
        cursor.executemany(
            """
            INSERT INTO semantic_observation_delta
                (delta_ref, document_ref, batch_ref, scope_ref, sequence_no,
                 parser_contract, observation_refs, observations, token_start,
                 token_end, char_start, char_end, token_count, coverage_barrier,
                 coverage_complete, payload_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                    %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (delta_ref) DO NOTHING
            """,
            [
                (
                    row["delta_ref"], document_ref, row["batch_ref"], row["scope_ref"],
                    int(row["sequence_no"]), row["parser_contract"],
                    _json(row.get("observation_refs") or ()),
                    _json(row.get("observations") or ()), int(row["token_start"]),
                    int(row["token_end"]), int(row["char_start"]), int(row["char_end"]),
                    int(row["token_count"]), row["coverage_barrier"],
                    bool(row["coverage_complete"]), _sha(row),
                )
                for row in deltas
            ],
        )
    notices = [
        row
        for row in streaming_build.get("coverage_notices") or ()
        if isinstance(row, Mapping)
    ]
    if notices:
        cursor.executemany(
            """
            INSERT INTO semantic_coverage_notice
                (notice_ref, document_ref, scope_ref, barrier, state, evidence_refs)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (notice_ref) DO NOTHING
            """,
            [
                (
                    row["notice_ref"], document_ref, row["scope_ref"], row["barrier"],
                    row["state"], _json(row.get("evidence_refs") or ()),
                )
                for row in notices
            ],
        )
    proposals = [
        row for row in streaming_build.get("proposals") or () if isinstance(row, Mapping)
    ]
    if proposals:
        cursor.executemany(
            """
            INSERT INTO pnf_factor_proposal
                (proposal_ref, proposal_digest, document_ref, source_revision_ref,
                 factor_type_ref, structural_signature, producer_contract,
                 declaration_revision, source_span_refs, input_observation_refs,
                 dependency_factor_refs, role_bindings, qualifier_state,
                 candidate_payload, residuals, authority)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, 'candidate_only')
            ON CONFLICT (proposal_ref) DO NOTHING
            """,
            [
                (
                    row["proposal_ref"], row["proposal_digest"], row["document_ref"],
                    row["source_revision_ref"], row["factor_type_ref"],
                    row["structural_signature"], row["producer_contract"],
                    row["declaration_revision"], _json(row.get("source_span_refs") or ()),
                    _json(row.get("input_observation_refs") or ()),
                    _json(row.get("dependency_factor_refs") or ()),
                    _json(row.get("role_bindings") or {}),
                    _json(row.get("qualifier_state") or {}),
                    _json(row.get("candidate_payload") or {}),
                    _json(row.get("residuals") or ()),
                )
                for row in proposals
            ],
        )
    jobs = [
        row for row in streaming_build.get("solver_jobs") or () if isinstance(row, Mapping)
    ]
    if jobs:
        cursor.executemany(
            """
            INSERT INTO semantic_solver_job
                (job_ref, document_ref, owner_ref, scope_ref, factor_family,
                 declaration_ref, input_revision, input_refs, input_payload,
                 rule_set_revision, coverage_requirements, assumptions, priority)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                    %s, %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (job_ref) DO NOTHING
            """,
            [
                (
                    row["job_ref"], document_ref,
                    "semantic-owner:" + canonical_sha256(row.get("owner_key") or {}),
                    str((row.get("owner_key") or {}).get("scope_ref") or ""),
                    str((row.get("owner_key") or {}).get("factor_family") or ""),
                    row["declaration_ref"], int(row["input_revision"]),
                    _json(row.get("input_refs") or ()), _json(row.get("input_payload") or {}),
                    row["rule_set_revision"], _json(row.get("coverage_requirements") or ()),
                    _json(row.get("assumptions") or ()), int(row.get("priority", 100)),
                )
                for row in jobs
            ],
        )
    receipts = [
        row for row in streaming_build.get("solver_receipts") or () if isinstance(row, Mapping)
    ]
    if receipts:
        cursor.executemany(
            """
            INSERT INTO semantic_solver_receipt
                (receipt_ref, job_ref, document_ref, owner_ref, input_revision,
                 input_refs, rule_set_revision, proposal_refs, residuals,
                 assumptions, coverage_requirements, metrics, backend_ref,
                 semantic_state_promoted)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, FALSE)
            ON CONFLICT (receipt_ref) DO NOTHING
            """,
            [
                (
                    row["receipt_ref"], row["job_ref"], document_ref,
                    "semantic-owner:" + canonical_sha256(row.get("owner_key") or {}),
                    int(row["input_revision"]), _json(row.get("input_refs") or ()),
                    row["rule_set_revision"], _json(row.get("proposal_refs") or ()),
                    _json(row.get("residuals") or ()), _json(row.get("assumptions") or ()),
                    _json(row.get("coverage_requirements") or ()),
                    _json(row.get("metrics") or {}), str(row.get("backend_ref") or ""),
                )
                for row in receipts
            ],
        )
    state_deltas = [
        row for row in streaming_build.get("state_deltas") or () if isinstance(row, Mapping)
    ]
    if state_deltas:
        cursor.executemany(
            """
            INSERT INTO semantic_state_delta
                (document_ref, resulting_revision, prior_revision,
                 accepted_observation_refs, accepted_proposal_refs,
                 changed_factor_refs, introduced_residual_refs,
                 discharged_residual_refs, dirty_owner_refs, emitted_job_refs)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
            ON CONFLICT (document_ref, resulting_revision) DO NOTHING
            """,
            [
                (
                    document_ref, int(row["resulting_revision"]), int(row["prior_revision"]),
                    _json(row.get("accepted_observation_refs") or ()),
                    _json(row.get("accepted_proposal_refs") or ()),
                    _json(row.get("changed_factor_refs") or ()),
                    _json(row.get("introduced_residual_refs") or ()),
                    _json(row.get("discharged_residual_refs") or ()),
                    _json(row.get("dirty_owner_refs") or ()),
                    _json(row.get("emitted_job_refs") or ()),
                )
                for row in state_deltas
            ],
        )
    materialized = streaming_build.get("materialized_reduction") or {}
    cursor.execute(
        """
        INSERT INTO semantic_materialized_reduction
            (graph_ref, document_ref, revision, ledger_ref, proposal_count,
             factor_refs, residual_refs, shared_graph_mutation, last_writer_wins)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, FALSE, FALSE)
        ON CONFLICT (graph_ref) DO NOTHING
        """,
        (
            materialized["graph_ref"], document_ref, int(streaming_build["revision"]),
            ledger["ledger_ref"], int(materialized.get("proposal_count", 0)),
            _json([row.get("factor_ref") for row in materialized.get("factors") or ()]),
            _json([row.get("residual_ref") for row in materialized.get("residuals") or ()]),
        ),
    )
    boundaries = [
        row
        for row in streaming_build.get("region_boundary_summaries") or ()
        if isinstance(row, Mapping)
    ]
    if boundaries:
        cursor.executemany(
            """
            INSERT INTO semantic_region_boundary_summary
                (summary_ref, document_ref, scope_ref, stable_factor_refs,
                 unresolved_external_refs, possible_cross_scope_hosts,
                 definition_scope_obligations, coverage_notice_refs)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb)
            ON CONFLICT (summary_ref) DO NOTHING
            """,
            [
                (
                    row["summary_ref"], document_ref, row["scope_ref"],
                    _json(row.get("stable_factor_refs") or ()),
                    _json(row.get("unresolved_external_refs") or ()),
                    _json(row.get("possible_cross_scope_hosts") or ()),
                    _json(row.get("definition_scope_obligations") or ()),
                    _json(row.get("coverage_notice_refs") or ()),
                )
                for row in boundaries
            ],
        )
    certificate = streaming_build.get("fixed_point_certificate") or {}
    cursor.execute(
        """
        INSERT INTO semantic_fixed_point_certificate
            (certificate_ref, document_ref, revision, ledger_ref,
             materialized_graph_ref, local_fixed_point,
             unconsumed_observation_deltas, dirty_reduction_groups,
             pending_jobs, in_flight_jobs, unresolved_local_boundary_obligations,
             open_required_coverage_barriers, unresolved_external_residuals,
             resource_limit_reached, identity_promoted, legal_truth_closed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s, FALSE, FALSE)
        ON CONFLICT (certificate_ref) DO NOTHING
        """,
        (
            certificate["certificate_ref"], document_ref, int(certificate["revision"]),
            certificate["ledger_ref"], certificate["materialized_graph_ref"],
            certificate["local_fixed_point"], int(certificate["unconsumed_observation_deltas"]),
            int(certificate["dirty_reduction_groups"]), int(certificate["pending_jobs"]),
            int(certificate["in_flight_jobs"]),
            int(certificate["unresolved_local_boundary_obligations"]),
            int(certificate["open_required_coverage_barriers"]),
            _json(certificate.get("unresolved_external_residuals") or ()),
            bool(certificate.get("resource_limit_reached", False)),
        ),
    )
    persist_stage_timings(
        cursor,
        document_ref=document_ref,
        timings=(
            row
            for row in stage_timing_ledger.get("timings") or ()
            if isinstance(row, Mapping)
        ),
    )


__all__ = ["persist_streaming_semantic_artifacts_batched"]
