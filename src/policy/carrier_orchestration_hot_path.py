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

Canonical JSON here is a defended legacy *identity boundary*, not an execution
carrier. Ordinary post-spaCy semantic execution remains numeric.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
from typing import Any, Iterator, Mapping

from src.policy import artifact_projection
from src.runtime import execution_resource_ledger
from src.runtime.numeric_hot_path_constitution import (
    BoundaryOperation,
    LEGACY_MANIFEST_IDENTITY_BOUNDARY,
    require_boundary_operation,
)

_CANONICAL_RECORD_ENCODER = json.JSONEncoder(
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode


def _canonical_record_bytes(record: Mapping[str, Any]) -> bytes:
    """Return byte-identical canonical manifest JSON without encoder setup."""

    return _CANONICAL_RECORD_ENCODER(record).encode("utf-8")


def _reused_encoder_record_stream_digest(
    records: Iterator[Mapping[str, Any]],
) -> tuple[int, str]:
    """Match the established JSON-list digest with one reusable encoder."""

    require_boundary_operation(
        LEGACY_MANIFEST_IDENTITY_BOUNDARY,
        BoundaryOperation.JSON,
    )
    digest = hashlib.sha256()
    digest.update(b"[")
    count = 0
    for record in records:
        if count:
            digest.update(b",")
        digest.update(_canonical_record_bytes(record))
        count += 1
    digest.update(b"]")
    return count, digest.hexdigest()


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


def _descriptor_seal(reader: Any, descriptor: Mapping[str, Any]) -> tuple[int, str] | None:
    artifact_key = str(descriptor.get("artifact_key") or "")
    seals = getattr(reader, "_producer_descriptor_seals", None)
    if not isinstance(seals, Mapping):
        return None
    seal = seals.get(artifact_key)
    if not isinstance(seal, tuple) or len(seal) != 2:
        return None
    return int(seal[0]), str(seal[1])


def _descriptor_matches_seal(reader: Any, descriptor: Mapping[str, Any]) -> bool:
    if not _trust_inprocess_seals():
        return False
    return _descriptor_seal(reader, descriptor) == (
        int(descriptor["record_count"]),
        str(descriptor["ordered_digest"]),
    )


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
    """Attach descriptor-generation receipts to the same in-process reader.

    Descriptor generation is one sequential immutable pass.  Sampling process
    resources before and after every artifact family adds observational work but
    no semantic evidence, so the work-conserving path emits one aggregate sample
    around the pass and then reattaches the ledger to the reader for subsequent
    bounded replay observations.
    """

    def project_artifacts(*args: Any, **kwargs: Any) -> Any:
        ledger = kwargs.get("resource_ledger")
        call_kwargs = dict(kwargs)
        if ledger is not None:
            call_kwargs["resource_ledger"] = None
            ledger.sample(
                "descriptor_generation:aggregate:start",
                phase="descriptor_generation",
                details={"sampling": "aggregate"},
            )

        projected, reader = original_project_artifacts(*args, **call_kwargs)
        seals: dict[str, tuple[int, str]] = {}
        if isinstance(reader, artifact_projection.InMemoryArtifactManifestReader):
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
            if ledger is not None:
                reader.attach_resource_ledger(ledger)

        if ledger is not None:
            ledger.sample(
                "descriptor_generation:aggregate:complete",
                phase="descriptor_generation",
                semantic_counts={
                    "manifest_families": len(seals),
                    "manifest_records": sum(count for count, _digest in seals.values()),
                },
                details={"sampling": "aggregate"},
            )
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
        if _descriptor_matches_seal(reader, descriptor):
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


def _sealed_receipt_verify(original_verify_descriptor: Any) -> Any:
    """Skip row traversal when a descriptor is only being consumed as a receipt."""

    def verify_descriptor(reader: Any, descriptor: Mapping[str, Any]) -> None:
        if _descriptor_matches_seal(reader, descriptor):
            return
        original_verify_descriptor(reader, descriptor)

    return verify_descriptor


def _memoized_factor_revision_ref(original_factor_revision_ref: Any) -> Any:
    """Hash each completed in-memory factor mapping once per document scope."""

    cache: dict[int, tuple[Any, str]] = {}

    def factor_revision_ref(factor: Mapping[str, Any]) -> str:
        identity = id(factor)
        cached = cache.get(identity)
        if cached is not None and cached[0] is factor:
            return cached[1]
        revision_ref = str(original_factor_revision_ref(factor))
        cache[identity] = (factor, revision_ref)
        return revision_ref

    return factor_revision_ref


@contextmanager
def activate_carrier_orchestration_hot_path() -> Iterator[None]:
    """Install physical-only carrier optimisations for one document runtime."""

    from src.policy import manifest_stream_validation
    from src.policy import operational_corpus_compilation
    from src.policy import postgres_corpus_compilation
    from src.policy.algebra import revision_identity
    from src.storage.postgres import work_conserving_graph_persistence
    from src.storage.postgres import work_conserving_language_persistence
    from src.storage.postgres import work_conserving_resolution_persistence

    reader_type = artifact_projection.InMemoryArtifactManifestReader
    original_iter_records = _install_manifest_replay_hot_path()
    original_resource_sampler = execution_resource_ledger.sample_process_resources
    original_record_stream_digest = artifact_projection._record_stream_digest
    original_project_artifacts = artifact_projection.project_artifacts
    original_operational_project = operational_corpus_compilation.project_artifacts
    original_verified = artifact_projection.iter_verified_records
    original_postgres_verified = postgres_corpus_compilation.iter_verified_records
    original_language_verified = work_conserving_language_persistence.iter_verified_records
    original_verify_descriptor = postgres_corpus_compilation._verify_descriptor
    original_revision_ref = revision_identity.factor_revision_ref
    original_manifest_revision_ref = manifest_stream_validation.factor_revision_ref
    original_postgres_revision_ref = postgres_corpus_compilation.factor_revision_ref
    original_graph_revision_ref = work_conserving_graph_persistence.factor_revision_ref
    original_resolution_revision_ref = work_conserving_resolution_persistence.factor_revision_ref

    sealed_project = _seal_projected_reader(original_project_artifacts)
    sealed_verified = _sealed_iter_verified_records(original_verified)
    memo_revision_ref = _memoized_factor_revision_ref(original_revision_ref)
    execution_resource_ledger.sample_process_resources = _single_read_process_resources
    artifact_projection._record_stream_digest = _reused_encoder_record_stream_digest
    artifact_projection.project_artifacts = sealed_project
    operational_corpus_compilation.project_artifacts = sealed_project
    artifact_projection.iter_verified_records = sealed_verified
    postgres_corpus_compilation.iter_verified_records = sealed_verified
    work_conserving_language_persistence.iter_verified_records = sealed_verified
    postgres_corpus_compilation._verify_descriptor = _sealed_receipt_verify(
        original_verify_descriptor
    )
    revision_identity.factor_revision_ref = memo_revision_ref
    manifest_stream_validation.factor_revision_ref = memo_revision_ref
    postgres_corpus_compilation.factor_revision_ref = memo_revision_ref
    work_conserving_graph_persistence.factor_revision_ref = memo_revision_ref
    work_conserving_resolution_persistence.factor_revision_ref = memo_revision_ref
    try:
        yield
    finally:
        reader_type.iter_records = original_iter_records
        execution_resource_ledger.sample_process_resources = original_resource_sampler
        artifact_projection._record_stream_digest = original_record_stream_digest
        artifact_projection.project_artifacts = original_project_artifacts
        operational_corpus_compilation.project_artifacts = original_operational_project
        artifact_projection.iter_verified_records = original_verified
        postgres_corpus_compilation.iter_verified_records = original_postgres_verified
        work_conserving_language_persistence.iter_verified_records = original_language_verified
        postgres_corpus_compilation._verify_descriptor = original_verify_descriptor
        revision_identity.factor_revision_ref = original_revision_ref
        manifest_stream_validation.factor_revision_ref = original_manifest_revision_ref
        postgres_corpus_compilation.factor_revision_ref = original_postgres_revision_ref
        work_conserving_graph_persistence.factor_revision_ref = original_graph_revision_ref
        work_conserving_resolution_persistence.factor_revision_ref = original_resolution_revision_ref


__all__ = ["activate_carrier_orchestration_hot_path"]
