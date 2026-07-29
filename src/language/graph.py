"""One shared graph view over immutable language annotation layers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Sequence

from .annotations import (
    AnnotationLayer,
    RelationAnnotation,
    SpanAnnotation,
    TokenAnnotation,
)


@dataclass(frozen=True)
class AnnotationGraph:
    graph_ref: str
    layers: tuple[AnnotationLayer, ...]

    @classmethod
    def from_layers(cls, layers: Sequence[AnnotationLayer]) -> "AnnotationGraph":
        """Build a graph whose identity is the ordered immutable layer references.

        Annotation layers are already content-addressed.  Re-serialising their
        complete annotation payload here duplicates the largest parser product
        at precisely the point where the projection still retains its working
        structures.
        """

        layer_tuple = tuple(layers)
        if not layer_tuple:
            raise ValueError("annotation graph requires at least one layer")
        layer_refs = tuple(layer.layer_ref for layer in layer_tuple)
        if any(not isinstance(ref, str) or not ref for ref in layer_refs):
            raise ValueError(
                "annotation graph layers require non-empty layer_ref values"
            )
        if len(set(layer_refs)) != len(layer_refs):
            raise ValueError("annotation graph layer_ref values must be distinct")
        return cls(
            graph_ref=cls._graph_ref(layer_refs),
            layers=layer_tuple,
        )

    @staticmethod
    def _graph_ref(layer_refs: Sequence[str]) -> str:
        """Return the graph identity without reading layer payloads."""

        identity = json.dumps(
            {"layer_refs": tuple(layer_refs)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "annotation-graph:" + hashlib.sha256(identity).hexdigest()

    @classmethod
    def from_layer_refs(cls, layer_refs: Sequence[str]) -> "AnnotationGraph":
        """Construct a reference-only graph manifest.

        Partitioned readers use this form so graph identity never requires an
        in-memory annotation-layer payload.  ``from_layers`` remains the
        compatibility constructor for in-memory callers.
        """

        refs = tuple(layer_refs)
        if not refs:
            raise ValueError("annotation graph requires at least one layer_ref")
        if any(not isinstance(ref, str) or not ref for ref in refs):
            raise ValueError("annotation graph layer_ref values must be non-empty")
        if len(set(refs)) != len(refs):
            raise ValueError("annotation graph layer_ref values must be distinct")
        return cls(graph_ref=cls._graph_ref(refs), layers=())

    def token_annotations(
        self, annotation_type: str | None = None
    ) -> tuple[TokenAnnotation, ...]:
        rows = tuple(row for layer in self.layers for row in layer.token_annotations)
        if annotation_type is not None:
            rows = tuple(row for row in rows if row.annotation_type == annotation_type)
        return tuple(
            sorted(rows, key=lambda row: (row.token_index, row.annotation_type))
        )

    def span_annotations(
        self, annotation_type: str | None = None
    ) -> tuple[SpanAnnotation, ...]:
        rows = tuple(row for layer in self.layers for row in layer.span_annotations)
        if annotation_type is not None:
            rows = tuple(row for row in rows if row.annotation_type == annotation_type)
        return tuple(
            sorted(rows, key=lambda row: (row.start_token, row.end_token, row.span_ref))
        )

    def relation_annotations(
        self, relation_type: str | None = None
    ) -> tuple[RelationAnnotation, ...]:
        rows = tuple(row for layer in self.layers for row in layer.relation_annotations)
        if relation_type is not None:
            rows = tuple(row for row in rows if row.relation_type == relation_type)
        return tuple(sorted(rows, key=lambda row: row.relation_ref))
