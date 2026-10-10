from __future__ import annotations

from copy import deepcopy

from src.policy.domain_invariants import build_invariant_revision
from src.policy.item_property_evidence import build_item_property_evidence_surface
from src.policy.nat_climate_peer_pressure import weld_nat_peer_cohort_residual


def _snapshot_and_surface() -> tuple[dict[str, object], dict[str, object]]:
    surface = build_item_property_evidence_surface(
        subject_qid="Q1",
        source_revision_ref="1",
        statements=[
            {
                "statement_ref": "Q1$P31",
                "property_id": "P31",
                "snak_type": "value",
                "value": "Q783794",
                "value_ref": "Q783794",
                "value_kind": "wikibase-item",
                "rank": "normal",
            }
        ],
        coverage_state="observed",
        coverage_policy_ref="coverage:nat",
        required_property_ids=["P31"],
        property_coverage={"P31": "observed"},
    )
    contributions = surface["peer_features"]
    revision = build_invariant_revision(
        domain_invariant_ref="wikidata:climate_ghg_p5991_to_p14143:v0_1",
        policy_model_ref="policy:P14143",
        policy_requirements=[],
        contribution_receipts=[
            {
                "member": {
                    "candidate_ref": "candidate:reviewed",
                    "source_revision_ref": "wikidata:Q1@1",
                    "review_disposition": "confirmed_model_conformant",
                    "review_decision_ref": "review:1",
                    "reviewer_authority_ref": "reviewer:1",
                    "coverage_state": "observed",
                    "feature_contributions": contributions,
                }
            }
        ],
        reviewer_authority_ref="reviewer:1",
    )
    return revision["snapshot"], surface


def _assessment() -> dict[str, object]:
    return {
        "schema_version": "sl.domain_pressure_assessment.v0_1",
        "candidate_ref": "candidate:Q1",
        "domain_invariant_ref": "wikidata:climate_ghg_p5991_to_p14143:v0_1",
        "coverage_state": "observed",
        "review_disposition": "C",
        "residuals": [
            {"residual_kind": "target_model", "state": "exact"},
            {
                "residual_kind": "peer_cohort",
                "state": "unresolved",
                "coverage_state": "uninspected",
            },
            {"residual_kind": "temporal", "state": "exact"},
        ],
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }


def test_weld_replaces_only_peer_residual_and_preserves_authority() -> None:
    snapshot, surface = _snapshot_and_surface()
    original = _assessment()
    before = deepcopy(original)
    result = weld_nat_peer_cohort_residual(
        pressure_assessment=original,
        invariant_snapshot=snapshot,
        item_surface=surface,
    )

    assert result["residuals"][0] == before["residuals"][0]
    assert result["residuals"][2] == before["residuals"][2]
    assert result["residuals"][1]["residual_kind"] == "peer_cohort"
    assert result["residuals"][1]["state"] == "exact"
    assert result["authority"] == "diagnostic_only"
    assert result["promotion_effect"] == "not_evaluated"
    assert result["edit_effect"] == "none"
    assert original == before


def test_uninspected_required_property_keeps_welded_peer_unresolved() -> None:
    snapshot, surface = _snapshot_and_surface()
    surface = deepcopy(surface)
    surface["coverage_state"] = "uninspected"
    surface["property_inventory"]["coverage_by_property"]["P31"] = "uninspected"
    surface["property_inventory"]["unresolved_required_property_ids"] = ["P31"]
    result = weld_nat_peer_cohort_residual(
        pressure_assessment=_assessment(),
        invariant_snapshot=snapshot,
        item_surface=surface,
    )
    peer = next(row for row in result["residuals"] if row["residual_kind"] == "peer_cohort")
    assert peer["state"] == "unresolved"
