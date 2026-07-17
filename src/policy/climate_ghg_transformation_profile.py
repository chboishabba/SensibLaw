"""Climate-GHG profile over generic transformation-rule contracts.

The module supplies bounded P5991-to-P14143 policy predicates. It does not
retrieve Wikidata, approve rules, create edit manifests, or treat an A-E
classifier label as an applicability decision.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from .statement_family_context import build_statement_family_member_evidence
from .transformation_rules import (
    build_rule_coverage_report,
    build_rule_detector_result,
    build_transformation_rule,
)


DOMAIN_CONTRACT_REF = "wikidata:climate_ghg_p5991_to_p14143:v0_1"
TRANSFORMATION_CONTRACT_REF = "transform:P5991-to-P14143:preserve-statement-bundle"


GHG_SCOPE_PROPERTIES = frozenset({"P3831", "P518"})
GHG_DETERMINATION_METHOD_PROPERTY = "P459"
GHG_TEMPORAL_PROPERTIES = frozenset({"P580", "P582", "P585"})


def _extract_year_from_date_str(val: str) -> str | None:
    val = val.strip().lstrip("+").lstrip("-")
    if len(val) >= 4 and val[:4].isdigit():
        return val[:4]
    for i in range(len(val) - 3):
        chunk = val[i:i+4]
        if chunk.isdigit() and (chunk.startswith("19") or chunk.startswith("20")):
            return chunk
    return None


def _resolve_fiscal_canonical_year(qualifiers: Mapping[str, Any]) -> tuple[str, str]:
    p585_vals = _text_list(qualifiers.get("P585"))
    p580_vals = _text_list(qualifiers.get("P580"))
    p582_vals = _text_list(qualifiers.get("P582"))

    point_years = sorted(list(set(
        year for v in p585_vals for year in [_extract_year_from_date_str(v)] if year
    )))
    if len(point_years) == 1:
        return point_years[0], "exact"
    if len(point_years) > 1:
        return "", "unresolved"

    start_years = sorted(list(set(
        year for v in p580_vals for year in [_extract_year_from_date_str(v)] if year
    )))
    end_years = sorted(list(set(
        year for v in p582_vals for year in [_extract_year_from_date_str(v)] if year
    )))

    if start_years and end_years:
        if len(start_years) == 1 and len(end_years) == 1:
            sy = int(start_years[0])
            ey = int(end_years[0])
            if sy == ey:
                return start_years[0], "exact"
            if ey == sy + 1:
                return end_years[0], "fiscal_canonical"
        return "", "unresolved"

    if start_years or end_years:
        return "", "partial"

    return "", "unresolved"


@dataclass(frozen=True)
class GHGStatementSlot:
    """Normalized semantic identity for one GHG statement within a family.

    ``semantic_slot`` is the core identity: two statements with the same
    ``(year, scope, applies_to_part, method, unit)`` contend for the same
    cell.  ``rank`` and ``reference_group`` sit outside the semantic core and
    identify revision or duplicate assertions rather than different cells.
    """

    year: str
    scope: str
    applies_to_part: str
    method: str
    unit: str
    slot_identity_state: str

    semantic_slot: tuple[str, str, str, str, str] = field(init=False)

    rank: str = "normal"
    reference_group: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantic_slot",
            (self.year, self.scope, self.applies_to_part, self.method, self.unit),
        )

    @classmethod
    def from_candidate(cls, candidate: Mapping[str, Any]) -> GHGStatementSlot:
        bundle = candidate.get("claim_bundle_before") or {}
        qualifiers = bundle.get("qualifiers") or {}
        validation = candidate.get("model_validation") or {}
        classifier = candidate.get("family_classifier") or {}

        year = _text(validation.get("resolved_year"))
        if not year:
            year, slot_identity_state = _resolve_fiscal_canonical_year(qualifiers)
        else:
            slot_identity_state = "exact"

        scope_values = _text_list(qualifiers.get("P3831"))
        applies_to_part_values = _text_list(qualifiers.get("P518"))
        method_values = _text_list(qualifiers.get("P459"))
        unit = _text(validation.get("resolved_unit_qid"))

        rank = _text(bundle.get("rank")) or "normal"

        reference_group = _ref_group(bundle.get("references") or ())

        scope = scope_values[0] if scope_values else ""
        applies_to_part = applies_to_part_values[0] if applies_to_part_values else ""

        method = method_values[0] if method_values else ""

        return cls(
            year=year,
            scope=scope,
            applies_to_part=applies_to_part,
            method=method,
            unit=unit,
            slot_identity_state=slot_identity_state,
            rank=rank,
            reference_group=reference_group,
        )

    @property
    def comparable_basis(self) -> tuple[str, str, str, str]:
        """Basis on which total/component reconciliation is meaningful."""
        return (self.year, self.method, self.unit, self.reference_group)

    def is_total(self) -> bool:
        return not self.scope and not self.applies_to_part


def _ref_group(references: Any) -> str:
    if not isinstance(references, (list, tuple)):
        return ""
    urls: list[str] = []
    for ref in references:
        if not isinstance(ref, Mapping):
            continue
        for values in ref.values():
            if not isinstance(values, (list, tuple)):
                continue
            for value in values:
                text = _text(value)
                if text:
                    urls.append(text)
    return "|".join(sorted(urls)) if urls else ""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_slot(member_evidence: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    """Extract the normalized semantic slot from member evidence."""
    slot = member_evidence.get("ghg_slot") or {}
    return (
        slot.get("year") or "",
        slot.get("scope") or "",
        slot.get("applies_to_part") or "",
        slot.get("method") or "",
        slot.get("unit") or "",
    )


def _slot_collisions(
    member_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Detect slot-level collisions within a family and classify H4 sub-dispositions.

    Returns a mapping from collision reason/type to details.
    """
    slot_map: dict[tuple[str, str, str, str, str], list[Mapping[str, Any]]] = {}
    guidance_map: dict[str, list[str]] = {}

    for evidence in member_evidence:
        statement_id = _text(evidence.get("statement_id"))
        if not statement_id:
            continue
        slot = _normalize_slot(evidence)
        slot_map.setdefault(slot, []).append(evidence)

        guidance_id = _text((evidence.get("ghg_slot") or {}).get("reference_group"))
        if guidance_id:
            guidance_map.setdefault(guidance_id, []).append(statement_id)

    collisions: dict[str, Any] = {}

    duplicate_slots: list[list[str]] = []
    h4_details: list[dict[str, Any]] = []

    for slot, ev_list in slot_map.items():
        if len(ev_list) > 1:
            statement_ids = [
                _text(ev.get("statement_id")) for ev in ev_list if _text(ev.get("statement_id"))
            ]
            duplicate_slots.append(statement_ids)

            values = set()
            ranks = set()
            has_unresolved_coordinate = False
            for ev in ev_list:
                ghg_slot = ev.get("ghg_slot") or {}
                val = _text(ghg_slot.get("value"))
                rank = _text(ghg_slot.get("rank")) or "normal"
                state = _text(ghg_slot.get("slot_identity_state")) or "unresolved"

                values.add(val)
                ranks.add(rank)
                if state in ("fiscal_canonical", "unresolved"):
                    has_unresolved_coordinate = True

            if len(values) > 1:
                collision_type = "conflicting_value"
                sub_disposition = "H4c"
            elif len(ranks) > 1:
                collision_type = "rank_variant"
                sub_disposition = "H4d"
            else:
                collision_type = "duplicate_assertion"
                if has_unresolved_coordinate:
                    sub_disposition = "H4b"
                else:
                    sub_disposition = "H4a"

            h4_details.append({
                "slot": list(slot),
                "member_guids": statement_ids,
                "collision_type": collision_type,
                "has_unresolved_coordinate": has_unresolved_coordinate,
                "sub_disposition": sub_disposition,
            })

    if duplicate_slots:
        collisions["duplicate_semantic_slot"] = duplicate_slots
        collisions["h4_details"] = h4_details

    overloaded_guids: list[str] = []
    guid_slots: dict[str, list[tuple[str, str, str, str, str]]] = {}
    for evidence in member_evidence:
        statement_id = _text(evidence.get("statement_id"))
        if not statement_id:
            continue
        slot = _normalize_slot(evidence)
        guid_slots.setdefault(statement_id, []).append(slot)
    for guid, slots in guid_slots.items():
        if len(set(slots)) > 1:
            overloaded_guids.append(guid)
    if overloaded_guids:
        collisions["genuinely_overloaded_guid"] = [overloaded_guids]

    return collisions


