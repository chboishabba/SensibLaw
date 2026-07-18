"""Generic validation and aggregation for orthogonal derived assessments."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any, Mapping, Sequence


_AXES = (
    "family_geometry",
    "slot_integrity",
    "component_coverage",
    "statement_semantics",
    "execution_outcome",
)
_ALLOWED_AUTHORITY = "candidate_review_only"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = str(record.get(field) or "").strip()
    if not value:
        raise ValueError(f"orthogonal assessment requires {field}")
    return value


def build_assessment(
    *,
    schema_version: str,
    classifier: str,
    families: Sequence[Mapping[str, Any]],
    statements: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, str],
    authority: str = _ALLOWED_AUTHORITY,
) -> dict[str, Any]:
    """Validate and deterministically construct an orthogonal assessment."""

    if authority != _ALLOWED_AUTHORITY:
        raise ValueError(
            "orthogonal assessment authority must be candidate_review_only"
        )
    if not provenance or any(len(str(value)) != 64 for value in provenance.values()):
        raise ValueError("provenance must contain SHA-256 hex digests")

    family_rows = sorted(
        (dict(row) for row in families),
        key=lambda row: _required_text(row, "family_ref"),
    )
    statement_rows = sorted(
        (dict(row) for row in statements),
        key=lambda row: _required_text(row, "statement_ref"),
    )
    family_refs = [_required_text(row, "family_ref") for row in family_rows]
    if len(family_refs) != len(set(family_refs)):
        raise ValueError("family references must be unique")
    statement_refs = [_required_text(row, "statement_ref") for row in statement_rows]
    if len(statement_refs) != len(set(statement_refs)):
        raise ValueError("statement references must be unique")

    family_ref_set = set(family_refs)
    members_by_family: dict[str, list[str]] = {ref: [] for ref in family_refs}
    for row in statement_rows:
        family_ref = _required_text(row, "family_ref")
        if family_ref not in family_ref_set:
            raise ValueError(f"unknown statement family reference: {family_ref}")
        axes = row.get("axes")
        if not isinstance(axes, Mapping) or set(axes) != set(_AXES):
            raise ValueError("every statement must carry exactly one value on all axes")
        for axis in _AXES:
            _required_text(axes, axis)
        predicates = row.get("eligibility_predicates")
        if not isinstance(predicates, Mapping) or not predicates:
            raise ValueError("statement eligibility predicates are required")
        if any(
            value not in {"true", "false", "unresolved"}
            for value in predicates.values()
        ):
            raise ValueError(
                "eligibility predicates must be true, false, or unresolved"
            )
        projections = set(row.get("legacy_projections") or ())
        outcome = axes["execution_outcome"]
        collision = (
            axes["slot_integrity"] == "collided"
            or predicates.get("no_target_collision") == "false"
        )
        if outcome == "eligible" and (collision or "H4" in projections):
            raise ValueError("eligible statements cannot coexist with collisions or H4")
        if outcome == "eligible" and any(
            value != "true" for value in predicates.values()
        ):
            raise ValueError("eligible statements require all predicates true")
        members_by_family[family_ref].append(row["statement_ref"])

    for row in family_rows:
        family_ref = row["family_ref"]
        members = sorted(str(value) for value in row.get("member_statement_refs") or ())
        if members != members_by_family[family_ref]:
            raise ValueError(
                f"family member references do not match statements: {family_ref}"
            )
        if not members:
            raise ValueError("families cannot be empty")

    identity = {
        "schema_version": schema_version,
        "classifier": classifier,
        "authority": authority,
        "provenance": dict(sorted(provenance.items())),
        "families": family_rows,
        "statements": statement_rows,
    }
    return {
        **identity,
        "assessment_ref": f"orthogonal-assessment:{_digest(identity)}",
        "execution_effect": "none",
        "promotion_effect": "none",
        "summary": {
            "family_count": len(family_rows),
            "statement_count": len(statement_rows),
        },
    }


def build_coverage_report(assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Aggregate axis, subtype, projection, intersection, and outcome counts."""

    statements = list(assessment.get("statements") or ())
    families = list(assessment.get("families") or ())
    axis_counts = {axis: Counter() for axis in _AXES}
    projection_counts: Counter[str] = Counter()
    intersection_counts: Counter[str] = Counter()
    predicate_attrition: dict[str, Counter[str]] = {}
    for row in statements:
        axes = row["axes"]
        for axis in _AXES:
            axis_counts[axis][axes[axis]] += 1
        projections = sorted(row.get("legacy_projections") or ())
        projection_counts.update(projections)
        intersection_counts["+".join(projections) if projections else "none"] += 1
        for predicate, state in row["eligibility_predicates"].items():
            predicate_attrition.setdefault(predicate, Counter())[state] += 1

    family_geometry = Counter(row["geometry_state"] for row in families)
    geometry_subtypes = Counter(row["geometry_subtype"] for row in families)
    coverage = Counter(row["component_coverage"] for row in families)
    integrity = Counter(row["slot_integrity"] for row in families)
    report = {
        "schema_version": "sl.orthogonal_coverage_report.v1",
        "assessment_ref": assessment.get("assessment_ref"),
        "authority": "diagnostic_aggregation_only",
        "execution_effect": "none",
        "family_count": len(families),
        "statement_count": len(statements),
        "family_counts": {
            "geometry_state": dict(sorted(family_geometry.items())),
            "geometry_subtype": dict(sorted(geometry_subtypes.items())),
            "component_coverage": dict(sorted(coverage.items())),
            "slot_integrity": dict(sorted(integrity.items())),
        },
        "statement_axis_counts": {
            axis: dict(sorted(counter.items())) for axis, counter in axis_counts.items()
        },
        "legacy_projection_counts": dict(sorted(projection_counts.items())),
        "legacy_projection_intersections": dict(sorted(intersection_counts.items())),
        "predicate_attrition": {
            key: dict(sorted(counter.items()))
            for key, counter in sorted(predicate_attrition.items())
        },
    }
    report["report_hash"] = _digest(report)
    return report


