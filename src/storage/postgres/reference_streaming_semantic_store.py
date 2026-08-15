"""Bounded PostgreSQL persistence for reference-backed semantic builds."""

from __future__ import annotations

import json
from typing import Any, Mapping

from src.pnf.streaming_build_reader import StreamingBuildReader
from src.policy.carriers.canonical import canonical_sha256
from src.runtime.stage_memory_budget import StageMemoryBudgetGuard
from src.storage.postgres.distributed_semantic_execution_store import (
    DistributedSemanticExecutionStore,
)
from src.storage.postgres.stage_timing_store import persist_stage_timings


DEFAULT_BATCH_SIZE = 256


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def _persist_observation_batch(
    cursor: Any, document_ref: str, rows: tuple[Mapping[str, Any], ...]
) -> None:
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
            )
            for row in rows
        ],
    )


def _persist_notice_batch(
    cursor: Any, document_ref: str, rows: tuple[Mapping[str, Any], ...]
) -> None:
    cursor.executemany(
        """
        INSERT INTO semantic_coverage_notice
            (notice_ref, document_ref, scope_ref, barrier, state, evidence_refs)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (notice_ref) DO NOTHING
        """,
        [
            (
                str(row["notice_ref"]),
                document_ref,
                str(row["scope_ref"]),
                str(row["barrier"]),
                str(row["state"]),
                _json(row.get("evidence_refs") or ()),
            )
            for row in rows
        ],
    )


def _persist_proposal_batch(cursor: Any, rows: tuple[Mapping[str, Any], ...]) -> None:
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
                str(row["proposal_ref"]),
                str(row.get("proposal_digest") or canonical_sha256(row)),
                str(row["document_ref"]),
                str(row["source_revision_ref"]),
                str(row["factor_type_ref"]),
                str(row.get("structural_signature") or ""),
                str(row.get("producer_contract") or ""),
                str(row.get("declaration_revision") or ""),
                _json(row.get("source_span_refs") or ()),
                _json(row.get("input_observation_refs") or ()),
                _json(row.get("dependency_factor_refs") or ()),
                _json(row.get("role_bindings") or {}),
                _json(row.get("qualifier_state") or {}),
                _json(row.get("candidate_payload") or {}),
                _json(row.get("residuals") or ()),
            )
            for row in rows
        ],
    )


def _persist_job_batch(
    cursor: Any, document_ref: str, rows: tuple[Mapping[str, Any], ...]
) -> None:
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
                str(row["job_ref"]),
                document_ref,
                "semantic-owner:" + canonical_sha256(row.get("owner_key") or {}),
                str((row.get("owner_key") or {}).get("scope_ref") or ""),
                str((row.get("owner_key") or {}).get("factor_family") or ""),
                str(row.get("declaration_ref") or ""),
                int(row.get("input_revision") or 0),
                _json(row.get("input_refs") or ()),
                _json(row.get("input_payload") or {}),
                str(row.get("rule_set_revision") or ""),
                _json(row.get("coverage_requirements") or ()),
                _json(row.get("assumptions") or ()),
                int(row.get("priority") or 100),
            )
            for row in rows
        ],
    )


def _persist_receipt_batch(
    cursor: Any, document_ref: str, rows: tuple[Mapping[str, Any], ...]
) -> None:
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
                str(row["receipt_ref"]),
                str(row["job_ref"]),
                document_ref,
                "semantic-owner:" + canonical_sha256(row.get("owner_key") or {}),
                int(row.get("input_revision") or 0),
                _json(row.get("input_refs") or ()),
                str(row.get("rule_set_revision") or ""),
                _json(row.get("proposal_refs") or ()),
                _json(row.get("residuals") or ()),
                _json(row.get("assumptions") or ()),
                _json(row.get("coverage_requirements") or ()),
                _json(row.get("metrics") or {}),
                str(row.get("backend_ref") or ""),
            )
            for row in rows
        ],
    )


def _persist_state_delta_batch(
    cursor: Any, document_ref: str, rows: tuple[Mapping[str, Any], ...]
) -> None:
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
            )
            for row in rows
        ],
    )


def _append_reduction_refs(
    cursor: Any,
    *,
    graph_ref: str,
    column: str,
    refs: list[str],
) -> None:
    if column not in {"factor_refs", "residual_refs"}:
        raise ValueError("invalid reduction reference column")
    cursor.execute(
        f"""
        UPDATE semantic_materialized_reduction
        SET {column} = {column} || %s::jsonb
        WHERE graph_ref = %s
        """,
        (_json(refs), graph_ref),
    )


