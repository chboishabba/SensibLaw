"""One shared graph view over immutable language annotation layers."""

from __future__ import annotations

from dataclasses import dataclass

from .annotations import AnnotationLayer, RelationAnnotation, SpanAnnotation, TokenAnnotation


@dataclass(frozen=True)
class AnnotationGraph:
    graph_ref: str
    layers: tuple[AnnotationLayer, ...]

    def token_annotations(self, annotation_type: str | None = None) -> tuple[TokenAnnotation, ...]:
        rows = tuple(row for layer in self.layers for row in layer.token_annotations)
        if annotation_type is not None:
            rows = tuple(row for row in rows if row.annotation_type == annotation_type)
        return tuple(sorted(rows, key=lambda row: (row.token_index, row.annotation_type)))

    def span_annotations(self, annotation_type: str | None = None) -> tuple[SpanAnnotation, ...]:
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
