"""Cheap scalar metadata access for in-process manifest persistence.

The production compiler hands persistence an ``InMemoryArtifactManifestReader``
that already retains the immutable artifact source as its sole rich carrier.
Walking the reconstructed record stream just to rediscover top-level primitive
fields (for example ``graph_ref`` or annotation ``layer_ref``) is therefore
redundant. Read those primitive fields directly when that source is available;
other reader implementations fail closed to their existing verified/preflight
path.
"""

from __future__ import annotations

from typing import Any, Mapping


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
    return {
        str(field): value
        for field, value in source.items()
        if value is None or isinstance(value, (str, int, float, bool))
    }


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
