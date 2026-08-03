"""Fail-fast closure finalisation and deferred materialised-view execution.

The canonical reducers and semantic identities remain unchanged. This module
installs an execution-specialised owner class into the bounded compiler seam so
batch admission does not rebuild the complete document reduction after every
batch, and an exhausted closure frontier must terminate with either a
fixed-point certificate or a finite diagnostic failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from time import monotonic_ns
from typing import Any, Mapping

from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner
from src.pnf.factor_proposals import ProposalReduction, reduce_factor_proposals
from src.pnf.streaming_fixed_point import (
    ConvergentLedger,
    CoverageNotice,
    DocumentFixedPointCertificate,
    OwnerKey,
    RegionBoundarySummary,
)

_INSTALL_MARKER = "_closure_liveness_execution_installed"


class ClosureLifecycleState(StrEnum):
    PRODUCING = "producing"
    DRAINING = "draining"
    REDUCING_FINAL_DIRTY = "reducing_final_dirty"
    CERTIFYING = "certifying"
    COMPLETED = "completed"
    FAILED = "failed"


class ClosureLivenessError(RuntimeError):
    """An exhausted closure frontier cannot make further semantic progress."""

    def __init__(self, diagnostic: Mapping[str, Any]):
        self.diagnostic = dict(diagnostic)
        super().__init__(
            "closure frontier exhausted without a fixed point: "
            + ", ".join(
                f"{key}={value}"
                for key, value in self.diagnostic.get("blocking_counts", {}).items()
                if value
            )
        )


@dataclass
class _DeferredProposalReduction:
    owner: "LivenessBoundedStreamingSemanticOwner"
    generation: int
    _resolved: ProposalReduction | None = None

    def _value(self) -> ProposalReduction:
        if self._resolved is None:
            self._resolved = self.owner._materialize_reduction_now(self.generation)
        return self._resolved

    def __getattr__(self, name: str) -> Any:
        return getattr(self._value(), name)

    def to_dict(self) -> dict[str, Any]:
        return self._value().to_dict()


class LivenessBoundedStreamingSemanticOwner(BoundedStreamingSemanticOwner):
    """Bounded owner with deferred global views and explicit terminal states."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._closure_state = ClosureLifecycleState.PRODUCING
        self._producer_exhausted = False
        self._lifecycle_started_ns = monotonic_ns()
        self._last_transition_ns = self._lifecycle_started_ns
        self._lifecycle_events: list[dict[str, Any]] = []
        self._materialization_generation = 0
        self._deferred_reduction: _DeferredProposalReduction | None = None
        self._materialization_count = 0
        self._materialization_elapsed_ns = 0
        self._ledger_cache: ConvergentLedger | None = None
        self._ledger_cache_revision = -1
        self._certificate_count = 0
        self._certificate_elapsed_ns = 0
        self._reduction_keys_by_scope: dict[str, set[OwnerKey]] = {}
        self._coverage_notice_refs_by_scope: dict[str, set[str]] = {}
        self._transition(ClosureLifecycleState.PRODUCING, reason="owner_created")

    def _transition(self, state: ClosureLifecycleState, *, reason: str) -> None:
        now = monotonic_ns()
        if self._closure_state != state or not self._lifecycle_events:
            self._closure_state = state
            self._last_transition_ns = now
            self._lifecycle_events.append(
                {
                    "state": state.value,
                    "reason": reason,
                    "monotonic_ns": now,
                    "revision": self.revision,
                    "pending_jobs": len(self._pending_jobs),
                    "in_flight_jobs": len(self._in_flight_jobs),
                    "dirty_groups": len(self._dirty_groups),
                }
            )

    def _invalidate_execution_views(self) -> None:
        self._ledger_cache = None
        self._ledger_cache_revision = -1

    def _advance(self, **kwargs: Any):  # type: ignore[override]
        prior_revision = self.revision
        delta = super()._advance(**kwargs)
        if self.revision != prior_revision:
            self._invalidate_execution_views()
        return delta

    def admit_observation_delta(self, delta: Any):  # type: ignore[override]
        self._transition(
            ClosureLifecycleState.PRODUCING, reason="observation_admission"
        )
        result = super().admit_observation_delta(delta)
        if delta.coverage_complete:
            notice = CoverageNotice(
                document_ref=self.document_ref,
                scope_ref=delta.scope_ref,
                barrier=delta.coverage_barrier,
                state="complete",
                evidence_refs=(delta.delta_ref,),
            )
            self._coverage_notice_refs_by_scope.setdefault(delta.scope_ref, set()).add(
                notice.notice_ref
            )
        self._invalidate_execution_views()
        return result

    def admit_solver_receipt(self, receipt: Any):  # type: ignore[override]
        self._transition(ClosureLifecycleState.DRAINING, reason="receipt_admission")
        self._invalidate_execution_views()
        return super().admit_solver_receipt(receipt)

    def reduce_dirty_groups(self):  # type: ignore[override]
        dirty = tuple(self._dirty_groups)
        if dirty and not self._pending_jobs and not self._in_flight_jobs:
            self._transition(
                ClosureLifecycleState.REDUCING_FINAL_DIRTY,
                reason="final_dirty_reduction",
            )
        result = super().reduce_dirty_groups()
        for key in dirty:
            self._reduction_keys_by_scope.setdefault(key.scope_ref, set()).add(key)
        self._materialization_generation += 1
        self._deferred_reduction = None
        self._invalidate_execution_views()
        return result

    def admit_coverage_notice(self, notice: CoverageNotice):  # type: ignore[override]
        result = super().admit_coverage_notice(notice)
        self._coverage_notice_refs_by_scope.setdefault(notice.scope_ref, set()).add(
            notice.notice_ref
        )
        self._invalidate_execution_views()
        if (
            notice.scope_ref == "document-global"
            and notice.barrier == "document"
            and notice.state == "complete"
        ):
            self._producer_exhausted = True
            self._transition(
                ClosureLifecycleState.CERTIFYING,
                reason="document_coverage_complete",
            )
        return result

    @property
    def materialized_reduction(self) -> ProposalReduction:  # type: ignore[override]
        if self._materialized_reduction_cache is not None:
            return self._materialized_reduction_cache
        if (
            self._deferred_reduction is None
            or self._deferred_reduction.generation != self._materialization_generation
        ):
            self._deferred_reduction = _DeferredProposalReduction(
                owner=self,
                generation=self._materialization_generation,
            )
        return self._deferred_reduction  # type: ignore[return-value]

    def _materialize_reduction_now(self, generation: int) -> ProposalReduction:
        if self._materialized_reduction_cache is not None:
            return self._materialized_reduction_cache
        started = monotonic_ns()
        reduction = reduce_factor_proposals(
            document_ref=self.document_ref,
            proposals=tuple(
                self._proposals[proposal_ref]
                for proposal_ref in sorted(self._proposals)
            ),
            known_observation_refs=self._observation_refs,
            known_dependency_refs=self._known_dependency_refs,
        )
        self._materialized_reduction_cache = reduction
        self._materialization_count += 1
        self._materialization_elapsed_ns += monotonic_ns() - started
        return reduction

    @property
    def ledger(self) -> ConvergentLedger:  # type: ignore[override]
        if (
            self._ledger_cache is not None
            and self._ledger_cache_revision == self.revision
        ):
            return self._ledger_cache
        residual_refs = {
            row.residual_ref
            for reduction in self._reductions.values()
            for row in reduction.residuals
        }
        ledger = ConvergentLedger(
            observation_deltas=tuple(
                self._observation_deltas[key]
                for key in sorted(self._observation_deltas)
            ),
            proposals=tuple(self._proposals[key] for key in sorted(self._proposals)),
            receipts=tuple(self._receipts[key] for key in sorted(self._receipts)),
            coverage_notices=tuple(
                self._coverage_notices[key] for key in sorted(self._coverage_notices)
            ),
            residual_refs=tuple(sorted(residual_refs)),
        )
        self._ledger_cache = ledger
        self._ledger_cache_revision = self.revision
        return ledger

    def region_boundary_summary(self, scope_ref: str) -> RegionBoundarySummary:
        reductions = tuple(
            self._reductions[key]
            for key in sorted(self._reduction_keys_by_scope.get(scope_ref, ()))
        )
        factors = [factor for reduction in reductions for factor in reduction.factors]
        residuals = [
            residual for reduction in reductions for residual in reduction.residuals
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
            coverage_notice_refs=tuple(
                sorted(self._coverage_notice_refs_by_scope.get(scope_ref, ()))
            ),
        )

    def terminal_diagnostic(self) -> dict[str, Any]:
        required_barriers = {
            (delta.scope_ref, declaration.coverage_barrier)
            for delta in self._observation_deltas.values()
            for declaration in self._declarations.values()
            if not declaration.requires
            or set(declaration.requires).intersection(
                {
                    str(row.get("observation_type") or row.get("type_ref") or "")
                    for row in delta.observations
                }
            )
        }
        open_barriers = sum(
            not self.coverage_complete(scope_ref=scope_ref, barrier=barrier)
            for scope_ref, barrier in required_barriers
        )
        return {
            "schema_version": "sensiblaw.closure-liveness.v1",
            "document_ref": self.document_ref,
            "state": self._closure_state.value,
            "producer_exhausted": self._producer_exhausted,
            "revision": self.revision,
            "last_transition_ns": self._last_transition_ns,
            "elapsed_ns": monotonic_ns() - self._lifecycle_started_ns,
            "blocking_counts": {
                "pending_jobs": len(self._pending_jobs),
                "in_flight_jobs": len(self._in_flight_jobs),
                "dirty_groups": len(self._dirty_groups),
                "boundary_obligations": len(self._boundary_obligations),
                "open_required_coverage_barriers": open_barriers,
            },
            "retention_counts": self.retention_counts(),
            "materialization_count": self._materialization_count,
            "materialization_elapsed_ns": self._materialization_elapsed_ns,
            "certificate_count": self._certificate_count,
            "certificate_elapsed_ns": self._certificate_elapsed_ns,
            "indexed_scope_count": len(self._reduction_keys_by_scope),
            "events": list(self._lifecycle_events),
        }

    def fixed_point_certificate(
        self, *, resource_limit_reached: bool = False
    ) -> DocumentFixedPointCertificate:  # type: ignore[override]
        started = monotonic_ns()
        certificate = super().fixed_point_certificate(
            resource_limit_reached=resource_limit_reached
        )
        self._certificate_count += 1
        self._certificate_elapsed_ns += monotonic_ns() - started
        if certificate.local_fixed_point_reached:
            if self._producer_exhausted:
                self._transition(
                    ClosureLifecycleState.COMPLETED,
                    reason="fixed_point_certified",
                )
            return certificate
        if (
            self._producer_exhausted
            and not self._pending_jobs
            and not self._in_flight_jobs
            and not self._dirty_groups
        ):
            self._transition(
                ClosureLifecycleState.FAILED,
                reason="exhausted_frontier_without_fixed_point",
            )
            raise ClosureLivenessError(self.terminal_diagnostic())
        return certificate

    def kernel_telemetry(self) -> dict[str, Any]:  # type: ignore[override]
        payload = super().kernel_telemetry()
        payload["closure_lifecycle"] = self.terminal_diagnostic()
        return payload

    def to_dict(self) -> dict[str, Any]:  # type: ignore[override]
        payload = super().to_dict()
        payload["closure_lifecycle"] = self.terminal_diagnostic()
        return payload


def install_closure_liveness_execution() -> bool:
    """Install the hardened owner class into the existing bounded compiler seam."""

    from src.policy import bounded_operational_execution as bounded

    if getattr(bounded, _INSTALL_MARKER, False):
        return False
    bounded.BoundedStreamingSemanticOwner = LivenessBoundedStreamingSemanticOwner
    setattr(bounded, _INSTALL_MARKER, True)
    return True


__all__ = [
    "ClosureLifecycleState",
    "ClosureLivenessError",
    "LivenessBoundedStreamingSemanticOwner",
    "install_closure_liveness_execution",
]
