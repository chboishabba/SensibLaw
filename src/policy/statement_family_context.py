"""Generic, coverage-aware context for atomic statement families.

The carrier deliberately distinguishes a statement's own multiplicity from
variation across sibling statements.  It is usable by any adapter that turns a
source into statement records; source/domain profiles configure which
qualifiers identify a component partition.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "STATEMENT_FAMILY_CONFORMANCE_RECEIPT_SCHEMA_VERSION",
    "build_statement_family_member_evidence",
    "build_statement_family_conformance_receipt",
    "build_statement_family_context",
]


STATEMENT_FAMILY_CONFORMANCE_RECEIPT_SCHEMA_VERSION = (
    "sl.statement_family_conformance_receipt.v0_1"
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _values(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return tuple()
    if isinstance(raw, (list, tuple, set)):
        return tuple(sorted({_text(value) for value in raw if _text(value)}))
    value = _text(raw)
    return (value,) if value else tuple()


def _quantity(value: Any) -> Decimal | None:
    if isinstance(value, Mapping):
        value = value.get("amount")
    text = _text(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _digest(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _family_id(record: Mapping[str, Any]) -> str:
    subject = _text(record.get("subject"))
    property_id = _text(record.get("property"))
    if not subject or not property_id:
        raise ValueError("statement family records require subject and property")
    return f"{subject}|{property_id}"


def _context_for_family(
    records: Sequence[Mapping[str, Any]],
    *,
    scope_properties: frozenset[str],
    complete: bool,
) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    scoped_members: list[dict[str, Any]] = []
    unscoped_members: list[dict[str, Any]] = []
    scope_signatures: dict[tuple[str, ...], list[str]] = defaultdict(list)

    for record in records:
        statement_id = _text(record.get("statement_id"))
        if not statement_id:
            raise ValueError("statement family records require statement_id")
        qualifiers = record.get("qualifiers")
        if not isinstance(qualifiers, Mapping):
            qualifiers = {}
        scope_values = tuple(
            sorted(
                {
                    value
                    for property_id in scope_properties
                    for value in _values(qualifiers.get(property_id))
                }
            )
        )
        member = {
            "statement_id": statement_id,
            "scope_values": list(scope_values),
            "scope_cardinality": len(scope_values),
            "quantity": _quantity(record.get("value")),
        }
        members.append(member)
        if scope_values:
            scoped_members.append(member)
            scope_signatures[scope_values].append(statement_id)
        else:
            unscoped_members.append(member)

    if not complete:
        partition_state = "incomplete"
    elif any(member["scope_cardinality"] > 1 for member in members):
        partition_state = "overloaded"
    elif any(len(ids) > 1 for ids in scope_signatures.values()):
        partition_state = "overlapping"
    elif len(scoped_members) >= 2:
        partition_state = "already_partitioned"
    else:
        partition_state = "unknown"

    total_relation = "no_total"
    component_sum: str | None = None
    total_value: str | None = None
    if not complete:
        total_relation = "not_comparable"
    elif scoped_members and unscoped_members:
        quantities = [member["quantity"] for member in scoped_members]
        totals = [member["quantity"] for member in unscoped_members]
        if any(value is None for value in quantities) or any(
            value is None for value in totals
        ):
            total_relation = "not_comparable"
        elif len(totals) != 1:
            total_relation = "not_comparable"
        else:
            component_total = sum(quantities, Decimal("0"))
            component_sum = str(component_total)
            total_value = str(totals[0])
            total_relation = (
                "exact_reconciliation"
                if component_total == totals[0]
                else "contradiction"
            )

    return {
        "family_id": _family_id(records[0]),
        "coverage_complete": complete,
        "member_statement_ids": sorted(member["statement_id"] for member in members),
        "member_count": len(members),
        "scope_partition_state": partition_state,
        "total_component_relation": total_relation,
        "component_sum": component_sum,
        "total_value": total_value,
        "duplicate_scope_statement_ids": sorted(
            statement_id
            for statement_ids in scope_signatures.values()
            if len(statement_ids) > 1
            for statement_id in statement_ids
        ),
        "split_requirement": (
            "new_split_required"
            if partition_state == "overloaded"
            else "manual_reconstruction"
            if partition_state in {"overlapping"} or total_relation == "contradiction"
            else "existing_partition_preserved"
            if partition_state == "already_partitioned"
            else "none"
        ),
    }


def build_statement_family_context(
    records: Iterable[Mapping[str, Any]],
    *,
    scope_properties: Iterable[str] = (),
    complete: bool = True,
) -> dict[str, dict[str, Any]]:
    """Build deterministic family context keyed by ``subject|property``.

    ``complete`` describes whether all siblings required for family-level
    claims were supplied.  Atomic statement assessment may still proceed when
    it is false, but partition, duplicate, and total inferences must not.
    """

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[_family_id(record)].append(record)
    scope_ids = frozenset(_text(property_id) for property_id in scope_properties)
    return {
        family_id: _context_for_family(
            sorted(group, key=lambda member: _text(member.get("statement_id"))),
            scope_properties=scope_ids,
            complete=complete,
        )
        for family_id, group in sorted(grouped.items())
    }


def build_statement_family_member_evidence(
    family_contexts: Mapping[str, Mapping[str, Any]],
    member_evidence: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return family contexts enriched by explicitly supplied member evidence.

    The generic carrier does not interpret what a period or a conforming member
    means. A profile/adaptor supplies normalized period values and one of
    ``conformant``, ``nonconformant``, or ``unresolved`` for each member. This
    function only checks family coverage and derives partition/conformance
    states without treating an omitted member as a negative observation.
    """

    supported_conformance = {"conformant", "nonconformant", "unresolved"}
    supported_period_coverage = {"observed", "unresolved"}
    grouped: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for supplied in member_evidence:
        family_id = _text(supplied.get("family_id"))
        statement_id = _text(supplied.get("statement_id"))
        if not family_id or not statement_id:
            raise ValueError("family member evidence requires family_id and statement_id")
        if family_id not in family_contexts:
            raise ValueError("family member evidence references unknown family")
        if statement_id in grouped[family_id]:
            raise ValueError("family member evidence requires unique statement IDs")
        grouped[family_id][statement_id] = supplied

    hydrated: dict[str, dict[str, Any]] = {}
    for family_id, supplied_context in sorted(family_contexts.items()):
        context = dict(supplied_context)
        member_ids = _values(context.get("member_statement_ids"))
        evidence_by_statement = grouped.get(family_id, {})
        unknown_members = sorted(set(member_ids) - set(evidence_by_statement))
        unexpected_members = sorted(set(evidence_by_statement) - set(member_ids))
        if unexpected_members:
            raise ValueError("family member evidence references non-member statement")

        period_values: dict[str, list[str]] = {}
        period_shapes: dict[str, str] = {}
        conformance_states: dict[str, str] = {}
        period_states: dict[str, str] = {}
        for statement_id in member_ids:
            evidence = evidence_by_statement.get(statement_id)
            if evidence is None:
                continue
            period_state = _text(evidence.get("period_coverage_state")) or "unresolved"
            conformance_state = _text(evidence.get("conformance_state")) or "unresolved"
            if period_state not in supported_period_coverage:
                raise ValueError("family member evidence has unsupported period coverage")
            if conformance_state not in supported_conformance:
                raise ValueError("family member evidence has unsupported conformance")
            period_states[statement_id] = period_state
            conformance_states[statement_id] = conformance_state
            period_values[statement_id] = list(_values(evidence.get("period_values")))
            period_shapes[statement_id] = (
                _text(evidence.get("period_shape"))
                or "single_observed_slot"
                if period_state == "observed" and len(period_values[statement_id]) == 1
                else "unresolved"
            )

        complete_member_evidence = not unknown_members and bool(member_ids)
        if not context.get("coverage_complete") or not complete_member_evidence:
            period_partition_state = "incomplete"
        elif any(state != "observed" for state in period_states.values()):
            period_partition_state = "unresolved"
        elif any(len(values) != 1 for values in period_values.values()):
            period_partition_state = "unresolved"
        else:
            values = [values[0] for values in period_values.values()]
            period_partition_state = (
                "overlapping" if len(set(values)) != len(values) else "distinct_non_overlapping"
            )

        if not context.get("coverage_complete") or not complete_member_evidence:
            period_geometry = "incomplete"
        elif any(state != "observed" for state in period_states.values()):
            period_geometry = "unresolved"
        elif any(shape in {"absent", "unparsable"} for shape in period_shapes.values()):
            period_geometry = (
                "period_absent"
                if any(shape == "absent" for shape in period_shapes.values())
                else "period_unparsable"
            )
        elif any(shape == "multi_year_interval" for shape in period_shapes.values()):
            period_geometry = "multi_year_interval"
        elif len(set(period_shapes.values())) > 1:
            period_geometry = "mixed_period_representation"
        elif period_partition_state == "overlapping":
            period_geometry = (
                "same_annual_period_component_partition"
                if context.get("scope_partition_state") == "already_partitioned"
                and context.get("total_component_relation") == "exact_reconciliation"
                else "duplicate_or_overlapping_period"
            )
        elif len(member_ids) == 1:
            period_geometry = "single_annual_period"
        else:
            period_geometry = "distinct_annual_periods"

        if not context.get("coverage_complete") or not complete_member_evidence:
            member_conformance_state = "incomplete"
        elif any(state == "unresolved" for state in conformance_states.values()):
            member_conformance_state = "unresolved"
        elif any(state == "nonconformant" for state in conformance_states.values()):
            member_conformance_state = "member_conflict"
        else:
            member_conformance_state = "all_conform"

        context.update(
            {
                "member_evidence_coverage": (
                    "complete" if complete_member_evidence else "incomplete"
                ),
                "missing_member_evidence_statement_ids": unknown_members,
                "period_partition_state": period_partition_state,
                "period_geometry": period_geometry,
                "member_conformance_state": member_conformance_state,
                "member_period_values": {
                    statement_id: period_values[statement_id]
                    for statement_id in sorted(period_values)
                },
                "member_period_coverage_states": {
                    statement_id: period_states[statement_id]
                    for statement_id in sorted(period_states)
                },
                "member_period_shapes": {
                    statement_id: period_shapes[statement_id]
                    for statement_id in sorted(period_shapes)
                },
                "member_conformance_states": {
                    statement_id: conformance_states[statement_id]
                    for statement_id in sorted(conformance_states)
                },
            }
        )
        hydrated[family_id] = context
    return hydrated