def _text_list(raw: Any) -> list[str]:
    if isinstance(raw, (list, tuple)):
        return [_text(v) for v in raw if _text(v)]
    value = _text(raw)
    return [value] if value else []


def _predicate(
    predicate_ref: str,
    condition: bool | None,
    *,
    reason_code: str,
    observed: Any,
    evidence_refs: Sequence[str] = (),
    incomplete_evidence_kind: str | None = None,
) -> dict[str, Any]:
    state = (
        "unresolved" if condition is None else "satisfied" if condition else "failed"
    )
    return {
        "predicate_ref": predicate_ref,
        "state": state,
        "reason_code": reason_code,
        "observed": observed,
        "evidence_refs": list(evidence_refs),
        "incomplete_evidence_kind": incomplete_evidence_kind,
    }


def build_rules() -> list[dict[str, Any]]:
    """Return the candidate-only A1/A2/A3/A5/H4 rule catalogue."""

    common = {
        "domain_contract_ref": DOMAIN_CONTRACT_REF,
        "transformation_contract_ref": TRANSFORMATION_CONTRACT_REF,
        "rule_state": "candidate",
    }
    return [
        build_transformation_rule(
            **common,
            structural_family_ref="climate-ghg:A1:atomic-annual-total:v0_1",
            detector_ref="detector:atomic-annual-total:v0_1",
            near_miss_refs=["residual:scope-overlap", "residual:period-mismatch"],
        ),
        build_transformation_rule(
            **common,
            structural_family_ref="climate-ghg:A2:atomic-scoped-component:v0_1",
            detector_ref="detector:atomic-scoped-component:v0_1",
            evidence_refs=[
                "review-confirmation:Q101416961$FA70FC6A-B0CD-4838-8475-375506C8B6FB"
            ],
            near_miss_refs=[
                "residual:scope-overlap",
                "residual:component-total-contradiction",
            ],
        ),
        build_transformation_rule(
            **common,
            structural_family_ref="climate-ghg:A3:already-separated-annual-series:v0_1",
            detector_ref="detector:already-separated-annual-series:v0_1",
            near_miss_refs=["residual:period-overlap", "residual:multi-year-range"],
        ),
        build_transformation_rule(
            **common,
            structural_family_ref="climate-ghg:A5:nonexhaustive-partial-family:v0_1",
            detector_ref="detector:nonexhaustive-partial-family:v0_1",
        ),
        build_transformation_rule(
            **common,
            structural_family_ref="climate-ghg:H4:duplicate-semantic-slot-hold:v0_1",
            detector_ref="detector:duplicate-semantic-slot-hold:v0_1",
        ),
    ]


