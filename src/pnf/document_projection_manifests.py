"""Immutable, execution-only projection partitions for one document.

Partitions retain parser/annotation products without becoming semantic
documents.  The document join below is deliberately the only place that may
accept all partitions together.  It validates ownership and returns refs for
the existing document-level typing, reduction, closure, and publication path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.language import AnnotationGraph
from src.pnf.document_fibres import DocumentFibre
from src.policy.carriers.canonical import canonical_sha256


DOCUMENT_PROJECTION_MANIFEST_SCHEMA_VERSION = "sl.document_projection_manifest.v0_1"
PARTITION_MANIFEST_SCHEMA_VERSION = "sl.projection_partition_manifest.v0_1"
LOGICAL_LAYER_MANIFEST_SCHEMA_VERSION = "sl.logical_layer_manifest.v0_1"


def _ref(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}:{canonical_sha256(payload)}"


def _record_ref(kind: str, row: Mapping[str, Any]) -> str:
    """Give legacy annotation rows stable content refs without serialising layers."""

    existing = row.get(f"{kind}_ref")
    if isinstance(existing, str) and existing:
        return existing
    if kind == "annotation_record":
        existing = row.get("span_ref") or row.get("relation_ref")
        if isinstance(existing, str) and existing:
            return existing
    return _ref(kind, dict(row))


def _annotation_rows(layer: Mapping[str, Any] | Any, name: str) -> Iterable[Any]:
    if isinstance(layer, Mapping):
        return layer.get(name) or ()
    return getattr(layer, name, ()) or ()


def _annotation_row_mapping(row: Mapping[str, Any] | Any) -> Mapping[str, Any] | None:
    if isinstance(row, Mapping):
        return row
    to_dict = getattr(row, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return None


def annotation_record_refs(layer: Mapping[str, Any] | Any) -> tuple[str, ...]:
    """Return deterministic record refs in logical layer order.

    This is intentionally independent of partition boundaries and avoids a
    whole-layer ``to_dict`` round trip for graph identity.
    """

    token_rows = sorted(
        (
            mapped
            for row in _annotation_rows(layer, "token_annotations")
            if (mapped := _annotation_row_mapping(row)) is not None
        ),
        key=lambda row: (
            int(row.get("token_index") or 0),
            str(row.get("annotation_type") or ""),
        ),
    )
    span_rows = sorted(
        (
            mapped
            for row in _annotation_rows(layer, "span_annotations")
            if (mapped := _annotation_row_mapping(row)) is not None
        ),
        key=lambda row: (
            int(row.get("start_token") or 0),
            int(row.get("end_token") or 0),
            str(row.get("span_ref") or ""),
        ),
    )
    relation_rows = sorted(
        (
            mapped
            for row in _annotation_rows(layer, "relation_annotations")
            if (mapped := _annotation_row_mapping(row)) is not None
        ),
        key=lambda row: str(row.get("relation_ref") or ""),
    )
    return tuple(
        _record_ref("annotation_record", row)
        for row in (*token_rows, *span_rows, *relation_rows)
    )


@dataclass(frozen=True)
class ProjectionPartitionManifest:
    partition_ref: str
    document_ref: str
    source_sha256: str
    carrier_ref: str
    build_key_sha256: str
    sequence_no: int
    owner_start: int
    owner_end: int
    context_start: int
    context_end: int
    parser_contract_ref: str
    reducer_contract_ref: str
    annotation_record_refs: tuple[str, ...]
    relation_record_refs: tuple[str, ...]
    parser_observation_refs: tuple[str, ...]
    layer_segment_refs: tuple[str, ...]
    relational_bundle_ref: str | None
    boundary_demand_refs: tuple[str, ...]
    counts: Mapping[str, int]
    schema_version: str = PARTITION_MANIFEST_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "partition_ref": self.partition_ref,
            "document_ref": self.document_ref,
            "source_sha256": self.source_sha256,
            "carrier_ref": self.carrier_ref,
            "build_key_sha256": self.build_key_sha256,
            "sequence_no": self.sequence_no,
            "owner_start": self.owner_start,
            "owner_end": self.owner_end,
            "context_start": self.context_start,
            "context_end": self.context_end,
            "parser_contract_ref": self.parser_contract_ref,
            "reducer_contract_ref": self.reducer_contract_ref,
            "annotation_record_refs": list(self.annotation_record_refs),
            "relation_record_refs": list(self.relation_record_refs),
            "parser_observation_refs": list(self.parser_observation_refs),
            "layer_segment_refs": list(self.layer_segment_refs),
            "relational_bundle_ref": self.relational_bundle_ref,
            "boundary_demand_refs": list(self.boundary_demand_refs),
            "counts": dict(sorted(self.counts.items())),
            "semantic_authority": "document_projection_join_only",
        }


@dataclass(frozen=True)
class LogicalLayerManifest:
    layer_ref: str
    document_ref: str
    source_sha256: str
    annotation_record_refs: tuple[str, ...]
    schema_version: str = LOGICAL_LAYER_MANIFEST_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "layer_ref": self.layer_ref,
            "document_ref": self.document_ref,
            "source_sha256": self.source_sha256,
            "annotation_record_refs": list(self.annotation_record_refs),
            "partition_independent": True,
        }


@dataclass(frozen=True)
class DocumentProjectionManifest:
    manifest_ref: str
    document_ref: str
    source_sha256: str
    carrier_ref: str
    build_key_sha256: str
    partition_refs: tuple[str, ...]
    logical_layer_refs: tuple[str, ...]
    graph_ref: str
    cross_part_demand_refs: tuple[str, ...]
    coverage_proof: Mapping[str, Any]
    schema_version: str = DOCUMENT_PROJECTION_MANIFEST_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_ref": self.manifest_ref,
            "document_ref": self.document_ref,
            "source_sha256": self.source_sha256,
            "carrier_ref": self.carrier_ref,
            "build_key_sha256": self.build_key_sha256,
            "partition_refs": list(self.partition_refs),
            "logical_layer_refs": list(self.logical_layer_refs),
            "graph_ref": self.graph_ref,
            "cross_part_demand_refs": list(self.cross_part_demand_refs),
            "coverage_proof": dict(self.coverage_proof),
            "semantic_authority": "document_projection_join",
        }


def build_logical_layer_manifest(
    *, document_ref: str, source_sha256: str, layer: Mapping[str, Any] | Any
) -> LogicalLayerManifest:
    refs = annotation_record_refs(layer)
    layer_ref = "logical-annotation-layer:" + canonical_sha256(
        {"document_ref": document_ref, "source_sha256": source_sha256, "records": refs}
    )
    return LogicalLayerManifest(layer_ref, document_ref, source_sha256, refs)


def build_partition_manifest(
    *,
    fibre: DocumentFibre,
    carrier_ref: str,
    source_sha256: str,
    build_key_sha256: str,
    parser_contract_ref: str,
    reducer_contract_ref: str,
    annotation_record_refs: Iterable[str] = (),
    relation_record_refs: Iterable[str] = (),
    parser_observation_refs: Iterable[str] = (),
    layer_segment_refs: Iterable[str] = (),
    relational_bundle_ref: str | None = None,
    boundary_demand_refs: Iterable[str] = (),
) -> ProjectionPartitionManifest:
    refs = tuple(sorted(set(annotation_record_refs)))
    relations = tuple(sorted(set(relation_record_refs)))
    observations = tuple(sorted(set(parser_observation_refs)))
    segments = tuple(sorted(set(layer_segment_refs)))
    demands = tuple(sorted(set(boundary_demand_refs)))
    identity = {
        "schema_version": PARTITION_MANIFEST_SCHEMA_VERSION,
        "document_ref": fibre.document_ref,
        "source_sha256": source_sha256,
        "carrier_ref": carrier_ref,
        "build_key_sha256": build_key_sha256,
        "fibre": fibre.to_dict(),
        "parser_contract_ref": parser_contract_ref,
        "reducer_contract_ref": reducer_contract_ref,
        "annotation_record_refs": refs,
        "relation_record_refs": relations,
        "parser_observation_refs": observations,
        "layer_segment_refs": segments,
        "relational_bundle_ref": relational_bundle_ref,
        "boundary_demand_refs": demands,
    }
    return ProjectionPartitionManifest(
        partition_ref=_ref("projection-partition", identity),
        document_ref=fibre.document_ref,
        source_sha256=source_sha256,
        carrier_ref=carrier_ref,
        build_key_sha256=build_key_sha256,
        sequence_no=fibre.sequence_no,
        owner_start=fibre.owner_start,
        owner_end=fibre.owner_end,
        context_start=fibre.context_start,
        context_end=fibre.context_end,
        parser_contract_ref=parser_contract_ref,
        reducer_contract_ref=reducer_contract_ref,
        annotation_record_refs=refs,
        relation_record_refs=relations,
        parser_observation_refs=observations,
        layer_segment_refs=segments,
        relational_bundle_ref=relational_bundle_ref,
        boundary_demand_refs=demands,
        counts={
            "annotations": len(refs),
            "relations": len(relations),
            "observations": len(observations),
            "boundary_demands": len(demands),
        },
    )


def partition_layer_records(
    *,
    layer: Mapping[str, Any] | Any,
    token_char_spans: Sequence[tuple[int, int]],
    fibre: DocumentFibre,
    partition_count: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Select exactly one owner for annotation and relation records.

    Tokens and spans use their start token's canonical character coordinate.
    Relations may have no coordinate in the annotation contract, so their
    stable relation ref selects one owner deterministically.  Context copies
    therefore never create another owned record.
    """

    def owned(token_index: object) -> bool:
        try:
            start, _end = token_char_spans[int(token_index)]
        except (IndexError, TypeError, ValueError):
            return False
        return fibre.owner_start <= start < fibre.owner_end

    annotation_rows = [
        mapped
        for row in _annotation_rows(layer, "token_annotations")
        if (mapped := _annotation_row_mapping(row)) is not None
        and owned(mapped.get("token_index"))
    ]
    annotation_rows.extend(
        mapped
        for row in _annotation_rows(layer, "span_annotations")
        if (mapped := _annotation_row_mapping(row)) is not None
        and owned(mapped.get("start_token"))
    )
    if partition_count < 1:
        raise ValueError("partition_count must be positive")
    relation_rows = [
        mapped
        for row in _annotation_rows(layer, "relation_annotations")
        if (mapped := _annotation_row_mapping(row)) is not None
        and int(
            canonical_sha256({"relation_ref": str(mapped.get("relation_ref") or "")})[:8],
            16,
        )
        % partition_count
        == fibre.sequence_no
    ]
    return annotation_record_refs(
        {"token_annotations": annotation_rows}
    ), annotation_record_refs({"relation_annotations": relation_rows})


