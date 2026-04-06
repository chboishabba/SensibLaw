from __future__ import annotations

import json
from pathlib import Path

from scripts.build_gwb_public_review import build_gwb_public_review
from src.policy.alignment_readiness_assessment import (
    assess_lane_semantics_equivalence,
    build_lane_semantics_profile_from_review_claim_records,
    review_alignment_emission_allowed,
)
from src.models.lane_semantics_profile import build_lane_semantics_profile_dict
from src.policy.review_claim_records import (
    attach_review_item_relations_by_seed_id,
    build_review_claim_records_from_affidavit_rows,
    build_review_claim_records_from_queue_rows,
    build_review_claim_records_from_review_rows,
)


def _build_affidavit_profile() -> dict[str, object]:
    records = build_review_claim_records_from_affidavit_rows(
        rows=[
            {
                "proposition_id": "prop:1",
                "paragraph_id": "p1",
                "text": "The claimant says the filing was missed.",
                "coverage_status": "needs_review",
                "best_source_row_id": "row:source:1",
                "best_match_basis": "segment",
                "best_response_role": "support",
            }
        ],
        lane="affidavit",
        family_id="affidavit_coverage_review",
        cohort_id="aff:1",
        root_artifact_id="aff-run:1",
        source_family="affidavit_coverage_review",
        recommended_view="source_review_rows",
        include_target_proposition_identity=True,
        include_proposition_relation=True,
    )
    return build_lane_semantics_profile_from_review_claim_records(
        lane="affidavit",
        family_id="affidavit_coverage_review",
        review_claim_records=records,
    )


def _build_gwb_profile() -> dict[str, object]:
    records = build_review_claim_records_from_review_rows(
        rows=[
            {
                "source_row_id": "row:1",
                "source_kind": "gwb_seed_event",
                "source_family": "gwb_public_review",
                "text": "Section 1 imposes a filing requirement.",
                "seed_id": "seed:1",
                "review_status": "missing_review",
                "primary_workload_class": "linkage_gap",
                "workload_classes": ["linkage_gap"],
                "support_kinds": ["authority"],
                "linkage_kind": "legal_interaction",
            }
        ],
        lane="gwb",
        family_id="gwb_public_review",
        cohort_id="gwb_public_review_v1",
        root_artifact_id="gwb_public_review_v1",
        source_family="gwb_public_review",
        recommended_view="source_review_rows",
    )
    records = attach_review_item_relations_by_seed_id(
        review_claim_records=records,
        review_item_rows=[{"seed_id": "seed:1", "review_item_id": "review:1"}],
    )
    return build_lane_semantics_profile_from_review_claim_records(
        lane="gwb",
        family_id="gwb_public_review",
        review_claim_records=records,
    )


def _build_au_profile() -> dict[str, object]:
    records = build_review_claim_records_from_queue_rows(
        rows=[
            {
                "fact_id": "fact:1",
                "label": "Applicant filed complaint",
                "event_ids": ["ev1"],
                "source_ids": ["src1"],
                "statement_ids": ["stmt1"],
                "reason_codes": ["needs_review"],
                "policy_outcomes": ["must_review"],
                "candidate_status": "candidate_conflict",
                "latest_review_status": "open",
            }
        ],
        lane="au",
        family_id="au_fact_review_bundle",
        cohort_id="semantic:1",
        root_artifact_id="factrun:1",
        source_family="au_fact_review_bundle",
        recommended_view="authority_follow",
        queue_family="authority_follow",
        include_target_proposition_identity=True,
        include_proposition_relation=True,
    )
    return build_lane_semantics_profile_from_review_claim_records(
        lane="au",
        family_id="au_fact_review_bundle",
        review_claim_records=records,
    )


def test_affidavit_gwb_equivalence_is_prototype_only() -> None:
    result = assess_lane_semantics_equivalence(
        left_profile=_build_affidavit_profile(),
        right_profile=_build_gwb_profile(),
    )

    assert result["verdict"] == "prototype_only"
    assert result["source_semantics_shared"] is True
    assert result["target_semantics_shared"] is True
    assert result["basis_vocabulary_shared"] is True
    assert result["interpretation_shared"] is True


def test_affidavit_au_equivalence_is_hold() -> None:
    result = assess_lane_semantics_equivalence(
        left_profile=_build_affidavit_profile(),
        right_profile=_build_au_profile(),
    )

    assert result["verdict"] == "hold"
    assert result["target_semantics_shared"] is False
    assert result["interpretation_shared"] is False


def test_gwb_au_equivalence_is_hold() -> None:
    result = assess_lane_semantics_equivalence(
        left_profile=_build_gwb_profile(),
        right_profile=_build_au_profile(),
    )

    assert result["verdict"] == "hold"
    assert result["target_semantics_shared"] is False
    assert result["cardinality_shared"] is False


