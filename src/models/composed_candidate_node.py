from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema
import yaml

COMPOSED_CANDIDATE_NODE_SCHEMA_VERSION = "sl.composed_candidate_node.v1"
COMPOSED_CANDIDATE_NODE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas" / "sl.composed_candidate_node.v1.schema.yaml"
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _copy_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _copy_jsonish(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_jsonish(item) for item in value]
    return value


def _normalize_kind_value(mapping: Mapping[str, Any]) -> dict[str, Any]:
    copied = _copy_jsonish(mapping)
    if not isinstance(copied, dict):
        return {}
    kind = copied.get("kind")
    if isinstance(kind, str):
        copied["kind"] = kind.strip()
    value = copied.get("value")
    if isinstance(value, str):
        copied["value"] = value.strip()
    return copied


def _copy_ref_list(values: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    copied: list[dict[str, Any]] = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, Mapping):
            raise ValueError(f"{field_name}[{index}] must be an object")
        kind = _as_text(value.get("kind"))
        ref_value = _as_text(value.get("value"))
        if not kind or not ref_value:
            raise ValueError(f"{field_name}[{index}] must include non-empty kind and value")
        copied.append(_normalize_kind_value(value))
    return copied


def _copy_text_list(values: Any, *, field_name: str) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    copied: list[str] = []
    for index, value in enumerate(values, start=1):
        text = _as_text(value)
        if not text:
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
        copied.append(text)
    return copied


@dataclass(frozen=True)
class ComposedCandidateNode:
    schema_version: str
    kind: str
    predicate_family: str
    slots: dict[str, Any]
    content_refs: list[dict[str, Any]]
    authority_wrapper: dict[str, Any]
    status: str
    support_phi_ids: list[str]
    span_refs: list[dict[str, Any]]
    provenance_receipts: list[dict[str, Any]]
    section: str
    genre: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "predicate_family": self.predicate_family,
            "slots": _copy_jsonish(self.slots),
            "content_refs": [_copy_jsonish(item) for item in self.content_refs],
            "authority_wrapper": _copy_jsonish(self.authority_wrapper),
            "status": self.status,
            "support_phi_ids": list(self.support_phi_ids),
            "span_refs": [_copy_jsonish(item) for item in self.span_refs],
            "provenance_receipts": [_copy_jsonish(item) for item in self.provenance_receipts],
            "section": self.section,
            "genre": self.genre,
        }


def load_composed_candidate_node_schema() -> dict[str, Any]:
    with COMPOSED_CANDIDATE_NODE_SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def validate_composed_candidate_node_dict(payload: Mapping[str, Any]) -> None:
    jsonschema.validate(payload, load_composed_candidate_node_schema())


def build_composed_candidate_node_dict(
    *,
    kind: Any,
    predicate_family: Any,
    slots: Mapping[str, Any] | None,
    content_refs: Sequence[Any] | None,
    authority_wrapper: Mapping[str, Any] | None,
    status: Any,
    support_phi_ids: Sequence[Any] | None,
    span_refs: Sequence[Any] | None,
    provenance_receipts: Sequence[Any] | None,
    section: Any,
    genre: Any,
    schema_version: Any = COMPOSED_CANDIDATE_NODE_SCHEMA_VERSION,
) -> dict[str, Any]:
    authority_mapping = _copy_mapping(authority_wrapper)
    if not authority_mapping:
        raise ValueError("authority_wrapper is required and must be a non-empty object")
    return ComposedCandidateNode(
        schema_version=_as_text(schema_version) or COMPOSED_CANDIDATE_NODE_SCHEMA_VERSION,
        kind=_as_text(kind),
        predicate_family=_as_text(predicate_family),
        slots=_copy_mapping(slots),
        content_refs=_copy_ref_list(content_refs, field_name="content_refs"),
        authority_wrapper=_normalize_kind_value(authority_mapping),
        status=_as_text(status),
        support_phi_ids=_copy_text_list(support_phi_ids, field_name="support_phi_ids"),
        span_refs=_copy_ref_list(span_refs, field_name="span_refs"),
        provenance_receipts=_copy_ref_list(provenance_receipts, field_name="provenance_receipts"),
        section=_as_text(section),
        genre=_as_text(genre),
    ).as_dict()


__all__ = [
    "COMPOSED_CANDIDATE_NODE_SCHEMA_PATH",
    "COMPOSED_CANDIDATE_NODE_SCHEMA_VERSION",
    "ComposedCandidateNode",
    "build_composed_candidate_node_dict",
    "load_composed_candidate_node_schema",
    "validate_composed_candidate_node_dict",
]
