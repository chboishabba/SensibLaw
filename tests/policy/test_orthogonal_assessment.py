from __future__ import annotations

from copy import deepcopy

import pytest

from src.policy.orthogonal_assessment import build_assessment, build_coverage_report


def _rows() -> tuple[list[dict], list[dict]]:
    family = {
        "family_ref": "family:1",
        "member_statement_refs": ["statement:1"],
        "geometry_state": "atomic",
        "geometry_subtype": "atomic",
        "component_coverage": "not_applicable",
        "slot_integrity": "coherent",
    }
    statement = {
        "statement_ref": "statement:1",
        "family_ref": "family:1",
        "axes": {
            "family_geometry": "atomic",
            "slot_integrity": "coherent",
            "component_coverage": "not_applicable",
            "statement_semantics": "supported",
            "execution_outcome": "eligible",
        },
        "eligibility_predicates": {"supported": "true"},
        "legacy_projections": ["A1"],
    }
    return [family], [statement]


def _build(families: list[dict], statements: list[dict]) -> dict:
    return build_assessment(
        schema_version="test.v1",
        classifier="test",
        families=families,
        statements=statements,
        provenance={"input.json": "a" * 64},
    )


def test_build_assessment_is_deterministic_and_aggregates_axes() -> None:
    families, statements = _rows()
    first = _build(families, statements)
    second = _build(list(reversed(families)), list(reversed(statements)))
    assert first == second
    report = build_coverage_report(first)
    assert report["statement_axis_counts"]["execution_outcome"] == {"eligible": 1}
    assert report["legacy_projection_counts"] == {"A1": 1}


def test_rejects_axis_and_family_reference_mismatches() -> None:
    families, statements = _rows()
    invalid_axis = deepcopy(statements)
    del invalid_axis[0]["axes"]["component_coverage"]
    with pytest.raises(ValueError, match="all axes"):
        _build(families, invalid_axis)
    unknown_family = deepcopy(statements)
    unknown_family[0]["family_ref"] = "family:missing"
    with pytest.raises(ValueError, match="unknown statement family"):
        _build(families, unknown_family)


def test_rejects_eligible_collision_and_false_predicate() -> None:
    families, statements = _rows()
    collided = deepcopy(statements)
    collided[0]["axes"]["slot_integrity"] = "collided"
    with pytest.raises(ValueError, match="cannot coexist"):
        _build(families, collided)
    false_predicate = deepcopy(statements)
    false_predicate[0]["eligibility_predicates"]["supported"] = "false"
    with pytest.raises(ValueError, match="all predicates true"):
        _build(families, false_predicate)