def build_statement_family_conformance_receipt(
    *,
    family_context: Mapping[str, Any],
    selected_statement_ref: str,
    source_revision_ref: str,
    alignment_observations: Mapping[str, str],
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Bind a selected atomic statement to the inspected sibling-family witness.

    This records evidence used to assess an atomic candidate; it is not an
    approval of every family member, a migration instruction, or a cohort
    contribution. Domain adapters provide the alignment observations because
    their period, method, and unit semantics are profile-specific.
    """

    selected = _text(selected_statement_ref)
    revision = _text(source_revision_ref)
    family_id = _text(family_context.get("family_id"))
    members = _values(family_context.get("member_statement_ids"))
    if not selected or not revision or not family_id:
        raise ValueError(
            "family conformance receipt requires selected statement, revision, and family"
        )
    if selected not in members:
        raise ValueError("selected statement must be a member of the family context")
    alignments = {
        _text(name): _text(state)
        for name, state in alignment_observations.items()
        if _text(name) and _text(state)
    }
    required_alignment_names = {"period", "method", "unit"}
    if not required_alignment_names.issubset(alignments):
        raise ValueError("family conformance receipt requires period, method, and unit")
    payload = {
        "schema_version": STATEMENT_FAMILY_CONFORMANCE_RECEIPT_SCHEMA_VERSION,
        "family_id": family_id,
        "selected_statement_ref": selected,
        "source_revision_ref": revision,
        "family_coverage": (
            "complete" if family_context.get("coverage_complete") else "incomplete"
        ),
        "member_statement_refs": list(members),
        "scope_partition_state": _text(family_context.get("scope_partition_state")),
        "total_component_relation": _text(
            family_context.get("total_component_relation")
        ),
        "alignment_observations": dict(sorted(alignments.items())),
        "evidence_refs": sorted({_text(ref) for ref in evidence_refs if _text(ref)}),
        "authority": "diagnostic_context_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }
    payload["conformance_context_ref"] = "family-conformance:" + _digest(payload)
    return payload
