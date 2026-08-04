"""Versioned, bounded artifact projection contracts.

The compiler owns semantics; this module only selects how completed immutable
artifacts cross the compilation boundary.  Production exposes descriptors and
an iterable reader.  Explicit compatibility mode exposes legacy materialised
values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from itertools import islice
import json
from typing import Any, Iterator, Mapping, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from src.runtime.execution_resource_ledger import ExecutionResourceLedger

from src.policy.carriers.canonical import canonical_sha256


ARTIFACT_DESCRIPTOR_SCHEMA_VERSION = "sl.artifact_descriptor.v1"
ARTIFACT_READER_CONTRACT = "sensiblaw.manifest-reader.iter-records.v1"
MANIFEST_ARTIFACT_KEYS = frozenset(
    {
        "annotation_layer",
        "semantic_annotation_layer",
        "relational_bundle",
        "pnf_graph",
        "refined_pnf_graph",
        "resolution_demands",
        "factor_refinements",
        "local_evidence",
        "typed_meets",
        "binding_candidate_sets",
        "binding_candidate_set_builds",
        "factor_anchors",
        "canonical_token_rows",
    }
)


class ArtifactRepresentation(str, Enum):
    MANIFEST = "manifest"
    MATERIALISED = "materialised"


@dataclass(frozen=True)
class ArtifactProjectionPolicy:
    """Injected artifact representation policy; never inferred from size."""

    representation: ArtifactRepresentation = ArtifactRepresentation.MANIFEST

    @classmethod
    def production(cls) -> "ArtifactProjectionPolicy":
        return cls(ArtifactRepresentation.MANIFEST)

    @classmethod
    def materialised_compatibility(cls) -> "ArtifactProjectionPolicy":
        return cls(ArtifactRepresentation.MATERIALISED)


@dataclass(frozen=True)
class ArtifactDescriptor:
    artifact_key: str
    manifest_ref: str
    root_ref: str
    ordered_digest: str
    record_count: int
    reader_contract: str = ARTIFACT_READER_CONTRACT
    representation: str = "manifest"
    schema_version: str = ARTIFACT_DESCRIPTOR_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "representation": self.representation,
            "artifact_key": self.artifact_key,
            "manifest_ref": self.manifest_ref,
            "root_ref": self.root_ref,
            "ordered_digest": self.ordered_digest,
            "record_count": self.record_count,
            "reader_contract": self.reader_contract,
        }


class ArtifactManifestReader(Protocol):
    def iter_records(
        self, artifact_key: str, batch_size: int = 256
    ) -> Iterator[tuple[Mapping[str, Any], ...]]: ...

    def materialise(self, artifact_key: str) -> Any: ...


def iter_verified_records(
    reader: ArtifactManifestReader,
    descriptor: Mapping[str, Any],
    *,
    batch_size: int = 256,
) -> Iterator[tuple[Mapping[str, Any], ...]]:
    """Yield a descriptor stream and verify its exact ordered identity at EOF."""

    if batch_size < 1 or batch_size > 256:
        raise ValueError("record batch size must be between 1 and 256")
    digest = hashlib.sha256()
    digest.update(b"[")
    count = 0
    artifact_key = str(descriptor["artifact_key"])
    for batch in reader.iter_records(artifact_key, batch_size):
        if len(batch) > batch_size:
            raise ValueError("manifest reader exceeded requested batch size")
        for record in batch:
            if count:
                digest.update(b",")
            digest.update(
                json.dumps(
                    record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            )
            count += 1
        yield batch
    digest.update(b"]")
    if count != int(descriptor["record_count"]):
        raise ValueError(f"record count mismatch for artifact {artifact_key!r}")
    if digest.hexdigest() != str(descriptor["ordered_digest"]):
        raise ValueError(f"ordered digest mismatch for artifact {artifact_key!r}")


def _records(value: Any) -> Iterator[dict[str, Any]]:
    """Emit ordered record families plus enough data to reconstruct them.

    A record is deliberately not an opaque whole-artifact field: ``family``
    names the logical collection, ``ordinal`` gives stable ordering, and the
    reconstruction metadata records whether the value is scalar, mapping, or
    a repeated member.  This makes the same descriptor usable by bounded
    writers and the explicit legacy materialiser.
    """

    if isinstance(value, Mapping):
        for field in sorted(value):
            field_value = value[field]
            if isinstance(field_value, (list, tuple)):
                for index, item in enumerate(field_value):
                    yield {
                        "family": str(field),
                        "ordinal": index,
                        "field": str(field),
                        "index": index,
                        "value": item,
                        "reconstruction": "mapping_repeated_member",
                    }
            else:
                yield {
                    "family": str(field),
                    "ordinal": 0,
                    "field": str(field),
                    "value": field_value,
                    "reconstruction": "mapping_scalar",
                }
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield {
                "family": "rows",
                "ordinal": index,
                "index": index,
                "value": item,
                "reconstruction": "sequence_member",
            }
        return
    yield {"family": "value", "ordinal": 0, "value": value, "reconstruction": "scalar"}


def _materialise(records: Iterator[Mapping[str, Any]]) -> Any:
    first: Mapping[str, Any] | None = None
    result: dict[str, Any] = {}
    sequence: list[tuple[int, Any]] = []
    scalar: Any = None
    for row in records:
        first = first or row
        if "field" not in row:
            if "index" in row:
                sequence.append((int(row["index"]), row.get("value")))
            else:
                scalar = row.get("value")
            continue
        field = str(row["field"])
        if "index" not in row:
            result[field] = row.get("value")
            continue
        result.setdefault(field, []).append((int(row["index"]), row.get("value")))
    if first is None:
        return {}
    if "field" not in first:
        if sequence:
            return [item for _index, item in sorted(sequence)]
        return scalar
    for field, value in tuple(result.items()):
        if isinstance(value, list) and value and isinstance(value[0], tuple):
            result[field] = [item for _index, item in sorted(value)]
    return result


class InMemoryArtifactManifestReader:
    """Bounded reader used between compilation and persistence.

    PostgreSQL readers implement the same contract for completed builds.
    """

    def __init__(self, sources_by_key: Mapping[str, Any]):
        # Keep the compiler-owned artifact family as the sole retained source.
        # In particular, do not retain a second tuple containing every emitted
        # manifest record: large documents otherwise briefly hold both shapes.
        self._sources = dict(sources_by_key)
        self._resource_ledger: ExecutionResourceLedger | None = None

    def attach_resource_ledger(self, ledger: "ExecutionResourceLedger") -> None:
        """Attach observational telemetry without changing the source shape."""

        self._resource_ledger = ledger

    def _iter(self, artifact_key: str) -> Iterator[dict[str, Any]]:
        return _records(self._sources[artifact_key])

    def iter_records(
        self, artifact_key: str, batch_size: int = 256
    ) -> Iterator[tuple[Mapping[str, Any], ...]]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if artifact_key not in self._sources:
            return
        iterator = self._iter(artifact_key)
        while batch := tuple(islice(iterator, batch_size)):
            if self._resource_ledger is not None:
                self._resource_ledger.batch(
                    f"manifest_replay:{artifact_key}",
                    rows=len(batch),
                    payload_bytes=sum(
                        len(
                            json.dumps(
                                row, sort_keys=True, separators=(",", ":")
                            ).encode("utf-8")
                        )
                        for row in batch
                    ),
                )
            yield batch

    def materialise(self, artifact_key: str) -> Any:
        # This intentionally remains an explicit debug/legacy operation.
        return _materialise(self._iter(artifact_key))

    def verify(self, descriptor: Mapping[str, Any], *, batch_size: int = 256) -> None:
        """Check a descriptor while consuming its repeatable ordered stream."""

        artifact_key = str(descriptor["artifact_key"])
        count, digest = _record_stream_digest(self._iter(artifact_key))
        if count != int(descriptor["record_count"]):
            raise ValueError(f"record count mismatch for artifact {artifact_key!r}")
        if digest != str(descriptor["ordered_digest"]):
            raise ValueError(f"ordered digest mismatch for artifact {artifact_key!r}")


def _record_stream_digest(records: Iterator[Mapping[str, Any]]) -> tuple[int, str]:
    """Return the canonical JSON-list digest without retaining its records."""

    digest = hashlib.sha256()
    digest.update(b"[")
    count = 0
    for record in records:
        if count:
            digest.update(b",")
        digest.update(
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        count += 1
    digest.update(b"]")
    return count, digest.hexdigest()


def reconstruct_artifact(
    artifacts: Mapping[str, Any],
    artifact_key: str,
    reader: ArtifactManifestReader | None,
) -> Any:
    """Reconstruct an artifact for a legacy semantic consumer.

    Production persistence uses record batches where a family has a native
    writer.  This small bridge exists for the remaining legacy semantic
    consumers and, unlike ``materialise_artifact``, is not a public debug API.
    """

    value = artifacts.get(artifact_key)
    if not isinstance(value, Mapping) or value.get("representation") != "manifest":
        return value
    if reader is None:
        raise ValueError(f"manifest artifact {artifact_key!r} requires a reader")

    def records() -> Iterator[Mapping[str, Any]]:
        yield from (
            row for batch in iter_verified_records(reader, value) for row in batch
        )

    return _materialise(records())


def project_artifacts(
    artifacts: Mapping[str, Any],
    *,
    policy: ArtifactProjectionPolicy,
    resource_ledger: "ExecutionResourceLedger | None" = None,
) -> tuple[dict[str, Any], ArtifactManifestReader | None]:
    if policy.representation is ArtifactRepresentation.MATERIALISED:
        return dict(artifacts), None
    projected = dict(artifacts)
    sources_by_key: dict[str, Any] = {}
    for artifact_key in sorted(MANIFEST_ARTIFACT_KEYS.intersection(artifacts)):
        source = artifacts[artifact_key]
        if resource_ledger is not None:
            resource_ledger.sample(
                f"descriptor_generation:{artifact_key}",
                phase="descriptor_generation",
                details={"artifact_key": artifact_key, "operation": "digest"},
            )
        record_count, ordered_digest = _record_stream_digest(_records(source))
        root_ref = f"artifact-root:{artifact_key}:{ordered_digest}"
        manifest_identity = {
            "schema_version": ARTIFACT_DESCRIPTOR_SCHEMA_VERSION,
            "artifact_key": artifact_key,
            "root_ref": root_ref,
            "ordered_digest": ordered_digest,
            "record_count": record_count,
            "reader_contract": ARTIFACT_READER_CONTRACT,
        }
        descriptor = ArtifactDescriptor(
            artifact_key=artifact_key,
            manifest_ref="artifact-manifest:" + canonical_sha256(manifest_identity),
            root_ref=root_ref,
            ordered_digest=ordered_digest,
            record_count=record_count,
        )
        projected[artifact_key] = descriptor.to_dict()
        sources_by_key[artifact_key] = source
        if resource_ledger is not None:
            resource_ledger.sample(
                f"descriptor_generation:{artifact_key}:complete",
                phase="descriptor_generation",
                details={"artifact_key": artifact_key, "record_count": record_count},
            )
    reader = InMemoryArtifactManifestReader(sources_by_key)
    if resource_ledger is not None:
        reader.attach_resource_ledger(resource_ledger)
    return projected, reader


def materialise_artifact(
    artifacts: Mapping[str, Any],
    artifact_key: str,
    reader: ArtifactManifestReader | None,
) -> Any:
    value = artifacts.get(artifact_key)
    if not isinstance(value, Mapping) or value.get("representation") != "manifest":
        return value
    if reader is None:
        raise ValueError(f"manifest artifact {artifact_key!r} requires a reader")
    return reconstruct_artifact(artifacts, artifact_key, reader)


__all__ = [
    "ARTIFACT_DESCRIPTOR_SCHEMA_VERSION",
    "ARTIFACT_READER_CONTRACT",
    "MANIFEST_ARTIFACT_KEYS",
    "ArtifactDescriptor",
    "ArtifactManifestReader",
    "ArtifactProjectionPolicy",
    "ArtifactRepresentation",
    "InMemoryArtifactManifestReader",
    "iter_verified_records",
    "materialise_artifact",
    "project_artifacts",
    "reconstruct_artifact",
]
