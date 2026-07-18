"""Immutable projections over a shared token stream.

The token stream may be produced by spaCy or another tokenizer. Annotation
layers never mutate token extension attributes and never select semantic
interpretations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_mapping, canonical_refs, require_text


@dataclass(frozen=True)
class TokenAnnotation:
    token_index: int
    annotation_type: str
    value: Any
    provenance_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        if self.token_index < 0:
            raise ValueError("token_index must be non-negative")
        return {
            "token_index": self.token_index,
            "annotation_type": require_text(self.annotation_type, "annotation_type"),
            "value": self.value,
            "provenance_refs": list(canonical_refs(self.provenance_refs)),
        }


@dataclass(frozen=True)
class SpanAnnotation:
    span_ref: str
    start_token: int
    end_token: int
    annotation_type: str
    value: Any
    provenance_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        if self.start_token < 0 or self.end_token <= self.start_token:
            raise ValueError("span token range must be non-empty")
        return {
            "span_ref": require_text(self.span_ref, "span_ref"),
            "start_token": self.start_token,
            "end_token": self.end_token,
            "annotation_type": require_text(self.annotation_type, "annotation_type"),
            "value": self.value,
            "provenance_refs": list(canonical_refs(self.provenance_refs)),
        }


@dataclass(frozen=True)
class RelationAnnotation:
    relation_ref: str
    relation_type: str
    left_ref: str
    right_ref: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    provenance_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_ref": require_text(self.relation_ref, "relation_ref"),
            "relation_type": require_text(self.relation_type, "relation_type"),
            "left_ref": require_text(self.left_ref, "left_ref"),
            "right_ref": require_text(self.right_ref, "right_ref"),
            "payload": canonical_mapping(self.payload),
            "provenance_refs": list(canonical_refs(self.provenance_refs)),
        }


@dataclass(frozen=True)
class AnnotationLayer:
    layer_ref: str
    tokenizer_ref: str
    text_sha256: str
    token_annotations: tuple[TokenAnnotation, ...] = ()
    span_annotations: tuple[SpanAnnotation, ...] = ()
    relation_annotations: tuple[RelationAnnotation, ...] = ()
    provenance_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "sl.annotation_layer.v0_1",
            "layer_ref": require_text(self.layer_ref, "layer_ref"),
            "tokenizer_ref": require_text(self.tokenizer_ref, "tokenizer_ref"),
            "text_sha256": require_text(self.text_sha256, "text_sha256"),
            "token_annotations": [
                row.to_dict()
                for row in sorted(
                    self.token_annotations,
                    key=lambda value: (value.token_index, value.annotation_type),
                )
            ],
            "span_annotations": [
                row.to_dict()
                for row in sorted(
                    self.span_annotations,
                    key=lambda value: (value.start_token, value.end_token, value.span_ref),
                )
            ],
            "relation_annotations": [
                row.to_dict()
                for row in sorted(
                    self.relation_annotations, key=lambda value: value.relation_ref
                )
            ],
            "provenance_refs": list(canonical_refs(self.provenance_refs)),
            "authority": "annotation_only",
        }
