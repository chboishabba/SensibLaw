"""Revision-bound Wikidata item/property evidence for governed peer comparison.

Carrier hierarchy:

    item -> required/observed property family -> statement -> value/rank/qualifiers/references

Peer features are conditioned projections of that carrier, never detached labels.
Rank is intrinsic to a statement, while truthy visibility is computed over the
subject+property family. Therefore property-family coverage is required before
truthiness or property absence can be treated as observed.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .domain_pressure import COVERAGE_STATES

ITEM_PROPERTY_EVIDENCE_SCHEMA_VERSION = "sl.wikidata_item_property_evidence.v0_2"
RANKS = frozenset({"preferred", "normal", "deprecated"})
VISIBILITY_STATES = frozenset({"truthy", "non_truthy", "unresolved"})
CONSTRAINT_STATES = frozenset({"valid", "invalid", "uninspected"})
RELATION_ORIGINS = frozenset({"asserted", "derived", "unresolved"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strings(values: Sequence[Any]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def _qualifier_rows(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(value, Mapping):
        for property_id, values in value.items():
            for observed in values if isinstance(values, (list, tuple, set)) else (values,):
                rows.append({"property_id": _text(property_id), "value": _text(observed)})
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for row in value:
            if isinstance(row, Mapping):
                property_id = _text(row.get("property_id") or row.get("property"))
                observed = _text(row.get("value"))
                if property_id:
                    rows.append({"property_id": property_id, "value": observed})
    rows.sort(key=lambda row: (row["property_id"], row["value"]))
    return rows


def _statement_rows(statements: Sequence[Mapping[str, Any]], subject_qid: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(statements, start=1):
        if not isinstance(raw, Mapping):
            continue
        property_id = _text(raw.get("property_id") or raw.get("property"))
        if not property_id:
            raise ValueError("item-property statement requires property_id")
        rank = _text(raw.get("rank")) or "normal"
        if rank not in RANKS:
            raise ValueError(f"unsupported Wikidata statement rank: {rank}")
        statement_ref = _text(raw.get("statement_ref") or raw.get("statement_id"))
        if not statement_ref:
            statement_ref = f"{subject_qid}|{property_id}|{index}"
        rows.append(
            {
                "statement_ref": statement_ref,
                "property_id": property_id,
                "value": deepcopy(raw.get("value")),
                "value_ref": _text(raw.get("value_ref") or raw.get("value")),
                "value_kind": _text(raw.get("value_kind")) or "unknown",
                "rank": rank,
                "qualifiers": _qualifier_rows(raw.get("qualifiers") or ()),
                "reference_refs": _strings(raw.get("reference_refs") or ()),
            }
        )
    rows.sort(key=lambda row: (row["property_id"], row["statement_ref"]))
    return rows


def _property_coverage_map(
    *,
    rows: Sequence[Mapping[str, Any]],
    required_property_ids: Sequence[str],
    item_coverage_state: str,
    property_coverage: Mapping[str, Any] | None,
) -> dict[str, str]:
    supplied = property_coverage or {}
    property_ids = {
        *(_text(row.get("property_id")) for row in rows),
        *(_text(value) for value in required_property_ids),
        *(_text(value) for value in supplied),
    }
    result: dict[str, str] = {}
    for property_id in sorted(value for value in property_ids if value):
        state = _text(supplied.get(property_id)) or item_coverage_state
        if state not in COVERAGE_STATES:
            raise ValueError(f"unsupported property-family coverage state for {property_id}: {state}")
        result[property_id] = state
    return result


def _truthy_statement_refs(
    rows: Sequence[Mapping[str, Any]], property_coverage: Mapping[str, str]
) -> set[str]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_text(row.get("property_id"))].append(row)
    truthy: set[str] = set()
    for property_id, group in grouped.items():
        if property_coverage.get(property_id) != "observed":
            continue
        preferred = [row for row in group if row.get("rank") == "preferred"]
        visible = preferred or [row for row in group if row.get("rank") == "normal"]
        truthy.update(_text(row.get("statement_ref")) for row in visible)
    return truthy


def _qualifier_constraint_state(
    statement: Mapping[str, Any],
    qualifier_specs: Mapping[str, Mapping[str, Sequence[str]]],
) -> str:
    property_id = _text(statement.get("property_id"))
    spec = qualifier_specs.get(property_id)
    if not isinstance(spec, Mapping):
        return "uninspected"
    observed = {_text(row.get("property_id")) for row in statement.get("qualifiers", ())}
    allowed = {_text(value) for value in spec.get("allowed", ())}
    mandatory = {_text(value) for value in spec.get("mandatory", ())}
    return "valid" if observed <= allowed and mandatory <= observed else "invalid"


def _scope_state(*, property_id: str, slot: str, scope_specs: Mapping[str, Mapping[str, Any]]) -> str:
    spec = scope_specs.get(property_id)
    if not isinstance(spec, Mapping):
        return "uninspected"
    allowed = spec.get("as_main", True) if slot == "main" else spec.get("as_qualifier", True)
    return "valid" if allowed is True else "invalid"


def _relation_key(property_id: str, subject_qid: str, object_ref: str) -> tuple[str, str, str]:
    return property_id, subject_qid, object_ref


def build_item_property_evidence_surface(
    *,
    subject_qid: str,
    source_revision_ref: str,
    statements: Sequence[Mapping[str, Any]],
    coverage_state: str,
    coverage_policy_ref: str,
    required_property_ids: Sequence[str] = (),
    property_coverage: Mapping[str, Any] | None = None,
    qualifier_specs: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    scope_specs: Mapping[str, Mapping[str, Any]] | None = None,
    derived_relations: Sequence[Mapping[str, Any]] = (),
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a property-aware item surface and conditioned peer features.

    ``property_coverage[P] == observed`` means the declared bounded policy
    covered enough of Q/P to decide rank truthiness and meaningful absence for
    that property family. It never means Wikidata is globally complete.
    """

    qid = _text(subject_qid)
    revision = _text(source_revision_ref)
    policy = _text(coverage_policy_ref)
    coverage = _text(coverage_state) or "uninspected"
    if not qid or not revision or not policy:
        raise ValueError("item-property evidence requires subject_qid, source_revision_ref, and coverage_policy_ref")
    if coverage not in COVERAGE_STATES:
        raise ValueError(f"unsupported item-property coverage state: {coverage}")

    required = _strings(required_property_ids)
    q_specs = qualifier_specs or {}
    s_specs = scope_specs or {}
    rows = _statement_rows(statements, qid)
    family_coverage = _property_coverage_map(
        rows=rows,
        required_property_ids=required,
        item_coverage_state=coverage,
        property_coverage=property_coverage,
    )
    truthy_refs = _truthy_statement_refs(rows, family_coverage)

    asserted_relations: set[tuple[str, str, str]] = set()
    normalized_statements: list[dict[str, Any]] = []
    feature_rows: list[dict[str, str]] = []

    for property_id, state in family_coverage.items():
        feature_rows.append(
            {"feature": "property_family_coverage", "condition": property_id, "value": state}
        )

    for row in rows:
        statement_ref = row["statement_ref"]
        property_id = row["property_id"]
        property_is_observed = family_coverage[property_id] == "observed"
        truthy = property_is_observed and statement_ref in truthy_refs
        visibility = "truthy" if truthy else "non_truthy" if property_is_observed else "unresolved"
        qualifier_state = _qualifier_constraint_state(row, q_specs)
        main_scope_state = _scope_state(property_id=property_id, slot="main", scope_specs=s_specs)
        qualifier_scope = [
            {
                "property_id": qualifier["property_id"],
                "state": _scope_state(
                    property_id=qualifier["property_id"], slot="qualifier", scope_specs=s_specs
                ),
            }
            for qualifier in row["qualifiers"]
        ]

        relation_origin = "unresolved"
        if truthy and row["value_kind"] == "item" and row["value_ref"]:
            relation_origin = "asserted"
            asserted_relations.add(_relation_key(property_id, qid, row["value_ref"]))

        normalized_statements.append(
            {
                **row,
                "property_family_coverage": family_coverage[property_id],
                "statement_visibility": visibility,
                "truthy": truthy if property_is_observed else None,
                "qualifier_constraint": qualifier_state,
                "main_property_scope": main_scope_state,
                "qualifier_property_scopes": qualifier_scope,
                "property_relation": relation_origin,
            }
        )

        statement_condition = f"{property_id}|{statement_ref}"
        feature_rows.extend(
            [
                {"feature": "statement_rank", "condition": statement_condition, "value": row["rank"]},
                {"feature": "statement_visibility", "condition": statement_condition, "value": visibility},
                {"feature": "qualifier_constraint", "condition": statement_condition, "value": qualifier_state},
                {"feature": "property_scope", "condition": f"{property_id}:main", "value": main_scope_state},
            ]
        )
        for qualifier in qualifier_scope:
            feature_rows.append(
                {
                    "feature": "property_scope",
                    "condition": f"{qualifier['property_id']}:qualifier",
                    "value": qualifier["state"],
                }
            )
        if row["value_kind"] == "item" and row["value_ref"]:
            feature_rows.append(
                {
                    "feature": "property_relation",
                    "condition": f"{property_id}->{row['value_ref']}",
                    "value": relation_origin,
                }
            )

    derived_rows: list[dict[str, str]] = []
    for raw in derived_relations:
        if not isinstance(raw, Mapping):
            continue
        property_id = _text(raw.get("property_id") or raw.get("property"))
        object_ref = _text(raw.get("object_ref") or raw.get("object"))
        if not property_id or not object_ref:
            continue
        key = _relation_key(property_id, qid, object_ref)
        origin = "asserted" if key in asserted_relations else "derived"
        derived_rows.append({"property_id": property_id, "object_ref": object_ref, "origin": origin})
        feature_rows.append(
            {"feature": "property_relation", "condition": f"{property_id}->{object_ref}", "value": origin}
        )

    observed_with_rows = sorted({row["property_id"] for row in normalized_statements})
    truthy_property_ids = sorted(
        {row["property_id"] for row in normalized_statements if row["truthy"] is True}
    )
    observed_absent = sorted(
        property_id
        for property_id in required
        if family_coverage.get(property_id) == "observed" and property_id not in observed_with_rows
    )
    unresolved_required = sorted(
        property_id
        for property_id in required
        if family_coverage.get(property_id) != "observed"
    )
    for property_id in observed_absent:
        feature_rows.append(
            {"feature": "property_presence", "condition": property_id, "value": "absent"}
        )
    for property_id in observed_with_rows:
        feature_rows.append(
            {"feature": "property_presence", "condition": property_id, "value": "present"}
        )

    unique_features = sorted(
        {(row["feature"], row.get("condition", ""), row["value"]) for row in feature_rows}
    )
    peer_features = [
        {"feature": feature, "condition": condition, "value": value}
        for feature, condition, value in unique_features
    ]

    return {
        "schema_version": ITEM_PROPERTY_EVIDENCE_SCHEMA_VERSION,
        "subject_qid": qid,
        "source_revision_ref": revision,
        "coverage_state": coverage,
        "coverage_policy_ref": policy,
        "property_inventory": {
            "required_property_ids": required,
            "observed_property_ids": observed_with_rows,
            "truthy_property_ids": truthy_property_ids,
            "observed_absent_property_ids": observed_absent,
            "unresolved_required_property_ids": unresolved_required,
            "coverage_by_property": family_coverage,
            "statement_count": len(normalized_statements),
        },
        "statements": normalized_statements,
        "derived_relations": sorted(
            derived_rows, key=lambda row: (row["property_id"], row["object_ref"], row["origin"])
        ),
        "peer_features": peer_features,
        "evidence_refs": _strings(evidence_refs),
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }


__all__ = ["ITEM_PROPERTY_EVIDENCE_SCHEMA_VERSION", "build_item_property_evidence_surface"]
