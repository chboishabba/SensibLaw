from __future__ import annotations

from src.policy.domain_invariants import build_invariant_revision
from src.policy.peer_cohort import build_peer_cohort_residual


def _snapshot() -> dict[str, object]:
    result = build_invariant_revision(
        domain_invariant_ref="domain:climate",
        policy_model_ref="policy:P14143",
        policy_requirements=[{"feature": "subject_kind", "value": "company"}],
        contribution_receipts=[
            {
                "member": {
                    "candidate_ref": "candidate:reviewed",
                    "source_revision_ref": "wikidata:Q1@2",
                    "review_disposition": "confirmed_model_conformant",
                    "review_decision_ref": "review:1",
                    "reviewer_authority_ref": "reviewer:1",
                    "coverage_state": "observed",
                    "feature_contributions": [
                        {"feature": "subject_kind", "value": "company"},
                        {"feature": "year_shape", "value": "annual"},
                        {"feature": "method", "value": "ghg_protocol"},
                    ],
                }
            }
        ],
        reviewer_authority_ref="reviewer:1",
    )
    return result["snapshot"]


def test_incomplete_coverage_keeps_peer_unresolved() -> None:
    residual = build_peer_cohort_residual(
        candidate_ref="candidate:focal",
        invariant_snapshot=_snapshot(),
        candidate_features=[{"feature": "subject_kind", "value": "company"}],
        coverage_state="incomplete",
        graph_revision_ref="wikidata:2026-09-08",
        coverage_policy_ref="coverage:nat-company-v1",
        evidence_refs=["zelph:manifest:1"],
    )
    assert residual["state"] == "unresolved"
    assert residual["coverage_state"] == "incomplete"


def test_exact_peer_match_is_diagnostic_residual_only() -> None:
    residual = build_peer_cohort_residual(
        candidate_ref="candidate:focal",
        invariant_snapshot=_snapshot(),
        candidate_features=[
            {"feature": "subject_kind", "value": "company"},
            {"feature": "year_shape", "value": "annual"},
            {"feature": "method", "value": "ghg_protocol"},
        ],
        coverage_state="observed",
        graph_revision_ref="wikidata:2026-09-08",
        coverage_policy_ref="coverage:nat-company-v1",
    )
    assert residual["state"] == "exact"
    assert residual["observed"]["contradicted_features"] == []
    assert residual["observed"]["unmodelled_features"] == []


def test_unmodelled_feature_is_partial_not_exact() -> None:
    residual = build_peer_cohort_residual(
        candidate_ref="candidate:focal",
        invariant_snapshot=_snapshot(),
        candidate_features=[
            {"feature": "subject_kind", "value": "company"},
            {"feature": "scope_shape", "value": "scope_1"},
        ],
        coverage_state="observed",
        graph_revision_ref="wikidata:2026-09-08",
        coverage_policy_ref="coverage:nat-company-v1",
    )
    assert residual["state"] == "partial"
    assert residual["observed"]["unmodelled_features"][0]["feature"] == "scope_shape"


def test_conflicting_peer_value_is_contradictory() -> None:
    residual = build_peer_cohort_residual(
        candidate_ref="candidate:focal",
        invariant_snapshot=_snapshot(),
        candidate_features=[{"feature": "subject_kind", "value": "human"}],
        coverage_state="observed",
        graph_revision_ref="wikidata:2026-09-08",
        coverage_policy_ref="coverage:nat-company-v1",
    )
    assert residual["state"] == "contradictory"
    assert residual["observed"]["contradicted_features"][0]["peer_values"] == [
        "company"
    ]
