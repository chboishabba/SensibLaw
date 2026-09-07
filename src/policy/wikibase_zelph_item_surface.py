"""Weld native Wikibase statements to a bounded Zelph graph view.

This adapter keeps two evidence planes separate:

* the revision-pinned Wikibase entity owns native statement semantics — GUID,
  mainsnak type/value, rank, qualifiers and references;
* the bounded Zelph/ITIR graph view owns graph-neighbourhood evidence and derived
  relation context.

The join is diagnostic. A complete Zelph graph view does not by itself certify
that a native Q/P statement family was completely inspected, and a missing
native statement is never rewritten as an explicit Wikidata ``novalue`` snak.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .domain_pressure import COVERAGE_STATES
from .external_graph_bridge import EXTERNAL_GRAPH_BRIDGE_SCHEMA_VERSION, normalize_graph_view
from .item_property_evidence import build_item_property_evidence_surface

WIKIBASE_ZELPH_ITEM_SURFACE_SCHEMA_VERSION = "sl.wikibase_zelph_item_surface.v0_2"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)]


def _entity_from_document(document: Mapping[str, Any], *, qid: str) -> Mapping[str, Any]:
    entities = document.get("entities")
    if isinstance(entities, Mapping):
        entity = entities.get(qid)
        if not isinstance(entity, Mapping):
            raise ValueError(f"entity export does not contain {qid}")
        return entity
    if _text(document.get("id")) != qid:
        raise ValueError(f"entity export id does not match {qid}")
    return document


def _value_payload(snak: Mapping[str, Any]) -> tuple[Any, str, str]:
    datatype = _text(snak.get("datatype")) or "unknown"
    datavalue = snak.get("datavalue")
    if not isinstance(datavalue, Mapping):
        return None, "", datatype
    value = deepcopy(datavalue.get("value"))
    value_ref = ""
    if isinstance(value, Mapping):
        value_ref = _text(value.get("id"))
        if not value_ref and "amount" in value:
            value_ref = _text(value.get("amount"))
        if not value_ref and "time" in value:
            value_ref = _text(value.get("time"))
    elif value is not None:
        value_ref = _text(value)
    return value, value_ref, datatype


def _qualifier_rows(qualifiers: Any) -> list[dict[str, str]]:
    if not isinstance(qualifiers, Mapping):
        return []
    rows: list[dict[str, str]] = []
    for property_id, snaks in sorted(qualifiers.items()):
        for snak in _mapping_rows(snaks):
            snak_type = _text(snak.get("snaktype")) or "value"
            _, value_ref, _ = _value_payload(snak)
            rows.append(
                {
                    "property_id": _text(property_id),
                    "value": value_ref if snak_type == "value" else snak_type,
                }
            )
    rows.sort(key=lambda row: (row["property_id"], row["value"]))
    return rows


def _reference_refs(statement_ref: str, references: Any) -> list[str]:
    refs: list[str] = []
    for index, reference in enumerate(_mapping_rows(references), start=1):
        native_hash = _text(reference.get("hash"))
        refs.append(native_hash or f"{statement_ref}#reference:{index}")
    return sorted(set(refs))


def native_statement_rows_from_entity_export(
    entity_document: Mapping[str, Any],
    *,
    subject_qid: str,
    entity_revision_ref: str,
) -> list[dict[str, Any]]:
    """Extract native statement bundles without assigning property absence."""

    qid = _text(subject_qid)
    revision = _text(entity_revision_ref)
    if not qid or not revision:
        raise ValueError("subject_qid and entity_revision_ref are required")
    if not isinstance(entity_document, Mapping):
        raise ValueError("entity_document must be a mapping")
    entity = _entity_from_document(entity_document, qid=qid)
    if _text(entity.get("id")) != qid:
        raise ValueError(f"entity export id does not match {qid}")
    observed_revision = _text(entity.get("lastrevid"))
    if observed_revision != revision:
        raise ValueError(
            f"entity export revision {observed_revision or '<missing>'} does not match {revision}"
        )

    rows: list[dict[str, Any]] = []
    claims = entity.get("claims")
    if not isinstance(claims, Mapping):
        return rows
    for property_id, statements in sorted(claims.items()):
        for index, statement in enumerate(_mapping_rows(statements), start=1):
            statement_ref = _text(statement.get("id")) or f"{qid}|{property_id}|{index}"
            mainsnak = statement.get("mainsnak")
            if not isinstance(mainsnak, Mapping):
                raise ValueError(f"native statement {statement_ref} has no mainsnak")
            snak_type = _text(mainsnak.get("snaktype")) or "value"
            value, value_ref, value_kind = _value_payload(mainsnak)
            rows.append(
                {
                    "statement_ref": statement_ref,
                    "property_id": _text(property_id),
                    "snak_type": snak_type,
                    "value": value,
                    "value_ref": value_ref,
                    "value_kind": value_kind,
                    "rank": _text(statement.get("rank")) or "normal",
                    "qualifiers": _qualifier_rows(statement.get("qualifiers")),
                    "reference_refs": _reference_refs(statement_ref, statement.get("references")),
                }
            )
    rows.sort(key=lambda row: (row["property_id"], row["statement_ref"]))
    return rows


def _normalize_property_coverage(
    *, required_property_ids: Sequence[str], property_coverage: Mapping[str, Any] | None
) -> dict[str, str]:
    supplied = property_coverage or {}
    result: dict[str, str] = {}
    for property_id in sorted({_text(value) for value in required_property_ids if _text(value)}):
        state = _text(supplied.get(property_id)) or "uninspected"
        if state not in COVERAGE_STATES:
            raise ValueError(f"unsupported property-family coverage state for {property_id}: {state}")
        result[property_id] = state
    return result


def build_wikibase_zelph_item_surface(
    *,
    entity_document: Mapping[str, Any],
    subject_qid: str,
    entity_revision_ref: str,
    graph_view: Mapping[str, Any],
    coverage_policy_ref: str,
    required_property_ids: Sequence[str],
    property_coverage: Mapping[str, Any] | None = None,
    derived_relations: Sequence[Mapping[str, Any]] = (),
    qualifier_specs: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    qualifier_profile_coverage_state: str = "uninspected",
    scope_specs: Mapping[str, Mapping[str, Any]] | None = None,
    scope_profile_coverage_state: str = "uninspected",
    revision_alignment_ref: str | None = None,
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build the preferred Nat item surface from native + graph evidence.

    ``revision_alignment_ref`` is required when the graph artifact revision and
    entity revision are different identifiers. It is a correspondence receipt,
    not a claim that the identifiers are definitionally equal.
    """

    qid = _text(subject_qid)
    entity_revision = _text(entity_revision_ref)
    policy_ref = _text(coverage_policy_ref)
    if not qid or not entity_revision or not policy_ref:
        raise ValueError("subject_qid, entity_revision_ref and coverage_policy_ref are required")

    normalized_graph = normalize_graph_view(graph_view)
    if _text(normalized_graph.get("schema_version")) != EXTERNAL_GRAPH_BRIDGE_SCHEMA_VERSION:
        raise ValueError("graph_view must normalize to the external graph bridge schema")
    graph_revision = _text(normalized_graph.get("artifact_revision"))
    alignment_ref = _text(revision_alignment_ref)
    if graph_revision and graph_revision != entity_revision and not alignment_ref:
        raise ValueError("different graph/entity revisions require revision_alignment_ref")

    statements = native_statement_rows_from_entity_export(
        entity_document,
        subject_qid=qid,
        entity_revision_ref=entity_revision,
    )
    required = sorted({_text(value) for value in required_property_ids if _text(value)})
    family_coverage = _normalize_property_coverage(
        required_property_ids=required,
        property_coverage=property_coverage,
    )

    # Item-wide coverage is deliberately conservative. Required Q/P families
    # control whether statement presence and truthy rank visibility are decidable.
    item_coverage = (
        "observed"
        if required and all(family_coverage.get(p) == "observed" for p in required)
        else "uninspected"
    )
    graph_ref = _text(normalized_graph.get("graph_view_id"))
    joined_evidence = sorted(
        {
            *(_text(value) for value in evidence_refs if _text(value)),
            *([graph_ref] if graph_ref else []),
            *([alignment_ref] if alignment_ref else []),
            f"wikibase:{qid}@{entity_revision}",
        }
    )

    surface = build_item_property_evidence_surface(
        subject_qid=qid,
        source_revision_ref=entity_revision,
        statements=statements,
        coverage_state=item_coverage,
        coverage_policy_ref=policy_ref,
        required_property_ids=required,
        property_coverage=family_coverage,
        qualifier_specs=qualifier_specs,
        qualifier_profile_coverage_state=qualifier_profile_coverage_state,
        scope_specs=scope_specs,
        scope_profile_coverage_state=scope_profile_coverage_state,
        derived_relations=derived_relations,
        evidence_refs=joined_evidence,
    )
    return {
        "schema_version": WIKIBASE_ZELPH_ITEM_SURFACE_SCHEMA_VERSION,
        "subject_qid": qid,
        "native_entity_revision_ref": entity_revision,
        "graph_artifact_revision_ref": graph_revision,
        "revision_alignment_ref": alignment_ref or None,
        "native_statement_plane": {
            "provider_id": "wikibase_entity_export",
            "statement_count": len(statements),
            "owns": ["statement_guid", "mainsnak", "rank", "qualifiers", "references"],
        },
        "graph_context_plane": {
            "provider_id": "zelph_bounded_graph",
            "graph_view_ref": graph_ref,
            "coverage_state": _text(normalized_graph.get("coverage_state")),
            "owns": ["bounded_adjacency", "graph_relation_context", "derived_relations"],
        },
        "item_surface": surface,
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }


__all__ = [
    "WIKIBASE_ZELPH_ITEM_SURFACE_SCHEMA_VERSION",
    "native_statement_rows_from_entity_export",
    "build_wikibase_zelph_item_surface",
]
