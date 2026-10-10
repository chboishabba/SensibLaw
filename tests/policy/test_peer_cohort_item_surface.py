from __future__ import annotations

from src.policy.domain_invariants import build_invariant_revision
from src.policy.item_property_evidence import build_item_property_evidence_surface
from src.policy.peer_cohort import build_peer_cohort_residual_from_item_surface


def _surface(p14143_coverage: str) -> dict[str, object]:
    return build_item_property_evidence_surface(
        subject_qid="QCOMPANY",
        source_revision_ref="wikidata:QCOMPANY@60",
        coverage_state="observed",
        coverage_policy_ref="coverage:nat-required-v1",
        required_property_ids=["P5991", "P14143"],
        property_coverage={"P5991": "observed", "P14143": p14143_coverage},
        statements=[
            {
                "statement_ref": "QCOMPANY$P5991",
                "property_id": "P5991",
                "value": "1000",
                "rank": "normal",
            }
        ],
    )


def _snapshot(peer_features: list[dict[str, str]]) -> dict[str, object]:
    result = build_invariant_revision(
        domain_invariant_ref="domain:climate",
        policy_model_ref="policy:P14143",
        policy_requirements=[{"feature": "property_family_coverage", "value": "observed"}],
        contribution_receipts=[
            {
                "member": {
                    "candidate_ref": "candidate:reviewed",
                    "source_revision_ref": "wikidata:QPEER@1",
                    "review_disposition": "confirmed_model_conformant",
                    "review_decision_ref": "review:1",
                    "reviewer_authority_ref": "reviewer:1",
                    "coverage_state": "observed",
                    "feature_contributions": peer_features,
                }
            }
        ],
        reviewer_authority_ref="reviewer:1",
    )
    return result["snapshot"]


def test_direct_surface_can_reach_exact_when_all_required_families_observed() -> None:
    surface = _surface("observed")
    residual = build_peer_cohort_residual_from_item_surface(
        candidate_ref="candidate:QCOMPANY",
        invariant_snapshot=_snapshot(surface["peer_features"]),
        item_surface=surface,
    )
    assert residual["coverage_state"] == "observed"
    assert residual["state"] == "exact"


def test_direct_surface_stays_unresolved_when_required_family_uninspected() -> None:
    surface = _surface("uninspected")
    residual = build_peer_cohort_residual_from_item_surface(
        candidate_ref="candidate:QCOMPANY",
        invariant_snapshot=_snapshot(surface["peer_features"]),
        item_surface=surface,
    )
    assert residual["coverage_state"] == "uninspected"
    assert residual["state"] == "unresolved"


def test_direct_surface_stays_unresolved_when_required_family_incomplete() -> None:
    surface = _surface("incomplete")
    residual = build_peer_cohort_residual_from_item_surface(
        candidate_ref="candidate:QCOMPANY",
        invariant_snapshot=_snapshot(surface["peer_features"]),
        item_surface=surface,
    )
    assert residual["coverage_state"] == "incomplete"
    assert residual["state"] == "unresolved"
