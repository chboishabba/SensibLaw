"""Normalized machine-facing relation observations from a routed Zelph execution.

ITIR's bounded graph-slice surface is a transport PLAN, not a query result, and
Zelph's current `.out` / `.in` commands are human-facing REPL operations.  This
carrier therefore begins *after* a routed execution has produced explicit
relation rows.  It deliberately does not parse terminal text.

The carrier is diagnostic-only.  It records the exact graph view, execution
receipt, selectors and relation rows that a downstream conservative module may
consume.  It creates no native Wikibase statement, truth, support, promotion or
edit authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .external_graph_bridge import EXTERNAL_GRAPH_BRIDGE_SCHEMA_VERSION, normalize_graph_view

ZELPH_ROUTED_RELATION_OBSERVATIONS_SCHEMA_VERSION = (
    "sl.zelph_routed_relation_observations.v0_1"
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strings(values: Sequence[Any]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def build_zelph_routed_relation_observations(
    *,
    graph_view: Mapping[str, Any],
    execution_receipt_ref: str,
    relation_rows: Sequence[Mapping[str, Any]],
    selectors: Sequence[str] = (),
    query_family_ref: str,
    subject_qid: str,
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Normalize explicit routed graph rows without reconstructing native claims."""

    graph = normalize_graph_view(graph_view)
    if _text(graph.get("schema_version")) != EXTERNAL_GRAPH_BRIDGE_SCHEMA_VERSION:
        raise ValueError("graph_view must normalize to the external graph bridge schema")

    execution_ref = _text(execution_receipt_ref)
    family = _text(query_family_ref)
    qid = _text(subject_qid)
    if not execution_ref or not family or not qid:
        raise ValueError(
            "execution_receipt_ref, query_family_ref and subject_qid are required"
        )

    normalized: list[dict[str, str]] = []
    for raw in relation_rows:
        if not isinstance(raw, Mapping):
            continue
        source_ref = _text(raw.get("source_ref") or raw.get("subject_ref")) or qid
        property_id = _text(raw.get("property_id") or raw.get("property"))
        object_ref = _text(raw.get("object_ref") or raw.get("object"))
        direction = _text(raw.get("direction")) or "out"
        if not property_id or not object_ref:
            raise ValueError("routed relation row requires property_id and object_ref")
        if direction not in {"out", "in"}:
            raise ValueError("routed relation direction must be out or in")
        normalized.append(
            {
                "source_ref": source_ref,
                "property_id": property_id,
                "object_ref": object_ref,
                "direction": direction,
                "origin": _text(raw.get("origin")) or "zelph_graph_observed",
            }
        )
    normalized.sort(
        key=lambda row: (
            row["source_ref"],
            row["property_id"],
            row["object_ref"],
            row["direction"],
        )
    )

    return {
        "schema_version": ZELPH_ROUTED_RELATION_OBSERVATIONS_SCHEMA_VERSION,
        "subject_qid": qid,
        "query_family_ref": family,
        "graph_view_ref": _text(graph.get("graph_view_id")),
        "graph_artifact_revision_ref": _text(graph.get("artifact_revision")),
        "execution_receipt_ref": execution_ref,
        "selectors": _strings(selectors),
        "relations": normalized,
        "evidence_refs": _strings([*evidence_refs, execution_ref]),
        "native_statement_authority": False,
        "truth_authority": False,
        "support_authority": False,
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
        "source_contract": "normalized_post_execution_relation_rows",
    }


def type_relation_rows(
    routed_observations: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Project only P31/P279 rows for the conservative type-module consumer."""

    if (
        _text(routed_observations.get("schema_version"))
        != ZELPH_ROUTED_RELATION_OBSERVATIONS_SCHEMA_VERSION
    ):
        raise ValueError("type projection requires routed Zelph relation observations")
    rows: list[dict[str, str]] = []
    for raw in routed_observations.get("relations") or ():
        if not isinstance(raw, Mapping):
            continue
        property_id = _text(raw.get("property_id"))
        if property_id not in {"P31", "P279"}:
            continue
        rows.append(
            {
                "source_ref": _text(raw.get("source_ref")),
                "property_id": property_id,
                "object_ref": _text(raw.get("object_ref")),
                "origin": _text(raw.get("origin")) or "zelph_graph_observed",
            }
        )
    return deepcopy(rows)


__all__ = [
    "ZELPH_ROUTED_RELATION_OBSERVATIONS_SCHEMA_VERSION",
    "build_zelph_routed_relation_observations",
    "type_relation_rows",
]
