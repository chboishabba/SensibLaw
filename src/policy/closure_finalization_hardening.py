"""Physical hardening for observable closure finalisation.

This layer is deliberately execution-only.  It subclasses the liveness owner to
cache immutable state fingerprints, keep diagnostics observational, stream the
large reduction checkpoint, and reuse a matching terminal certificate after the
canonical replay contract reconstructs the same owner state.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from time import monotonic_ns
from typing import Any, Mapping

from src.pnf.factor_proposals import ProposalReduction
from src.pnf.streaming_fixed_point import DocumentFixedPointCertificate
from src.policy.carriers.canonical import canonical_sha256
from src.policy.closure_liveness_execution import (
    ClosureLifecycleState,
    FinalizationPhase,
    LivenessBoundedStreamingSemanticOwner,
    _atomic_json,
    _reduced_factor_from_dict,
    _residual_from_dict,
)

_INSTALL_MARKER = "_closure_finalization_hardening_installed"


def _atomic_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    written = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            encoded = json.dumps(dict(row), sort_keys=True, separators=(",", ":"))
            handle.write(encoded)
            handle.write("\n")
            written += len(encoded.encode("utf-8")) + 1
    temporary.replace(path)
    return written


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return tuple(rows)


@dataclass(frozen=True)
class _FingerprintCacheKey:
    revision: int
    proposal_count: int
    reduction_count: int
    obligation_count: int
    coverage_count: int


class FinalizationHardenedOwner(LivenessBoundedStreamingSemanticOwner):
    """Liveness owner with output-linear durable terminal checkpoints."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._fingerprint_cache_key: _FingerprintCacheKey | None = None
        self._fingerprint_cache: dict[str, Any] | None = None
        self._blocking_cache_revision = -1
        self._blocking_cache: dict[str, int] | None = None

    def _owner_fingerprint(self) -> dict[str, Any]:
        key = _FingerprintCacheKey(
            revision=self.revision,
            proposal_count=len(self._proposals),
            reduction_count=len(self._reductions),
            obligation_count=len(self._boundary_obligations),
            coverage_count=len(self._coverage_notices),
        )
        if key == self._fingerprint_cache_key and self._fingerprint_cache is not None:
            return dict(self._fingerprint_cache)
        reduction_keys = [row.to_dict() for row in sorted(self._reductions)]
        payload = {
            "schema_version": "sensiblaw.closure-finalization.v2",
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
        self._fingerprint_cache_key = key
        self._fingerprint_cache = payload
        return dict(payload)

    def _pure_blocking_counts(self) -> dict[str, int]:
        if self._blocking_cache_revision == self.revision and self._blocking_cache:
            return dict(self._blocking_cache)
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
        payload = {
            "pending_jobs": len(self._pending_jobs),
            "in_flight_jobs": len(self._in_flight_jobs),
            "dirty_groups": len(self._dirty_groups),
            "boundary_obligations": len(self._boundary_obligations),
            "open_required_coverage_barriers": sum(
                not self.coverage_complete(scope_ref=scope_ref, barrier=barrier)
                for scope_ref, barrier in required_barriers
            ),
        }
        self._blocking_cache_revision = self.revision
        self._blocking_cache = payload
        return dict(payload)

    def terminal_diagnostic(self) -> dict[str, Any]:
        return {
            "schema_version": "sensiblaw.closure-liveness.v2",
            "document_ref": self.document_ref,
            "state": self._closure_state.value,
            "producer_exhausted": self._producer_exhausted,
            "revision": self.revision,
            "last_transition_ns": self._last_transition_ns,
            "elapsed_ns": monotonic_ns() - self._lifecycle_started_ns,
            "blocking_counts": self._pure_blocking_counts(),
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

    def _load_reduction_checkpoint(self) -> ProposalReduction | None:
        manifest_path = self._checkpoint_path("materialized-reduction.manifest.json")
        factors_path = self._checkpoint_path("materialized-factors.jsonl")
        residuals_path = self._checkpoint_path("materialized-residuals.jsonl")
        if (
            manifest_path is None
            or factors_path is None
            or residuals_path is None
            or not manifest_path.exists()
            or not factors_path.exists()
            or not residuals_path.exists()
        ):
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            factor_rows = _read_jsonl(factors_path)
            residual_rows = _read_jsonl(residuals_path)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
        if manifest.get("owner_fingerprint") != self._owner_fingerprint():
            return None
        reduction = ProposalReduction(
            document_ref=self.document_ref,
            factors=tuple(_reduced_factor_from_dict(row) for row in factor_rows),
            residuals=tuple(_residual_from_dict(row) for row in residual_rows),
            proposal_count=int(manifest["proposal_count"]),
            deduplicated_count=int(manifest["deduplicated_count"]),
            metrics=dict(manifest.get("metrics") or {}),
        )
        if reduction.graph_ref != manifest.get("graph_ref"):
            return None
        return reduction

    def _materialize_reduction_now(self, generation: int) -> ProposalReduction:
        if self._materialized_reduction_cache is not None:
            return self._materialized_reduction_cache
        started = monotonic_ns()
        checkpoint = self._load_reduction_checkpoint()
        if checkpoint is not None:
            self._materialized_reduction_cache = checkpoint
            self._materialization_count += 1
            self._materialization_elapsed_ns += monotonic_ns() - started
            total = len(checkpoint.factors) + len(checkpoint.residuals)
            self._begin_phase(FinalizationPhase.ASSEMBLE_REDUCTION, total=total)
            self._emit_progress(
                processed=total,
                total=total,
                completed=True,
                reused_checkpoint=True,
            )
            return checkpoint
        original_root = self._finalization_root
        self._finalization_root = None
        try:
            reduction = super()._materialize_reduction_now(generation)
        finally:
            self._finalization_root = original_root
        if original_root is None:
            return reduction
        factors_path = original_root / "materialized-factors.jsonl"
        residuals_path = original_root / "materialized-residuals.jsonl"
        factor_bytes = _atomic_jsonl(
            factors_path, [row.to_dict() for row in reduction.factors]
        )
        residual_bytes = _atomic_jsonl(
            residuals_path, [row.to_dict() for row in reduction.residuals]
        )
        _atomic_json(
            original_root / "materialized-reduction.manifest.json",
            {
                "owner_fingerprint": self._owner_fingerprint(),
                "graph_ref": reduction.graph_ref,
                "proposal_count": reduction.proposal_count,
                "deduplicated_count": reduction.deduplicated_count,
                "factor_count": len(reduction.factors),
                "residual_count": len(reduction.residuals),
                "metrics": dict(reduction.metrics),
                "factor_bytes": factor_bytes,
                "residual_bytes": residual_bytes,
                "resumability_boundary": "canonical_reduction",
            },
        )
        return reduction

    def _load_certificate_checkpoint(
        self, *, resource_limit_reached: bool
    ) -> DocumentFixedPointCertificate | None:
        path = self._checkpoint_path("fixed-point-certificate.json")
        if path is None or not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            row = payload["certificate"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            return None
        if payload.get("owner_fingerprint") != self._owner_fingerprint():
            return None
        if bool(row.get("resource_limit_reached")) != resource_limit_reached:
            return None
        try:
            certificate = DocumentFixedPointCertificate(
                document_ref=str(row["document_ref"]),
                revision=int(row["revision"]),
                ledger_ref=str(row["ledger_ref"]),
                materialized_graph_ref=str(row["materialized_graph_ref"]),
                unconsumed_observation_deltas=int(row["unconsumed_observation_deltas"]),
                dirty_reduction_groups=int(row["dirty_reduction_groups"]),
                pending_jobs=int(row["pending_jobs"]),
                in_flight_jobs=int(row["in_flight_jobs"]),
                unresolved_local_boundary_obligations=int(
                    row["unresolved_local_boundary_obligations"]
                ),
                open_required_coverage_barriers=int(
                    row["open_required_coverage_barriers"]
                ),
                unresolved_external_residuals=tuple(
                    row.get("unresolved_external_residuals") or ()
                ),
                resource_limit_reached=resource_limit_reached,
            )
        except (KeyError, TypeError, ValueError):
            return None
        return certificate

    def fixed_point_certificate(
        self, *, resource_limit_reached: bool = False
    ) -> DocumentFixedPointCertificate:
        checkpoint = self._load_certificate_checkpoint(
            resource_limit_reached=resource_limit_reached
        )
        if checkpoint is not None:
            self._certificate_cache = checkpoint
            self._certificate_cache_revision = self.revision
            self._certificate_count += 1
            self._begin_phase(FinalizationPhase.BUILD_FIXED_POINT_CERTIFICATE, total=1)
            self._emit_progress(
                processed=1,
                total=1,
                completed=True,
                reused_checkpoint=True,
            )
            if checkpoint.local_fixed_point_reached and self._producer_exhausted:
                self._transition(
                    ClosureLifecycleState.COMPLETED,
                    reason="fixed_point_checkpoint_reused",
                )
            return checkpoint
        return super().fixed_point_certificate(
            resource_limit_reached=resource_limit_reached
        )

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        self._begin_phase(FinalizationPhase.RELEASE_OWNER_STATE, total=1)
        self._deferred_reduction = None
        self._emit_progress(processed=1, total=1, completed=True)
        return payload


def install_closure_finalization_hardening() -> bool:
    """Install the hardened subclass before parallel wrappers capture the owner."""

    from src.policy import bounded_operational_execution as bounded

    if getattr(bounded, _INSTALL_MARKER, False):
        return False
    bounded.BoundedStreamingSemanticOwner = FinalizationHardenedOwner
    setattr(bounded, _INSTALL_MARKER, True)
    return True


__all__ = [
    "FinalizationHardenedOwner",
    "install_closure_finalization_hardening",
]
