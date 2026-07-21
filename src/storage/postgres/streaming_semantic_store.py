"""Persistence helpers for immutable streaming semantic execution evidence."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def _persist_factor_proposal(cursor: Any, proposal: Mapping[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO pnf_factor_proposal
            (proposal_ref, proposal_digest, document_ref, source_revision_ref,
             factor_type_ref, structural_signature, producer_contract,
             declaration_revision, source_span_refs, input_observation_refs,
             dependency_factor_refs, role_bindings, qualifier_state,
             candidate_payload, residuals, authority)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s,
             %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
             %s::jsonb, %s::jsonb, 'candidate_only')
        ON CONFLICT (proposal_ref) DO NOTHING
        """,
        (
            str(proposal["proposal_ref"]),
            str(proposal["proposal_digest"]),
            str(proposal["document_ref"]),
            str(proposal["source_revision_ref"]),
            str(proposal["factor_type_ref"]),
            str(proposal["structural_signature"]),
            str(proposal["producer_contract"]),
            str(proposal["declaration_revision"]),
            _json(proposal.get("source_span_refs") or ()),
            _json(proposal.get("input_observation_refs") or ()),
            _json(proposal.get("dependency_factor_refs") or ()),
            _json(proposal.get("role_bindings") or {}),
            _json(proposal.get("qualifier_state") or {}),
            _json(proposal.get("candidate_payload") or {}),
            _json(proposal.get("residuals") or ()),
        ),
    )


