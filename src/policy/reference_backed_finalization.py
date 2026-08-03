"""Reference-backed, release-before-serialize closure finalisation.

Large semantic families are sealed as immutable streams before the owner drops
its document-sized Python state.  A fresh interpreter then serializes only the
compact manifest receipt.  JSONL is a transitional local transport; each family
is content-addressed so PostgreSQL/object segments can replace it without
changing the outward semantic identity.
"""

from __future__ import annotations

import ctypes
import gc
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.pnf.streaming_build_reader import (
    REFERENCE_BUILD_SCHEMA_VERSION,
    family_descriptor,
)
from src.policy.closure_finalization_hardening import FinalizationHardenedOwner
from src.policy.closure_liveness_execution import FinalizationPhase
from src.runtime.reference_receipt import (
    atomic_stream_json,
    run_isolated_reference_serializer,
    stream_jsonl_family,
)


_INSTALL_MARKER = "_reference_backed_finalization_installed"
REFERENCE_FINALIZATION_CONTRACT = "reference-backed-finalization:v1"
MIB = 1024 * 1024


def _existing_jsonl_descriptor(
    path: Path,
    *,
    family: str,
    record_count: int,
) -> dict[str, Any]:
    digest = sha256()
    byte_count = 0
    observed = 0
    with path.open("rb") as handle:
        for line in handle:
            if not line.strip():
                continue
            digest.update(line)
            byte_count += len(line)
            observed += 1
    if observed != record_count:
        raise ValueError(f"{family} checkpoint count changed")
    return family_descriptor(
        family=family,
        storage_kind="jsonl",
        record_count=observed,
        byte_count=byte_count,
        ordered_digest=digest.hexdigest(),
        path=str(path),
    )


def _malloc_trim() -> bool:
    """Best-effort glibc arena release; process exit remains the hard boundary."""

    try:
        libc = ctypes.CDLL(None)
        trim = libc.malloc_trim
        trim.argtypes = [ctypes.c_size_t]
        trim.restype = ctypes.c_int
        return bool(trim(0))
    except (AttributeError, OSError):
        return False


class ReferenceBackedFinalizationOwner(FinalizationHardenedOwner):
    """Return a compact build while preserving one canonical semantic owner."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._reference_build_cache: dict[str, Any] | None = None
        self._retention_snapshot: dict[str, int] | None = None
        self._sealed_owner_fingerprint: dict[str, Any] | None = None
        self._owner_state_released = False

    def _owner_fingerprint(self) -> dict[str, Any]:
        if self._sealed_owner_fingerprint is not None:
            return dict(self._sealed_owner_fingerprint)
        return super()._owner_fingerprint()

    def retention_counts(self) -> dict[str, int]:
        if self._owner_state_released and self._retention_snapshot is not None:
            return dict(self._retention_snapshot)
        return super().retention_counts()

    def _rows(self, values: Iterable[Any]) -> Iterable[Mapping[str, Any]]:
        for value in values:
            if isinstance(value, Mapping):
                yield dict(value)
            else:
                yield value.to_dict()

    def _seal_families(self, root: Path) -> dict[str, dict[str, Any]]:
        materialized = self.materialized_reduction
        factors_path = root / "materialized-factors.jsonl"
        residuals_path = root / "materialized-residuals.jsonl"
        if not factors_path.exists():
            factors = stream_jsonl_family(
                factors_path,
                family="factors",
                rows=self._rows(materialized.factors),
            )
        else:
            factors = _existing_jsonl_descriptor(
                factors_path,
                family="factors",
                record_count=len(materialized.factors),
            )
        if not residuals_path.exists():
            residuals = stream_jsonl_family(
                residuals_path,
                family="residuals",
                rows=self._rows(materialized.residuals),
            )
        else:
            residuals = _existing_jsonl_descriptor(
                residuals_path,
                family="residuals",
                record_count=len(materialized.residuals),
            )

        self._build_boundary_summaries()
        specifications: tuple[tuple[str, Iterable[Any]], ...] = (
            (
                "observation_deltas",
                (self._observation_deltas[key] for key in sorted(self._observation_deltas)),
            ),
            (
                "coverage_notices",
                (self._coverage_notices[key] for key in sorted(self._coverage_notices)),
            ),
            (
                "proposals",
                (self._proposals[key] for key in sorted(self._proposals)),
            ),
            (
                "solver_jobs",
                (self._compact_jobs[key] for key in sorted(self._compact_jobs)),
            ),
            (
                "solver_receipts",
                (
                    self._compact_receipts[key]
                    for key in sorted(self._compact_receipts)
                ),
            ),
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
            manifests[family] = stream_jsonl_family(
                root / f"{family.replace('_', '-')}.jsonl",
                family=family,
                rows=self._rows(rows),
            )
        return manifests

    def _release_heavy_owner_state(self) -> dict[str, Any]:
        self._begin_phase(FinalizationPhase.RELEASE_OWNER_STATE, total=1)
        self._pure_blocking_counts()
        self._retention_snapshot = super().retention_counts()
        self._sealed_owner_fingerprint = super()._owner_fingerprint()
        released_counts = {
            "observation_deltas": len(self._observation_deltas),
            "proposals": len(self._proposals),
            "proposal_owner_groups": len(self._proposals_by_owner),
            "jobs": len(self._jobs) + len(self._compact_jobs),
            "receipts": len(self._receipts) + len(self._compact_receipts),
            "state_deltas": len(self._state_deltas),
            "reductions": len(self._reductions),
        }
        self._observation_deltas.clear()
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
        self._state_deltas.clear()
        self._reductions.clear()
        self._known_dependency_refs.clear()
        self._materialized_reduction_cache = None
        self._deferred_reduction = None
        self._ledger_cache = None
        self._serialized_payload_cache = None
        self._owner_state_released = True
        collected = gc.collect()
        trimmed = _malloc_trim()
        self._emit_progress(processed=1, total=1, completed=True)
        return {
            "released_counts": released_counts,
            "gc_collected": collected,
            "malloc_trim_attempted": True,
            "malloc_trim_succeeded": trimmed,
            "process_exit_required_for_strict_release": True,
        }

    def to_dict(self) -> dict[str, Any]:
        if self._reference_build_cache is not None:
            return dict(self._reference_build_cache)
        if self._finalization_root is None:
            # Small fixtures retain the established materialised contract.  Exact
            # and production runs always configure a durable checkpoint root.
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
            "jsonl_authority": "transitional_debug_transport_only",
            "durable_authority_target": "postgresql_execution_schema",
        }
        spec_path = root / "closure-reference-receipt.spec.json"
        output_path = root / "closure-reference-receipt.json"
        report_path = root / "closure-reference-serializer-report.json"
        atomic_stream_json(spec_path, payload)
        release_receipt = self._release_heavy_owner_state()
        payload["owner_release"] = release_receipt
        atomic_stream_json(spec_path, payload)

        self._begin_phase(FinalizationPhase.SERIALIZE_CLOSURE_RECEIPT, total=1)
        hard_mib = int(os.environ.get("SENSIBLAW_STAGE_SERIALIZATION_HARD_MIB", "3072"))
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
        payload["closure_lifecycle"] = self.terminal_diagnostic()
        self._reference_build_cache = payload
        return dict(payload)


def install_reference_backed_finalization() -> bool:
    """Install after liveness/finalisation hardening and before parallel wrappers."""

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
