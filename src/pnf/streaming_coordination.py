"""Coordination policies for convergent streaming semantic owners.

This module adds the non-happy-path mechanics required by concurrent partial solving:
explicit input supersession and proposal retraction, stale-receipt rescheduling, bounded
semantic backpressure, continuous owner/worker streaming, and hierarchical regional
coordination.  Retractions and supersessions are themselves immutable append-only facts;
there is no last-writer-wins graph mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from src.pnf.factor_proposals import (
    ProposalReduction,
    ReducedFactor,
    ReductionResidual,
    reduce_factor_proposals,
)
from src.pnf.streaming_fixed_point import (
    ClosureExecutor,
    DocumentFixedPointCertificate,
    ObservationDelta,
    OwnerKey,
    RegionBoundarySummary,
    SolverJob,
    SolverReceipt,
    StateDelta,
    StreamingSemanticOwner,
    execute_ready_jobs,
)
from src.policy.carriers.canonical import canonical_sha256


STREAMING_COORDINATION_SCHEMA_VERSION = "sl.pnf.streaming_coordination.v0_1"


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class SupersessionNotice:
    document_ref: str
    replacement_pairs: tuple[tuple[str, str], ...]
    reason_ref: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.replacement_pairs:
            raise ValueError("supersession notice requires replacement pairs")
        old_refs = [old for old, _new in self.replacement_pairs]
        if len(old_refs) != len(set(old_refs)):
            raise ValueError("supersession notice repeats an old input ref")
        if any(not old or not new or old == new for old, new in self.replacement_pairs):
            raise ValueError("supersession pairs require distinct non-empty refs")

    @property
    def notice_ref(self) -> str:
        return "semantic-supersession:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_ref": self.document_ref,
            "replacement_pairs": [list(row) for row in sorted(self.replacement_pairs)],
            "reason_ref": self.reason_ref,
            "evidence_refs": list(_refs(self.evidence_refs)),
        }
        if include_ref:
            payload["notice_ref"] = self.notice_ref
        return payload


@dataclass(frozen=True)
class RetractionNotice:
    document_ref: str
    proposal_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    supersession_notice_ref: str
    reason: str = "superseded_input"

    @property
    def notice_ref(self) -> str:
        return "semantic-retraction:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_ref": self.document_ref,
            "proposal_refs": list(_refs(self.proposal_refs)),
            "receipt_refs": list(_refs(self.receipt_refs)),
            "supersession_notice_ref": self.supersession_notice_ref,
            "reason": self.reason,
            "semantic_state_promoted": False,
        }
        if include_ref:
            payload["notice_ref"] = self.notice_ref
        return payload


@dataclass(frozen=True)
class StaleReceiptRecord:
    receipt_ref: str
    job_ref: str
    stale_input_refs: tuple[str, ...]
    replacement_job_ref: str | None
    supersession_notice_refs: tuple[str, ...]

    @property
    def record_ref(self) -> str:
        return "stale-solver-receipt:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "receipt_ref": self.receipt_ref,
            "job_ref": self.job_ref,
            "stale_input_refs": list(_refs(self.stale_input_refs)),
            "replacement_job_ref": self.replacement_job_ref,
            "supersession_notice_refs": list(
                _refs(self.supersession_notice_refs)
            ),
            "proposal_outputs_admitted": False,
        }
        if include_ref:
            payload["record_ref"] = self.record_ref
        return payload


@dataclass(frozen=True)
class BackpressurePolicy:
    max_pending_jobs: int = 128
    max_in_flight_jobs: int = 64
    max_dirty_groups: int = 128
    max_branching_mass: int = 20_000
    max_deferred_deltas: int = 64
    release_batch_size: int = 8

    def __post_init__(self) -> None:
        if min(
            self.max_pending_jobs,
            self.max_in_flight_jobs,
            self.max_dirty_groups,
            self.max_branching_mass,
            self.max_deferred_deltas,
            self.release_batch_size,
        ) < 1:
            raise ValueError("backpressure limits must be positive")

    def to_dict(self) -> dict[str, int]:
        return {
            "max_pending_jobs": self.max_pending_jobs,
            "max_in_flight_jobs": self.max_in_flight_jobs,
            "max_dirty_groups": self.max_dirty_groups,
            "max_branching_mass": self.max_branching_mass,
            "max_deferred_deltas": self.max_deferred_deltas,
            "release_batch_size": self.release_batch_size,
        }


@dataclass(frozen=True)
class BackpressureSnapshot:
    pending_jobs: int
    in_flight_jobs: int
    dirty_groups: int
    branching_mass: int
    deferred_deltas: int
    paused: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pending_jobs": self.pending_jobs,
            "in_flight_jobs": self.in_flight_jobs,
            "dirty_groups": self.dirty_groups,
            "branching_mass": self.branching_mass,
            "deferred_deltas": self.deferred_deltas,
            "paused": self.paused,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class DeltaAdmission:
    delta_ref: str
    state: str
    snapshot: BackpressureSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "delta_ref": self.delta_ref,
            "state": self.state,
            "snapshot": self.snapshot.to_dict(),
        }


class BackpressureCapacityError(RuntimeError):
    """The upstream parser must pause; no semantic delta was discarded."""


class CoordinatedStreamingSemanticOwner(StreamingSemanticOwner):
    """Streaming owner with explicit supersession and bounded admission pressure."""

    def __init__(
        self,
        *,
        document_ref: str,
        partition_count: int = 1,
        backpressure_policy: BackpressurePolicy | None = None,
    ):
        super().__init__(
            document_ref=document_ref,
            partition_count=partition_count,
        )
        self.backpressure_policy = backpressure_policy or BackpressurePolicy()
        self._deferred_deltas: dict[str, ObservationDelta] = {}
        self._supersessions: dict[str, SupersessionNotice] = {}
        self._replacement_by_old_ref: dict[str, str] = {}
        self._retractions: dict[str, RetractionNotice] = {}
        self._retracted_proposal_refs: set[str] = set()
        self._stale_receipts: dict[str, StaleReceiptRecord] = {}
        self._waiting_replacement_jobs: dict[str, SolverJob] = {}
        self._coordination_residual_refs: set[str] = set()
        self._admission_events: list[DeltaAdmission] = []

    @property
    def branching_mass(self) -> int:
        group_counts: dict[OwnerKey, int] = {}
        for proposal in self._proposals.values():
            if proposal.proposal_ref in self._retracted_proposal_refs:
                continue
            key = self.proposal_owner_key(proposal)
            group_counts[key] = group_counts.get(key, 0) + 1
        return sum(count * max(1, count - 1) for count in group_counts.values())

    def backpressure_snapshot(self) -> BackpressureSnapshot:
        policy = self.backpressure_policy
        reasons: list[str] = []
        if len(self._pending_jobs) >= policy.max_pending_jobs:
            reasons.append("pending_jobs")
        if len(self._in_flight_jobs) >= policy.max_in_flight_jobs:
            reasons.append("in_flight_jobs")
        if len(self._dirty_groups) >= policy.max_dirty_groups:
            reasons.append("dirty_groups")
        if self.branching_mass >= policy.max_branching_mass:
            reasons.append("branching_mass")
        return BackpressureSnapshot(
            pending_jobs=len(self._pending_jobs),
            in_flight_jobs=len(self._in_flight_jobs),
            dirty_groups=len(self._dirty_groups),
            branching_mass=self.branching_mass,
            deferred_deltas=len(self._deferred_deltas),
            paused=bool(reasons),
            reasons=tuple(reasons),
        )

    def offer_observation_delta(self, delta: ObservationDelta) -> DeltaAdmission:
        if delta.document_ref != self.document_ref:
            raise ValueError("cross-document observation supplied to owner")
        if delta.delta_ref in self._observation_deltas:
            result = DeltaAdmission(
                delta_ref=delta.delta_ref,
                state="duplicate",
                snapshot=self.backpressure_snapshot(),
            )
            self._admission_events.append(result)
            return result
        snapshot = self.backpressure_snapshot()
        if snapshot.paused:
            if len(self._deferred_deltas) >= self.backpressure_policy.max_deferred_deltas:
                raise BackpressureCapacityError(
                    "semantic owner inbox is full; upstream parser must pause and retry"
                )
            self._deferred_deltas.setdefault(delta.delta_ref, delta)
            result = DeltaAdmission(
                delta_ref=delta.delta_ref,
                state="deferred",
                snapshot=self.backpressure_snapshot(),
            )
            self._admission_events.append(result)
            return result
        self.admit_observation_delta(delta)
        self._activate_waiting_replacement_jobs()
        result = DeltaAdmission(
            delta_ref=delta.delta_ref,
            state="accepted",
            snapshot=self.backpressure_snapshot(),
        )
        self._admission_events.append(result)
        return result

    def release_deferred_deltas(self, *, limit: int | None = None) -> tuple[str, ...]:
        released: list[str] = []
        maximum = limit or self.backpressure_policy.release_batch_size
        for delta_ref in list(sorted(self._deferred_deltas)):
            if len(released) >= maximum or self.backpressure_snapshot().paused:
                break
            delta = self._deferred_deltas.pop(delta_ref)
            self.admit_observation_delta(delta)
            released.append(delta_ref)
        if released:
            self._activate_waiting_replacement_jobs()
        return tuple(released)

    def _active_observation_rows(self) -> dict[str, Mapping[str, Any]]:
        rows: dict[str, Mapping[str, Any]] = {}
        for delta in self._observation_deltas.values():
            for row in delta.observations:
                ref = str(row.get("observation_ref") or "")
                if ref:
                    rows[ref] = row
        return rows

    def _replacement_job(self, job: SolverJob) -> SolverJob | None:
        replacement_refs = tuple(
            sorted(
                {
                    self._replacement_by_old_ref.get(ref, ref)
                    for ref in job.input_refs
                    if self._replacement_by_old_ref.get(ref, ref)
                    not in self._replacement_by_old_ref
                }
            )
        )
        active_rows = self._active_observation_rows()
        if any(ref not in active_rows for ref in replacement_refs):
            return None
        payload = dict(job.input_payload)
        if "observation_delta" in payload:
            prior_delta = dict(payload.get("observation_delta") or {})
            prior_delta["observation_refs"] = list(replacement_refs)
            prior_delta["observations"] = [
                dict(active_rows[ref]) for ref in replacement_refs
            ]
            payload["observation_delta"] = prior_delta
        return SolverJob(
            owner_key=job.owner_key,
            declaration_ref=job.declaration_ref,
            input_revision=self.revision,
            input_refs=replacement_refs,
            input_payload=payload,
            rule_set_revision=job.rule_set_revision,
            coverage_requirements=job.coverage_requirements,
            assumptions=tuple(
                sorted(set(job.assumptions) | {"rescheduled_after_supersession"})
            ),
            priority=job.priority,
        )

    def _schedule_replacement_job(self, job: SolverJob) -> str | None:
        replacement = self._replacement_job(job)
        if replacement is None:
            self._waiting_replacement_jobs[job.job_ref] = job
            residual_ref = "coordination-residual:" + canonical_sha256(
                {
                    "kind": "replacement_input_not_admitted",
                    "job_ref": job.job_ref,
                }
            )
            self._coordination_residual_refs.add(residual_ref)
            return None
        self._jobs.setdefault(replacement.job_ref, replacement)
        self._pending_jobs.setdefault(replacement.job_ref, replacement)
        self._waiting_replacement_jobs.pop(job.job_ref, None)
        return replacement.job_ref

    def _activate_waiting_replacement_jobs(self) -> None:
        for job in tuple(self._waiting_replacement_jobs.values()):
            self._schedule_replacement_job(job)

    def admit_supersession_notice(self, notice: SupersessionNotice) -> StateDelta:
        if notice.document_ref != self.document_ref:
            raise ValueError("cross-document supersession supplied to owner")
        prior = self.revision
        if notice.notice_ref in self._supersessions:
            return self._advance(prior_revision=prior)
        self._supersessions[notice.notice_ref] = notice
        for old_ref, new_ref in notice.replacement_pairs:
            self._replacement_by_old_ref[old_ref] = new_ref
        superseded = set(self._replacement_by_old_ref)
        proposal_refs = tuple(
            sorted(
                proposal.proposal_ref
                for proposal in self._proposals.values()
                if set(proposal.input_observation_refs) & superseded
            )
        )
        receipt_refs = tuple(
            sorted(
                receipt.receipt_ref
                for receipt in self._receipts.values()
                if set(receipt.input_refs) & superseded
            )
        )
        retraction = RetractionNotice(
            document_ref=self.document_ref,
            proposal_refs=proposal_refs,
            receipt_refs=receipt_refs,
            supersession_notice_ref=notice.notice_ref,
        )
        self._retractions[retraction.notice_ref] = retraction
        self._retracted_proposal_refs.update(proposal_refs)
        dirty = {
            self.proposal_owner_key(self._proposals[ref])
            for ref in proposal_refs
            if ref in self._proposals
        }
        self._dirty_groups.update(dirty)
        replacement_jobs = {
            ref
            for job in self.all_jobs
            if set(job.input_refs) & superseded
            for ref in (self._schedule_replacement_job(job),)
            if ref is not None
        }
        return self._advance(
            prior_revision=prior,
            introduced_residuals=(retraction.notice_ref,),
            dirty_owners=(key.owner_ref for key in dirty),
            jobs=replacement_jobs,
        )

    def admit_solver_receipt(self, receipt: SolverReceipt) -> StateDelta:
        stale_refs = tuple(
            sorted(set(receipt.input_refs) & set(self._replacement_by_old_ref))
        )
        if not stale_refs:
            return super().admit_solver_receipt(receipt)
        prior = self.revision
        job = self._in_flight_jobs.pop(receipt.job_ref, None)
        if job is None:
            if receipt.receipt_ref in self._stale_receipts:
                return self._advance(prior_revision=prior)
            raise ValueError("stale receipt does not match an in-flight job")
        replacement_job_ref = self._schedule_replacement_job(job)
        notice_refs = tuple(
            sorted(
                notice.notice_ref
                for notice in self._supersessions.values()
                if set(old for old, _new in notice.replacement_pairs)
                & set(stale_refs)
            )
        )
        record = StaleReceiptRecord(
            receipt_ref=receipt.receipt_ref,
            job_ref=receipt.job_ref,
            stale_input_refs=stale_refs,
            replacement_job_ref=replacement_job_ref,
            supersession_notice_refs=notice_refs,
        )
        self._stale_receipts[record.record_ref] = record
        return self._advance(
            prior_revision=prior,
            introduced_residuals=(record.record_ref,),
            jobs=(replacement_job_ref,) if replacement_job_ref else (),
        )

    def reduce_dirty_groups(self) -> StateDelta:
        prior = self.revision
        changed_factors: set[str] = set()
        introduced: set[str] = set()
        discharged: set[str] = set()
        for key in sorted(self._dirty_groups):
            group = tuple(
                proposal
                for proposal in self._proposals.values()
                if self.proposal_owner_key(proposal) == key
                and proposal.proposal_ref not in self._retracted_proposal_refs
            )
            before = self._reductions.get(key)
            reduction = reduce_factor_proposals(
                document_ref=self.document_ref,
                proposals=group,
                known_observation_refs={
                    ref
                    for ref in self._observation_refs
                    if ref not in self._replacement_by_old_ref
                },
                known_dependency_refs={
                    factor.factor_ref
                    for owner_key, row in self._reductions.items()
                    if owner_key != key
                    for factor in row.factors
                },
            )
            self._reductions[key] = reduction
            before_factors = (
                {row.factor_ref for row in before.factors} if before else set()
            )
            after_factors = {row.factor_ref for row in reduction.factors}
            changed_factors.update(before_factors.symmetric_difference(after_factors))
            before_residuals = (
                {row.residual_ref for row in before.residuals}
                if before
                else set()
            )
            after_residuals = {row.residual_ref for row in reduction.residuals}
            introduced.update(after_residuals - before_residuals)
            discharged.update(before_residuals - after_residuals)
        self._dirty_groups.clear()
        return self._advance(
            prior_revision=prior,
            changed_factors=changed_factors,
            introduced_residuals=introduced,
            discharged_residuals=discharged,
        )

    @property
    def materialized_reduction(self) -> ProposalReduction:
        factors: dict[str, ReducedFactor] = {}
        residuals: dict[str, ReductionResidual] = {}
        for reduction in self._reductions.values():
            factors.update({row.factor_ref: row for row in reduction.factors})
            residuals.update({row.residual_ref: row for row in reduction.residuals})
        return ProposalReduction(
            document_ref=self.document_ref,
            factors=tuple(factors[key] for key in sorted(factors)),
            residuals=tuple(residuals[key] for key in sorted(residuals)),
            proposal_count=len(self._proposals) - len(self._retracted_proposal_refs),
            deduplicated_count=0,
        )

    def fixed_point_certificate(
        self,
        *,
        resource_limit_reached: bool = False,
    ) -> DocumentFixedPointCertificate:
        base = super().fixed_point_certificate(
            resource_limit_reached=resource_limit_reached
        )
        return DocumentFixedPointCertificate(
            document_ref=base.document_ref,
            revision=base.revision,
            ledger_ref=base.ledger_ref,
            materialized_graph_ref=self.materialized_reduction.graph_ref,
            unconsumed_observation_deltas=len(self._deferred_deltas),
            dirty_reduction_groups=base.dirty_reduction_groups,
            pending_jobs=base.pending_jobs + len(self._waiting_replacement_jobs),
            in_flight_jobs=base.in_flight_jobs,
            unresolved_local_boundary_obligations=(
                base.unresolved_local_boundary_obligations
            ),
            open_required_coverage_barriers=base.open_required_coverage_barriers,
            unresolved_external_residuals=tuple(
                sorted(
                    set(base.unresolved_external_residuals)
                    | self._coordination_residual_refs
                )
            ),
            resource_limit_reached=resource_limit_reached,
        )

    def coordination_to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STREAMING_COORDINATION_SCHEMA_VERSION,
            "backpressure_policy": self.backpressure_policy.to_dict(),
            "backpressure": self.backpressure_snapshot().to_dict(),
            "admission_events": [row.to_dict() for row in self._admission_events],
            "supersession_notices": [
                self._supersessions[key].to_dict()
                for key in sorted(self._supersessions)
            ],
            "retraction_notices": [
                self._retractions[key].to_dict()
                for key in sorted(self._retractions)
            ],
            "stale_receipts": [
                self._stale_receipts[key].to_dict()
                for key in sorted(self._stale_receipts)
            ],
            "retracted_proposal_refs": sorted(self._retracted_proposal_refs),
            "waiting_replacement_job_refs": sorted(
                self._waiting_replacement_jobs
            ),
            "coordination_residual_refs": sorted(
                self._coordination_residual_refs
            ),
            "last_writer_wins": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "materialized_reduction": self.materialized_reduction.to_dict(),
            "fixed_point_certificate": self.fixed_point_certificate().to_dict(),
            "coordination": self.coordination_to_dict(),
        }


def run_continuous_owner_stream(
    *,
    owner: CoordinatedStreamingSemanticOwner,
    deltas: Sequence[ObservationDelta],
    executor: ClosureExecutor,
    workers: int,
) -> tuple[SolverReceipt, ...]:
    """Interleave parser admission, closure execution, reduction, and backpressure."""

    receipts: list[SolverReceipt] = []
    for delta in deltas:
        admission = owner.offer_observation_delta(delta)
        if admission.state == "deferred" or owner.backpressure_snapshot().paused:
            receipts.extend(execute_ready_jobs(owner, executor, workers=workers))
            owner.reduce_dirty_groups()
            owner.release_deferred_deltas()
    while True:
        prior = (
            len(owner._pending_jobs),
            len(owner._in_flight_jobs),
            len(owner._deferred_deltas),
            len(owner._dirty_groups),
        )
        receipts.extend(execute_ready_jobs(owner, executor, workers=workers))
        owner.reduce_dirty_groups()
        owner.release_deferred_deltas()
        current = (
            len(owner._pending_jobs),
            len(owner._in_flight_jobs),
            len(owner._deferred_deltas),
            len(owner._dirty_groups),
        )
        if current == (0, 0, 0, 0):
            break
        if current == prior:
            break
    return tuple(sorted({row.receipt_ref: row for row in receipts}.values(), key=lambda row: row.receipt_ref))


@dataclass
class HierarchicalDocumentCoordinator:
    """Reduce regional fixed points to a document boundary fixed point."""

    document_ref: str
    region_summaries: dict[str, RegionBoundarySummary] = field(default_factory=dict)
    region_certificates: dict[str, DocumentFixedPointCertificate] = field(
        default_factory=dict
    )
    boundary_routes: dict[str, str] = field(default_factory=dict)
    discharged_boundary_refs: set[str] = field(default_factory=set)

    def register_region(
        self,
        *,
        summary: RegionBoundarySummary,
        certificate: DocumentFixedPointCertificate,
    ) -> None:
        if summary.document_ref != self.document_ref:
            raise ValueError("cross-document region summary")
        if certificate.document_ref != self.document_ref:
            raise ValueError("cross-document region certificate")
        self.region_summaries[summary.scope_ref] = summary
        self.region_certificates[summary.scope_ref] = certificate

    def route_boundary_obligation(
        self,
        *,
        obligation_ref: str,
        target_scope_ref: str,
    ) -> None:
        if target_scope_ref not in self.region_summaries:
            raise ValueError("boundary obligation target scope is unknown")
        self.boundary_routes[obligation_ref] = target_scope_ref

    def discharge_boundary_obligation(self, obligation_ref: str) -> None:
        if obligation_ref not in self.boundary_routes:
            raise ValueError("cannot discharge an unrouted boundary obligation")
        self.discharged_boundary_refs.add(obligation_ref)

    @property
    def unresolved_boundary_refs(self) -> tuple[str, ...]:
        return tuple(
            sorted(set(self.boundary_routes) - self.discharged_boundary_refs)
        )

    @property
    def local_fixed_point_reached(self) -> bool:
        return bool(self.region_summaries) and all(
            certificate.local_fixed_point_reached
            for certificate in self.region_certificates.values()
        ) and not self.unresolved_boundary_refs

    @property
    def coordinator_ref(self) -> str:
        return "document-region-coordinator:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_ref": self.document_ref,
            "region_summaries": [
                self.region_summaries[key].to_dict()
                for key in sorted(self.region_summaries)
            ],
            "region_certificate_refs": {
                key: self.region_certificates[key].certificate_ref
                for key in sorted(self.region_certificates)
            },
            "boundary_routes": {
                key: self.boundary_routes[key]
                for key in sorted(self.boundary_routes)
            },
            "discharged_boundary_refs": sorted(
                self.discharged_boundary_refs
            ),
            "unresolved_boundary_refs": list(self.unresolved_boundary_refs),
            "local_fixed_point": (
                "reached" if self.local_fixed_point_reached else "not_reached"
            ),
            "identity_promoted": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["coordinator_ref"] = self.coordinator_ref
        return payload


__all__ = [
    "BackpressureCapacityError",
    "BackpressurePolicy",
    "BackpressureSnapshot",
    "CoordinatedStreamingSemanticOwner",
    "DeltaAdmission",
    "HierarchicalDocumentCoordinator",
    "RetractionNotice",
    "StaleReceiptRecord",
    "SupersessionNotice",
    "run_continuous_owner_stream",
]