def document_projection_join(
    *,
    partitions: Sequence[ProjectionPartitionManifest],
    logical_layers: Sequence[LogicalLayerManifest],
    canonical_length: int,
) -> DocumentProjectionManifest:
    """Validate immutable partition inputs and create the sole document join."""

    ordered = tuple(sorted(partitions, key=lambda row: row.sequence_no))
    if not ordered:
        raise ValueError("document projection join requires partitions")
    first = ordered[0]
    identity = (
        first.document_ref,
        first.source_sha256,
        first.carrier_ref,
        first.build_key_sha256,
    )
    if any(
        (row.document_ref, row.source_sha256, row.carrier_ref, row.build_key_sha256)
        != identity
        for row in ordered
    ):
        raise ValueError("partition manifests do not share document/build identity")
    cursor = 0
    coordinates: set[str] = set()
    for expected, partition in enumerate(ordered):
        if (
            partition.sequence_no != expected
            or partition.owner_start != cursor
            or partition.owner_end <= cursor
        ):
            raise ValueError("partition ownership is not contiguous exact coverage")
        cursor = partition.owner_end
        duplicate = coordinates.intersection(partition.annotation_record_refs)
        if duplicate:
            raise ValueError("duplicate owned annotation coordinates in partitions")
        coordinates.update(partition.annotation_record_refs)
    if cursor != canonical_length:
        raise ValueError("partition ownership does not cover canonical document")
    unresolved_overlaps = [
        row.partition_ref
        for row in ordered
        if (row.context_start < row.owner_start or row.context_end > row.owner_end)
        and not row.annotation_record_refs
        and not row.relation_record_refs
        and not row.boundary_demand_refs
    ]
    if unresolved_overlaps:
        raise ValueError(
            "overlap requires exactly-owned records or an explicit boundary demand: "
            + ", ".join(unresolved_overlaps)
        )
    layers = tuple(logical_layers)
    if not layers or any(
        row.document_ref != first.document_ref
        or row.source_sha256 != first.source_sha256
        for row in layers
    ):
        raise ValueError("logical layers do not match document identity")
    layer_refs = tuple(row.layer_ref for row in layers)
    graph = AnnotationGraph.from_layer_refs(layer_refs)
    demands = tuple(
        sorted({ref for row in ordered for ref in row.boundary_demand_refs})
    )
    coverage = {
        "owner_start": 0,
        "owner_end": canonical_length,
        "exactly_once": True,
        "owned_annotation_coordinates": len(coordinates),
        "overlap_validation": "exact_owner_or_boundary_demand",
    }
    manifest_identity = {
        "document_ref": first.document_ref,
        "source_sha256": first.source_sha256,
        "carrier_ref": first.carrier_ref,
        "build_key_sha256": first.build_key_sha256,
        "partition_refs": tuple(row.partition_ref for row in ordered),
        "logical_layer_refs": layer_refs,
        "graph_ref": graph.graph_ref,
        "cross_part_demand_refs": demands,
        "coverage_proof": coverage,
    }
    return DocumentProjectionManifest(
        manifest_ref=_ref("document-projection-manifest", manifest_identity),
        document_ref=first.document_ref,
        source_sha256=first.source_sha256,
        carrier_ref=first.carrier_ref,
        build_key_sha256=first.build_key_sha256,
        partition_refs=tuple(row.partition_ref for row in ordered),
        logical_layer_refs=layer_refs,
        graph_ref=graph.graph_ref,
        cross_part_demand_refs=demands,
        coverage_proof=coverage,
    )


__all__ = [
    "DOCUMENT_PROJECTION_MANIFEST_SCHEMA_VERSION",
    "LOGICAL_LAYER_MANIFEST_SCHEMA_VERSION",
    "PARTITION_MANIFEST_SCHEMA_VERSION",
    "DocumentProjectionManifest",
    "LogicalLayerManifest",
    "ProjectionPartitionManifest",
    "annotation_record_refs",
    "build_logical_layer_manifest",
    "build_partition_manifest",
    "document_projection_join",
    "partition_layer_records",
]
