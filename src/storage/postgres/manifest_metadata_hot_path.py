"""Cheap scalar metadata access for in-process manifest persistence.

The production compiler hands persistence an ``InMemoryArtifactManifestReader``
that already retains the immutable artifact source as its sole rich carrier.
Walking the reconstructed record stream just to rediscover top-level scalar
fields is redundant when every scalar field is already primitive. Rich scalar
values fail closed to the established record-stream preflight so derived hashes
and persistence identities remain exact.
"""

from __future__ import annotations

from typing import Any, Mapping


_PRIMITIVE = (str, int, float, bool)


def execution_scalar_metadata(
    reader: Any, descriptor: Mapping[str, Any]
) -> dict[str, Any] | None:
    sources = getattr(reader, "_sources", None)
    if not isinstance(sources, Mapping):
        return None
    artifact_key = str(descriptor.get("artifact_key") or "")
    source = sources.get(artifact_key)
    if not isinstance(source, Mapping):
        return None

    metadata: dict[str, Any] = {}
    for field, value in source.items():
        # Lists/tuples are repeated manifest families, not mapping scalars.
        if isinstance(value, (list, tuple)):
            continue
        if value is None or isinstance(value, _PRIMITIVE):
            metadata[str(field)] = value
            continue
        # The old preflight includes every mapping_scalar value in metadata and
        # some callers hash that mapping. Never silently omit a rich scalar.
        return None
    return metadata


def install_descriptor_metadata_hot_path(compiler: Any) -> Any:
    """Use direct immutable scalar metadata for the PNF graph preflight."""

    original = compiler._descriptor_metadata

    def descriptor_metadata(reader: Any, descriptor: Mapping[str, Any]) -> dict[str, Any]:
        direct = execution_scalar_metadata(reader, descriptor)
        if direct is not None and "graph_ref" in direct:
            return direct
        return original(reader, descriptor)

    compiler._descriptor_metadata = descriptor_metadata
    return original


__all__ = ["execution_scalar_metadata", "install_descriptor_metadata_hot_path"]
