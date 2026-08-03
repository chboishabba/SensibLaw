"""Observable, resumable and fail-fast closure finalisation.

The semantic owner remains authoritative.  This module changes only the physical
finalisation path: settled keyed reductions are assembled once, in bounded
batches, rather than reducing the complete proposal population again.  Durable
phase manifests make the terminal path observable and allow completed
materialisation/certification work to be reused after replay reconstructs the
same owner state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from math import comb
import os
from pathlib import Path
from time import monotonic_ns, time_ns
from typing import Any, Iterable, Mapping

from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner
from src.pnf.factor_proposals import (
    ProposalReduction,
    ReducedFactor,
    ReductionResidual,
)
from src.pnf.streaming_fixed_point import (
    ConvergentLedger,
    CoverageNotice,
    DocumentFixedPointCertificate,
    OwnerKey,
    RegionBoundarySummary,
)
from src.policy.carriers.canonical import canonical_sha256

_INSTALL_MARKER = "_closure_liveness_execution_installed"
_FINALIZATION_SCHEMA = "sensiblaw.closure-finalization.v2"
_DEFAULT_BATCH_SIZE = 4096
_DEFAULT_STALL_SECONDS = 900


class ClosureLifecycleState(StrEnum):
    PRODUCING = "producing"
    DRAINING = "draining"
    REDUCING_FINAL_DIRTY = "reducing_final_dirty"
    CERTIFYING = "certifying"
    COMPLETED = "completed"
    FAILED = "failed"


class FinalizationPhase(StrEnum):
    MATERIALIZE_FACTOR_REDUCTIONS = "materialize_factor_reductions"
    MATERIALIZE_RESIDUALS = "materialize_residuals"
    ASSEMBLE_REDUCTION = "assemble_reduction"
    BUILD_CONVERGENT_LEDGER = "build_convergent_ledger"
    BUILD_REGION_BOUNDARY_SUMMARIES = "build_region_boundary_summaries"
    VALIDATE_COVERAGE = "validate_coverage"
    VALIDATE_UNRESOLVED_OBLIGATIONS = "validate_unresolved_obligations"
    BUILD_FIXED_POINT_CERTIFICATE = "build_fixed_point_certificate"
    SERIALIZE_CLOSURE_RECEIPT = "serialize_closure_receipt"
    RELEASE_OWNER_STATE = "release_owner_state"


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


class FinalizationStallError(RuntimeError):
    """Finalisation made no observable bounded-batch progress."""

    def __init__(self, diagnostic: Mapping[str, Any]):
        self.diagnostic = dict(diagnostic)
        super().__init__(
            "closure finalisation exceeded its no-progress interval in phase "
            f"{self.diagnostic.get('phase')}"
        )


def _integer_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _safe_ref(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_." else "_"
        for character in value
    )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(dict(payload), indent=2, sort_keys=True) + "\n"
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)
    return len(encoded.encode("utf-8"))


def _process_memory() -> dict[str, int]:
    values = {"rss_bytes": 0, "pss_bytes": 0, "uss_bytes": 0}
    try:
        rows = Path("/proc/self/smaps_rollup").read_text(encoding="ascii").splitlines()
    except OSError:
        return values
    private_bytes = 0
    for row in rows:
        if not row or ":" not in row:
            continue
        key, raw = row.split(":", 1)
        fields = raw.strip().split()
        if not fields:
            continue
        try:
            amount = int(fields[0]) * 1024
        except ValueError:
            continue
        if key == "Rss":
            values["rss_bytes"] = amount
        elif key == "Pss":
            values["pss_bytes"] = amount
        elif key in {"Private_Clean", "Private_Dirty"}:
            private_bytes += amount
    values["uss_bytes"] = private_bytes
    return values


def _reduced_factor_from_dict(row: Mapping[str, Any]) -> ReducedFactor:
    return ReducedFactor(
        factor_ref=str(row["factor_ref"]),
        document_ref=str(row["document_ref"]),
        semantic_coordinate_ref=str(row["semantic_coordinate_ref"]),
        fibre_kind=str(row["fibre_kind"]),
        factor_type_ref=str(row["factor_type_ref"]),
        structural_signature=str(row["structural_signature"]),
        proposal_refs=tuple(row.get("proposal_refs") or ()),
        alternatives=tuple(row.get("alternatives") or ()),
        role_bindings=dict(row.get("role_bindings") or {}),
        qualifier_state=dict(row.get("qualifier_state") or {}),
        residuals=tuple(row.get("residuals") or ()),
        derivation_roles=tuple(row.get("derivation_roles") or ()),
        ontology_axis_refs=tuple(row.get("ontology_axis_refs") or ()),
        transport_refs=tuple(row.get("transport_refs") or ()),
        support_states=tuple(row.get("support_states") or ()),
    )


def _residual_from_dict(row: Mapping[str, Any]) -> ReductionResidual:
    return ReductionResidual(
        residual_ref=str(row["residual_ref"]),
        document_ref=str(row["document_ref"]),
        residual_type=str(row["residual_type"]),
        proposal_refs=tuple(row.get("proposal_refs") or ()),
        message=str(row["message"]),
        semantic_coordinate_ref=(
            str(row["semantic_coordinate_ref"])
            if row.get("semantic_coordinate_ref") is not None
            else None
        ),
        boundary_kind=str(row.get("boundary_kind") or "fibre"),
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
    """Bounded owner with indexed, checkpointed terminal materialisation."""

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
        self._certificate_cache: DocumentFixedPointCertificate | None = None
        self._certificate_cache_revision = -1
        self._certificate_count = 0
        self._certificate_elapsed_ns = 0
        self._reduction_keys_by_scope: dict[str, set[OwnerKey]] = {}
        self._coverage_notice_refs_by_scope: dict[str, set[str]] = {}
        self._boundary_summary_cache: dict[str, RegionBoundarySummary] = {}
        self._serialized_payload_cache: dict[str, Any] | None = None
        self._finalization_events: list[dict[str, Any]] = []
        self._finalization_phase: FinalizationPhase | None = None
        self._phase_started_ns = 0
        self._last_progress_ns = monotonic_ns()
        self._finalization_batch_size = _integer_env(
            "SENSIBLAW_FINALIZATION_BATCH_SIZE", _DEFAULT_BATCH_SIZE
        )
        self._finalization_stall_ns = (
            _integer_env("SENSIBLAW_FINALIZATION_STALL_SECONDS", _DEFAULT_STALL_SECONDS)
            * 1_000_000_000
        )
        root = os.environ.get("SENSIBLAW_RESOURCE_CHECKPOINT_DIR")
        self._finalization_root = (
            Path(root) / "closure-finalization" / _safe_ref(self.document_ref)
            if root
            else None
        )
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
        self._certificate_cache = None
        self._certificate_cache_revision = -1
        self._serialized_payload_cache = None
        self._boundary_summary_cache.clear()

    def _owner_fingerprint(self) -> dict[str, Any]:
        reduction_keys = [key.to_dict() for key in sorted(self._reductions)]
        return {
            "schema_version": _FINALIZATION_SCHEMA,
            "document_ref": self.document_ref,
            "revision": self.revision,
            "proposal_count": len(self._proposals),
            "proposal_manifest_ref": canonical_sha256(sorted(self._proposals)),
            "reduction_key_manifest_ref": canonical_sha256(reduction_keys),
            "boundary_obligation_manifest_ref": canonical_sha256(
                sorted(self._boundary_obligations)
            ),
            "coverage_manifest_ref": canonical_sha256(sorted(self._coverage_notices)),
        }

    def _checkpoint_path(self, name: str) -> Path | None:
        if self._finalization_root is None:
            return None
        return self._finalization_root / name

    def _begin_phase(self, phase: FinalizationPhase, *, total: int) -> None:
        self._finalization_phase = phase
        self._phase_started_ns = monotonic_ns()
        self._last_progress_ns = self._phase_started_ns
        self._emit_progress(processed=0, total=total, completed=False)

    def _emit_progress(
        self,
        *,
        processed: int,
        total: int,
        completed: bool,
        rows_scanned: int | None = None,
        bytes_written: int = 0,
        reused_checkpoint: bool = False,
    ) -> None:
        now = monotonic_ns()
        if not completed and now - self._last_progress_ns > self._finalization_stall_ns:
            diagnostic = {
                "schema_version": _FINALIZATION_SCHEMA,
                "document_ref": self.document_ref,
                "phase": self._finalization_phase.value
                if self._finalization_phase
                else None,
                "processed": processed,
                "total": total,
                "no_progress_ns": now - self._last_progress_ns,
                "memory": _process_memory(),
                "owner_fingerprint": self._owner_fingerprint(),
            }
            self._transition(ClosureLifecycleState.FAILED, reason="finalization_stall")
            path = self._checkpoint_path("finalization-stall.json")
            if path is not None:
                _atomic_json(path, diagnostic)
            raise FinalizationStallError(diagnostic)
        self._last_progress_ns = now
        event = {
            "schema_version": _FINALIZATION_SCHEMA,
            "phase": self._finalization_phase.value
            if self._finalization_phase
            else None,
            "processed": processed,
            "total": total,
            "rows_scanned": processed if rows_scanned is None else rows_scanned,
            "elapsed_ns": now - self._phase_started_ns,
            "completed": completed,
            "bytes_written": bytes_written,
            "reused_checkpoint": reused_checkpoint,
            "wall_time_ns": time_ns(),
            **_process_memory(),
        }
        self._finalization_events.append(event)
        path = self._checkpoint_path("finalization-progress.json")
        if path is not None:
            _atomic_json(
                path,
                {
                    "owner_fingerprint": self._owner_fingerprint(),
                    "latest": event,
                    "events": self._finalization_events,
                },
            )

    def _iter_batches(self, rows: Iterable[Any]) -> Iterable[tuple[Any, ...]]:
        batch: list[Any] = []
        for row in rows:
            batch.append(row)
            if len(batch) >= self._finalization_batch_size:
                yield tuple(batch)
                batch.clear()
        if batch:
            yield tuple(batch)

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

    def _load_reduction_checkpoint(self) -> ProposalReduction | None:
        path = self._checkpoint_path("materialized-reduction.json")
        if path is None or not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if payload.get("owner_fingerprint") != self._owner_fingerprint():
            return None
        reduction = payload.get("reduction") or {}
        return ProposalReduction(
            document_ref=str(reduction["document_ref"]),
            factors=tuple(
                _reduced_factor_from_dict(row) for row in reduction.get("factors") or ()
            ),
            residuals=tuple(
                _residual_from_dict(row) for row in reduction.get("residuals") or ()
            ),
            proposal_count=int(reduction.get("proposal_count") or 0),
            deduplicated_count=int(reduction.get("deduplicated_count") or 0),
            metrics=dict(reduction.get("metrics") or {}),
        )

    def _materialize_reduction_now(self, generation: int) -> ProposalReduction:
        del generation
        if self._materialized_reduction_cache is not None:
            return self._materialized_reduction_cache
        started = monotonic_ns()
        checkpoint = self._load_reduction_checkpoint()
        if checkpoint is not None:
            self._materialized_reduction_cache = checkpoint
            self._materialization_count += 1
            self._materialization_elapsed_ns += monotonic_ns() - started
            self._begin_phase(
                FinalizationPhase.ASSEMBLE_REDUCTION,
                total=len(checkpoint.factors) + len(checkpoint.residuals),
            )
            self._emit_progress(
                processed=len(checkpoint.factors) + len(checkpoint.residuals),
                total=len(checkpoint.factors) + len(checkpoint.residuals),
                completed=True,
                reused_checkpoint=True,
            )
            return checkpoint

        reduction_rows = tuple(
            self._reductions[key] for key in sorted(self._reductions)
        )
        factor_by_ref: dict[str, ReducedFactor] = {}
        residual_by_ref: dict[str, ReductionResidual] = {}

        factor_total = sum(len(row.factors) for row in reduction_rows)
        self._begin_phase(
            FinalizationPhase.MATERIALIZE_FACTOR_REDUCTIONS, total=factor_total
        )
        processed = 0
        for batch in self._iter_batches(
            factor for reduction in reduction_rows for factor in reduction.factors
        ):
            for factor in batch:
                factor_by_ref[factor.factor_ref] = factor
            processed += len(batch)
            self._emit_progress(
                processed=processed, total=factor_total, completed=False
            )
        self._emit_progress(processed=processed, total=factor_total, completed=True)

        residual_total = sum(len(row.residuals) for row in reduction_rows)
        self._begin_phase(FinalizationPhase.MATERIALIZE_RESIDUALS, total=residual_total)
        processed = 0
        for batch in self._iter_batches(
            residual for reduction in reduction_rows for residual in reduction.residuals
        ):
            for residual in batch:
                residual_by_ref[residual.residual_ref] = residual
            processed += len(batch)
            self._emit_progress(
                processed=processed, total=residual_total, completed=False
            )
        self._emit_progress(processed=processed, total=residual_total, completed=True)

        total = len(factor_by_ref) + len(residual_by_ref)
        self._begin_phase(FinalizationPhase.ASSEMBLE_REDUCTION, total=total)
        alternatives_retained = sum(
            int(row.metrics.get("alternatives_retained") or 0) for row in reduction_rows
        )
        candidate_comparisons = sum(
            int(row.metrics.get("candidate_comparisons") or 0) for row in reduction_rows
        )
        potential_candidate_comparisons = (
            comb(alternatives_retained, 2) if alternatives_retained > 1 else 0
        )
        comparisons_avoided = max(
            0, potential_candidate_comparisons - candidate_comparisons
        )
        reduction = ProposalReduction(
            document_ref=self.document_ref,
            factors=tuple(factor_by_ref[key] for key in sorted(factor_by_ref)),
            residuals=tuple(residual_by_ref[key] for key in sorted(residual_by_ref)),
            proposal_count=len(self._proposals),
            deduplicated_count=sum(row.deduplicated_count for row in reduction_rows),
            metrics={
                "bucket_count": sum(
                    int(row.metrics.get("bucket_count") or 0) for row in reduction_rows
                ),
                "largest_bucket": max(
                    (
                        int(row.metrics.get("largest_bucket") or 0)
                        for row in reduction_rows
                    ),
                    default=0,
                ),
                "candidate_comparisons": candidate_comparisons,
                "potential_candidate_comparisons": potential_candidate_comparisons,
                "comparisons_avoided": comparisons_avoided,
                "comparison_avoidance_ratio": (
                    comparisons_avoided / potential_candidate_comparisons
                    if potential_candidate_comparisons
                    else 1.0
                ),
                "duplicates_collapsed": sum(
                    int(row.metrics.get("duplicates_collapsed") or 0)
                    for row in reduction_rows
                ),
                "alternatives_retained": alternatives_retained,
                "factor_count": len(factor_by_ref),
                "reduction_ratio": (
                    len(factor_by_ref) / alternatives_retained
                    if alternatives_retained
                    else 0.0
                ),
            },
        )
        bytes_written = 0
        path = self._checkpoint_path("materialized-reduction.json")
        if path is not None:
            bytes_written = _atomic_json(
                path,
                {
                    "owner_fingerprint": self._owner_fingerprint(),
                    "reduction": reduction.to_dict(),
                },
            )
        self._materialized_reduction_cache = reduction
        self._materialization_count += 1
        self._materialization_elapsed_ns += monotonic_ns() - started
        self._emit_progress(
            processed=total,
            total=total,
            completed=True,
            bytes_written=bytes_written,
        )
        return reduction

    @property
    def ledger(self) -> ConvergentLedger:  # type: ignore[override]
        if (
            self._ledger_cache is not None
            and self._ledger_cache_revision == self.revision
        ):
            return self._ledger_cache
        total = (
            len(self._observation_deltas)
            + len(self._proposals)
            + len(self._receipts)
            + len(self._coverage_notices)
        )
        self._begin_phase(FinalizationPhase.BUILD_CONVERGENT_LEDGER, total=total)
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
        bytes_written = 0
        path = self._checkpoint_path("convergent-ledger.json")
        if path is not None:
            bytes_written = _atomic_json(
                path,
                {
                    "owner_fingerprint": self._owner_fingerprint(),
                    "ledger": ledger.to_dict(),
                },
            )
        self._ledger_cache = ledger
        self._ledger_cache_revision = self.revision
        self._emit_progress(
            processed=total,
            total=total,
            completed=True,
            bytes_written=bytes_written,
        )
        return ledger

    def _build_boundary_summaries(self) -> None:
        if self._boundary_summary_cache:
            return
        scopes = sorted(
            set(self._reduction_keys_by_scope)
            | set(self._coverage_notice_refs_by_scope)
        )
        self._begin_phase(
            FinalizationPhase.BUILD_REGION_BOUNDARY_SUMMARIES, total=len(scopes)
        )
        processed = 0
        for batch in self._iter_batches(scopes):
            for scope_ref in batch:
                reductions = tuple(
                    self._reductions[key]
                    for key in sorted(self._reduction_keys_by_scope.get(scope_ref, ()))
                )
                factors = (
                    factor for reduction in reductions for factor in reduction.factors
                )
                residuals = tuple(
                    residual
                    for reduction in reductions
                    for residual in reduction.residuals
                )
                self._boundary_summary_cache[scope_ref] = RegionBoundarySummary(
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
            processed += len(batch)
            self._emit_progress(processed=processed, total=len(scopes), completed=False)
        bytes_written = 0
        path = self._checkpoint_path("region-boundary-summaries.json")
        if path is not None:
            bytes_written = _atomic_json(
                path,
                {
                    "owner_fingerprint": self._owner_fingerprint(),
                    "summaries": [
                        self._boundary_summary_cache[key].to_dict()
                        for key in sorted(self._boundary_summary_cache)
                    ],
                },
            )
        self._emit_progress(
            processed=processed,
            total=len(scopes),
            completed=True,
            bytes_written=bytes_written,
        )

    def region_boundary_summary(self, scope_ref: str) -> RegionBoundarySummary:
        self._build_boundary_summaries()
        summary = self._boundary_summary_cache.get(scope_ref)
        if summary is not None:
            return summary
        return RegionBoundarySummary(
            document_ref=self.document_ref,
            scope_ref=scope_ref,
            stable_factor_refs=(),
            unresolved_external_refs=(),
            possible_cross_scope_hosts=(),
            definition_scope_obligations=tuple(
                ref for ref in self._boundary_obligations if scope_ref in ref
            ),
            coverage_notice_refs=tuple(
                sorted(self._coverage_notice_refs_by_scope.get(scope_ref, ()))
            ),
        )

    def _blocking_counts(self) -> dict[str, int]:
        self._begin_phase(FinalizationPhase.VALIDATE_COVERAGE, total=1)
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
        self._emit_progress(processed=1, total=1, completed=True)
        self._begin_phase(FinalizationPhase.VALIDATE_UNRESOLVED_OBLIGATIONS, total=1)
        counts = {
            "pending_jobs": len(self._pending_jobs),
            "in_flight_jobs": len(self._in_flight_jobs),
            "dirty_groups": len(self._dirty_groups),
            "boundary_obligations": len(self._boundary_obligations),
            "open_required_coverage_barriers": open_barriers,
        }
        self._emit_progress(processed=1, total=1, completed=True)
        return counts

    def terminal_diagnostic(self) -> dict[str, Any]:
        return {
            "schema_version": "sensiblaw.closure-liveness.v2",
            "document_ref": self.document_ref,
            "state": self._closure_state.value,
            "producer_exhausted": self._producer_exhausted,
            "revision": self.revision,
            "last_transition_ns": self._last_transition_ns,
            "elapsed_ns": monotonic_ns() - self._lifecycle_started_ns,
            "blocking_counts": self._blocking_counts(),
            "retention_counts": self.retention_counts(),
            "materialization_count": self._materialization_count,
            "materialization_elapsed_ns": self._materialization_elapsed_ns,
            "certificate_count": self._certificate_count,
            "certificate_elapsed_ns": self._certificate_elapsed_ns,
            "indexed_scope_count": len(self._reduction_keys_by_scope),
            "finalization_phase": (
                self._finalization_phase.value if self._finalization_phase else None
            ),
            "finalization_events": list(self._finalization_events),
            "owner_fingerprint": self._owner_fingerprint(),
            "events": list(self._lifecycle_events),
        }

    def fixed_point_certificate(
        self, *, resource_limit_reached: bool = False
    ) -> DocumentFixedPointCertificate:  # type: ignore[override]
        if (
            self._certificate_cache is not None
            and self._certificate_cache_revision == self.revision
            and self._certificate_cache.resource_limit_reached == resource_limit_reached
        ):
            return self._certificate_cache
        self._transition(ClosureLifecycleState.CERTIFYING, reason="certificate_started")
        self._begin_phase(FinalizationPhase.BUILD_FIXED_POINT_CERTIFICATE, total=1)
        started = monotonic_ns()
        certificate = super().fixed_point_certificate(
            resource_limit_reached=resource_limit_reached
        )
        self._certificate_count += 1
        self._certificate_elapsed_ns += monotonic_ns() - started
        self._certificate_cache = certificate
        self._certificate_cache_revision = self.revision
        bytes_written = 0
        path = self._checkpoint_path("fixed-point-certificate.json")
        if path is not None:
            bytes_written = _atomic_json(
                path,
                {
                    "owner_fingerprint": self._owner_fingerprint(),
                    "certificate": certificate.to_dict(),
                },
            )
        self._emit_progress(
            processed=1,
            total=1,
            completed=True,
            bytes_written=bytes_written,
        )
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

    def release_finalization_scratch(self) -> None:
        self._begin_phase(FinalizationPhase.RELEASE_OWNER_STATE, total=1)
        self._deferred_reduction = None
        self._serialized_payload_cache = None
        self._emit_progress(processed=1, total=1, completed=True)

    def to_dict(self) -> dict[str, Any]:  # type: ignore[override]
        if self._serialized_payload_cache is not None:
            return dict(self._serialized_payload_cache)
        payload = super().to_dict()
        self._begin_phase(FinalizationPhase.SERIALIZE_CLOSURE_RECEIPT, total=1)
        payload["closure_lifecycle"] = self.terminal_diagnostic()
        self._serialized_payload_cache = payload
        bytes_written = 0
        path = self._checkpoint_path("closure-receipt.json")
        if path is not None:
            bytes_written = _atomic_json(
                path,
                {
                    "owner_fingerprint": self._owner_fingerprint(),
                    "closure_receipt": payload,
                },
            )
        self._emit_progress(
            processed=1,
            total=1,
            completed=True,
            bytes_written=bytes_written,
        )
        payload["closure_lifecycle"] = self.terminal_diagnostic()
        return dict(payload)


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
    "FinalizationPhase",
    "FinalizationStallError",
    "LivenessBoundedStreamingSemanticOwner",
    "install_closure_liveness_execution",
]
