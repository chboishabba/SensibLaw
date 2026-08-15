"""Execution-only carrier/orchestration hot-path cuts.

These optimisations deliberately do not participate in semantic identity.
They remove observational and duplicate-verification costs from the in-process
manifest path while preserving the canonical descriptor digest and PostgreSQL
authority.

The producer-seal optimisation relies on the existing contract that projected
artifacts are completed immutable values. Descriptor generation has already
computed their exact ordered digest. For the same in-process reader, persistence
may therefore reuse that producer proof instead of canonical-JSON hashing the
same immutable records a second time. Other readers, mismatched descriptors, or
an explicitly disabled seal take the full verifier.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import platform
from typing import Any, Iterator, Mapping

from src.policy import artifact_projection
from src.runtime import execution_resource_ledger


def _single_read_process_resources() -> dict[str, int | str]:
    """Return the existing resource fields using one smaps_rollup read."""

    rss = execution_resource_ledger._rss_bytes()
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/self/smaps_rollup").read_text(encoding="ascii").splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                continue
            name = key.strip()
            if name not in {"Pss", "Private_Clean", "Private_Dirty"}:
                continue
            values[name] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        values = {}

    pss = values.get("Pss")
    private_clean = values.get("Private_Clean")
    private_dirty = values.get("Private_Dirty")
    uss = (
        private_clean + (private_dirty or 0)
        if private_clean is not None
        else rss
    )
    return {
        "rss_bytes": rss,
        "pss_bytes": pss if pss is not None else rss,
        "uss_bytes": uss,
        "resource_source": "proc_smaps_rollup" if pss is not None else "resource_rusage_fallback",
        "kernel": platform.release(),
    }


def _manifest_telemetry_stride() -> int:
    raw = os.environ.get("SENSIBLAW_MANIFEST_TELEMETRY_STRIDE", "8")
    stride = int(raw)
    if stride < 1:
        raise ValueError("SENSIBLAW_MANIFEST_TELEMETRY_STRIDE must be positive")
    return stride


def _trust_inprocess_seals() -> bool:
    return os.environ.get("SENSIBLAW_TRUST_INPROCESS_ARTIFACT_SEALS", "1") != "0"


def _install_manifest_replay_hot_path() -> Any:
    """Remove telemetry-only JSON sizing and coalesce resource observations."""

    reader_type = artifact_projection.InMemoryArtifactManifestReader
    original = reader_type.iter_records

    def iter_records(
        self: Any, artifact_key: str, batch_size: int = 256
    ) -> Iterator[tuple[Mapping[str, Any], ...]]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if artifact_key not in self._sources:
            return
        iterator = self._iter(artifact_key)
        stride = _manifest_telemetry_stride()
        pending_rows = 0
        batch_no = 0
        while batch := tuple(artifact_projection.islice(iterator, batch_size)):
            batch_no += 1
            pending_rows += len(batch)
            if self._resource_ledger is not None and batch_no % stride == 0:
                self._resource_ledger.batch(
                    f"manifest_replay:{artifact_key}",
                    rows=pending_rows,
                    payload_bytes=0,
                )
                pending_rows = 0
            yield batch
        if self._resource_ledger is not None and pending_rows:
            self._resource_ledger.batch(
                f"manifest_replay:{artifact_key}",
                rows=pending_rows,
                payload_bytes=0,
            )

    reader_type.iter_records = iter_records
    return original


def _seal_projected_reader(original_project_artifacts: Any) -> Any:
    """Attach descriptor-generation receipts to the same in-process reader."""

    def project_artifacts(*args: Any, **kwargs: Any) -> Any:
        projected, reader = original_project_artifacts(*args, **kwargs)
        if isinstance(reader, artifact_projection.InMemoryArtifactManifestReader):
            seals: dict[str, tuple[int, str]] = {}
            for artifact_key, descriptor in projected.items():
                if not isinstance(descriptor, Mapping):
                    continue
                if descriptor.get("representation") != "manifest":
                    continue
                seals[str(artifact_key)] = (
                    int(descriptor["record_count"]),
                    str(descriptor["ordered_digest"]),
                )
            setattr(reader, "_producer_descriptor_seals", seals)
        return projected, reader

    return project_artifacts


def _sealed_iter_verified_records(original_iter_verified_records: Any) -> Any:
    """Reuse the producer digest for the same completed immutable source."""

    def iter_verified_records(
        reader: Any,
        descriptor: Mapping[str, Any],
        *,
        batch_size: int = 256,
    ) -> Iterator[tuple[Mapping[str, Any], ...]]:
        if batch_size < 1 or batch_size > 256:
            raise ValueError("record batch size must be between 1 and 256")
        artifact_key = str(descriptor["artifact_key"])
        expected_count = int(descriptor["record_count"])
        expected_digest = str(descriptor["ordered_digest"])
        seals = getattr(reader, "_producer_descriptor_seals", None)
        seal = seals.get(artifact_key) if isinstance(seals, Mapping) else None
        if _trust_inprocess_seals() and seal == (expected_count, expected_digest):
            count = 0
            for batch in reader.iter_records(artifact_key, batch_size):
                if len(batch) > batch_size:
                    raise ValueError("manifest reader exceeded requested batch size")
                count += len(batch)
                yield batch
            if count != expected_count:
                raise ValueError(f"record count mismatch for artifact {artifact_key!r}")
            return
        yield from original_iter_verified_records(
            reader,
            descriptor,
            batch_size=batch_size,
        )

    return iter_verified_records


@contextmanager
def activate_carrier_orchestration_hot_path() -> Iterator[None]:
    """Install physical-only carrier optimisations for one document runtime."""

    from src.policy import operational_corpus_compilation
    from src.policy import postgres_corpus_compilation
    from src.storage.postgres import work_conserving_language_persistence

    reader_type = artifact_projection.InMemoryArtifactManifestReader
    original_iter_records = _install_manifest_replay_hot_path()
    original_resource_sampler = execution_resource_ledger.sample_process_resources
    original_project_artifacts = artifact_projection.project_artifacts
    original_operational_project = operational_corpus_compilation.project_artifacts
    original_verified = artifact_projection.iter_verified_records
    original_postgres_verified = postgres_corpus_compilation.iter_verified_records
    original_language_verified = work_conserving_language_persistence.iter_verified_records

    sealed_project = _seal_projected_reader(original_project_artifacts)
    sealed_verified = _sealed_iter_verified_records(original_verified)
    execution_resource_ledger.sample_process_resources = _single_read_process_resources
    artifact_projection.project_artifacts = sealed_project
    operational_corpus_compilation.project_artifacts = sealed_project
    artifact_projection.iter_verified_records = sealed_verified
    postgres_corpus_compilation.iter_verified_records = sealed_verified
    work_conserving_language_persistence.iter_verified_records = sealed_verified
    try:
        yield
    finally:
        reader_type.iter_records = original_iter_records
        execution_resource_ledger.sample_process_resources = original_resource_sampler
        artifact_projection.project_artifacts = original_project_artifacts
        operational_corpus_compilation.project_artifacts = original_operational_project
        artifact_projection.iter_verified_records = original_verified
        postgres_corpus_compilation.iter_verified_records = original_postgres_verified
        work_conserving_language_persistence.iter_verified_records = original_language_verified


__all__ = ["activate_carrier_orchestration_hot_path"]