def test_structural_overlap_without_shared_interpretation_stays_hold() -> None:
    left = build_lane_semantics_profile_dict(
        lane="lane_left",
        family_id="family:left",
        origin_kinds=["source_row"],
        target_kinds=["source_row"],
        cardinality_mode="singleton",
        basis_vocabulary=["anchor_overlap"],
        interpretation_kind="alignment",
        descriptive_only=True,
        control_leakage_risk=False,
    )
    right = build_lane_semantics_profile_dict(
        lane="lane_right",
        family_id="family:right",
        origin_kinds=["source_row"],
        target_kinds=["source_row"],
        cardinality_mode="singleton",
        basis_vocabulary=["anchor_overlap"],
        interpretation_kind="routing",
        descriptive_only=True,
        control_leakage_risk=False,
    )

    result = assess_lane_semantics_equivalence(left_profile=left, right_profile=right)

    assert result["verdict"] == "hold"
    assert result["interpretation_shared"] is False


def test_review_alignment_emission_requires_promote_verdict() -> None:
    prototype_only = assess_lane_semantics_equivalence(
        left_profile=_build_affidavit_profile(),
        right_profile=_build_gwb_profile(),
    )
    hold = assess_lane_semantics_equivalence(
        left_profile=_build_affidavit_profile(),
        right_profile=_build_au_profile(),
    )

    assert review_alignment_emission_allowed(equivalence_assessment=prototype_only) is False
    assert review_alignment_emission_allowed(equivalence_assessment=hold) is False
    assert review_alignment_emission_allowed(equivalence_assessment={**prototype_only, "verdict": "promote"}) is True


def test_synthetic_gwb_multiplicity_drops_to_hold_until_target_semantics_are_instantiated(tmp_path: Path) -> None:
    synthetic_slice_path = tmp_path / "gwb_public_multiplicity.slice.json"
    synthetic_slice_path.write_text(
        json.dumps(
            {
                "selected_seed_lanes": [
                    {
                        "seed_id": "seed:multi",
                        "action_summary": "Synthetic ambiguous public-review seed",
                        "support_kind": "authority",
                        "linkage_kind": "legal_interaction",
                        "candidate_event_count": 3,
                        "matched_event_count": 2,
                        "events": [
                            {
                                "event_id": "event:1",
                                "matched": True,
                                "confidence": "high",
                                "text": "First matched event.",
                            },
                            {
                                "event_id": "event:2",
                                "matched": True,
                                "confidence": "medium",
                                "text": "Second matched event.",
                            },
                            {
                                "event_id": "event:3",
                                "matched": False,
                                "confidence": "abstain",
                                "text": "Unmatched event that remains review-only.",
                            },
                        ],
                    }
                ],
                "unresolved_surfaces": [],
                "summary": {},
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = build_gwb_public_review(
        tmp_path / "out",
        source_slice_path=synthetic_slice_path,
    )
    payload = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    gwb_profile = build_lane_semantics_profile_from_review_claim_records(
        lane="gwb",
        family_id="gwb_public_review",
        review_claim_records=payload["review_claim_records"],
        review_item_rows=payload["review_item_rows"],
    )

    assessment = assess_lane_semantics_equivalence(
        left_profile=_build_affidavit_profile(),
        right_profile=gwb_profile,
    )

    assert gwb_profile["cardinality_mode"] == "set"
    assert "semantic_separability:separable" in gwb_profile["semantic_notes"]
    assert "semantic_reason:distinct_target_splits" in gwb_profile["semantic_notes"]
    assert "normalized_split:event_split" in gwb_profile["semantic_notes"]
    assert assessment["verdict"] == "hold"
    assert assessment["cardinality_shared"] is False
    assert assessment["target_semantics_shared"] is False
    assert review_alignment_emission_allowed(equivalence_assessment=assessment) is False


def test_family_split_normalizes_into_semantic_notes() -> None:
    profile = build_lane_semantics_profile_from_review_claim_records(
        lane="gwb",
        family_id="gwb_broader_review",
        review_claim_records=build_review_claim_records_from_review_rows(
            rows=[
                {
                    "source_row_id": "row:1",
                    "source_kind": "gwb_seed_event",
                    "source_family": "gwb_broader_review",
                    "text": "Broader review row",
                    "seed_id": "seed:family",
                    "review_status": "missing_review",
                    "primary_workload_class": "linkage_gap",
                    "workload_classes": ["linkage_gap"],
                    "support_kinds": ["authority"],
                    "linkage_kind": "legal_interaction",
                }
            ],
            lane="gwb",
            family_id="gwb_broader_review",
            cohort_id="gwb_broader_review_v1",
            root_artifact_id="gwb_broader_review_v1",
            source_family="gwb_broader_review",
            recommended_view="source_review_rows",
        ),
        review_item_rows=[
            {
                "seed_id": "seed:family",
                "review_item_id": "review:family:a",
                "matched_source_family": "family:a",
                "source_family": "gwb_broader_review",
            },
            {
                "seed_id": "seed:family",
                "review_item_id": "review:family:b",
                "matched_source_family": "family:b",
                "source_family": "gwb_broader_review",
            },
        ],
    )

    assert "normalized_split:family_split" in profile["semantic_notes"]
