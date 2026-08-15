"""Bounded access to embedded or reference-backed streaming-build families.

Exact documents expose content-addressed framed binary families. Raw artifact
bytes are verified before any pickle decode; decoded semantic integrity is then
checked with typed canonical bytes. Pickle is only a bounded local artifact
codec and never execution identity or database authority.
"""

from __future__ import annotations

from hashlib import sha256
from itertools import islice
from pathlib import Path
import pickle
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

from src.policy.carriers.canonical import canonical_bytes


FAMILY_DESCRIPTOR_SCHEMA_VERSION = "sensiblaw.streaming-family-descriptor.v3"
REFERENCE_BUILD_SCHEMA_VERSION = "sensiblaw.reference-streaming-build.v3"
DEFAULT_BATCH_SIZE = 256
BINARY_FAMILY_ENCODING = "python-pickle-framed:5+sha256+itir-typed-digest:v1"
RowSource = Callable[[Mapping[str, Any]], Iterable[Mapping[str, Any]]]


def is_family_descriptor(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("schema_version") == (
        FAMILY_DESCRIPTOR_SCHEMA_VERSION
    )


def _batches(
    values: Iterable[Mapping[str, Any]], size: int
) -> Iterator[tuple[Mapping[str, Any], ...]]:
    if size < 1:
        raise ValueError("batch size must be positive")
    iterator = iter(values)
    while batch := tuple(islice(iterator, size)):
        yield batch


def family_descriptor(
    *,
    family: str,
    storage_kind: str,
    record_count: int,
    byte_count: int,
    ordered_digest: str,
    path: str | None = None,
    manifest_ref: str | None = None,
    segment_refs: Sequence[str] = (),
    encoding_ref: str = BINARY_FAMILY_ENCODING,
    artifact_byte_count: int | None = None,
    artifact_digest: str | None = None,
) -> dict[str, Any]:
    if record_count < 0 or byte_count < 0:
        raise ValueError("family counts must be non-negative")
    if storage_kind not in {"binary", "postgresql", "object"}:
        raise ValueError("unsupported family storage kind")
    if storage_kind == "binary" and not path:
        raise ValueError("binary family descriptor requires a path")
    if storage_kind == "binary" and not artifact_digest:
        raise ValueError("binary family descriptor requires an artifact digest")
    if storage_kind != "binary" and not manifest_ref:
        raise ValueError("authoritative family descriptor requires a manifest ref")
    return {
        "schema_version": FAMILY_DESCRIPTOR_SCHEMA_VERSION,
        "family": str(family),
        "storage_kind": storage_kind,
        "record_count": int(record_count),
        "byte_count": int(byte_count),
        "artifact_byte_count": int(
            artifact_byte_count if artifact_byte_count is not None else byte_count
        ),
        "artifact_digest": artifact_digest,
        "ordered_digest": str(ordered_digest),
        "encoding_ref": str(encoding_ref),
        "path": path,
        "manifest_ref": manifest_ref,
        "segment_refs": list(segment_refs),
    }


def _semantic_frame(row: Mapping[str, Any]) -> bytes:
    encoded = canonical_bytes(dict(row))
    return len(encoded).to_bytes(8, "big") + encoded


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


class StreamingBuildReader:
    """Read a streaming build without reconstructing every family at once."""

    def __init__(
        self,
        build: Mapping[str, Any],
        *,
        base_path: str | Path | None = None,
        row_source: RowSource | None = None,
    ) -> None:
        self.build = build
        self.base_path = Path(base_path).resolve() if base_path is not None else None
        self.row_source = row_source

    def descriptor(self, family: str) -> Mapping[str, Any] | None:
        manifests = self.build.get("family_manifests") or {}
        value = manifests.get(family) if isinstance(manifests, Mapping) else None
        if is_family_descriptor(value):
            return value
        direct = self.build.get(family)
        if is_family_descriptor(direct):
            return direct
        if family in {"factors", "residuals"}:
            reduction = self.build.get("materialized_reduction") or {}
            if isinstance(reduction, Mapping):
                nested = reduction.get(family)
                if is_family_descriptor(nested):
                    return nested
        return None

    def family_count(self, family: str) -> int:
        descriptor = self.descriptor(family)
        if descriptor is not None:
            return int(descriptor.get("record_count") or 0)
        value = self._embedded_family(family)
        return len(value) if isinstance(value, (list, tuple)) else 0

    def _embedded_family(self, family: str) -> Any:
        if family in {"factors", "residuals"}:
            reduction = self.build.get("materialized_reduction") or {}
            if isinstance(reduction, Mapping):
                return reduction.get(family)
        return self.build.get(family)

    def _resolve_path(self, descriptor: Mapping[str, Any]) -> Path:
        raw = Path(str(descriptor["path"]))
        if raw.is_absolute():
            return raw
        if self.base_path is None:
            raise ValueError("relative family path requires a base path")
        path = (self.base_path / raw).resolve()
        try:
            path.relative_to(self.base_path)
        except ValueError as error:
            raise ValueError("family path escapes its manifest root") from error
        return path

    def _verify_binary_artifact(
        self,
        path: Path,
        descriptor: Mapping[str, Any],
    ) -> None:
        observed_digest, observed_bytes = _sha256_file(path)
        expected_bytes = int(descriptor.get("artifact_byte_count") or 0)
        expected_digest = str(descriptor.get("artifact_digest") or "")
        if observed_bytes != expected_bytes:
            raise ValueError(f"family artifact byte count changed: {path}")
        if observed_digest != expected_digest:
            raise ValueError(f"family artifact digest changed: {path}")

    def _iter_binary(
        self, descriptor: Mapping[str, Any]
    ) -> Iterator[Mapping[str, Any]]:
        path = self._resolve_path(descriptor)
        # Verify untrusted artifact bytes before invoking the binary codec.
        self._verify_binary_artifact(path, descriptor)

        digest = sha256()
        count = 0
        semantic_bytes = 0
        with path.open("rb") as handle:
            while True:
                length_bytes = handle.read(8)
                if not length_bytes:
                    break
                if len(length_bytes) != 8:
                    raise ValueError(f"truncated family frame length: {path}")
                length = int.from_bytes(length_bytes, "big")
                encoded = handle.read(length)
                if len(encoded) != length:
                    raise ValueError(f"truncated family frame payload: {path}")
                try:
                    value = pickle.loads(encoded)
                except (
                    EOFError,
                    pickle.PickleError,
                    AttributeError,
                    ValueError,
                ) as error:
                    raise ValueError(f"family frame decode failed: {path}") from error
                if not isinstance(value, Mapping):
                    raise ValueError(f"family row is not a mapping: {path}")
                row = dict(value)
                semantic = _semantic_frame(row)
                digest.update(semantic)
                semantic_bytes += len(semantic)
                count += 1
                yield row
        if count != int(descriptor.get("record_count") or 0):
            raise ValueError(f"family row count changed: {path}")
        if semantic_bytes != int(descriptor.get("byte_count") or 0):
            raise ValueError(f"family canonical byte count changed: {path}")
        if digest.hexdigest() != str(descriptor.get("ordered_digest") or ""):
            raise ValueError(f"family ordered digest changed: {path}")

    def iter_rows(self, family: str) -> Iterator[Mapping[str, Any]]:
        descriptor = self.descriptor(family)
        if descriptor is None:
            value = self._embedded_family(family) or ()
            if isinstance(value, Mapping):
                raise ValueError(
                    f"streaming family {family!r} is neither rows nor a descriptor"
                )
            for row in value:
                if isinstance(row, Mapping):
                    yield row
            return
        storage_kind = str(descriptor.get("storage_kind") or "")
        if storage_kind == "binary":
            yield from self._iter_binary(descriptor)
            return
        if self.row_source is None:
            raise ValueError(
                f"{storage_kind} family {family!r} requires an authoritative row source"
            )
        count = 0
        digest = sha256()
        semantic_bytes = 0
        for row in self.row_source(descriptor):
            semantic = _semantic_frame(row)
            digest.update(semantic)
            semantic_bytes += len(semantic)
            count += 1
            yield row
        if count != int(descriptor.get("record_count") or 0):
            raise ValueError(f"authoritative family count changed: {family}")
        if semantic_bytes != int(descriptor.get("byte_count") or 0):
            raise ValueError(f"authoritative family bytes changed: {family}")
        if digest.hexdigest() != str(descriptor.get("ordered_digest") or ""):
            raise ValueError(f"authoritative family digest changed: {family}")

    def iter_batches(
        self, family: str, *, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> Iterator[tuple[Mapping[str, Any], ...]]:
        yield from _batches(self.iter_rows(family), batch_size)

    def require_reference_backed(self) -> None:
        if self.build.get("schema_version") != REFERENCE_BUILD_SCHEMA_VERSION:
            raise ValueError("streaming build is not reference-backed")
        if not isinstance(self.build.get("family_manifests"), Mapping):
            raise ValueError("reference-backed build lacks family manifests")


__all__ = [
    "BINARY_FAMILY_ENCODING",
    "DEFAULT_BATCH_SIZE",
    "FAMILY_DESCRIPTOR_SCHEMA_VERSION",
    "REFERENCE_BUILD_SCHEMA_VERSION",
    "StreamingBuildReader",
    "family_descriptor",
    "is_family_descriptor",
]
