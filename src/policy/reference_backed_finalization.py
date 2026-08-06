"""Reference-backed, release-before-handoff closure finalisation.

Large semantic families are sealed as framed binary streams before the owner
drops its document-sized Python state.  A fresh interpreter receives only a
compact binary spec.  Semantic digests use typed canonical bytes; neither local
checkpointing nor PostgreSQL authority uses JSON or JSONL.
"""

from __future__ import annotations

import ctypes
import gc
from hashlib import sha256
import os
from pathlib import Path
import pickle
from time import monotonic_ns
from typing import Any, Iterable, Mapping

from src.pnf.factor_proposals import ProposalReduction
from src.pnf.streaming_build_reader import (
    BINARY_FAMILY_ENCODING,
    REFERENCE_BUILD_SCHEMA_VERSION,
    family_descriptor,
)
from src.policy.carriers.canonical import canonical_bytes
from src.policy.closure_finalization_hardening import FinalizationHardenedOwner
from src.policy.closure_liveness_execution import (
    FinalizationPhase,
    LivenessBoundedStreamingSemanticOwner,
)
from src.runtime.reference_receipt import (
    atomic_write_binary,
    run_isolated_reference_serializer,
    stream_binary_family,
)
from src.runtime.stage_memory_budget import StageMemoryBudgetGuard


_INSTALL_MARKER = "_reference_backed_finalization_installed"
REFERENCE_FINALIZATION_CONTRACT = "reference-backed-finalization:v2"
MIB = 1024 * 1024


def _existing_binary_descriptor(
    path: Path,
    *,
    family: str,
    record_count: int,
) -> dict[str, Any]:
    digest = sha256()
    semantic_byte_count = 0
    artifact_byte_count = 0
    observed = 0
    with path.open("rb") as handle:
        while True:
            length_bytes = handle.read(8)
            if not length_bytes:
                break
            if len(length_bytes) != 8:
                raise ValueError(f"{family} checkpoint has a truncated frame")
            length = int.from_bytes(length_bytes, "big")
            encoded = handle.read(length)
            if len(encoded) != length:
                raise ValueError(f"{family} checkpoint has a truncated payload")
            value = pickle.loads(encoded)
            if not isinstance(value, Mapping):
                raise ValueError(f"{family} checkpoint row is not a mapping")
            semantic = canonical_bytes(dict(value))
            frame = len(semantic).to_bytes(8, "big") + semantic
            digest.update(frame)
            semantic_byte_count += len(frame)
            artifact_byte_count += 8 + length
            observed += 1
    if observed != record_count:
        raise ValueError(f"{family} checkpoint count changed")
    return family_descriptor(
        family=family,
        storage_kind="binary",
        record_count=observed,
        byte_count=semantic_byte_count,
        artifact_byte_count=artifact_byte_count,
        ordered_digest=digest.hexdigest(),
        path=str(path),
        encoding_ref=BINARY_FAMILY_ENCODING,
    )


def _malloc_trim() -> bool:
    try:
        libc = ctypes.CDLL(None)
        trim = libc.malloc_trim
        trim.argtypes = [ctypes.c_size_t]
        trim.restype = ctypes.c_int
        return bool(trim(0))
    except (AttributeError, OSError):
        return False


