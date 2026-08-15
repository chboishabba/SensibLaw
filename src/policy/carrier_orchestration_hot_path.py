"""Execution-only carrier/orchestration hot-path cuts.

These optimisations deliberately do not participate in semantic identity.
They remove two observational costs from the in-process manifest path:

* manifest replay no longer canonical-JSON serialises every record merely to
  estimate telemetry bytes before the authoritative verifier serialises it;
* process RSS/PSS/USS sampling reads Linux ``smaps_rollup`` once per sample
  instead of reopening and reparsing the same file three times.

The canonical descriptor digest, manifest row order and PostgreSQL authority
remain unchanged.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import platform
from typing import Any, Iterator

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


def _install_manifest_replay_hot_path() -> Any:
    """Replace telemetry-only JSON sizing and coalesce observational samples.

    The authoritative ordered digest still lives in ``iter_verified_records``.
    This method only changes the reader's resource-ledger observation cadence.
    Exact row accounting is retained by carrying skipped rows into the next
    sample and flushing the remainder at EOF.
    """

    reader_type = artifact_projection.InMemoryArtifactManifestReader
    original = reader_type.iter_records

    def iter_records(
        self: Any, artifact_key: str, batch_size: int = 256
    ) -> Iterator[tuple[dict[str, Any], ...]]:
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


@contextmanager
def activate_carrier_orchestration_hot_path() -> Iterator[None]:
    """Install physical-only carrier optimisations for one document runtime."""

    reader_type = artifact_projection.InMemoryArtifactManifestReader
    original_iter_records = _install_manifest_replay_hot_path()
    original_resource_sampler = execution_resource_ledger.sample_process_resources
    execution_resource_ledger.sample_process_resources = _single_read_process_resources
    try:
        yield
    finally:
        reader_type.iter_records = original_iter_records
        execution_resource_ledger.sample_process_resources = original_resource_sampler


__all__ = ["activate_carrier_orchestration_hot_path"]