def persist_streaming_semantic_artifacts(
    cursor: Any,
    *,
    document_ref: str,
    streaming_build: Mapping[str, Any],
    stage_timing_ledger: Mapping[str, Any],
) -> None:
    """Persist one convergent ledger and deterministic materialised view."""

    ledger = streaming_build.get("ledger") or {}
    delta_by_ref = {
        str(row.get("delta_ref") or ""): row
        for row in streaming_build.get("observation_deltas") or ()
        if isinstance(row, Mapping) and row.get("delta_ref")
    }
    for delta_ref in ledger.get("observation_delta_refs") or ():
        row = delta_by_ref.get(str(delta_ref))
        if row is None:
            continue
        cursor.execute(
            """
            INSERT INTO semantic_observation_delta
                (delta_ref, document_ref, batch_ref, scope_ref, sequence_no,
                 parser_contract, observation_refs, observations, token_start,
                 token_end, char_start, char_end, token_count, coverage_barrier,
                 coverage_complete, payload_sha256)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                 %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (delta_ref) DO NOTHING
            """,
            (
                str(row["delta_ref"]),
                document_ref,
                str(row["batch_ref"]),
                str(row["scope_ref"]),
                int(row["sequence_no"]),
                str(row["parser_contract"]),
                _json(row.get("observation_refs") or ()),
                _json(row.get("observations") or ()),
                int(row["token_start"]),
                int(row["token_end"]),
                int(row["char_start"]),
                int(row["char_end"]),
                int(row["token_count"]),
                str(row["coverage_barrier"]),
                bool(row["coverage_complete"]),
                _sha(row),
            ),
        )

    notice_by_ref = {
        str(row.get("notice_ref") or ""): row
        for row in streaming_build.get("coverage_notices") or ()
        if isinstance(row, Mapping) and row.get("notice_ref")
    }
    for notice_ref in ledger.get("coverage_notice_refs") or ():
        row = notice_by_ref.get(str(notice_ref))
        if row is None:
            continue
        cursor.execute(
            """
            INSERT INTO semantic_coverage_notice
                (notice_ref, document_ref, scope_ref, barrier, state, evidence_refs)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (notice_ref) DO NOTHING
            """,
            (
                str(row["notice_ref"]),
                document_ref,
                str(row["scope_ref"]),
                str(row["barrier"]),
                str(row["state"]),
                _json(row.get("evidence_refs") or ()),
            ),
        )

    proposals = streaming_build.get("proposals") or ()
    for proposal in proposals:
        if isinstance(proposal, Mapping):
            _persist_factor_proposal(cursor, proposal)

    jobs = {
        str(row.get("job_ref") or ""): row
        for row in streaming_build.get("solver_jobs") or ()
        if isinstance(row, Mapping) and row.get("job_ref")
    }
    for row in jobs.values():
        owner = row.get("owner_key") or {}
        cursor.execute(
            """
            INSERT INTO semantic_solver_job
                (job_ref, document_ref, owner_ref, scope_ref, factor_family,
                 declaration_ref, input_revision, input_refs, input_payload,
                 rule_set_revision, coverage_requirements, assumptions, priority)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                 %s, %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (job_ref) DO NOTHING
            """,
            (
                str(row["job_ref"]),
                document_ref,
                "semantic-owner:" + canonical_sha256(owner),
                str(owner.get("scope_ref") or ""),
                str(owner.get("factor_family") or ""),
                str(row["declaration_ref"]),
                int(row["input_revision"]),
                _json(row.get("input_refs") or ()),
                _json(row.get("input_payload") or {}),
                str(row["rule_set_revision"]),
                _json(row.get("coverage_requirements") or ()),
                _json(row.get("assumptions") or ()),
                int(row.get("priority", 100)),
            ),
        )

    for row in streaming_build.get("solver_receipts") or ():
        if not isinstance(row, Mapping):
            continue
        owner = row.get("owner_key") or {}
        cursor.execute(
            """
            INSERT INTO semantic_solver_receipt
                (receipt_ref, job_ref, document_ref, owner_ref, input_revision,
                 input_refs, rule_set_revision, proposal_refs, residuals,
                 assumptions, coverage_requirements, metrics, backend_ref,
                 semantic_state_promoted)
            VALUES
                (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb,
                 %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, FALSE)
            ON CONFLICT (receipt_ref) DO NOTHING
            """,
            (
                str(row["receipt_ref"]),
                str(row["job_ref"]),
                document_ref,
                "semantic-owner:" + canonical_sha256(owner),
                int(row["input_revision"]),
                _json(row.get("input_refs") or ()),
                str(row["rule_set_revision"]),
                _json(row.get("proposal_refs") or ()),
                _json(row.get("residuals") or ()),
                _json(row.get("assumptions") or ()),
                _json(row.get("coverage_requirements") or ()),
                _json(row.get("metrics") or {}),
                str(row.get("backend_ref") or ""),
            ),
        )

    for row in streaming_build.get("state_deltas") or ():
        if not isinstance(row, Mapping):
            continue
        cursor.execute(
            """
            INSERT INTO semantic_state_delta
                (document_ref, resulting_revision, prior_revision,
                 accepted_observation_refs, accepted_proposal_refs,
                 changed_factor_refs, introduced_residual_refs,
                 discharged_residual_refs, dirty_owner_refs, emitted_job_refs)
            VALUES
                (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                 %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
            ON CONFLICT (document_ref, resulting_revision) DO NOTHING
            """,
            (
                document_ref,
                int(row["resulting_revision"]),
                int(row["prior_revision"]),
                _json(row.get("accepted_observation_refs") or ()),
                _json(row.get("accepted_proposal_refs") or ()),
                _json(row.get("changed_factor_refs") or ()),
                _json(row.get("introduced_residual_refs") or ()),
                _json(row.get("discharged_residual_refs") or ()),
                _json(row.get("dirty_owner_refs") or ()),
                _json(row.get("emitted_job_refs") or ()),
            ),
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
            str(materialized["graph_ref"]),
            document_ref,
            int(streaming_build["revision"]),
            str(ledger["ledger_ref"]),
            int(materialized.get("proposal_count", 0)),
            _json([row.get("factor_ref") for row in materialized.get("factors") or ()]),
            _json([row.get("residual_ref") for row in materialized.get("residuals") or ()]),
        ),
    )

    for row in streaming_build.get("region_boundary_summaries") or ():
        if not isinstance(row, Mapping):
            continue
        cursor.execute(
            """
            INSERT INTO semantic_region_boundary_summary
                (summary_ref, document_ref, scope_ref, stable_factor_refs,
                 unresolved_external_refs, possible_cross_scope_hosts,
                 definition_scope_obligations, coverage_notice_refs)
            VALUES
                (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                 %s::jsonb, %s::jsonb)
            ON CONFLICT (summary_ref) DO NOTHING
            """,
            (
                str(row["summary_ref"]),
                document_ref,
                str(row["scope_ref"]),
                _json(row.get("stable_factor_refs") or ()),
                _json(row.get("unresolved_external_refs") or ()),
                _json(row.get("possible_cross_scope_hosts") or ()),
                _json(row.get("definition_scope_obligations") or ()),
                _json(row.get("coverage_notice_refs") or ()),
            ),
        )

    certificate = streaming_build.get("fixed_point_certificate") or {}
    cursor.execute(
        """
        INSERT INTO semantic_fixed_point_certificate
            (certificate_ref, document_ref, revision, ledger_ref,
             materialized_graph_ref, local_fixed_point,
             unconsumed_observation_deltas, dirty_reduction_groups,
             pending_jobs, in_flight_jobs,
             unresolved_local_boundary_obligations,
             open_required_coverage_barriers,
             unresolved_external_residuals, resource_limit_reached,
             identity_promoted, legal_truth_closed)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
             %s::jsonb, %s, FALSE, FALSE)
        ON CONFLICT (certificate_ref) DO NOTHING
        """,
        (
            str(certificate["certificate_ref"]),
            document_ref,
            int(certificate["revision"]),
            str(certificate["ledger_ref"]),
            str(certificate["materialized_graph_ref"]),
            str(certificate["local_fixed_point"]),
            int(certificate["unconsumed_observation_deltas"]),
            int(certificate["dirty_reduction_groups"]),
            int(certificate["pending_jobs"]),
            int(certificate["in_flight_jobs"]),
            int(certificate["unresolved_local_boundary_obligations"]),
            int(certificate["open_required_coverage_barriers"]),
            _json(certificate.get("unresolved_external_residuals") or ()),
            bool(certificate.get("resource_limit_reached", False)),
        ),
    )

    for timing in stage_timing_ledger.get("timings") or ():
        if not isinstance(timing, Mapping):
            continue
        cursor.execute(
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
            ),
        )


def load_stage_timings(cursor: Any, *, document_ref: str) -> tuple[dict[str, Any], ...]:
    cursor.execute(
        """
        SELECT stage, ordinal, elapsed_ms, backend_ref, input_nodes, output_nodes,
               input_edges, output_edges, proposals_generated,
               duplicates_collapsed, invalid_rejected, alternatives_retained,
               residuals_emitted, tokens_processed, tokens_per_second,
               reduction_ratio, reduction_efficiency_edges_per_second, details
        FROM semantic_stage_timing
        WHERE document_ref = %s
        ORDER BY ordinal
        """,
        (document_ref,),
    )
    columns = (
        "stage",
        "ordinal",
        "elapsed_ms",
        "backend_ref",
        "input_nodes",
        "output_nodes",
        "input_edges",
        "output_edges",
        "proposals_generated",
        "duplicates_collapsed",
        "invalid_rejected",
        "alternatives_retained",
        "residuals_emitted",
        "tokens_processed",
        "tokens_per_second",
        "reduction_ratio",
        "reduction_efficiency_edges_per_second",
        "details",
    )
    return tuple(dict(zip(columns, row, strict=True)) for row in cursor.fetchall())


__all__ = ["load_stage_timings", "persist_streaming_semantic_artifacts"]