def _common_predicates(
    candidate: Mapping[str, Any], *, target_collision_state: str
) -> list[dict[str, Any]]:
    classifier = candidate.get("family_classifier") or {}
    validation = candidate.get("model_validation") or {}
    bundle = candidate.get("claim_bundle_before") or {}
    family = candidate.get("statement_family_context") or {}
    statement_ref = _text(candidate.get("source_statement_id"))
    subject_family = _text(classifier.get("subject_family"))
    reporting_period = _text(classifier.get("reporting_period_kind"))
    unit = _text(validation.get("resolved_unit_qid"))
    method = _text(classifier.get("method_resolution"))
    references = bundle.get("references")
    collision = _text(target_collision_state) or "unknown"
    return [
        _predicate(
            "subject.enterprise-compatible",
            True
            if subject_family == "company"
            else False
            if subject_family == "non_company"
            else None,
            reason_code="subject_company"
            if subject_family == "company"
            else "subject_not_company_or_unresolved",
            observed=subject_family or "unknown",
            evidence_refs=classifier.get("subject_resolution", {}).get(
                "matched_type_qids", ()
            ),
            incomplete_evidence_kind=(
                "bounded_inspection" if subject_family not in {"company", "non_company"} else None
            ),
        ),
        _predicate(
            "statement.target-model-safe",
            _text(validation.get("status")) == "model_safe",
            reason_code="model_safe"
            if _text(validation.get("status")) == "model_safe"
            else "model_not_safe",
            observed=_text(validation.get("status")) or "unknown",
            evidence_refs=[statement_ref],
        ),
        _predicate(
            "statement.atomic-substitution-shape",
            _text(candidate.get("classification"))
            in {"safe_equivalent", "safe_with_reference_transfer"},
            reason_code="atomic_substitution_shape"
            if _text(candidate.get("classification"))
            in {"safe_equivalent", "safe_with_reference_transfer"}
            else "statement_requires_other_disposition",
            observed=_text(candidate.get("classification")) or "unknown",
            evidence_refs=[statement_ref],
        ),
        _predicate(
            "statement.annual-period",
            reporting_period in {"single_reporting_period", "single_interval_period"},
            reason_code="annual_period_resolved"
            if reporting_period in {"single_reporting_period", "single_interval_period"}
            else "annual_period_unresolved_or_overloaded",
            observed=reporting_period or "unknown",
            evidence_refs=[statement_ref],
        ),
        _predicate(
            "statement.compatible-unit",
            True if unit else None,
            reason_code="unit_resolved" if unit else "unit_unresolved",
            observed=unit or "unknown",
            evidence_refs=[unit] if unit else (),
            incomplete_evidence_kind="source_data" if not unit else None,
        ),
        _predicate(
            "statement.recognized-method",
            True
            if method == "recognized_method"
            else None
            if method in {"", "missing_but_inferable"}
            else False,
            reason_code="method_recognized"
            if method == "recognized_method"
            else "method_unresolved_or_incompatible",
            observed=method or "unknown",
            evidence_refs=validation.get("determination_method_values", ()),
            incomplete_evidence_kind=(
                "source_data" if method in {"", "missing_but_inferable"} else None
            ),
        ),
        _predicate(
            "statement.transferable-reference",
            True
            if isinstance(references, Sequence)
            and not isinstance(references, (str, bytes))
            and bool(references)
            else None,
            reason_code="reference_present"
            if references
            else "reference_transfer_unresolved",
            observed={
                "reference_count": len(references)
                if isinstance(references, list)
                else 0
            },
            evidence_refs=[statement_ref],
            incomplete_evidence_kind="source_data" if not references else None,
        ),
        _predicate(
            "family.complete-coverage",
            True if family.get("coverage_complete") is True else None,
            reason_code="family_coverage_complete"
            if family.get("coverage_complete") is True
            else "family_coverage_incomplete",
            observed=bool(family.get("coverage_complete")),
            evidence_refs=family.get("member_statement_ids", ()),
            incomplete_evidence_kind=(
                "recoverable_retrieval" if not family.get("coverage_complete") else None
            ),
        ),
        _predicate(
            "entity.target-property-absent",
            True
            if collision == "absent"
            else False
            if collision == "present"
            else None,
            reason_code="target_property_absent"
            if collision == "absent"
            else "target_property_present_or_unresolved",
            observed=collision,
            incomplete_evidence_kind="recoverable_retrieval" if collision == "unknown" else None,
        ),
    ]


def _family_conflict_predicate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    family = candidate.get("statement_family_context") or {}
    partition = _text(family.get("scope_partition_state"))
    total_relation = _text(family.get("total_component_relation"))
    conflicting = (
        partition in {"overlapping", "overloaded"} or total_relation == "contradiction"
    )
    unresolved = partition in {"", "incomplete"} or total_relation == "not_comparable"
    return _predicate(
        "family.no-conflict",
        None if unresolved and not conflicting else not conflicting,
        reason_code="family_coherent"
        if not conflicting and not unresolved
        else "family_conflict"
        if conflicting
        else "family_coherence_unresolved",
        observed={
            "scope_partition_state": partition,
            "total_component_relation": total_relation,
        },
        evidence_refs=family.get("member_statement_ids", ()),
        incomplete_evidence_kind="bounded_inspection" if unresolved and not conflicting else None,
    )


def _target_domain(candidate: Mapping[str, Any], *, target_collision_state: str) -> tuple[str, list[str]]:
    """Classify explicit target-domain exclusions without inventing a migration rule."""

    classifier = candidate.get("family_classifier") or {}
    validation = candidate.get("model_validation") or {}
    subject_family = _text(classifier.get("subject_family"))
    issues = {_text(value) for value in validation.get("issues") or ()}
    collision = _text(target_collision_state) or "unknown"
    reasons: list[str] = []
    if subject_family == "non_company":
        reasons.append("X1_different_subject_domain")
    if "non_climate_unit" in issues:
        reasons.append("X5_incompatible_quantity_semantics")
    if "non_ghg_protocol_method" in issues:
        reasons.append("X5_incompatible_quantity_semantics")
    if collision == "present":
        reasons.append("X6_target_property_collision")
    if reasons:
        return "excluded", sorted(set(reasons))
    return ("in_scope" if subject_family == "company" else "unknown"), []


