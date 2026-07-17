from __future__ import annotations

from copy import deepcopy

from src.policy.climate_ghg_transformation_profile import build_orthogonal_assessment


def _candidate(index: int, year: str, *, scope: str = "", value: str = "+10") -> dict:
    statement = f"Q1$S{index}"
    qualifiers = {
        "P459": ["Q56296245"],
        "P580": [f"+{year}-01-01T00:00:00Z"],
        "P582": [f"+{year}-12-31T00:00:00Z"],
    }
    if scope:
        qualifiers["P3831"] = [scope]
    return {
        "candidate_id": f"Q1|P5991|{index}",
        "source_statement_id": statement,
        "classification": "safe_with_reference_transfer",
        "family_classifier": {
            "subject_family": "company",
            "reporting_period_kind": "single_interval_period",
            "scope_resolution": "explicit_scope" if scope else "total_unscoped",
            "method_resolution": "recognized_method",
        },
        "model_validation": {
            "status": "model_safe",
            "resolved_year": year,
            "resolved_unit_qid": "Q57084755",
        },
        "claim_bundle_before": {
            "value": value,
            "rank": "normal",
            "unit": "Q57084755",
            "qualifiers": qualifiers,
            "references": [{"P854": ["https://example.test/report"]}],
        },
        "statement_family_context": {
            "family_id": "Q1|P5991",
            "coverage_complete": True,
            "member_statement_ids": [],
            "scope_partition_state": "unknown",
            "total_component_relation": "no_total",
        },
    }


def _assessment(candidates: list[dict], states: dict[str, str] | None = None) -> dict:
    member_ids = [row["source_statement_id"] for row in candidates]
    for row in candidates:
        row["statement_family_context"]["member_statement_ids"] = member_ids
    return build_orthogonal_assessment(
        {"candidates": candidates},
        provenance={"input.json": "b" * 64},
        target_collision_states=states
        or {row["source_statement_id"]: "absent" for row in candidates},
    )


def test_annual_series_is_coherent_a3_and_eligible() -> None:
    result = _assessment([_candidate(1, "2023"), _candidate(2, "2024")])
    family = result["families"][0]
    assert family["geometry_state"] == "annual_series"
    assert family["geometry_subtype"] == "total_series"
    assert all("A3" in row["legacy_projections"] for row in result["statements"])
    assert all(
        row["axes"]["execution_outcome"] == "eligible" for row in result["statements"]
    )


def test_partial_coverage_adds_a5_without_changing_eligibility() -> None:
    total = _candidate(1, "2024", value="+100")
    component = _candidate(2, "2024", scope="Q124883250", value="+40")
    for row in (total, component):
        row["statement_family_context"].update(
            total_component_relation="contradiction",
            total_value="100",
            component_sum="40",
        )
    result = _assessment([total, component])
    assert result["families"][0]["component_coverage"] == "partial"
    assert all("A5" in row["legacy_projections"] for row in result["statements"])
    assert all(
        row["axes"]["execution_outcome"] == "eligible" for row in result["statements"]
    )


def test_collisions_and_unresolved_target_evidence_hold() -> None:
    first = _candidate(1, "2024", scope="Q124883250")
    duplicate = deepcopy(first)
    duplicate["candidate_id"] = "Q1|P5991|2"
    duplicate["source_statement_id"] = "Q1$S2"
    result = _assessment([first, duplicate])
    assert all(
        row["axes"]["slot_integrity"] == "collided" for row in result["statements"]
    )
    assert all("H4" in row["legacy_projections"] for row in result["statements"])
    assert all(
        row["axes"]["execution_outcome"] == "hold" for row in result["statements"]
    )

    unresolved = _assessment([_candidate(1, "2024")], {"Q1$S1": "unresolved"})
    assert unresolved["statements"][0]["axes"]["execution_outcome"] == "hold"
