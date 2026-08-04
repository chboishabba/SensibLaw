"""Bounded access to embedded or reference-backed streaming-build families.

The compiler may expose small fixtures inline, while exact documents expose
content-addressed family descriptors.  Consumers use this module rather than
assuming every family is a document-sized Python list.  JSONL is supported as a
transitional local transport; PostgreSQL/object descriptors require an injected
row source and remain authoritative through their manifest identity.
"""

from __future__ import annotations

from hashlib import sha256
from itertools import islice
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence


FAMILY_DESCRIPTOR_SCHEMA_VERSION = "sensiblaw.streaming-family-descriptor.v1"
REFERENCE_BUILD_SCHEMA_VERSION = "sensiblaw.reference-streaming-build.v1"
DEFAULT_BATCH_SIZE = 256
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
    encoding_ref: str = "canonical-jsonl:v1",
) -> dict[str, Any]:
    if record_count < 0 or byte_count < 0:
        raise ValueError("family counts must be non-negative")
    if storage_kind not in {"jsonl", "postgresql", "object"}:
        raise ValueError("unsupported family storage kind")
    if storage_kind == "jsonl" and not path:
        raise ValueError("JSONL family descriptor requires a path")
    if storage_kind != "jsonl" and not manifest_ref:
        raise ValueError("authoritative family descriptor requires a manifest ref")
    return {
        "schema_version": FAMILY_DESCRIPTOR_SCHEMA_VERSION,
        "family": str(family),
        "storage_kind": storage_kind,
        "record_count": int(record_count),
        "byte_count": int(byte_count),
        "ordered_digest": str(ordered_digest),
        "encoding_ref": str(encoding_ref),
        "path": path,
        "manifest_ref": manifest_ref,
        "segment_refs": list(segment_refs),
    }


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

    def _iter_jsonl(
        self, descriptor: Mapping[str, Any]
    ) -> Iterator[Mapping[str, Any]]:
        path = self._resolve_path(descriptor)
        digest = sha256()
        count = 0
        byte_count = 0
        with path.open("rb") as handle:
            for encoded in handle:
                if not encoded.strip():
                    continue
                digest.update(encoded)
                byte_count += len(encoded)
                value = json.loads(encoded)
                if not isinstance(value, Mapping):
                    raise ValueError(f"family row is not a mapping: {path}")
                count += 1
                yield dict(value)
        if count != int(descriptor.get("record_count") or 0):
            raise ValueError(f"family row count changed: {path}")
        if byte_count != int(descriptor.get("byte_count") or 0):
            raise ValueError(f"family byte count changed: {path}")
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
        if storage_kind == "jsonl":
            yield from self._iter_jsonl(descriptor)
            return
        if self.row_source is None:
            raise ValueError(
                f"{storage_kind} family {family!r} requires an authoritative row source"
            )
        count = 0
        digest = sha256()
        byte_count = 0
        for row in self.row_source(descriptor):
            canonical = (
                json.dumps(
                    dict(row),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            digest.update(canonical)
            byte_count += len(canonical)
            count += 1
            yield row
        if count != int(descriptor.get("record_count") or 0):
            raise ValueError(f"authoritative family count changed: {family}")
        if byte_count != int(descriptor.get("byte_count") or 0):
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
    "DEFAULT_BATCH_SIZE",
    "FAMILY_DESCRIPTOR_SCHEMA_VERSION",
    "REFERENCE_BUILD_SCHEMA_VERSION",
    "StreamingBuildReader",
    "family_descriptor",
    "is_family_descriptor",
]
