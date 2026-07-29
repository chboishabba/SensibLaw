"""Bounded-memory execution view over the canonical streaming semantic owner.

The canonical algebra remains in :mod:`src.pnf.streaming_fixed_point`. This
subclass changes only execution retention and indexes: proposals are bucketed by
``OwnerKey``, known factor dependencies are maintained incrementally, jobs carry
a bounded observation slice rather than a complete serialised delta, and audit
history may be compacted after admission.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from src.pnf.factor_proposals import FactorProposal, reduce_factor_proposals
from src.pnf.streaming_fixed_point import (
    ObservationDelta,
    OwnerKey,
    SolverJob,
    SolverReceipt,
    StateDelta,
    StreamingSemanticOwner,
)
from src.policy.carriers.canonical import canonical_sha256
from src.runtime.document_execution_policy import DocumentRetentionPolicy


class BoundedStreamingSemanticOwner(StreamingSemanticOwner):
    """Indexed owner with explicitly bounded production-history retention."""

    def __init__(
        self,
        *,
        document_ref: str,
        partition_count: int = 1,
        retention: DocumentRetentionPolicy | None = None,
    ):
        super().__init__(document_ref=document_ref, partition_count=partition_count)
        self.retention = retention or DocumentRetentionPolicy()
        self._proposals_by_owner: dict[OwnerKey, dict[str, FactorProposal]] = (
            defaultdict(dict)
        )
        self._known_dependency_refs: set[str] = set()
        self._compact_jobs: dict[str, dict[str, Any]] = {}
        self._compact_receipts: dict[str, dict[str, Any]] = {}
        self._compact_receipt_refs: set[str] = set()
        self._complete_coverage: set[tuple[str, str]] = set()
        self._compaction_count = 0

    def admit_observation_delta(self, delta: ObservationDelta) -> StateDelta:
        """Index sentence coverage before canonical job activation."""

        if delta.coverage_complete:
            self._complete_coverage.add((delta.scope_ref, delta.coverage_barrier))
        return super().admit_observation_delta(delta)

    def admit_coverage_notice(self, notice: Any) -> StateDelta:
        """Keep coverage lookup bounded while retaining canonical notices."""

        if notice.state == "complete":
            self._complete_coverage.add((notice.scope_ref, notice.barrier))
        return super().admit_coverage_notice(notice)

    def coverage_complete(self, *, scope_ref: str, barrier: str) -> bool:
        return (scope_ref, barrier) in self._complete_coverage

    def _advance(
        self,
        *,
        prior_revision: int,
        observations: Iterable[str] = (),
        proposals: Iterable[str] = (),
        changed_factors: Iterable[str] = (),
        introduced_residuals: Iterable[str] = (),
        discharged_residuals: Iterable[str] = (),
        dirty_owners: Iterable[str] = (),
        jobs: Iterable[str] = (),
    ) -> StateDelta:
        delta = super()._advance(
            prior_revision=prior_revision,
            observations=observations,
            proposals=proposals,
            changed_factors=changed_factors,
            introduced_residuals=introduced_residuals,
            discharged_residuals=discharged_residuals,
            dirty_owners=dirty_owners,
            jobs=jobs,
        )
        if not self.retention.state_deltas and self._state_deltas:
            self._state_deltas.clear()
        return delta

    @staticmethod
    def _compact_job_row(job: SolverJob) -> dict[str, Any]:
        return {
            "schema_version": "sl.pnf.solver_job.compact.v0_1",
            "job_ref": job.job_ref,
            "owner_key": job.owner_key.to_dict(),
            "declaration_ref": job.declaration_ref,
            "input_revision": job.input_revision,
            "input_refs": list(job.input_refs),
            "input_delta_ref": str(job.input_payload.get("input_delta_ref") or ""),
            "rule_set_revision": job.rule_set_revision,
            "coverage_requirements": list(job.coverage_requirements),
            "assumptions": list(job.assumptions),
            "priority": job.priority,
            "payload_compacted": True,
        }

    @staticmethod
    def _compact_receipt_row(receipt: SolverReceipt) -> dict[str, Any]:
        return {
            "schema_version": "sl.pnf.solver_receipt.compact.v0_1",
            "receipt_ref": receipt.receipt_ref,
            "job_ref": receipt.job_ref,
            "owner_key": receipt.owner_key.to_dict(),
            "input_revision": receipt.input_revision,
            "input_refs": list(receipt.input_refs),
            "rule_set_revision": receipt.rule_set_revision,
            "proposal_refs": sorted(
                proposal.proposal_ref for proposal in receipt.proposals
            ),
            "residuals": list(receipt.residuals),
            "assumptions": list(receipt.assumptions),
            "coverage_requirements": list(receipt.coverage_requirements),
            "metrics": dict(receipt.metrics),
            "backend_ref": receipt.backend_ref,
            "proposals_compacted": True,
            "semantic_state_promoted": False,
        }

    def _activate_declarations_for_delta(
        self,
        delta: ObservationDelta,
    ) -> tuple[SolverJob, ...]:
        observation_types = {
            str(row.get("observation_type") or row.get("type_ref") or "")
            for row in delta.observations
        }
        emitted: list[SolverJob] = []
        for declaration in sorted(
            self._declarations.values(),
            key=lambda row: (row.priority, row.declaration_ref),
        ):
            if declaration.requires and not set(declaration.requires).intersection(
                observation_types
            ):
                continue
            if not self.coverage_complete(
                scope_ref=delta.scope_ref,
                barrier=declaration.coverage_barrier,
            ):
                continue
            owner_key = OwnerKey(
                self.document_ref,
                delta.scope_ref,
                declaration.affected_index,
            )
            input_refs = tuple(delta.observation_refs)
            signature = canonical_sha256(
                {
                    "declaration_ref": declaration.declaration_ref,
                    "input_refs": input_refs,
                    "rule_set_revision": declaration.declaration_revision,
                }
            )
            if signature in self._completed_job_signatures:
                continue

            # Keep only fields required by the current pure operator handler.
            # This avoids delta.to_dict(), schema metadata, coordinate metadata,
            # and repeated identity materialisation in every matching job.
            observation_slice = tuple(
                {
                    "observation_ref": str(row.get("observation_ref") or ""),
                    "observation_type": str(
                        row.get("observation_type") or row.get("type_ref") or ""
                    ),
                    "token": dict(row.get("token") or {}),
                }
                for row in delta.observations
            )
            job = SolverJob(
                owner_key=owner_key,
                declaration_ref=declaration.declaration_ref,
                input_revision=self.revision,
                input_refs=input_refs,
                input_payload={
                    "input_delta_ref": delta.delta_ref,
                    "observation_delta": {
                        "delta_ref": delta.delta_ref,
                        "scope_ref": delta.scope_ref,
                        "observations": observation_slice,
                    },
                },
                rule_set_revision=declaration.declaration_revision,
                coverage_requirements=(declaration.coverage_barrier,),
                priority=declaration.priority,
            )
            self._compact_jobs.setdefault(job.job_ref, self._compact_job_row(job))
            if self.retention.completed_jobs:
                self._jobs.setdefault(job.job_ref, job)
            if (
                job.job_ref not in self._pending_jobs
                and job.job_ref not in self._in_flight_jobs
                and signature not in self._completed_job_signatures
            ):
                self._pending_jobs[job.job_ref] = job
                emitted.append(job)
        return tuple(emitted)

    def _index_proposal(self, proposal: FactorProposal, *, stage: str) -> bool:
        if proposal.document_ref != self.document_ref:
            raise ValueError("cross-document proposal supplied to owner")
        if proposal.proposal_ref in self._proposals:
            return False
        key = self.proposal_owner_key(proposal)
        self._proposals[proposal.proposal_ref] = proposal
        self._proposal_stage[proposal.proposal_ref] = stage
        self._proposals_by_owner[key][proposal.proposal_ref] = proposal
        self._dirty_groups.add(key)
        return True

    def admit_proposals(
        self,
        proposals: Iterable[FactorProposal],
        *,
        stage: str,
    ) -> StateDelta:
        if stage not in {"base", "composition", "constraint"}:
            raise ValueError("unsupported proposal stage")
        prior = self.revision
        accepted: list[str] = []
        dirty: set[OwnerKey] = set()
        for proposal in proposals:
            if self._index_proposal(proposal, stage=stage):
                accepted.append(proposal.proposal_ref)
                dirty.add(self.proposal_owner_key(proposal))
        return self._advance(
            prior_revision=prior,
            proposals=accepted,
            dirty_owners=(key.owner_ref for key in dirty),
        )

    def admit_solver_receipt(self, receipt: SolverReceipt) -> StateDelta:
        if receipt.owner_key.document_ref != self.document_ref:
            raise ValueError("cross-document solver receipt supplied to owner")
        prior = self.revision
        job = self._in_flight_jobs.pop(receipt.job_ref, None)
        if job is None:
            if (
                receipt.receipt_ref in self._compact_receipt_refs
                or receipt.receipt_ref in self._receipts
            ):
                return self._advance(prior_revision=prior)
            raise ValueError("solver receipt does not match an in-flight job")
        if (
            receipt.input_refs != job.input_refs
            or receipt.rule_set_revision != job.rule_set_revision
        ):
            raise ValueError("solver receipt input contract disagrees with job")
        missing_inputs = set(receipt.input_refs) - self._observation_refs
        if missing_inputs:
            raise ValueError(
                "solver receipt refers to unavailable or superseded inputs"
            )

        signature = canonical_sha256(
            {
                "declaration_ref": job.declaration_ref,
                "input_refs": job.input_refs,
                "rule_set_revision": job.rule_set_revision,
            }
        )
        self._completed_job_signatures.add(signature)
        self._compact_receipt_refs.add(receipt.receipt_ref)
        self._compact_receipts.setdefault(
            receipt.receipt_ref,
            self._compact_receipt_row(receipt),
        )
        if self.retention.full_receipts:
            self._receipts[receipt.receipt_ref] = receipt
        if not self.retention.completed_jobs:
            self._jobs.pop(receipt.job_ref, None)

        accepted: list[str] = []
        dirty: set[OwnerKey] = set()
        for proposal in receipt.proposals:
            if self._index_proposal(proposal, stage="composition"):
                accepted.append(proposal.proposal_ref)
                dirty.add(self.proposal_owner_key(proposal))
        return self._advance(
            prior_revision=prior,
            proposals=accepted,
            introduced_residuals=receipt.residuals,
            dirty_owners=(key.owner_ref for key in dirty),
        )

    def reduce_dirty_groups(self) -> StateDelta:
        prior = self.revision
        changed_factors: set[str] = set()
        introduced: set[str] = set()
        discharged: set[str] = set()
        dirty = tuple(sorted(self._dirty_groups))
        for key in dirty:
            group = tuple(
                self._proposals_by_owner[key][proposal_ref]
                for proposal_ref in sorted(self._proposals_by_owner[key])
            )
            before = self._reductions.get(key)
            reduction = reduce_factor_proposals(
                document_ref=self.document_ref,
                proposals=group,
                known_observation_refs=self._observation_refs,
                known_dependency_refs=self._known_dependency_refs,
            )
            self._reductions[key] = reduction
            before_factors = (
                {row.factor_ref for row in before.factors} if before else set()
            )
            after_factors = {row.factor_ref for row in reduction.factors}
            self._known_dependency_refs.difference_update(
                before_factors - after_factors
            )
            self._known_dependency_refs.update(after_factors)
            changed_factors.update(before_factors.symmetric_difference(after_factors))
            before_residuals = (
                {row.residual_ref for row in before.residuals} if before else set()
            )
            after_residuals = {row.residual_ref for row in reduction.residuals}
            introduced.update(after_residuals - before_residuals)
            discharged.update(before_residuals - after_residuals)
            self._dirty_groups.discard(key)
        return self._advance(
            prior_revision=prior,
            changed_factors=changed_factors,
            introduced_residuals=introduced,
            discharged_residuals=discharged,
        )

    def compact_retained_history(self) -> dict[str, int]:
        """Release diagnostic-only generations without changing semantic state."""

        before = self.retention_counts()
        if not self.retention.completed_jobs:
            active_refs = set(self._pending_jobs) | set(self._in_flight_jobs)
            self._jobs = {
                ref: job for ref, job in self._jobs.items() if ref in active_refs
            }
        if not self.retention.full_receipts:
            self._receipts.clear()
        if not self.retention.state_deltas:
            self._state_deltas.clear()
        self._compaction_count += 1
        after = self.retention_counts()
        return {
            "jobs_released": before["jobs"] - after["jobs"],
            "receipts_released": before["receipts"] - after["receipts"],
            "state_deltas_released": (before["state_deltas"] - after["state_deltas"]),
            "compaction_count": self._compaction_count,
        }

    def retention_counts(self) -> dict[str, int]:
        return {
            "observation_deltas": len(self._observation_deltas),
            "coverage_index_entries": len(self._complete_coverage),
            "proposals": len(self._proposals),
            "proposal_owner_groups": len(self._proposals_by_owner),
            "jobs": len(self._jobs),
            "compact_jobs": len(self._compact_jobs),
            "pending_jobs": len(self._pending_jobs),
            "in_flight_jobs": len(self._in_flight_jobs),
            "receipts": len(self._receipts),
            "compact_receipts": len(self._compact_receipts),
            "compact_receipt_refs": len(self._compact_receipt_refs),
            "state_deltas": len(self._state_deltas),
            "reductions": len(self._reductions),
            "known_dependency_refs": len(self._known_dependency_refs),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        if not self.retention.completed_jobs:
            payload["solver_jobs"] = [
                self._compact_jobs[key] for key in sorted(self._compact_jobs)
            ]
        if not self.retention.full_receipts:
            payload["solver_receipts"] = [
                self._compact_receipts[key] for key in sorted(self._compact_receipts)
            ]
        payload["retention_mode"] = self.retention.mode.value
        payload["retention_counts"] = self.retention_counts()
        payload["compact_execution_evidence"] = True
        return payload

    def compact_summary(self) -> dict[str, Any]:
        reduction = self.materialized_reduction
        certificate = self.fixed_point_certificate()
        return {
            "document_ref": self.document_ref,
            "revision": self.revision,
            "partition_count": self.partition_count,
            "retention_mode": self.retention.mode.value,
            "retention_counts": self.retention_counts(),
            "materialized_reduction_ref": reduction.graph_ref,
            "materialized_factor_count": len(reduction.factors),
            "materialized_residual_count": len(reduction.residuals),
            "fixed_point_certificate": certificate.to_dict(),
            "shared_graph_mutation": False,
            "last_writer_wins": False,
        }


__all__ = ["BoundedStreamingSemanticOwner"]
