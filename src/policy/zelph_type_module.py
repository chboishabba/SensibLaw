"""Conservative bounded P31/P279 type-module adapter for Zelph graph evidence.

This is graph-context only. It never reconstructs native Wikibase statements.
Positive retained relations may be used when the pruned artifact has a soundness
receipt for the declared type query family. Negative/type-absence conclusions
require sound+complete preservation for that same family.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .external_graph_bridge import EXTERNAL_GRAPH_BRIDGE_SCHEMA_VERSION, normalize_graph_view
from .pruned_graph_preservation import (
    PRUNED_GRAPH_PRESERVATION_SCHEMA_VERSION,
    preservation_allows_absence,
)

ZELPH_TYPE_MODULE_SCHEMA_VERSION = "sl.zelph_type_module.v0_1"
TYPE_RELATIONS = frozenset({"P31", "P279"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_zelph_type_module(
    *,
    subject_qid: str,
    graph_view: Mapping[str, Any],
    relation_observations: Sequence[Mapping[str, Any]],
    preservation_receipt: Mapping[str, Any],
    query_family_ref: str = "query:p31-p279-type-closure",
    module_receipt_ref: str,
) -> dict[str, Any]:
    qid = _text(subject_qid)
    family = _text(query_family_ref)
    module_ref = _text(module_receipt_ref)
    if not qid or not family or not module_ref:
        raise ValueError("subject_qid, query_family_ref and module_receipt_ref are required")

    graph = normalize_graph_view(graph_view)
    if _text(graph.get("schema_version")) != EXTERNAL_GRAPH_BRIDGE_SCHEMA_VERSION:
        raise ValueError("graph_view must normalize to the external graph bridge schema")
    if _text(preservation_receipt.get("schema_version")) != PRUNED_GRAPH_PRESERVATION_SCHEMA_VERSION:
        raise ValueError("type module requires a pruned graph preservation receipt")
    if _text(preservation_receipt.get("query_family_ref")) != family:
        raise ValueError("preservation receipt query family does not match type module")
    if not bool(preservation_receipt.get("sound_for_positive_answers")):
        raise ValueError("type module requires sound preservation for positive answers")

    relations: list[dict[str, str]] = []
    for raw in relation_observations:
        if not isinstance(raw, Mapping):
            continue
        property_id = _text(raw.get("property_id") or raw.get("property"))
        object_ref = _text(raw.get("object_ref") or raw.get("object"))
        source_ref = _text(raw.get("source_ref") or raw.get("subject_ref")) or qid
        if property_id not in TYPE_RELATIONS:
            raise ValueError(f"type module relation must be P31 or P279, got {property_id}")
        if not object_ref:
            raise ValueError("type module relation requires object_ref")
        relations.append(
            {
                "source_ref": source_ref,
                "property_id": property_id,
                "object_ref": object_ref,
                "origin": _text(raw.get("origin")) or "graph_observed",
            }
        )
    relations.sort(key=lambda row: (row["source_ref"], row["property_id"], row["object_ref"]))

    return {
        "schema_version": ZELPH_TYPE_MODULE_SCHEMA_VERSION,
        "subject_qid": qid,
        "graph_view_ref": _text(graph.get("graph_view_id")),
        "graph_artifact_revision_ref": _text(graph.get("artifact_revision")),
        "query_family_ref": family,
        "module_receipt_ref": module_ref,
        "relations": relations,
        "positive_answers_sound": True,
        "negative_answers_complete": preservation_allows_absence(
            preservation_receipt, query_family_ref=family
        ),
        "native_statement_authority": False,
        "truth_authority": False,
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
        "preservation_receipt": deepcopy(dict(preservation_receipt)),
    }


def type_absence_is_admissible(module: Mapping[str, Any]) -> bool:
    return bool(
        _text(module.get("schema_version")) == ZELPH_TYPE_MODULE_SCHEMA_VERSION
        and module.get("negative_answers_complete") is True
    )


__all__ = [
    "ZELPH_TYPE_MODULE_SCHEMA_VERSION",
    "TYPE_RELATIONS",
    "build_zelph_type_module",
    "type_absence_is_admissible",
]
