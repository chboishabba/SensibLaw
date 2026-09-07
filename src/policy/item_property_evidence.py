"""Revision-bound Wikidata item/property evidence for governed peer comparison.

Carrier hierarchy:

    item -> required/observed property family -> statement -> snak/value/rank/qualifiers/references

Peer features are conditioned projections of that carrier, never detached labels.
Rank is intrinsic to a statement, while truthy visibility is computed over the
subject+property family. Therefore property-family coverage is required before
truthiness or statement absence can be treated as observed.

Native Wikibase snak semantics are separate from statement presence. A covered
Q/P with no returned statement is *not* the same thing as an explicit ``novalue``
snak. This mirrors RequestProject.Snaks: in a consistent snak base, ``novalue`` is
entailed exactly when it is asserted.

Constraint-table absence is coverage-sensitive too. When a qualifier/scope table
is known complete and contains no entry for P, Aristotle treats P as unconstrained;
when the table was not inspected, SensibLaw keeps the state uninspected.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .domain_pressure import COVERAGE_STATES

ITEM_PROPERTY_EVIDENCE_SCHEMA_VERSION = "sl.wikidata_item_property_evidence.v0_4"
RANKS = frozenset({"preferred", "normal", "deprecated"})
VISIBILITY_STATES = frozenset({"truthy", "non_truthy", "unresolved"})
CONSTRAINT_STATES = frozenset({"valid", "invalid", "unconstrained", "uninspected"})
RELATION_ORIGINS = frozenset({"asserted", "derived", "unresolved"})
SNAK_TYPES = frozenset({"value", "somevalue", "novalue"})
STATEMENT_PRESENCE_STATES = frozenset({"statement_present", "no_statement_observed", "unresolved"})


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
        snak_type = _text(raw.get("snak_type") or raw.get("snaktype")) or "value"
        if snak_type not in SNAK_TYPES:
            raise ValueError(f"unsupported Wikidata snak type: {snak_type}")
        statement_ref = _text(raw.get("statement_ref") or raw.get("statement_id"))
        if not statement_ref:
            statement_ref = f"{subject_qid}|{property_id}|{index}"
        rows.append(
            {
                "statement_ref": statement_ref,
                "property_id": property_id,
                "snak_type": snak_type,
                "value": deepcopy(raw.get("value")) if snak_type == "value" else None,
                "value_ref": _text(raw.get("value_ref") or raw.get("value")) if snak_type == "value" else "",
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


def _constraint_profile_state(value: str, *, field: str) -> str:
    state = _text(value) or "uninspected"
    if state not in COVERAGE_STATES:
        raise ValueError(f"unsupported {field}: {state}")
    return state


def _qualifier_constraint_state(
    statement: Mapping[str, Any],
    qualifier_specs: Mapping[str, Mapping[str, Sequence[str]]],
    profile_coverage_state: str,
) -> str:
    property_id = _text(statement.get("property_id"))
    spec = qualifier_specs.get(property_id)
    if not isinstance(spec, Mapping):
        return "unconstrained" if profile_coverage_state == "observed" else "uninspected"
    observed = {_text(row.get("property_id")) for row in statement.get("qualifiers", ())}
    allowed = {_text(value) for value in spec.get("allowed", ())}
    mandatory = {_text(value) for value in spec.get("mandatory", ())}
    return "valid" if observed <= allowed and mandatory <= observed else "invalid"


def _scope_state(
    *,
    property_id: str,
    slot: str,
    scope_specs: Mapping[str, Mapping[str, Any]],
    profile_coverage_state: str,
) -> str:
    spec = scope_specs.get(property_id)
    if not isinstance(spec, Mapping):
        return "unconstrained" if profile_coverage_state == "observed" else "uninspected"
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
    qualifier_profile_coverage_state: str = "uninspected",
    scope_specs: Mapping[str, Mapping[str, Any]] | None = None,
    scope_profile_coverage_state: str = "uninspected",
    derived_relations: Sequence[Mapping[str, Any]] = (),
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a property-aware item surface and conditioned peer features.

    ``property_coverage[P] == observed`` means the declared bounded policy
    covered enough of Q/P to decide rank truthiness and whether a statement is
    present. It never means Wikidata is globally complete, and an observed lack
    of statements never becomes a native ``novalue`` assertion.

    A property absent from a constraint table is ``unconstrained`` only when the
    corresponding profile coverage is itself ``observed``. Otherwise it remains
    ``uninspected``.
    """

    qid = _text(subject_qid)
    revision = _text(source_revision_ref)
    policy = _text(coverage_policy_ref)
    coverage = _text(coverage_state) or "uninspected"
    if not qid or not revision or not policy:
        raise ValueError("item-property evidence requires subject_qid, source_revision_ref, and coverage_policy_ref")
    if coverage not in COVERAGE_STATES:
        raise ValueError(f"unsupported item-property coverage state: {coverage}")

    qualifier_profile_coverage = _constraint_profile_state(
        qualifier_profile_coverage_state, field="qualifier_profile_coverage_state"
    )
    scope_profile_coverage = _constraint_profile_state(
        scope_profile_coverage_state, field="scope_profile_coverage_state"
    )
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
    feature_rows: list[dict[str, str]] = [
        {"feature": "qualifier_profile_coverage", "condition": "constraint_table", "value": qualifier_profile_coverage},
        {"feature": "scope_profile_coverage", "condition": "constraint_table", "value": scope_profile_coverage},
    ]

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
        qualifier_state = _qualifier_constraint_state(
            row, q_specs, qualifier_profile_coverage
        )
        main_scope_state = _scope_state(
            property_id=property_id,
            slot="main",
            scope_specs=s_specs,
            profile_coverage_state=scope_profile_coverage,
        )
        qualifier_scope = [
            {
                "property_id": qualifier["property_id"],
                "state": _scope_state(
                    property_id=qualifier["property_id"],
                    slot="qualifier",
                    scope_specs=s_specs,
                    profile_coverage_state=scope_profile_coverage,
                ),
            }
            for qualifier in row["qualifiers"]
        ]

        relation_origin = "unresolved"
        if (
            truthy
            and row["snak_type"] == "value"
            and row["value_kind"] == "item"
            and row["value_ref"]
        ):
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
                {"feature": "statement_snak_type", "condition": statement_condition, "value": row["snak_type"]},
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
        if row["snak_type"] == "value" and row["value_kind"] == "item" and row["value_ref"]:
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
    no_statement_observed = sorted(
        property_id
        for property_id in required
        if family_coverage.get(property_id) == "observed" and property_id not in observed_with_rows
    )
    unresolved_required = sorted(
        property_id
        for property_id in required
        if family_coverage.get(property_id) != "observed"
    )
    explicit_novalue_properties = sorted(
        {row["property_id"] for row in normalized_statements if row["snak_type"] == "novalue"}
    )
    explicit_somevalue_properties = sorted(
        {row["property_id"] for row in normalized_statements if row["snak_type"] == "somevalue"}
    )

    for property_id in no_statement_observed:
        feature_rows.append(
            {"feature": "property_statement_presence", "condition": property_id, "value": "no_statement_observed"}
        )
    for property_id in observed_with_rows:
        feature_rows.append(
            {"feature": "property_statement_presence", "condition": property_id, "value": "statement_present"}
        )
    for property_id in unresolved_required:
        feature_rows.append(
            {"feature": "property_statement_presence", "condition": property_id, "value": "unresolved"}
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
        "constraint_profile_coverage": {
            "qualifier": qualifier_profile_coverage,
            "scope": scope_profile_coverage,
        },
        "property_inventory": {
            "required_property_ids": required,
            "observed_property_ids": observed_with_rows,
            "truthy_property_ids": truthy_property_ids,
            "no_statement_observed_property_ids": no_statement_observed,
            "unresolved_required_property_ids": unresolved_required,
            "explicit_novalue_property_ids": explicit_novalue_properties,
            "explicit_somevalue_property_ids": explicit_somevalue_properties,
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


__all__ = [
    "ITEM_PROPERTY_EVIDENCE_SCHEMA_VERSION",
    "CONSTRAINT_STATES",
    "SNAK_TYPES",
    "STATEMENT_PRESENCE_STATES",
    "build_item_property_evidence_surface",
]