def _member_evidence(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Emit profile-configured member evidence for the generic family carrier."""

    family = candidate.get("statement_family_context") or {}
    classifier = candidate.get("family_classifier") or {}
    validation = candidate.get("model_validation") or {}
    period_kind = _text(classifier.get("reporting_period_kind"))
    resolved_year = _text(validation.get("resolved_year"))
    period_observed = period_kind in {
        "single_reporting_period",
        "single_interval_period",
    } and bool(resolved_year)
    period_shape = {
        "single_reporting_period": "point_in_time_year",
        "single_interval_period": "same_year_interval",
        "multi_year_range": "multi_year_interval",
    }.get(period_kind, "absent" if not period_kind else "unparsable")
    references = (candidate.get("claim_bundle_before") or {}).get("references")
    unresolved_inputs = (
        _text(classifier.get("subject_family")) not in {"company", "non_company"}
        or not period_observed
        or not bool(_text(validation.get("resolved_unit_qid")))
        or _text(classifier.get("method_resolution"))
        in {"", "missing_but_inferable", "unresolved"}
        or not isinstance(references, Sequence)
        or isinstance(references, (str, bytes))
        or not bool(references)
    )
    direct_conformant = (
        _text(classifier.get("subject_family")) == "company"
        and _text(validation.get("status")) == "model_safe"
        and not candidate.get("split_axes")
        and period_observed
        and bool(_text(validation.get("resolved_unit_qid")))
        and _text(classifier.get("method_resolution")) == "recognized_method"
        and isinstance(references, Sequence)
        and not isinstance(references, (str, bytes))
        and bool(references)
    )
    slot = GHGStatementSlot.from_candidate(candidate)
    bundle = candidate.get("claim_bundle_before") or {}
    qualifiers = bundle.get("qualifiers") or {}
    return {
        "family_id": _text(family.get("family_id")),
        "statement_id": _text(candidate.get("source_statement_id")),
        "period_values": [resolved_year] if period_observed else [],
        "period_coverage_state": "observed" if period_observed else "unresolved",
        "period_shape": period_shape if period_observed else "unresolved",
        "conformance_state": (
            "unresolved"
            if unresolved_inputs
            else "conformant"
            if direct_conformant
            else "nonconformant"
        ),
        "ghg_slot": {
            "year": slot.year,
            "scope": slot.scope,
            "applies_to_part": slot.applies_to_part,
            "method": slot.method,
            "unit": slot.unit,
            "slot_identity_state": slot.slot_identity_state,
            "rank": slot.rank,
            "value": _text(bundle.get("value")),
            "reference_group": slot.reference_group,
            "semantic_slot": list(slot.semantic_slot),
            "is_total": slot.is_total(),
        },
        "qualifier_values": {
            "scope_values": _text_list(qualifiers.get("P3831")),
            "applies_to_part_values": _text_list(qualifiers.get("P518")),
            "method_values": _text_list(qualifiers.get("P459")),
        },
    }


def _dependency_group_assessment(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Supply climate-family geometry for generic dependency-group inventory.

    This is a diagnostic action proposal, not a transformation decision. It
    names the strongest observed obstruction while retaining overlapping
    secondary geometry for later rule discovery and review.

    When member_slot_data is available, F4/F5 classification uses slot-level
    collisions rather than coarse family-level geometry.  Families whose
    members all occupy unique semantic slots are recognised as valid matrices
    even when the family-level scope check reports overlap.
    """

    family = candidate.get("statement_family_context") or {}
    member_ids = [
        _text(statement_id)
        for statement_id in family.get("member_statement_ids") or ()
        if _text(statement_id)
    ]
    partition = _text(family.get("scope_partition_state")) or "unknown"
    total_relation = _text(family.get("total_component_relation")) or "unknown"
    period_geometry = _text(family.get("period_geometry")) or "unresolved"
    period_partition = _text(family.get("period_partition_state")) or "unresolved"
    member_conformance = _text(family.get("member_conformance_state")) or "unresolved"
    member_states = family.get("member_conformance_states") or {}
    nonconforming_members = sorted(
        statement_id
        for statement_id, state in member_states.items()
        if _text(state) == "nonconformant"
    )
    conformant_members = sorted(
        statement_id
        for statement_id, state in member_states.items()
        if _text(state) == "conformant"
    )
    member_slot_data: list[dict[str, Any]] = family.get("member_slot_data") or []
    slot_collisions: dict[str, list[list[str]]] = (
        family.get("slot_collisions") or {}
    )

    has_duplicate_slot = bool(slot_collisions.get("duplicate_semantic_slot"))
    has_overloaded_guid = bool(slot_collisions.get("genuinely_overloaded_guid"))
    slot_data_available = bool(member_slot_data)
    all_slots_unique = (
        slot_data_available
        and not has_duplicate_slot
        and not has_overloaded_guid
    )

    component_coverage = _family_component_coverage_state(
        member_slot_data, family
    )

    has_total = _text(family.get("total_value")) or _text(
        family.get("component_sum")
    )
    has_total_and_components = bool(has_total) and any(
        not (ev.get("ghg_slot") or {}).get("is_total")
        for ev in member_slot_data
    )
    coverage_exhaustive = component_coverage == "exhaustive"
    coverage_partial = component_coverage in {
        "explicitly_partial",
        "inferred_partial",
        "components_exceed_total",
    }

    secondary: list[str] = []
    if total_relation == "contradiction":
        secondary.append("component_total_mismatch")
    if has_duplicate_slot:
        secondary.append("duplicate_semantic_slot")
    if has_overloaded_guid:
        secondary.append("genuinely_overloaded_guid")
    if partition == "overlapping":
        secondary.append("scope_overlap")
    elif partition == "overloaded":
        secondary.append("scope_not_partitioned")
    if period_geometry in {
        "multi_year_interval",
        "mixed_period_representation",
        "duplicate_or_overlapping_period",
        "period_absent",
        "period_unparsable",
        "unresolved",
        "incomplete",
    }:
        secondary.append("period_geometry:" + period_geometry)
    if member_conformance == "member_conflict":
        secondary.append("mixed_member_conformance")
    elif member_conformance in {"unresolved", "incomplete"}:
        secondary.append("sibling_semantics_unresolved")
    if component_coverage:
        secondary.append("component_coverage:" + component_coverage)

    transition_receipt: dict[str, Any] | None = None

    h4_sub_dispositions = []
    if slot_data_available and has_duplicate_slot:
        h4_details = slot_collisions.get("h4_details") or []
        for detail in h4_details:
            h4_sub_dispositions.append({
                "sub_disposition": detail.get("sub_disposition"),
                "collision_type": detail.get("collision_type"),
                "member_guids": detail.get("member_guids"),
                "slot": detail.get("slot"),
                "has_unresolved_coordinate": detail.get("has_unresolved_coordinate"),
            })
        sub_disp_types = {d.get("sub_disposition") for d in h4_details}
        if "H4c" in sub_disp_types:
            primary, action, affected = (
                "H4c_conflicting_value_semantic_slot",
                "review_conflicting_values",
                member_ids,
            )
        elif "H4a" in sub_disp_types:
            primary, action, affected = (
                "H4a_confirmed_duplicate_semantic_slot",
                "review_duplicate_slot",
                member_ids,
            )
        elif "H4b" in sub_disp_types:
            primary, action, affected = (
                "H4b_provisional_duplicate_unresolved_coordinate",
                "hold_provisional_collision",
                member_ids,
            )
        elif "H4d" in sub_disp_types:
            primary, action, affected = (
                "H4d_rank_variant_semantic_slot",
                "review_rank_supersession",
                member_ids,
            )
        else:
            primary, action, affected = (
                "H4_duplicate_semantic_slot",
                "review_duplicate_slot",
                member_ids,
            )
    elif slot_data_available and has_overloaded_guid:
        primary, action, affected = (
            "H5_genuinely_overloaded_guid",
            "review_overloaded_statement",
            member_ids,
        )
    elif (
        slot_data_available
        and all_slots_unique
        and has_total_and_components
        and coverage_exhaustive
    ):
        primary, action, affected = (
            "F1_coherent_atomic_total_component_family",
            "preserve_existing_partition",
            member_ids,
        )
    elif (
        slot_data_available
        and all_slots_unique
        and has_total_and_components
        and coverage_partial
    ):
        primary, action, affected = (
            "A5_nonexhaustive_partial_family",
            "hold_partial_component_coverage",
            member_ids,
        )
    elif slot_data_available and all_slots_unique:
        primary, action, affected = (
            "F1_coherent_atomic_total_component_family",
            "preserve_existing_partition",
            member_ids,
        )
    elif not slot_data_available and partition == "already_partitioned" and total_relation == "exact_reconciliation":
        primary, action, affected = (
            "F1_coherent_atomic_total_component_family",
            "preserve_existing_partition",
            member_ids,
        )
    elif not slot_data_available and total_relation == "contradiction":
        primary, action, affected = (
            "F5_contradictory_or_nonreconciling_total",
            "hold_total_reconciliation",
            member_ids,
        )
    elif partition in {"overlapping", "overloaded"}:
        primary, action, affected = (
            "F4_overlapping_or_nonpartitioned_scopes",
            "hold_scope_partition",
            member_ids,
        )
    elif period_geometry in {
        "multi_year_interval",
        "mixed_period_representation",
        "duplicate_or_overlapping_period",
        "period_absent",
        "period_unparsable",
        "unresolved",
        "incomplete",
    }:
        primary, action, affected = (
            "F3_unresolved_or_nonannual_period_representation",
            "hold_period_geometry",
            member_ids,
        )
    elif member_conformance == "member_conflict" and conformant_members:
        primary, action, affected = (
            "F7_conformant_member_blocked_by_sibling_dependency",
            "review_member_independence",
            nonconforming_members or member_ids,
        )
    elif member_conformance == "member_conflict":
        primary, action, affected = (
            "F6_mixed_statement_semantics",
            "separate_member_semantics",
            nonconforming_members or member_ids,
        )
    elif period_partition == "distinct_non_overlapping" and member_conformance == "all_conform":
        primary, action, affected = (
            "F2_coherent_multi_year_annual_series",
            "evaluate_already_separated_series",
            member_ids,
        )
    else:
        primary, action, affected = (
            "F8_malformed_or_legacy_reconstruction_family",
            "review_family_reconstruction",
            member_ids,
        )
    payload = {
        "primary_obstruction": primary,
        "secondary_obstructions": secondary,
        "candidate_action": action,
        "affected_member_refs": affected,
        "geometry": {
            "scope_partition_state": partition,
            "total_component_relation": total_relation,
            "period_partition_state": period_partition,
            "period_geometry": period_geometry,
            "member_conformance_state": member_conformance,
            "member_count": len(member_ids),
        },
    }
    if h4_sub_dispositions:
        payload["h4_sub_dispositions"] = h4_sub_dispositions
    if slot_data_available and family.get("scope_partition_state") in {
        "overlapping",
        "overloaded",
        "already_partitioned",
    }:
        transition_receipt = _transition_receipt(
            old_assessment={
                "scope_partition_state": partition,
                "total_component_relation": total_relation,
                "slot_collisions": slot_collisions,
                "component_coverage": component_coverage,
            },
            new_primary=primary,
            member_ids=member_ids,
            member_slot_data=member_slot_data,
        )
        if transition_receipt:
            payload["transition_receipt"] = transition_receipt
    return payload


def _transition_receipt(
    *,
    old_assessment: Mapping[str, Any],
    new_primary: str,
    member_ids: Sequence[str],
    member_slot_data: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Record classification transition with evidence when slot normalization changes the result.

    Returns None if no meaningful transition occurred (e.g. the new code
    reached the same conclusion as the equivalent old path).
    """
    old_partition = _text(old_assessment.get("scope_partition_state"))
    old_total_rel = _text(old_assessment.get("total_component_relation"))
    collisions = old_assessment.get("slot_collisions") or {}
    coverage = _text(old_assessment.get("component_coverage"))
    unique_slots = set()
    for ev in member_slot_data:
        slot_tuple = tuple(
            (ev.get("ghg_slot") or {}).get(k, "")
            for k in ("year", "scope", "applies_to_part", "method", "unit")
        )
        unique_slots.add(slot_tuple)

    member_node_ids = [
        {"statement_id": _text(ev.get("statement_id"))}
        for ev in member_slot_data
        if _text(ev.get("statement_id"))
    ]

    reasons: list[str] = []

    if new_primary in {
        "F1_coherent_atomic_total_component_family",
        "A5_nonexhaustive_partial_family",
    } and old_partition in {"overlapping", "overloaded"}:
        reasons.append(
            "apparent scope overlap dissolved by semantic-slot uniqueness"
        )
    if new_primary == "A5_nonexhaustive_partial_family" and old_total_rel == "contradiction":
        reasons.append(
            "component set not proven exhaustive; "
            "components below total are compatible with partial coverage"
        )
    if new_primary == "H4_duplicate_semantic_slot" and old_partition in {
        "overlapping",
        "overloaded",
    }:
        reasons.append(
            "same-slot collision confirmed by normalized slot identity"
        )
    if coverage and new_primary != "F1_coherent_atomic_total_component_family":
        reasons.append(
            f"component coverage state is {coverage}; "
            "no exhaustive-partition assertion in source evidence"
        )

    if not reasons:
        return None

    return {
        "old_scope_partition_state": old_partition,
        "old_total_component_relation": old_total_rel,
        "new_primary_obstruction": new_primary,
        "transition_reasons": reasons,
        "evidence": {
            "unique_semantic_slot_count": len(unique_slots),
            "slot_collisions": dict(collisions),
            "component_coverage_state": coverage,
            "member_count": len(member_ids),
            "affected_members": member_node_ids,
        },
        "authority": "diagnostic_transition_only",
        "promotion_effect": "not_evaluated",
    }


def _family_component_coverage_state(
    member_slot_data: Sequence[Mapping[str, Any]],
    family_context: Mapping[str, Any],
) -> str:
    """Derive component-coverage state from slot data and family context.

    Returns one of: exhaustive, explicitly_partial, components_exceed_total,
    unknown, or empty string.
    """
    if not member_slot_data:
        return ""

    total_relation = _text(family_context.get("total_component_relation"))
    if total_relation == "exact_reconciliation":
        return "exhaustive"
    if total_relation != "contradiction":
        return ""

    total_value = _text(family_context.get("total_value"))
    component_sum = _text(family_context.get("component_sum"))
    if not total_value or not component_sum:
        return "unknown"

    comp_dec = _safe_decimal(component_sum)
    total_dec = _safe_decimal(total_value)
    if comp_dec is None or total_dec is None:
        return "unknown"

    if comp_dec < total_dec:
        return "explicitly_partial"
    if comp_dec > total_dec:
        return "components_exceed_total"

    return "unknown"


def _safe_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _hydrate_family_evidence(
    candidates: Sequence[Mapping[str, Any]],
    family_member_candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    contexts: dict[str, Mapping[str, Any]] = {}
    for candidate in candidates:
        family = candidate.get("statement_family_context") or {}
        family_id = _text(family.get("family_id"))
        if family_id:
            contexts[family_id] = family
    evidence = [
        _member_evidence(candidate)
        for candidate in family_member_candidates
        if _text((candidate.get("statement_family_context") or {}).get("family_id"))
        in contexts
    ]
    hydrated = build_statement_family_member_evidence(contexts, evidence)
    member_slots: dict[str, list[dict[str, Any]]] = {}
    for member_ev in evidence:
        family_id = _text(member_ev.get("family_id"))
        statement_id = _text(member_ev.get("statement_id"))
        if not family_id or not statement_id:
            continue
        member_slots.setdefault(family_id, []).append(
            {
                "statement_id": statement_id,
                "ghg_slot": member_ev.get("ghg_slot") or {},
                "qualifier_values": member_ev.get("qualifier_values") or {},
            }
        )
    slot_collisions: dict[str, dict[str, list[list[str]]]] = {}
    for family_id, members in member_slots.items():
        collisions = _slot_collisions(members)
        if collisions:
            slot_collisions[family_id] = collisions

    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        copied = dict(candidate)
        family = candidate.get("statement_family_context") or {}
        family_id = _text(family.get("family_id"))
        copied["statement_family_context"] = dict(
            hydrated[family_id]
        )
        if family_id in slot_collisions:
            copied["statement_family_context"]["slot_collisions"] = slot_collisions[
                family_id
            ]
        copied["statement_family_context"]["member_slot_data"] = member_slots.get(
            family_id, []
        )
        enriched.append(copied)
    return enriched


def evaluate_candidate(
    candidate: Mapping[str, Any],
    *,
    rules: Sequence[Mapping[str, Any]],
    target_collision_state: str = "unknown",
) -> dict[str, Any]:
    """Evaluate one supplied candidate against the A1/A2/A3 contracts."""

    candidate_ref = _text(candidate.get("candidate_id"))
    family = candidate.get("statement_family_context") or {}
    dependency_group_ref = _text(family.get("family_id"))
    if not candidate_ref or not dependency_group_ref:
        raise ValueError("profile evaluation requires candidate and family refs")
    classifier = candidate.get("family_classifier") or {}
    validation = candidate.get("model_validation") or {}
    scope_resolution = _text(classifier.get("scope_resolution"))
    subject_family = _text(classifier.get("subject_family"))
    target_domain_state, exclusion_reasons = _target_domain(
        candidate, target_collision_state=target_collision_state
    )
    common = _common_predicates(
        candidate, target_collision_state=target_collision_state
    )
    results: list[dict[str, Any]] = []
    for rule in rules:
        family_ref = _text(rule.get("structural_family_ref"))
        predicates = list(common)
        if ":A1:" in family_ref:
            period_partition = _text(family.get("period_partition_state"))
            predicates.extend(
                [
                    _predicate(
                        "statement.entity-level-total",
                        scope_resolution == "total_unscoped",
                        reason_code="total_unscoped"
                        if scope_resolution == "total_unscoped"
                        else "not_entity_level_total",
                        observed=scope_resolution or "unknown",
                    ),
                    _predicate(
                        "family.not-distinct-annual-series",
                        period_partition != "distinct_non_overlapping",
                        reason_code="not_distinct_annual_series"
                        if period_partition != "distinct_non_overlapping"
                        else "distinct_annual_series_requires_A3",
                        observed=period_partition or "not_inspected",
                        evidence_refs=family.get("member_statement_ids", ()),
                    ),
                    _family_conflict_predicate(candidate),
                ]
            )
        elif ":A2:" in family_ref:
            partition = _text(family.get("scope_partition_state"))
            total_relation = _text(family.get("total_component_relation"))
            period_partition = _text(family.get("period_partition_state"))
            predicates.extend(
                [
                    _predicate(
                        "statement.explicit-scope",
                        scope_resolution == "explicit_scope",
                        reason_code="scope_explicit"
                        if scope_resolution == "explicit_scope"
                        else "scope_not_explicit",
                        observed=scope_resolution or "unknown",
                    ),
                    _predicate(
                        "family.non-overlapping-partition",
                        partition == "already_partitioned",
                        reason_code="partition_already_separated"
                        if partition == "already_partitioned"
                        else "partition_not_proven_non_overlapping",
                        observed=partition or "unknown",
                        evidence_refs=family.get("member_statement_ids", ()),
                    ),
                    _predicate(
                        "family.coherent-total-relation",
                        True
                        if total_relation in {"exact_reconciliation", "no_total"}
                        else False
                        if total_relation == "contradiction"
                        else None,
                        reason_code="total_relation_coherent"
                        if total_relation in {"exact_reconciliation", "no_total"}
                        else "total_relation_contradictory_or_unresolved",
                        observed=total_relation or "unknown",
                        evidence_refs=family.get("member_statement_ids", ()),
                    ),
                    _predicate(
                        "family.not-distinct-annual-series",
                        period_partition != "distinct_non_overlapping",
                        reason_code="not_distinct_annual_series"
                        if period_partition != "distinct_non_overlapping"
                        else "distinct_annual_series_requires_A3",
                        observed=period_partition or "not_inspected",
                        evidence_refs=family.get("member_statement_ids", ()),
                    ),
                ]
            )
        elif ":A3:" in family_ref:
            period_partition = _text(family.get("period_partition_state"))
            member_conformance = _text(family.get("member_conformance_state"))
            predicates.extend(
                [
                    _predicate(
                        "family.distinct-annual-periods",
                        True
                        if period_partition == "distinct_non_overlapping"
                        else False
                        if period_partition == "overlapping"
                        else None,
                        reason_code="annual_periods_distinct"
                        if period_partition == "distinct_non_overlapping"
                        else "annual_period_partition_unresolved",
                        observed=period_partition or "not_inspected",
                        incomplete_evidence_kind=(
                            "recoverable_retrieval"
                            if period_partition in {"incomplete", "not_inspected"}
                            else "source_data"
                            if period_partition == "unresolved"
                            else None
                        ),
                    ),
                    _predicate(
                        "family.members-independently-conform",
                        True
                        if member_conformance == "all_conform"
                        else False
                        if member_conformance == "member_conflict"
                        else None,
                        reason_code="members_independently_conform"
                        if member_conformance == "all_conform"
                        else "member_conformance_unresolved",
                        observed=member_conformance or "not_inspected",
                        incomplete_evidence_kind=(
                            "recoverable_retrieval"
                            if member_conformance in {"incomplete", "not_inspected"}
                            else "bounded_inspection"
                            if member_conformance == "unresolved"
                            else None
                        ),
                    ),
                    _family_conflict_predicate(candidate),
                ]
            )
        elif ":A5:" in family_ref:
            member_slot_data = family.get("member_slot_data") or []
            component_coverage = _family_component_coverage_state(member_slot_data, family)
            total_relation = _text(family.get("total_component_relation"))
            slot_collisions = family.get("slot_collisions") or {}
            has_duplicate_slot = bool(slot_collisions.get("duplicate_semantic_slot"))
            has_overloaded_guid = bool(slot_collisions.get("genuinely_overloaded_guid"))
            all_slots_unique = not has_duplicate_slot and not has_overloaded_guid
            predicates.extend(
                [
                    _predicate(
                        "statement.unique-exact-slot",
                        all_slots_unique,
                        reason_code="slots_unique" if all_slots_unique else "slot_collision_detected",
                        observed=all_slots_unique,
                    ),
                    _predicate(
                        "family.partial-coverage-compatible",
                        component_coverage in ("explicitly_partial", "inferred_partial", "components_exceed_total"),
                        reason_code="partial_coverage_compatible"
                        if component_coverage in ("explicitly_partial", "inferred_partial", "components_exceed_total")
                        else "not_partial_coverage",
                        observed=component_coverage or "unknown",
                    ),
                    _predicate(
                        "family.no-exhaustive-partition-claim",
                        total_relation != "exact_reconciliation",
                        reason_code="no_exhaustive_claim"
                        if total_relation != "exact_reconciliation"
                        else "exhaustive_claim_requires_F1",
                        observed=total_relation or "unknown",
                    ),
                ]
            )
        elif ":H4:" in family_ref:
            slot_collisions = family.get("slot_collisions") or {}
            has_duplicate_slot = bool(slot_collisions.get("duplicate_semantic_slot"))
            sub_disp = "none"
            h4_details = slot_collisions.get("h4_details") or []
            if h4_details:
                sub_disp = "|".join(sorted(list(set(d.get("sub_disposition") for d in h4_details))))
            predicates.extend(
                [
                    _predicate(
                        "family.duplicate-slot-detected",
                        has_duplicate_slot,
                        reason_code="duplicate_slot_found" if has_duplicate_slot else "no_duplicate_slots",
                        observed=has_duplicate_slot,
                    ),
                    _predicate(
                        "family.slot-collision-sub-disposition",
                        has_duplicate_slot,
                        reason_code="sub_disposition_" + sub_disp if has_duplicate_slot else "no_sub_disposition",
                        observed=sub_disp,
                    ),
                ]
            )
        else:
            raise ValueError("unsupported climate transformation rule")
        results.append(
            build_rule_detector_result(
                rule=rule,
                candidate_ref=candidate_ref,
                dependency_group_ref=dependency_group_ref,
                predicate_results=predicates,
                coverage_state="observed"
                if family.get("coverage_complete")
                else "incomplete",
                target_domain_state=target_domain_state,
                strata={
                    "subject_family": subject_family or "unknown",
                    "family_shape": _text(family.get("scope_partition_state"))
                    or "unknown",
                    "reporting_period_kind": _text(
                        classifier.get("reporting_period_kind")
                    )
                    or "unknown",
                    "period_geometry": _text(family.get("period_geometry"))
                    or "unresolved",
                    "method_resolution": _text(classifier.get("method_resolution"))
                    or "unknown",
                    "scope_resolution": scope_resolution or "unknown",
                    "unit": _text(validation.get("resolved_unit_qid")) or "unknown",
                    "legacy_bucket": _text(classifier.get("bucket")) or "unknown",
                },
            )
        )
    return {
        "candidate_ref": candidate_ref,
        "dependency_group_ref": dependency_group_ref,
        "coverage_state": "observed"
        if family.get("coverage_complete")
        else "incomplete",
        "target_domain_state": target_domain_state,
        "exclusion_reasons": exclusion_reasons,
        "dependency_group_assessment": _dependency_group_assessment(candidate),
        "detector_results": results,
        "strata": results[0]["strata"] if results else {},
    }


def build_coverage_report(
    migration_pack: Mapping[str, Any],
    *,
    source_snapshot_ref: str,
    target_collision_state: str = "unknown",
    family_member_candidates: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate a bounded supplied pack and return generic dry-run coverage."""

    rules = build_rules()
    candidates = [
        dict(candidate) for candidate in migration_pack.get("candidates") or ()
    ]
    if family_member_candidates is not None:
        candidates = _hydrate_family_evidence(candidates, family_member_candidates)
    evaluations = [
        evaluate_candidate(
            candidate,
            rules=rules,
            target_collision_state=target_collision_state,
        )
        for candidate in candidates
    ]
    report = build_rule_coverage_report(
        rules=rules,
        candidate_evaluations=evaluations,
        source_snapshot_ref=source_snapshot_ref,
    )
    return {"rules": rules, "coverage": report}


def build_h4_collision_report(
    migration_pack: Mapping[str, Any],
    family_member_candidates: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Inspect and classify all H4 families in the pack."""
    candidates = [
        dict(candidate) for candidate in migration_pack.get("candidates") or ()
    ]
    if family_member_candidates is not None:
        candidates = _hydrate_family_evidence(candidates, family_member_candidates)

    member_map = {}
    if family_member_candidates is not None:
        for c in family_member_candidates:
            stmt_id = _text(c.get("source_statement_id"))
            if stmt_id:
                member_map[stmt_id] = c
    for c in migration_pack.get("candidates") or ():
        stmt_id = _text(c.get("source_statement_id"))
        if stmt_id:
            member_map[stmt_id] = c

    collision_groups = []
    counts = {"H4a": 0, "H4b": 0, "H4c": 0, "H4d": 0}
    seen_group_refs = set()

    for candidate in candidates:
        family = candidate.get("statement_family_context") or {}
        family_id = _text(family.get("family_id"))
        if not family_id:
            continue

        slot_collisions = family.get("slot_collisions") or {}
        h4_details = slot_collisions.get("h4_details") or []
        for detail in h4_details:
            slot_tuple = tuple(detail.get("slot") or [])
            group_ref = f"{family_id}|slot:{slot_tuple}"
            if group_ref in seen_group_refs:
                continue
            seen_group_refs.add(group_ref)

            sub_disp = detail.get("sub_disposition") or "H4a"
            if sub_disp in counts:
                counts[sub_disp] += 1

            member_guids = detail.get("member_guids") or []
            values = {}
            ranks = {}
            temporal_evidence = {}
            slot_identity_states = {}
            unresolved_coordinates = []

            for guid in member_guids:
                member_cand = member_map.get(guid) or {}
                bundle = member_cand.get("claim_bundle_before") or {}
                qualifiers = bundle.get("qualifiers") or {}

                val = _text(bundle.get("value"))
                rank = _text(bundle.get("rank")) or "normal"

                ghg_slot = {}
                member_slot_list = family.get("member_slot_data") or []
                for msd in member_slot_list:
                    if _text(msd.get("statement_id")) == guid:
                        ghg_slot = msd.get("ghg_slot") or {}
                        break

                state = ghg_slot.get("slot_identity_state") or "unresolved"

                values[guid] = val
                ranks[guid] = rank
                slot_identity_states[guid] = state

                p580 = _text_list(qualifiers.get("P580"))
                p582 = _text_list(qualifiers.get("P582"))
                p585 = _text_list(qualifiers.get("P585"))
                temporal_evidence[guid] = {
                    "P580": p580,
                    "P582": p582,
                    "P585": p585,
                }

                if state in ("fiscal_canonical", "unresolved"):
                    unresolved_coordinates.append(guid)

            disposition_map = {
                "H4a": "confirmed_duplicate",
                "H4b": "provisional_temporal_collision",
                "H4c": "conflicting_value",
                "H4d": "rank_variant",
            }
            disposition = disposition_map.get(sub_disp, "confirmed_duplicate")

            slot_dict = {}
            if len(slot_tuple) == 5:
                slot_dict = {
                    "year": slot_tuple[0],
                    "scope": slot_tuple[1],
                    "applies_to_part": slot_tuple[2],
                    "method": slot_tuple[3],
                    "unit": slot_tuple[4],
                }

            collision_groups.append({
                "collision_group_ref": group_ref,
                "family_id": family_id,
                "slot": slot_dict,
                "sub_disposition": sub_disp,
                "member_guids": member_guids,
                "values": values,
                "ranks": ranks,
                "temporal_evidence": temporal_evidence,
                "slot_identity_states": slot_identity_states,
                "unresolved_coordinates": sorted(list(set(unresolved_coordinates))),
                "collision_disposition": disposition,
            })

    collision_groups.sort(key=lambda x: x["collision_group_ref"])

    return {
        "collision_groups": collision_groups,
        "counts_by_sub_disposition": counts,
    }


__all__ = [
    "build_coverage_report",
    "build_h4_collision_report",
    "build_rules",
    "evaluate_candidate",
]
