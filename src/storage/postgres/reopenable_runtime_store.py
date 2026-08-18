"""PostgreSQL gateway for the consumer-indexed reopenable PNF runtime.

This module deliberately delegates set operations to PostgreSQL.  Python owns
coordination and typed boundaries; it does not rebuild candidate fibres in
memory or turn retrieval rank into semantic authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.policy.reopenable_runtime import (
    EvidenceHorizon,
    RelevanceAccounting,
    SignedEvidence,
    StageCost,
)
from src.storage.postgres.spacy_parser_model import connect


@dataclass(frozen=True, slots=True)
class DemandFunnelRow:
    demand_id: int
    demand_state: int
    represented_candidate_count: int
    active_candidate_count: int
    residual_candidate_count: int
    refuted_candidate_count: int
    evidence_count: int
    admitted_identity_witness_count: int
    outside_model_possible: bool
    resource_limited: bool


@dataclass(frozen=True, slots=True)
class AlignmentSummaryRow:
    alignment_class: str
    projection_count: int


class ReopenableRuntimeStore:
    """Thin transactional API around migration 086's set-based runtime."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def record_evidence(self, evidence: SignedEvidence) -> int:
        """Insert one immutable evidence atom, or return its existing id.

        Reusing an ``evidence_ref`` is idempotent.  It never mutates an earlier
        signed residual; corrected evidence must receive a new provenance ref.
        """

        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        WITH inserted AS (
                            INSERT INTO execution.semantic_pnf_candidate_evidence
                                (demand_id, target_kind, target_id, evidence_ref,
                                 evidence_family, horizon, signed_residual,
                                 evidence_kind, provenance_ref)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (
                                demand_id, target_kind, target_id, evidence_ref
                            ) DO NOTHING
                            RETURNING evidence_id
                        )
                        SELECT evidence_id FROM inserted
                        UNION ALL
                        SELECT evidence_id
                          FROM execution.semantic_pnf_candidate_evidence
                         WHERE demand_id = %s
                           AND target_kind = %s
                           AND target_id = %s
                           AND evidence_ref = %s
                        LIMIT 1
                        """,
                        (
                            evidence.candidate.demand_id,
                            evidence.candidate.target_kind,
                            evidence.candidate.target_id,
                            evidence.evidence_ref,
                            int(evidence.family),
                            int(evidence.horizon),
                            evidence.signed_residual,
                            "runtime_evidence",
                            evidence.provenance_ref,
                            evidence.candidate.demand_id,
                            evidence.candidate.target_kind,
                            evidence.candidate.target_id,
                            evidence.evidence_ref,
                        ),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise RuntimeError(
                            "candidate evidence insert did not return an id"
                        )
                    return int(row[0])
        finally:
            connection.close()

    def prune_candidate(
        self,
        *,
        demand_id: int,
        target_kind: int,
        target_id: int,
        active_budget: int,
        reason_ref: str = "bounded-execution",
    ) -> int:
        return self._scalar_function(
            "execution.prune_numeric_pnf_candidate_execution",
            (demand_id, target_kind, target_id, active_budget, reason_ref),
        )

    def reopen_candidate(
        self,
        *,
        demand_id: int,
        target_kind: int,
        target_id: int,
        reason_ref: str = "new-evidence",
    ) -> int:
        return self._scalar_function(
            "execution.reopen_numeric_pnf_candidate_execution",
            (demand_id, target_kind, target_id, reason_ref),
        )

    def set_admissibility(
        self,
        *,
        demand_id: int,
        target_kind: int,
        target_id: int,
        refuted: bool,
        evidence_id: int,
    ) -> int:
        return self._scalar_function(
            "execution.record_numeric_pnf_candidate_admissibility",
            (demand_id, target_kind, target_id, 1 if refuted else 2, evidence_id),
        )

    def record_relevance(
        self,
        *,
        demand_id: int,
        consumer_ref: str,
        mass_kind: int,
        horizon: EvidenceHorizon,
        accounting: RelevanceAccounting,
        measurement_ref: str,
    ) -> int:
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_demand_relevance_accounting
                            (demand_id, consumer_ref, mass_kind, horizon,
                             active_mass, residual_candidate_mass,
                             represented_residual_mass, outside_model_mass,
                             total_mass, measurement_ref)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (measurement_ref) DO UPDATE SET
                            active_mass = EXCLUDED.active_mass,
                            residual_candidate_mass = EXCLUDED.residual_candidate_mass,
                            represented_residual_mass = EXCLUDED.represented_residual_mass,
                            outside_model_mass = EXCLUDED.outside_model_mass,
                            total_mass = EXCLUDED.total_mass
                        RETURNING accounting_id
                        """,
                        (
                            demand_id,
                            consumer_ref,
                            mass_kind,
                            int(horizon),
                            accounting.active_mass,
                            accounting.residual_candidate_mass,
                            accounting.represented_residual_mass,
                            accounting.outside_model_mass,
                            accounting.total_mass,
                            measurement_ref,
                        ),
                    )
                    return int(cursor.fetchone()[0])
        finally:
            connection.close()

    def record_stage_cost(self, cost: StageCost, *, measurement_ref: str) -> int:
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_runtime_stage_measurement
                            (measurement_ref, workload_ref, stage_name,
                             input_units, generated_units, retained_units,
                             output_units, work_units, elapsed_microseconds,
                             peak_memory_bytes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (measurement_ref) DO UPDATE SET
                            input_units = EXCLUDED.input_units,
                            generated_units = EXCLUDED.generated_units,
                            retained_units = EXCLUDED.retained_units,
                            output_units = EXCLUDED.output_units,
                            work_units = EXCLUDED.work_units,
                            elapsed_microseconds = EXCLUDED.elapsed_microseconds,
                            peak_memory_bytes = EXCLUDED.peak_memory_bytes
                        RETURNING measurement_id
                        """,
                        (
                            measurement_ref,
                            cost.workload_ref,
                            cost.stage_name,
                            cost.input_units,
                            cost.generated_units,
                            cost.retained_units,
                            cost.output_units,
                            cost.work_units,
                            cost.elapsed_microseconds,
                            cost.peak_memory_bytes,
                        ),
                    )
                    return int(cursor.fetchone()[0])
        finally:
            connection.close()

    def record_retrieval_measurement(
        self,
        *,
        measurement_ref: str,
        workload_ref: str,
        retrieval_kind: int,
        universe_units: int,
        frontier_units: int,
        probe_microseconds: int,
        downstream_work_units: int,
        exact_downstream_required: bool = False,
    ) -> int:
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_retrieval_measurement
                            (measurement_ref, workload_ref, retrieval_kind,
                             universe_units, frontier_units, probe_microseconds,
                             downstream_work_units, exact_downstream_required)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (measurement_ref) DO UPDATE SET
                            universe_units = EXCLUDED.universe_units,
                            frontier_units = EXCLUDED.frontier_units,
                            probe_microseconds = EXCLUDED.probe_microseconds,
                            downstream_work_units = EXCLUDED.downstream_work_units,
                            exact_downstream_required = EXCLUDED.exact_downstream_required
                        RETURNING measurement_id
                        """,
                        (
                            measurement_ref,
                            workload_ref,
                            retrieval_kind,
                            universe_units,
                            frontier_units,
                            probe_microseconds,
                            downstream_work_units,
                            exact_downstream_required,
                        ),
                    )
                    return int(cursor.fetchone()[0])
        finally:
            connection.close()

    def refresh_supported_identity_derivations(
        self, *, run_id: int, document_id: int
    ) -> int:
        return self._scalar_function(
            "execution.refresh_numeric_pnf_supported_identity_substitution_derivations",
            (run_id, document_id),
        )

    def demand_funnel(
        self, *, run_id: int, document_id: int
    ) -> tuple[DemandFunnelRow, ...]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT demand_id, demand_state,
                           represented_candidate_count,
                           active_candidate_count,
                           residual_candidate_count,
                           refuted_candidate_count,
                           evidence_count,
                           admitted_identity_witness_count,
                           outside_model_possible,
                           resource_limited
                      FROM execution.semantic_pnf_demand_funnel_v1
                     WHERE run_id = %s AND document_id = %s
                     ORDER BY demand_id
                    """,
                    (run_id, document_id),
                )
                return tuple(
                    DemandFunnelRow(
                        demand_id=int(row[0]),
                        demand_state=int(row[1]),
                        represented_candidate_count=int(row[2]),
                        active_candidate_count=int(row[3]),
                        residual_candidate_count=int(row[4]),
                        refuted_candidate_count=int(row[5]),
                        evidence_count=int(row[6]),
                        admitted_identity_witness_count=int(row[7]),
                        outside_model_possible=bool(row[8]),
                        resource_limited=bool(row[9]),
                    )
                    for row in cursor.fetchall()
                )
        finally:
            connection.close()

    def identity_factor_alignment(
        self, *, run_id: int, document_id: int
    ) -> tuple[AlignmentSummaryRow, ...]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT alignment_class, projection_count
                      FROM execution.semantic_pnf_identity_factor_alignment_summary_v1
                     WHERE run_id = %s AND document_id = %s
                     ORDER BY alignment_class
                    """,
                    (run_id, document_id),
                )
                return tuple(
                    AlignmentSummaryRow(str(row[0]), int(row[1]))
                    for row in cursor.fetchall()
                )
        finally:
            connection.close()

    def _scalar_function(self, qualified_name: str, args: Iterable[Any]) -> int:
        values = tuple(args)
        placeholders = ", ".join(["%s"] * len(values))
        connection = connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT {qualified_name}({placeholders})",  # noqa: S608
                        values,
                    )
                    return int(cursor.fetchone()[0])
        finally:
            connection.close()
