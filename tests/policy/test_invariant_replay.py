from __future__ import annotations

import pytest

from src.policy.domain_invariants import build_invariant_revision
from src.policy.domain_pressure import build_pressure_assessment
from src.policy.invariant_replay import build_invariant_replay
from src.policy.residual_profiles import build_typed_residual_profile


def _context() -> dict[str, bool]:
    return {
        "entity_kind_compatible": True,
        "relation_compatible": True,
        "temporal_compatible": True,
        "source_pnf_compatible": True,
        "superclass_compatible": True,
        "disjointness_clear": True,
    }


def _assessment(
    *, candidate_ref: str, invariant_ref: str, peer_state: str
) -> dict[str, object]:
    return build_pressure_assessment(
        candidate_ref=candidate_ref,
        domain_invariant_ref=invariant_ref,
        coverage_state="observed",
        review_disposition="split_required",
        residuals=[
            {
                "residual_kind": "target_model",
                "state": "partial",
                "expected": {"property": "P14143"},
                "observed": {"property": "P5991"},
            },
            {
                "residual_kind": "peer_cohort",
                "state": peer_state,
                "expected": {"trusted_member": "present"},
                "observed": {"trusted_member": "absent"},
            },
        ],
    )


def _snapshot() -> dict[str, object]:
    result = build_invariant_revision(
        domain_invariant_ref="domain:climate",
        policy_model_ref="policy:P14143",
        policy_requirements=[{"feature": "subject", "value": "company"}],
        contribution_receipts=[
            {
                "member": {
                    "candidate_ref": "candidate:confirmed",
                    "source_revision_ref": "wikidata:Q1@2",
                    "review_disposition": "confirmed_conformant_after_split",
                    "review_decision_ref": "review:1",
                    "reviewer_authority_ref": "reviewer:1",
                    "coverage_state": "observed",
                    "feature_contributions": [
                        {"feature": "year_shape", "value": "annual"}
                    ],
                }
            }
        ],
        reviewer_authority_ref="reviewer:1",
    )
    return result["snapshot"]


def test_replay_preserves_i0_and_records_i1_transition() -> None:
    original = _assessment(
        candidate_ref="candidate:remaining",
        invariant_ref="domain:climate:I0",
        peer_state="unresolved",
    )
    original_profile = build_typed_residual_profile(
        assessment=original,
        context=_context(),
        source_revision_ref="wikidata:Q2@7",
        source_anchor_refs=["Q2$abc"],
    )
    snapshot = _snapshot()
    replay = build_invariant_replay(
        source_snapshot_ref="domain:climate:I0",
        revised_snapshot=snapshot,
        original_profiles=[original_profile],
        reassessments=[
            _assessment(
                candidate_ref="candidate:remaining",
                invariant_ref=str(snapshot["snapshot_id"]),
                peer_state="exact",
            )
        ],
        source_graph_ref="graph:I0",
    )

    assert original_profile["domain_invariant_ref"] == "domain:climate:I0"
    assert (
        replay["replayed_profiles"][0]["domain_invariant_ref"]
        == snapshot["snapshot_id"]
    )
    assert replay["transitions"][0]["comparison_state_before"] == "unknown"
    assert replay["transitions"][0]["comparison_state_after"] == "admissible"
    assert replay["transitions"][0]["residual_transitions"][-1] == {
        "residual_kind": "target_model",
        "state_before": "partial",
        "state_after": "partial",
        "changed": False,
    }
    assert (
        replay["replayed_graph"]["summary"]["counts_by_kind"]["positive_similarity"]
        == 0
    )
    assert replay["promotion_effect"] == "not_evaluated"
    assert replay["edit_effect"] == "none"


def test_replay_rejects_changed_candidate_or_wrong_invariant() -> None:
    profile = build_typed_residual_profile(
        assessment=_assessment(
            candidate_ref="candidate:one",
            invariant_ref="domain:I0",
            peer_state="unresolved",
        ),
        context=_context(),
        source_revision_ref="wikidata:Q1@1",
    )
    snapshot = _snapshot()
    with pytest.raises(ValueError, match="match original candidates"):
        build_invariant_replay(
            source_snapshot_ref="domain:I0",
            revised_snapshot=snapshot,
            original_profiles=[profile],
            reassessments=[
                _assessment(
                    candidate_ref="candidate:changed",
                    invariant_ref=str(snapshot["snapshot_id"]),
                    peer_state="exact",
                )
            ],
            source_graph_ref="graph:I0",
        )