def validate_review_adjudications(
    *,
    assessment: Mapping[str, Any],
    manifest: Mapping[str, Any],
    adjudications: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a statement-level review sidecar against a sample manifest."""

    if adjudications.get("schema_version") != "sl.orthogonal_review_adjudications.v1":
        raise ValueError("unsupported orthogonal review adjudication schema")
    if adjudications.get("assessment_ref") != assessment.get("assessment_ref"):
        raise ValueError("review adjudications reference a different assessment")
    if adjudications.get("provenance") and dict(adjudications["provenance"]) != dict(
        assessment.get("provenance") or {}
    ):
        raise ValueError("review adjudications provenance differs from assessment")
    expected_families = {
        str(value) for value in manifest.get("selected_family_refs") or ()
    }
    expected_statements = {
        str(row.get("statement_ref"))
        for row in assessment.get("statements") or ()
        if str(row.get("family_ref")) in expected_families
    }
    statement_families = {
        str(row.get("statement_ref")): str(row.get("family_ref"))
        for row in assessment.get("statements") or ()
    }
    rows = [dict(row) for row in adjudications.get("statements") or ()]
    seen: set[str] = set()
    for row in rows:
        statement_ref = _required_text(row, "statement_ref")
        family_ref = _required_text(row, "family_ref")
        if statement_ref in seen:
            raise ValueError(f"duplicate review adjudication: {statement_ref}")
        if (
            family_ref not in expected_families
            or statement_ref not in expected_statements
        ):
            raise ValueError(
                f"review adjudication is outside the selected sample: {statement_ref}"
            )
        if statement_families.get(statement_ref) != family_ref:
            raise ValueError(f"review adjudication family mismatch: {statement_ref}")
        seen.add(statement_ref)
        for field in (
            "v2_outcome_correct",
            "semantic_subtype_correct",
            "target_semantics_appropriate",
            "qualifiers_preserved",
            "qualifier_repair_needed",
            "different_target_required",
            "hold_reason_correct",
        ):
            value = row.get(field)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f"review field must be boolean or null: {field}")
    if adjudications.get("status") == "complete" and seen != expected_statements:
        raise ValueError("complete adjudications must cover every sampled statement")
    return {
        **dict(adjudications),
        "statements": sorted(rows, key=lambda row: str(row["statement_ref"])),
        "reviewed_statement_count": len(seen),
        "sample_statement_count": len(expected_statements),
    }


__all__ = [
    "build_assessment",
    "build_coverage_report",
    "validate_review_adjudications",
]
