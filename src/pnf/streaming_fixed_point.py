"""Streaming, convergent document-local semantic fixed-point execution.

Workers may parse or solve concurrently, but they return immutable deltas and receipts
rather than mutating a shared graph.  A logical owner for each keyed semantic coordinate
admits those deltas, updates affected indexes, and materialises deterministic reduced
views.  Positive candidates may stream before coverage closes; absence, uniqueness,
exhaustion, and closure require explicit coverage barriers and an empty local frontier.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from src.pnf.factor_proposals import (
    FactorProposal,
    ProposalReduction,
    ReducedFactor,
    ReductionResidual,
    reduce_factor_proposals,
)
from src.policy.carriers.canonical import canonical_sha256


STREAMING_DELTA_SCHEMA_VERSION = "sl.pnf.observation_delta.v0_1"
STREAMING_LEDGER_SCHEMA_VERSION = "sl.pnf.convergent_ledger.v0_2"
STREAMING_JOB_SCHEMA_VERSION = "sl.pnf.solver_job.v0_1"
STREAMING_RECEIPT_SCHEMA_VERSION = "sl.pnf.solver_receipt.v0_1"
STREAMING_STATE_DELTA_SCHEMA_VERSION = "sl.pnf.state_delta.v0_2"
STREAMING_FIXED_POINT_SCHEMA_VERSION = "sl.pnf.fixed_point_certificate.v0_1"
STREAMING_BOUNDARY_SCHEMA_VERSION = "sl.pnf.region_boundary_summary.v0_1"

_COVERAGE_BARRIERS = ("token_batch", "sentence", "section", "document")
_COVERAGE_STATES = {"open", "complete"}
_PROPOSAL_STAGES = {"base", "composition", "constraint"}
_FINALISING_CLAIMS = {
    "absence",
    "unique",
    "exhausted",
    "closed",
    "all_alternatives_enumerated",
}


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True, order=True)
class OwnerKey:
    """One logical admission authority for a reducible semantic coordinate."""

    document_ref: str
    scope_ref: str
    factor_family: str

    @property
    def owner_ref(self) -> str:
        return "semantic-owner:" + canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, str]:
        return {
            "document_ref": self.document_ref,
            "scope_ref": self.scope_ref,
            "factor_family": self.factor_family,
        }


def owner_partition(key: OwnerKey, partition_count: int) -> int:
    if partition_count < 1:
        raise ValueError("partition_count must be positive")
    return int(canonical_sha256(key.to_dict())[:16], 16) % partition_count


@dataclass(frozen=True)
class ObservationDelta:
    """One immutable parser/source observation batch in canonical coordinates."""

    document_ref: str
    batch_ref: str
    scope_ref: str
    sequence_no: int
    parser_contract: str
    observation_refs: tuple[str, ...]
    observations: tuple[Mapping[str, Any], ...]
    token_start: int
    token_end: int
    char_start: int
    char_end: int
    token_count: int
    coverage_barrier: str = "sentence"
    coverage_complete: bool = False

    def __post_init__(self) -> None:
        if self.sequence_no < 0:
            raise ValueError("observation sequence_no must be non-negative")
        if not (0 <= self.token_start <= self.token_end):
            raise ValueError("observation token coordinates are invalid")
        if not (0 <= self.char_start <= self.char_end):
            raise ValueError("observation character coordinates are invalid")
        if self.token_count != self.token_end - self.token_start:
            raise ValueError("observation token_count disagrees with token interval")
        if self.coverage_barrier not in _COVERAGE_BARRIERS:
            raise ValueError("unsupported observation coverage barrier")
        if self.observation_refs != _refs(self.observation_refs):
            raise ValueError(
                "observation references must be unique and canonically ordered"
            )

    @property
    def delta_ref(self) -> str:
        return "observation-delta:" + canonical_sha256(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "document_ref": self.document_ref,
            "batch_ref": self.batch_ref,
            "scope_ref": self.scope_ref,
            "sequence_no": self.sequence_no,
            "parser_contract": self.parser_contract,
            "observation_refs": list(self.observation_refs),
            "observations": [dict(row) for row in self.observations],
            "token_start": self.token_start,
            "token_end": self.token_end,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "token_count": self.token_count,
            "coverage_barrier": self.coverage_barrier,
            "coverage_complete": self.coverage_complete,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STREAMING_DELTA_SCHEMA_VERSION,
            "delta_ref": self.delta_ref,
            **self.identity_payload(),
            "authority": "parser_observation_only",
        }


@dataclass(frozen=True)
class CoverageNotice:
    document_ref: str
    scope_ref: str
    barrier: str
    state: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.barrier not in _COVERAGE_BARRIERS:
            raise ValueError("unsupported coverage barrier")
        if self.state not in _COVERAGE_STATES:
            raise ValueError("unsupported coverage state")

    @property
    def notice_ref(self) -> str:
        return "coverage-notice:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_ref": self.document_ref,
            "scope_ref": self.scope_ref,
            "barrier": self.barrier,
            "state": self.state,
            "evidence_refs": list(_refs(self.evidence_refs)),
        }
        if include_ref:
            payload["notice_ref"] = self.notice_ref
        return payload


@dataclass(frozen=True)
class StreamingDeclaration:
    """Dependency-DAG declaration for one monotone proposal-producing operation."""

    declaration_ref: str
    producer_ref: str
    requires: tuple[str, ...]
    optional: tuple[str, ...]
    emits: tuple[str, ...]
    scope_kind: str
    coverage_barrier: str
    affected_index: str
    declaration_revision: str
    priority: int = 100

    def __post_init__(self) -> None:
        if self.coverage_barrier not in _COVERAGE_BARRIERS:
            raise ValueError("unsupported declaration coverage barrier")
        if self.priority < 0:
            raise ValueError("declaration priority must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "declaration_ref": self.declaration_ref,
            "producer_ref": self.producer_ref,
            "requires": list(_refs(self.requires)),
            "optional": list(_refs(self.optional)),
            "emits": list(_refs(self.emits)),
            "scope_kind": self.scope_kind,
            "coverage_barrier": self.coverage_barrier,
            "affected_index": self.affected_index,
            "declaration_revision": self.declaration_revision,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class SolverJob:
    owner_key: OwnerKey
    declaration_ref: str
    input_revision: int
    input_refs: tuple[str, ...]
    input_payload: Mapping[str, Any]
    rule_set_revision: str
    coverage_requirements: tuple[str, ...]
    assumptions: tuple[str, ...] = ()
    priority: int = 100

    @property
    def job_ref(self) -> str:
        return "semantic-job:" + canonical_sha256(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "owner_key": self.owner_key.to_dict(),
            "declaration_ref": self.declaration_ref,
            "input_revision": self.input_revision,
            "input_refs": list(_refs(self.input_refs)),
            "input_payload": dict(self.input_payload),
            "rule_set_revision": self.rule_set_revision,
            "coverage_requirements": list(_refs(self.coverage_requirements)),
            "assumptions": list(_refs(self.assumptions)),
            "priority": self.priority,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STREAMING_JOB_SCHEMA_VERSION,
            "job_ref": self.job_ref,
            **self.identity_payload(),
        }


@dataclass(frozen=True)
class SolverReceipt:
    job_ref: str
    owner_key: OwnerKey
    input_revision: int
    input_refs: tuple[str, ...]
    rule_set_revision: str
    proposals: tuple[FactorProposal, ...]
    residuals: tuple[str, ...]
    assumptions: tuple[str, ...]
    coverage_requirements: tuple[str, ...]
    metrics: Mapping[str, Any] = field(default_factory=dict)
    backend_ref: str = "python-worklist:v0_1"

    @property
    def receipt_ref(self) -> str:
        return "semantic-job-receipt:" + canonical_sha256(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "job_ref": self.job_ref,
            "owner_key": self.owner_key.to_dict(),
            "input_revision": self.input_revision,
            "input_refs": list(_refs(self.input_refs)),
            "rule_set_revision": self.rule_set_revision,
            "proposal_refs": [
                row.proposal_ref
                for row in sorted(self.proposals, key=lambda item: item.proposal_ref)
            ],
            "residuals": list(_refs(self.residuals)),
            "assumptions": list(_refs(self.assumptions)),
            "coverage_requirements": list(_refs(self.coverage_requirements)),
            "metrics": dict(self.metrics),
            "backend_ref": self.backend_ref,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STREAMING_RECEIPT_SCHEMA_VERSION,
            "receipt_ref": self.receipt_ref,
            **self.identity_payload(),
            "proposals": [
                row.to_dict()
                for row in sorted(self.proposals, key=lambda item: item.proposal_ref)
            ],
            "semantic_state_promoted": False,
        }


@dataclass(frozen=True)
class RegionBoundarySummary:
    document_ref: str
    scope_ref: str
    stable_factor_refs: tuple[str, ...]
    unresolved_external_refs: tuple[str, ...]
    possible_cross_scope_hosts: tuple[str, ...]
    definition_scope_obligations: tuple[str, ...]
    coverage_notice_refs: tuple[str, ...]

    @property
    def summary_ref(self) -> str:
        return "region-boundary:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": STREAMING_BOUNDARY_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "scope_ref": self.scope_ref,
            "stable_factor_refs": list(_refs(self.stable_factor_refs)),
            "unresolved_external_refs": list(_refs(self.unresolved_external_refs)),
            "possible_cross_scope_hosts": list(
                _refs(self.possible_cross_scope_hosts)
            ),
            "definition_scope_obligations": list(
                _refs(self.definition_scope_obligations)
            ),
            "coverage_notice_refs": list(_refs(self.coverage_notice_refs)),
        }
        if include_ref:
            payload["summary_ref"] = self.summary_ref
        return payload


@dataclass(frozen=True)
class ConvergentLedger:
    """Order-independent append-only substrate for eventually consistent workers."""

    observation_deltas: tuple[ObservationDelta, ...] = ()
    proposals: tuple[FactorProposal, ...] = ()
    receipts: tuple[SolverReceipt, ...] = ()
    coverage_notices: tuple[CoverageNotice, ...] = ()
    residual_refs: tuple[str, ...] = ()

    def join(self, other: "ConvergentLedger") -> "ConvergentLedger":
        observations = {
            row.delta_ref: row
            for row in (*self.observation_deltas, *other.observation_deltas)
        }
        proposals = {
            row.proposal_ref: row for row in (*self.proposals, *other.proposals)
        }
        receipts = {
            row.receipt_ref: row for row in (*self.receipts, *other.receipts)
        }
        notices = {
            row.notice_ref: row
            for row in (*self.coverage_notices, *other.coverage_notices)
        }
        return ConvergentLedger(
            observation_deltas=tuple(
                observations[key] for key in sorted(observations)
            ),
            proposals=tuple(proposals[key] for key in sorted(proposals)),
            receipts=tuple(receipts[key] for key in sorted(receipts)),
            coverage_notices=tuple(notices[key] for key in sorted(notices)),
            residual_refs=_refs((*self.residual_refs, *other.residual_refs)),
        )

    @property
    def ledger_ref(self) -> str:
        return "semantic-ledger:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": STREAMING_LEDGER_SCHEMA_VERSION,
            "observation_delta_refs": [
                row.delta_ref for row in self.observation_deltas
            ],
            "proposal_refs": [row.proposal_ref for row in self.proposals],
            "receipt_refs": [row.receipt_ref for row in self.receipts],
            "coverage_notice_refs": [
                row.notice_ref for row in self.coverage_notices
            ],
            "residual_refs": list(self.residual_refs),
            "merge_properties": ["associative", "commutative", "idempotent"],
        }
        if include_ref:
            payload["ledger_ref"] = self.ledger_ref
        return payload


@dataclass(frozen=True)
class StateDelta:
    document_ref: str
    prior_revision: int
    resulting_revision: int
    accepted_observation_refs: tuple[str, ...]
    accepted_proposal_refs: tuple[str, ...]
    changed_factor_refs: tuple[str, ...]
    introduced_residual_refs: tuple[str, ...]
    discharged_residual_refs: tuple[str, ...]
    dirty_owner_refs: tuple[str, ...]
    emitted_job_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STREAMING_STATE_DELTA_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "prior_revision": self.prior_revision,
            "resulting_revision": self.resulting_revision,
            "accepted_observation_refs": list(self.accepted_observation_refs),
            "accepted_proposal_refs": list(self.accepted_proposal_refs),
            "changed_factor_refs": list(self.changed_factor_refs),
            "introduced_residual_refs": list(self.introduced_residual_refs),
            "discharged_residual_refs": list(self.discharged_residual_refs),
            "dirty_owner_refs": list(self.dirty_owner_refs),
            "emitted_job_refs": list(self.emitted_job_refs),
        }


@dataclass(frozen=True)
class DocumentFixedPointCertificate:
    document_ref: str
    revision: int
    ledger_ref: str
    materialized_graph_ref: str
    unconsumed_observation_deltas: int
    dirty_reduction_groups: int
    pending_jobs: int
    in_flight_jobs: int
    unresolved_local_boundary_obligations: int
    open_required_coverage_barriers: int
    unresolved_external_residuals: tuple[str, ...]
    resource_limit_reached: bool = False

    @property
    def local_fixed_point_reached(self) -> bool:
        return not any(
            (
                self.unconsumed_observation_deltas,
                self.dirty_reduction_groups,
                self.pending_jobs,
                self.in_flight_jobs,
                self.unresolved_local_boundary_obligations,
                self.open_required_coverage_barriers,
            )
        ) and not self.resource_limit_reached

    @property
    def certificate_ref(self) -> str:
        return "semantic-fixed-point:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": STREAMING_FIXED_POINT_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "revision": self.revision,
            "ledger_ref": self.ledger_ref,
            "materialized_graph_ref": self.materialized_graph_ref,
            "local_fixed_point": (
                "reached" if self.local_fixed_point_reached else "not_reached"
            ),
            "unconsumed_observation_deltas": self.unconsumed_observation_deltas,
            "dirty_reduction_groups": self.dirty_reduction_groups,
            "pending_jobs": self.pending_jobs,
            "in_flight_jobs": self.in_flight_jobs,
            "unresolved_local_boundary_obligations": (
                self.unresolved_local_boundary_obligations
            ),
            "open_required_coverage_barriers": (
                self.open_required_coverage_barriers
            ),
            "unresolved_external_residuals": list(
                _refs(self.unresolved_external_residuals)
            ),
            "resource_limit_reached": self.resource_limit_reached,
            "identity_promoted": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["certificate_ref"] = self.certificate_ref
        return payload


class ClosureExecutor(Protocol):
    backend_ref: str

    def execute(self, job: SolverJob) -> SolverReceipt: ...


class PythonClosureExecutor:
    """Pure revision-bound closure execution over registered handlers."""

    backend_ref = "python-worklist:v0_1"

    def __init__(
        self,
        handlers: Mapping[
            str,
            Callable[[SolverJob], Sequence[FactorProposal]],
        ],
    ):
        self._handlers = dict(handlers)

    def execute(self, job: SolverJob) -> SolverReceipt:
        handler = self._handlers.get(job.declaration_ref)
        if handler is None:
            raise ValueError(
                f"no Python closure handler for {job.declaration_ref}"
            )
        proposals = tuple(
            sorted(handler(job), key=lambda row: row.proposal_ref)
        )
        return SolverReceipt(
            job_ref=job.job_ref,
            owner_key=job.owner_key,
            input_revision=job.input_revision,
            input_refs=job.input_refs,
            rule_set_revision=job.rule_set_revision,
            proposals=proposals,
            residuals=(),
            assumptions=job.assumptions,
            coverage_requirements=job.coverage_requirements,
            metrics={
                "input_ref_count": len(job.input_refs),
                "derived_proposal_count": len(proposals),
            },
            backend_ref=self.backend_ref,
        )


class StreamingSemanticOwner:
    """Logical admission authority and deterministic materialised-view reducer."""

    def __init__(self, *, document_ref: str, partition_count: int = 1):
        if partition_count < 1:
            raise ValueError("partition_count must be positive")
        self.document_ref = document_ref
        self.partition_count = partition_count
        self.revision = 0
        self._observation_deltas: dict[str, ObservationDelta] = {}
        self._observation_refs: set[str] = set()
        self._proposals: dict[str, FactorProposal] = {}
        self._proposal_stage: dict[str, str] = {}
        self._receipts: dict[str, SolverReceipt] = {}
        self._coverage_notices: dict[str, CoverageNotice] = {}
        self._declarations: dict[str, StreamingDeclaration] = {}
        self._jobs: dict[str, SolverJob] = {}
        self._pending_jobs: dict[str, SolverJob] = {}
        self._in_flight_jobs: dict[str, SolverJob] = {}
        self._completed_job_signatures: set[str] = set()
        self._dirty_groups: set[OwnerKey] = set()
        self._reductions: dict[OwnerKey, ProposalReduction] = {}
        self._boundary_obligations: set[str] = set()
        self._state_deltas: list[StateDelta] = []

    @staticmethod
    def proposal_owner_key(proposal: FactorProposal) -> OwnerKey:
        scope_ref = (
            min(proposal.source_span_refs)
            if proposal.source_span_refs
            else "document-global"
        )
        return OwnerKey(
            proposal.document_ref,
            scope_ref,
            proposal.factor_type_ref,
        )

    def register_declarations(
        self, declarations: Iterable[StreamingDeclaration]
    ) -> None:
        for declaration in declarations:
            self._declarations[declaration.declaration_ref] = declaration

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
        observation_refs = _refs(observations)
        proposal_refs = _refs(proposals)
        factor_refs = _refs(changed_factors)
        introduced_refs = _refs(introduced_residuals)
        discharged_refs = _refs(discharged_residuals)
        owner_refs = _refs(dirty_owners)
        job_refs = _refs(jobs)
        changed = any(
            (
                observation_refs,
                proposal_refs,
                factor_refs,
                introduced_refs,
                discharged_refs,
                owner_refs,
                job_refs,
            )
        )
        if changed:
            self.revision += 1
        delta = StateDelta(
            document_ref=self.document_ref,
            prior_revision=prior_revision,
            resulting_revision=self.revision,
            accepted_observation_refs=observation_refs,
            accepted_proposal_refs=proposal_refs,
            changed_factor_refs=factor_refs,
            introduced_residual_refs=introduced_refs,
            discharged_residual_refs=discharged_refs,
            dirty_owner_refs=owner_refs,
            emitted_job_refs=job_refs,
        )
        if changed:
            self._state_deltas.append(delta)
        return delta

    def admit_observation_delta(self, delta: ObservationDelta) -> StateDelta:
        if delta.document_ref != self.document_ref:
            raise ValueError("cross-document observation supplied to owner")
        prior = self.revision
        if delta.delta_ref in self._observation_deltas:
            return self._advance(prior_revision=prior)
        self._observation_deltas[delta.delta_ref] = delta
        new_refs = set(delta.observation_refs) - self._observation_refs
        self._observation_refs.update(new_refs)
        if delta.coverage_complete:
            notice = CoverageNotice(
                document_ref=self.document_ref,
                scope_ref=delta.scope_ref,
                barrier=delta.coverage_barrier,
                state="complete",
                evidence_refs=(delta.delta_ref,),
            )
            self._coverage_notices[notice.notice_ref] = notice
        jobs = self._activate_declarations_for_delta(delta)
        return self._advance(
            prior_revision=prior,
            observations=new_refs,
            jobs=(job.job_ref for job in jobs),
        )

    def admit_coverage_notice(self, notice: CoverageNotice) -> StateDelta:
        if notice.document_ref != self.document_ref:
            raise ValueError("cross-document coverage notice supplied to owner")
        prior = self.revision
        if notice.notice_ref in self._coverage_notices:
            return self._advance(prior_revision=prior)
        self._coverage_notices[notice.notice_ref] = notice
        jobs: list[SolverJob] = []
        for delta in self._observation_deltas.values():
            if delta.scope_ref == notice.scope_ref:
                jobs.extend(self._activate_declarations_for_delta(delta))
        return self._advance(
            prior_revision=prior,
            jobs=(job.job_ref for job in jobs),
        )

    def coverage_complete(self, *, scope_ref: str, barrier: str) -> bool:
        return any(
            row.scope_ref == scope_ref
            and row.barrier == barrier
            and row.state == "complete"
            for row in self._coverage_notices.values()
        )

    def _activate_declarations_for_delta(
        self, delta: ObservationDelta
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
            input_refs = _refs(delta.observation_refs)
            signature = canonical_sha256(
                {
                    "declaration_ref": declaration.declaration_ref,
                    "input_refs": input_refs,
                    "rule_set_revision": declaration.declaration_revision,
                }
            )
            if signature in self._completed_job_signatures:
                continue
            job = SolverJob(
                owner_key=owner_key,
                declaration_ref=declaration.declaration_ref,
                input_revision=self.revision,
                input_refs=input_refs,
                input_payload={"observation_delta": delta.to_dict()},
                rule_set_revision=declaration.declaration_revision,
                coverage_requirements=(declaration.coverage_barrier,),
                priority=declaration.priority,
            )
            self._jobs.setdefault(job.job_ref, job)
            if (
                job.job_ref not in self._pending_jobs
                and job.job_ref not in self._in_flight_jobs
                and not any(
                    receipt.job_ref == job.job_ref
                    for receipt in self._receipts.values()
                )
            ):
                self._pending_jobs[job.job_ref] = job
                emitted.append(job)
        return tuple(emitted)

    def drain_ready_jobs(
        self, *, limit: int | None = None
    ) -> tuple[SolverJob, ...]:
        ordered = sorted(
            self._pending_jobs.values(),
            key=lambda row: (row.priority, row.job_ref),
        )
        if limit is not None:
            ordered = ordered[:limit]
        for job in ordered:
            self._pending_jobs.pop(job.job_ref, None)
            self._in_flight_jobs[job.job_ref] = job
        return tuple(ordered)

    def admit_proposals(
        self,
        proposals: Iterable[FactorProposal],
        *,
        stage: str,
    ) -> StateDelta:
        if stage not in _PROPOSAL_STAGES:
            raise ValueError("unsupported proposal stage")
        prior = self.revision
        accepted: list[str] = []
        dirty: set[OwnerKey] = set()
        for proposal in proposals:
            if proposal.document_ref != self.document_ref:
                raise ValueError("cross-document proposal supplied to owner")
            if proposal.proposal_ref in self._proposals:
                continue
            self._proposals[proposal.proposal_ref] = proposal
            self._proposal_stage[proposal.proposal_ref] = stage
            accepted.append(proposal.proposal_ref)
            dirty.add(self.proposal_owner_key(proposal))
        self._dirty_groups.update(dirty)
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
            if receipt.receipt_ref in self._receipts:
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
        self._receipts[receipt.receipt_ref] = receipt
        signature = canonical_sha256(
            {
                "declaration_ref": job.declaration_ref,
                "input_refs": job.input_refs,
                "rule_set_revision": job.rule_set_revision,
            }
        )
        self._completed_job_signatures.add(signature)

        accepted: list[str] = []
        dirty: set[OwnerKey] = set()
        for proposal in receipt.proposals:
            if proposal.document_ref != self.document_ref:
                raise ValueError("cross-document proposal supplied to owner")
            if proposal.proposal_ref in self._proposals:
                continue
            self._proposals[proposal.proposal_ref] = proposal
            self._proposal_stage[proposal.proposal_ref] = "composition"
            accepted.append(proposal.proposal_ref)
            dirty.add(self.proposal_owner_key(proposal))
        self._dirty_groups.update(dirty)
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
        for key in sorted(self._dirty_groups):
            group = tuple(
                proposal
                for proposal in self._proposals.values()
                if self.proposal_owner_key(proposal) == key
            )
            before = self._reductions.get(key)
            reduction = reduce_factor_proposals(
                document_ref=self.document_ref,
                proposals=group,
                known_observation_refs=self._observation_refs,
                known_dependency_refs={
                    factor.factor_ref
                    for row in self._reductions.values()
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
    def all_jobs(self) -> tuple[SolverJob, ...]:
        return tuple(self._jobs[key] for key in sorted(self._jobs))

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
            proposal_count=len(self._proposals),
            deduplicated_count=0,
        )

    @property
    def ledger(self) -> ConvergentLedger:
        residual_refs = {
            row.residual_ref
            for reduction in self._reductions.values()
            for row in reduction.residuals
        }
        return ConvergentLedger(
            observation_deltas=tuple(
                self._observation_deltas[key]
                for key in sorted(self._observation_deltas)
            ),
            proposals=tuple(
                self._proposals[key] for key in sorted(self._proposals)
            ),
            receipts=tuple(
                self._receipts[key] for key in sorted(self._receipts)
            ),
            coverage_notices=tuple(
                self._coverage_notices[key]
                for key in sorted(self._coverage_notices)
            ),
            residual_refs=_refs(residual_refs),
        )

    def add_boundary_obligations(self, refs: Iterable[str]) -> None:
        self._boundary_obligations.update(_refs(refs))

    def discharge_boundary_obligations(self, refs: Iterable[str]) -> None:
        self._boundary_obligations.difference_update(_refs(refs))

    def region_boundary_summary(self, scope_ref: str) -> RegionBoundarySummary:
        factors = [
            factor
            for key, reduction in self._reductions.items()
            if key.scope_ref == scope_ref
            for factor in reduction.factors
        ]
        residuals = [
            residual
            for key, reduction in self._reductions.items()
            if key.scope_ref == scope_ref
            for residual in reduction.residuals
        ]
        notices = [
            row.notice_ref
            for row in self._coverage_notices.values()
            if row.scope_ref == scope_ref
        ]
        return RegionBoundarySummary(
            document_ref=self.document_ref,
            scope_ref=scope_ref,
            stable_factor_refs=tuple(row.factor_ref for row in factors),
            unresolved_external_refs=tuple(
                row.residual_ref
                for row in residuals
                if row.residual_type == "missing_reduction_input"
            ),
            possible_cross_scope_hosts=tuple(
                row.residual_ref
                for row in residuals
                if row.residual_type == "incompatible_alternatives"
            ),
            definition_scope_obligations=tuple(
                ref for ref in self._boundary_obligations if scope_ref in ref
            ),
            coverage_notice_refs=tuple(notices),
        )

    def fixed_point_certificate(
        self, *, resource_limit_reached: bool = False
    ) -> DocumentFixedPointCertificate:
        required_barriers = {
            (delta.scope_ref, declaration.coverage_barrier)
            for delta in self._observation_deltas.values()
            for declaration in self._declarations.values()
            if not declaration.requires
            or set(declaration.requires).intersection(
                {
                    str(
                        row.get("observation_type")
                        or row.get("type_ref")
                        or ""
                    )
                    for row in delta.observations
                }
            )
        }
        open_barriers = sum(
            not self.coverage_complete(scope_ref=scope_ref, barrier=barrier)
            for scope_ref, barrier in required_barriers
        )
        reduction = self.materialized_reduction
        external = tuple(
            row.residual_ref
            for row in reduction.residuals
            if row.residual_type != "missing_reduction_input"
        )
        return DocumentFixedPointCertificate(
            document_ref=self.document_ref,
            revision=self.revision,
            ledger_ref=self.ledger.ledger_ref,
            materialized_graph_ref=reduction.graph_ref,
            unconsumed_observation_deltas=0,
            dirty_reduction_groups=len(self._dirty_groups),
            pending_jobs=len(self._pending_jobs),
            in_flight_jobs=len(self._in_flight_jobs),
            unresolved_local_boundary_obligations=len(
                self._boundary_obligations
            ),
            open_required_coverage_barriers=open_barriers,
            unresolved_external_residuals=external,
            resource_limit_reached=resource_limit_reached,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_ref": self.document_ref,
            "revision": self.revision,
            "partition_count": self.partition_count,
            "ledger": self.ledger.to_dict(),
            "observation_deltas": [
                row.to_dict() for row in self.ledger.observation_deltas
            ],
            "coverage_notices": [
                row.to_dict() for row in self.ledger.coverage_notices
            ],
            "proposals": [row.to_dict() for row in self.ledger.proposals],
            "solver_jobs": [row.to_dict() for row in self.all_jobs],
            "solver_receipts": [
                row.to_dict() for row in self.ledger.receipts
            ],
            "materialized_reduction": self.materialized_reduction.to_dict(),
            "state_deltas": [row.to_dict() for row in self._state_deltas],
            "pending_job_refs": sorted(self._pending_jobs),
            "in_flight_job_refs": sorted(self._in_flight_jobs),
            "fixed_point_certificate": self.fixed_point_certificate().to_dict(),
            "shared_graph_mutation": False,
            "last_writer_wins": False,
        }


def execute_ready_jobs(
    owner: StreamingSemanticOwner,
    executor: ClosureExecutor,
    *,
    workers: int = 1,
) -> tuple[SolverReceipt, ...]:
    """Execute ready jobs concurrently and stream each receipt to its owner."""

    if workers < 1:
        raise ValueError("workers must be positive")
    jobs = owner.drain_ready_jobs()
    if not jobs:
        return ()
    receipts: list[SolverReceipt] = []
    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="semantic-closure",
    ) as pool:
        futures: dict[Future[SolverReceipt], str] = {
            pool.submit(executor.execute, job): job.job_ref for job in jobs
        }
        for future in as_completed(futures):
            receipt = future.result()
            owner.admit_solver_receipt(receipt)
            owner.reduce_dirty_groups()
            receipts.append(receipt)
    return tuple(sorted(receipts, key=lambda row: row.receipt_ref))


def assert_finalising_claim_allowed(
    *,
    claim: str,
    scope_ref: str,
    barrier: str,
    owner: StreamingSemanticOwner,
) -> None:
    """Reject absence/uniqueness/closure until the declared scope is complete."""

    if claim not in _FINALISING_CLAIMS:
        return
    if not owner.coverage_complete(scope_ref=scope_ref, barrier=barrier):
        raise ValueError(
            f"finalising claim {claim} requires closed {barrier} coverage"
        )
    certificate = owner.fixed_point_certificate()
    if claim in {
        "closed",
        "exhausted",
        "all_alternatives_enumerated",
    } and not certificate.local_fixed_point_reached:
        raise ValueError(
            f"finalising claim {claim} requires a local fixed point"
        )


__all__ = [
    "ClosureExecutor",
    "ConvergentLedger",
    "CoverageNotice",
    "DocumentFixedPointCertificate",
    "ObservationDelta",
    "OwnerKey",
    "PythonClosureExecutor",
    "RegionBoundarySummary",
    "SolverJob",
    "SolverReceipt",
    "StateDelta",
    "StreamingDeclaration",
    "StreamingSemanticOwner",
    "assert_finalising_claim_allowed",
    "execute_ready_jobs",
    "owner_partition",
]