def persist_reference_streaming_semantic_artifacts(
    cursor: Any,
    *,
    document_ref: str,
    streaming_build: Mapping[str, Any],
    stage_timing_ledger: Mapping[str, Any],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, int | str]:
    """Persist every family in bounded verified batches."""

    reader = StreamingBuildReader(streaming_build)
    budget = StageMemoryBudgetGuard()
    counts: dict[str, int | str] = {}
    writers = {
        "observation_deltas": lambda rows: _persist_observation_batch(
            cursor, document_ref, rows
        ),
        "coverage_notices": lambda rows: _persist_notice_batch(
            cursor, document_ref, rows
        ),
        "proposals": lambda rows: _persist_proposal_batch(cursor, rows),
        "solver_jobs": lambda rows: _persist_job_batch(cursor, document_ref, rows),
        "solver_receipts": lambda rows: _persist_receipt_batch(
            cursor, document_ref, rows
        ),
        "state_deltas": lambda rows: _persist_state_delta_batch(
            cursor, document_ref, rows
        ),
    }
    budget.checkpoint("publication", phase="reference_persistence_started")
    for family, writer in writers.items():
        completed = 0
        for batch in reader.iter_batches(family, batch_size=batch_size):
            writer(batch)
            completed += len(batch)
            budget.checkpoint(
                "publication",
                phase="family_batch_committed",
                semantic_counts={"rows": completed},
                details={"family": family, "batch_size": len(batch)},
            )
        counts[family] = completed

    materialized = streaming_build.get("materialized_reduction") or {}
    graph_ref = str(materialized["graph_ref"])
    ledger = streaming_build.get("ledger") or {}
    ledger_ref = str(ledger.get("ledger_ref") or "")
    cursor.execute(
        """
        INSERT INTO semantic_materialized_reduction
            (graph_ref, document_ref, revision, ledger_ref, proposal_count,
             factor_refs, residual_refs, shared_graph_mutation, last_writer_wins)
        VALUES (%s, %s, %s, %s, %s, '[]'::jsonb, '[]'::jsonb, FALSE, FALSE)
        ON CONFLICT (graph_ref) DO NOTHING
        """,
        (
            graph_ref,
            document_ref,
            int(streaming_build["revision"]),
            ledger_ref,
            int(materialized.get("proposal_count") or 0),
        ),
    )

    execution_store = DistributedSemanticExecutionStore()
    owner_fingerprint = streaming_build.get("owner_fingerprint") or {}
    factor_descriptor = reader.descriptor("factors") or {}
    residual_descriptor = reader.descriptor("residuals") or {}
    root_sha = canonical_sha256(
        {
            "graph_ref": graph_ref,
            "owner_fingerprint": owner_fingerprint,
            "factor_digest": factor_descriptor.get("ordered_digest"),
            "residual_digest": residual_descriptor.get("ordered_digest"),
        }
    )
    certificate = streaming_build.get("fixed_point_certificate") or {}
    manifest_ref = "semantic-graph-manifest:" + root_sha
    execution_store.persist_graph_manifest(
        cursor,
        manifest_ref=manifest_ref,
        document_ref=document_ref,
        graph_ref=graph_ref,
        graph_revision=int(streaming_build["revision"]),
        root_sha256=root_sha,
        coverage_digest=canonical_sha256(
            owner_fingerprint.get("coverage_manifest_ref") or ""
        ),
        node_count=reader.family_count("factors"),
        edge_count=reader.family_count("proposals"),
        unresolved_count=reader.family_count("residuals"),
        operation_contract_refs=("reference-backed-finalization:v1",),
    )

    # Each authoritative revision family is consumed once by its store method;
    # that method maintains a monotone sequence across all internal batches.
    factor_count = execution_store.persist_factor_revisions(
        cursor,
        manifest_ref=manifest_ref,
        rows=reader.iter_rows("factors"),
        batch_size=batch_size,
    )
    residual_count = execution_store.persist_residual_revisions(
        cursor,
        manifest_ref=manifest_ref,
        rows=reader.iter_rows("residuals"),
        batch_size=batch_size,
    )

    # Legacy materialized-reduction arrays remain a compatibility projection.
    # Re-read the verified stream in bounded batches rather than retaining refs.
    completed_factor_refs = 0
    for batch in reader.iter_batches("factors", batch_size=batch_size):
        _append_reduction_refs(
            cursor,
            graph_ref=graph_ref,
            column="factor_refs",
            refs=[str(row["factor_ref"]) for row in batch],
        )
        completed_factor_refs += len(batch)
        budget.checkpoint(
            "publication",
            phase="factor_reference_batch_committed",
            semantic_counts={"rows": completed_factor_refs},
            details={"batch_size": len(batch)},
        )
    completed_residual_refs = 0
    for batch in reader.iter_batches("residuals", batch_size=batch_size):
        _append_reduction_refs(
            cursor,
            graph_ref=graph_ref,
            column="residual_refs",
            refs=[str(row["residual_ref"]) for row in batch],
        )
        completed_residual_refs += len(batch)
        budget.checkpoint(
            "publication",
            phase="residual_reference_batch_committed",
            semantic_counts={"rows": completed_residual_refs},
            details={"batch_size": len(batch)},
        )
    if (
        factor_count != completed_factor_refs
        or residual_count != completed_residual_refs
    ):
        raise ValueError("authoritative and compatibility reduction counts disagree")
    counts["factors"] = factor_count
    counts["residuals"] = residual_count
    counts["graph_manifest_ref"] = manifest_ref

    boundary_count = 0
    for batch in reader.iter_batches(
        "region_boundary_summaries", batch_size=batch_size
    ):
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
                    str(row["summary_ref"]),
                    document_ref,
                    str(row["scope_ref"]),
                    _json(row.get("stable_factor_refs") or ()),
                    _json(row.get("unresolved_external_refs") or ()),
                    _json(row.get("possible_cross_scope_hosts") or ()),
                    _json(row.get("definition_scope_obligations") or ()),
                    _json(row.get("coverage_notice_refs") or ()),
                )
                for row in batch
            ],
        )
        boundary_count += len(batch)
        budget.checkpoint(
            "publication",
            phase="boundary_summary_batch_committed",
            semantic_counts={"rows": boundary_count},
            details={"batch_size": len(batch)},
        )
    counts["region_boundary_summaries"] = boundary_count

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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
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
    persist_stage_timings(
        cursor,
        document_ref=document_ref,
        timings=(
            row
            for row in stage_timing_ledger.get("timings") or ()
            if isinstance(row, Mapping)
        ),
    )
    budget.checkpoint(
        "publication",
        phase="reference_persistence_completed",
        semantic_counts={
            key: int(value) for key, value in counts.items() if isinstance(value, int)
        },
        details={"graph_manifest_ref": manifest_ref},
    )
    return counts


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "persist_reference_streaming_semantic_artifacts",
]