class ReferenceBackedFinalizationOwner(FinalizationHardenedOwner):
    """Return a compact reference build while preserving canonical semantics."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._reference_build_cache: dict[str, Any] | None = None
        self._retention_snapshot: dict[str, int] | None = None
        self._sealed_owner_fingerprint: dict[str, Any] | None = None
        self._owner_state_released = False
        self._stage_budget = StageMemoryBudgetGuard(root=self._finalization_root)

    def _owner_fingerprint(self) -> dict[str, Any]:
        if self._sealed_owner_fingerprint is not None:
            return dict(self._sealed_owner_fingerprint)
        return super()._owner_fingerprint()

    def retention_counts(self) -> dict[str, int]:
        if self._owner_state_released and self._retention_snapshot is not None:
            return dict(self._retention_snapshot)
        return super().retention_counts()

    @staticmethod
    def _rows(values: Iterable[Any]) -> Iterable[Mapping[str, Any]]:
        for value in values:
            if isinstance(value, Mapping):
                yield dict(value)
            else:
                yield value.to_dict()

    def _materialize_reduction_now(self, generation: int) -> ProposalReduction:
        if self._materialized_reduction_cache is not None:
            return self._materialized_reduction_cache
        started = monotonic_ns()
        original_root = self._finalization_root
        self._finalization_root = None
        try:
            reduction = LivenessBoundedStreamingSemanticOwner._materialize_reduction_now(
                self, generation
            )
        finally:
            self._finalization_root = original_root
        if original_root is None:
            return reduction
        factors = stream_binary_family(
            original_root / "materialized-factors.bin",
            family="factors",
            rows=self._rows(reduction.factors),
        )
        residuals = stream_binary_family(
            original_root / "materialized-residuals.bin",
            family="residuals",
            rows=self._rows(reduction.residuals),
        )
        atomic_write_binary(
            original_root / "materialized-reduction.manifest.pkl",
            {
                "owner_fingerprint": self._owner_fingerprint(),
                "graph_ref": reduction.graph_ref,
                "proposal_count": reduction.proposal_count,
                "deduplicated_count": reduction.deduplicated_count,
                "factor_count": len(reduction.factors),
                "residual_count": len(reduction.residuals),
                "metrics": dict(reduction.metrics),
                "factors": factors,
                "residuals": residuals,
                "full_proposal_rereduction_count": 0,
                "additional_row_dictionary_list_count": 0,
                "elapsed_ns": monotonic_ns() - started,
                "resumability_boundary": (
                    "settled_owner_index_plus_canonical_reduction"
                ),
                "text_serialization": False,
            },
        )
        return reduction

    def _seal_families(self, root: Path) -> dict[str, dict[str, Any]]:
        materialized = self.materialized_reduction
        factors = _existing_binary_descriptor(
            root / "materialized-factors.bin",
            family="factors",
            record_count=len(materialized.factors),
        )
        residuals = _existing_binary_descriptor(
            root / "materialized-residuals.bin",
            family="residuals",
            record_count=len(materialized.residuals),
        )

        self._build_boundary_summaries()
        jobs = self._compact_jobs if self._compact_jobs else self._jobs
        receipts = self._compact_receipts if self._compact_receipts else self._receipts
        specifications: tuple[tuple[str, Iterable[Any]], ...] = (
            (
                "observation_deltas",
                (
                    self._observation_deltas[key]
                    for key in sorted(self._observation_deltas)
                ),
            ),
            (
                "coverage_notices",
                (
                    self._coverage_notices[key]
                    for key in sorted(self._coverage_notices)
                ),
            ),
            ("proposals", (self._proposals[key] for key in sorted(self._proposals))),
            ("solver_jobs", (jobs[key] for key in sorted(jobs))),
            ("solver_receipts", (receipts[key] for key in sorted(receipts))),
            (
                "state_deltas",
                (self._state_deltas[index] for index in range(len(self._state_deltas))),
            ),
            (
                "region_boundary_summaries",
                (
                    self._boundary_summary_cache[key]
                    for key in sorted(self._boundary_summary_cache)
                ),
            ),
        )
        manifests: dict[str, dict[str, Any]] = {
            "factors": factors,
            "residuals": residuals,
        }
        for family, rows in specifications:
            manifests[family] = stream_binary_family(
                root / f"{family.replace('_', '-')}.bin",
                family=family,
                rows=self._rows(rows),
            )
        return manifests

    def _release_heavy_owner_state(self) -> dict[str, Any]:
        before = self._stage_budget.checkpoint(
            "finalization",
            phase="release_owner_state_started",
        )
        self._begin_phase(FinalizationPhase.RELEASE_OWNER_STATE, total=1)
        self._pure_blocking_counts()
        self._retention_snapshot = super().retention_counts()
        self._sealed_owner_fingerprint = super()._owner_fingerprint()
        released_counts = {
            "observation_deltas": len(self._observation_deltas),
            "observation_refs": len(self._observation_refs),
            "coverage_notices": len(self._coverage_notices),
            "declarations": len(self._declarations),
            "proposals": len(self._proposals),
            "proposal_owner_groups": len(self._proposals_by_owner),
            "jobs": len(self._jobs) + len(self._compact_jobs),
            "receipts": len(self._receipts) + len(self._compact_receipts),
            "completed_job_signatures": len(self._completed_job_signatures),
            "state_deltas": len(self._state_deltas),
            "dirty_groups": len(self._dirty_groups),
            "reductions": len(self._reductions),
            "boundary_obligations": len(self._boundary_obligations),
            "complete_coverage_entries": len(self._complete_coverage),
        }
        self._observation_deltas.clear()
        self._observation_refs.clear()
        self._coverage_notices.clear()
        self._declarations.clear()
        self._proposals.clear()
        self._proposal_stage.clear()
        self._proposals_by_owner.clear()
        self._jobs.clear()
        self._compact_jobs.clear()
        self._pending_jobs.clear()
        self._in_flight_jobs.clear()
        self._receipts.clear()
        self._compact_receipts.clear()
        self._compact_receipt_refs.clear()
        self._completed_job_signatures.clear()
        self._state_deltas.clear()
        self._dirty_groups.clear()
        self._reductions.clear()
        self._boundary_obligations.clear()
        self._complete_coverage.clear()
        self._known_dependency_refs.clear()
        self._materialized_reduction_cache = None
        self._deferred_reduction = None
        self._ledger_cache = None
        self._certificate_cache = None
        self._serialized_payload_cache = None
        self._owner_state_released = True
        collected = gc.collect()
        trimmed = _malloc_trim()
        self._emit_progress(processed=1, total=1, completed=True)
        after = self._stage_budget.checkpoint(
            "finalization",
            phase="release_owner_state_completed",
        )
        return {
            "released_counts": released_counts,
            "gc_collected": collected,
            "malloc_trim_attempted": True,
            "malloc_trim_succeeded": trimmed,
            "process_exit_required_for_strict_release": True,
            "before": before,
            "after": after,
            "pss_drop_bytes": max(
                0,
                int(before["resources"]["pss_bytes"])
                - int(after["resources"]["pss_bytes"]),
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        if self._reference_build_cache is not None:
            return dict(self._reference_build_cache)
        if self._finalization_root is None:
            return super().to_dict()

        root = self._finalization_root
        root.mkdir(parents=True, exist_ok=True)
        materialized = self.materialized_reduction
        certificate = self.fixed_point_certificate()
        ledger_ref = certificate.ledger_ref
        owner_fingerprint = self._owner_fingerprint()
        manifests = self._seal_families(root)
        reduction_manifest = {
            "representation": "family_manifests",
            "graph_ref": materialized.graph_ref,
            "document_ref": self.document_ref,
            "proposal_count": materialized.proposal_count,
            "deduplicated_count": materialized.deduplicated_count,
            "factor_count": len(materialized.factors),
            "residual_count": len(materialized.residuals),
            "metrics": dict(materialized.metrics),
            "factors": manifests["factors"],
            "residuals": manifests["residuals"],
        }
        del materialized
        compact_ledger = {
            "representation": "family_manifests",
            "ledger_ref": ledger_ref,
            "observation_deltas": manifests["observation_deltas"],
            "proposals": manifests["proposals"],
            "solver_receipts": manifests["solver_receipts"],
            "coverage_notices": manifests["coverage_notices"],
            "residuals": manifests["residuals"],
        }
        payload: dict[str, Any] = {
            "schema_version": REFERENCE_BUILD_SCHEMA_VERSION,
            "reference_finalization_contract": REFERENCE_FINALIZATION_CONTRACT,
            "document_ref": self.document_ref,
            "revision": self.revision,
            "partition_count": self.partition_count,
            "owner_fingerprint": owner_fingerprint,
            "ledger": compact_ledger,
            "observation_deltas": manifests["observation_deltas"],
            "coverage_notices": manifests["coverage_notices"],
            "proposals": manifests["proposals"],
            "solver_jobs": manifests["solver_jobs"],
            "solver_receipts": manifests["solver_receipts"],
            "state_deltas": manifests["state_deltas"],
            "materialized_reduction": reduction_manifest,
            "region_boundary_summaries": manifests[
                "region_boundary_summaries"
            ],
            "family_manifests": manifests,
            "pending_job_refs": [],
            "in_flight_job_refs": [],
            "fixed_point_certificate": certificate.to_dict(),
            "shared_graph_mutation": False,
            "last_writer_wins": False,
            "retention_mode": self.retention.mode.value,
            "retention_counts": super().retention_counts(),
            "compact_execution_evidence": True,
            "reference_backed": True,
            "text_serialization": False,
            "durable_authority": "postgresql_typed_execution_schema",
        }
        spec_path = root / "closure-reference-receipt.spec.pkl"
        output_path = root / "closure-receipt.pkl"
        report_path = root / "closure-reference-serializer-report.pkl"
        atomic_write_binary(spec_path, payload)
        release_receipt = self._release_heavy_owner_state()
        payload["owner_release"] = release_receipt
        atomic_write_binary(spec_path, payload)

        self._stage_budget.checkpoint(
            "serialization",
            phase="isolated_serializer_started",
        )
        self._begin_phase(FinalizationPhase.SERIALIZE_CLOSURE_RECEIPT, total=1)
        hard_mib = int(
            os.environ.get("SENSIBLAW_STAGE_SERIALIZATION_HARD_MIB", "3072")
        )
        serializer_report = run_isolated_reference_serializer(
            spec_path=spec_path,
            output_path=output_path,
            report_path=report_path,
            hard_pss_bytes=hard_mib * MIB,
        )
        payload["reference_receipt_path"] = str(output_path)
        payload["serializer_report"] = serializer_report
        payload["closure_lifecycle"] = self.terminal_diagnostic()
        self._emit_progress(
            processed=1,
            total=1,
            completed=True,
            bytes_written=int(serializer_report.get("bytes_written") or 0),
        )
        self._stage_budget.checkpoint(
            "serialization",
            phase="isolated_serializer_completed",
            details={"serializer_report": str(report_path)},
        )
        payload["closure_lifecycle"] = self.terminal_diagnostic()
        self._reference_build_cache = payload
        return dict(payload)


def install_reference_backed_finalization() -> bool:
    from src.policy import bounded_operational_execution as bounded

    if getattr(bounded, _INSTALL_MARKER, False):
        return False
    bounded.BoundedStreamingSemanticOwner = ReferenceBackedFinalizationOwner
    setattr(bounded, _INSTALL_MARKER, True)
    return True


__all__ = [
    "REFERENCE_FINALIZATION_CONTRACT",
    "ReferenceBackedFinalizationOwner",
    "install_reference_backed_finalization",
]
